import json
import math
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Vector

from al_config import load_autosize_config, nested_get, target_output_name

OPTIMIZER_PASSES = 20
CURVATURE_TRIGGER_1_PER_MM = 0.03
CURVATURE_ENERGY_CAP_1_PER_MM = 0.30
CURVATURE_BLEND = 0.30
MAX_DEPTH_MOVE_PER_PASS_MM = 2.5
CLEARANCE_PROXY_MM = 20.0
CLEARANCE_SKIP_NEIGHBORS = 70
CLEARANCE_TOLERANCE_RATIO = 1.02


def get_project_root():
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender file before running project scripts.")
    blend_dir = Path(bpy.data.filepath).resolve().parent
    return blend_dir.parent if blend_dir.name == "blender" else blend_dir


def percentile(values, amount):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * amount)))
    return ordered[index]


def project_target_to_depth(target, depth, camera_y, camera_z):
    factor = (depth - camera_y) / -camera_y
    return Vector(
        (
            target[0] * factor,
            depth,
            camera_z + (target[1] - camera_z) * factor,
        )
    )


def world_points(targets, depths, camera_y, camera_z):
    return [
        project_target_to_depth(targets[index], depths[index], camera_y, camera_z)
        for index in range(len(depths))
    ]


def cyclic_curvatures(points):
    count = len(points)
    result = []
    for index, point in enumerate(points):
        previous = points[(index - 1) % count]
        following = points[(index + 1) % count]
        incoming = point - previous
        outgoing = following - point
        span = (following - previous).length
        if incoming.length < 1e-8 or outgoing.length < 1e-8 or span < 1e-8:
            result.append(0.0)
            continue
        result.append((outgoing.normalized() - incoming.normalized()).length / span)
    return result


def curvature_energy(curvatures):
    return sum(
        max(
            0.0,
            min(curvature, CURVATURE_ENERGY_CAP_1_PER_MM) - CURVATURE_TRIGGER_1_PER_MM,
        )
        ** 2
        for curvature in curvatures
    )


def point_clearance_count(points):
    cells = defaultdict(list)
    conflicts = 0
    count = len(points)
    for index, point in enumerate(points):
        cell = tuple(math.floor(point[axis] / CLEARANCE_PROXY_MM) for axis in range(3))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other in cells.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()):
                        path_gap = abs(index - other)
                        path_gap = min(path_gap, count - path_gap)
                        if path_gap < CLEARANCE_SKIP_NEIGHBORS:
                            continue
                        if (point - points[other]).length < CLEARANCE_PROXY_MM:
                            conflicts += 1
        cells[cell].append(index)
    return conflicts


def optimize_depths(targets, depths, camera_y, camera_z, max_depth):
    result = list(depths)
    initial_points = world_points(targets, result, camera_y, camera_z)
    initial_curvatures = cyclic_curvatures(initial_points)
    initial_conflicts = point_clearance_count(initial_points)
    clearance_limit = max(
        initial_conflicts + 12,
        int(math.ceil(initial_conflicts * CLEARANCE_TOLERANCE_RATIO)),
    )
    accepted_passes = 0

    for _ in range(OPTIMIZER_PASSES):
        points = world_points(targets, result, camera_y, camera_z)
        curvatures = cyclic_curvatures(points)
        current_energy = curvature_energy(curvatures)
        candidate = list(result)

        for index, curvature in enumerate(curvatures):
            if curvature < CURVATURE_TRIGGER_1_PER_MM:
                continue
            midpoint = (points[(index - 1) % len(points)] + points[(index + 1) % len(points)]) * 0.5
            camera = Vector((0.0, camera_y, camera_z))
            target_world = Vector((targets[index][0], 0.0, targets[index][1]))
            ray = target_world - camera
            if ray.length_squared < 1e-9:
                continue
            factor = (midpoint - camera).dot(ray) / ray.length_squared
            desired_depth = camera_y + factor * (-camera_y)
            move = (desired_depth - result[index]) * CURVATURE_BLEND
            move = max(-MAX_DEPTH_MOVE_PER_PASS_MM, min(MAX_DEPTH_MOVE_PER_PASS_MM, move))
            candidate[index] = max(-max_depth, min(max_depth, result[index] + move))

        candidate_points = world_points(targets, candidate, camera_y, camera_z)
        candidate_curvatures = cyclic_curvatures(candidate_points)
        candidate_energy = curvature_energy(candidate_curvatures)
        candidate_conflicts = point_clearance_count(candidate_points)
        if candidate_energy >= current_energy or candidate_conflicts > clearance_limit:
            break
        result = candidate
        accepted_passes += 1

    final_points = world_points(targets, result, camera_y, camera_z)
    final_curvatures = cyclic_curvatures(final_points)
    return result, final_points, {
        "accepted_passes": accepted_passes,
        "initial_p95_curvature_1_per_mm": percentile(initial_curvatures, 0.95),
        "final_p95_curvature_1_per_mm": percentile(final_curvatures, 0.95),
        "initial_max_curvature_1_per_mm": max(initial_curvatures, default=0.0),
        "final_max_curvature_1_per_mm": max(final_curvatures, default=0.0),
        "initial_curvature_energy": curvature_energy(initial_curvatures),
        "final_curvature_energy": curvature_energy(final_curvatures),
        "initial_clearance_proxy_conflicts": initial_conflicts,
        "final_clearance_proxy_conflicts": point_clearance_count(final_points),
    }


def update_path_payload(path_data, depths, points, optimizer_stats):
    nodes = path_data["nodes"]
    total_length = 0.0
    segment_lengths = []
    for index in range(1, len(points)):
        segment_length = (points[index] - points[index - 1]).length
        segment_lengths.append(segment_length)
        total_length += segment_length

    accumulated = 0.0
    for index, node in enumerate(nodes):
        if index > 0:
            accumulated += segment_lengths[index - 1]
        node["sculptural_depth_y_mm"] = depths[index]
        node["point_world_mm"] = [points[index].x, points[index].y, points[index].z]
        node["s_normalized"] = accumulated / total_length if total_length else 0.0

    path_data["path_length_mm"] = total_length
    path_data.setdefault("stats", {}).update(
        {
            "curvature_optimizer_applied": True,
            "curvature_optimizer_passes": optimizer_stats["accepted_passes"],
            "curvature_optimizer_trigger_1_per_mm": CURVATURE_TRIGGER_1_PER_MM,
            "curvature_optimizer_max_depth_move_per_pass_mm": MAX_DEPTH_MOVE_PER_PASS_MM,
        }
    )


def update_debug_curve(points):
    obj = bpy.data.objects.get("AL_CONTINUOUS_PATH")
    if not obj or obj.type != "CURVE" or not obj.data.splines:
        return
    spline = obj.data.splines[0]
    if len(spline.points) != len(points):
        return
    for spline_point, point in zip(spline.points, points):
        spline_point.co = (point.x, point.y, point.z, 1.0)


def main():
    project_root = get_project_root()
    debug_dir = project_root / "output" / "debug"
    path_file = debug_dir / target_output_name(project_root, "continuous_path")
    path_data = json.loads(path_file.read_text(encoding="utf-8"))
    config = load_autosize_config(project_root)
    camera_y = -float(nested_get(config, ("camera", "distance_mm"), 1050.0))
    camera_z = float(nested_get(config, ("camera", "height_mm"), 175.0))
    max_depth = float(nested_get(config, ("lamp", "max_sculptural_depth_mm"), 96.0))

    nodes = path_data["nodes"]
    closed_loop = (
        len(nodes) > 3
        and (Vector(nodes[0]["point_world_mm"]) - Vector(nodes[-1]["point_world_mm"])).length < 1.5
    )
    unique_count = len(nodes) - 1 if closed_loop else len(nodes)
    targets = [
        (node["target_projection_mm"][0], node["target_projection_mm"][2])
        for node in nodes[:unique_count]
    ]
    depths = [node["sculptural_depth_y_mm"] for node in nodes[:unique_count]]
    optimized_depths, optimized_points, stats = optimize_depths(
        targets,
        depths,
        camera_y,
        camera_z,
        max_depth,
    )
    if closed_loop:
        optimized_depths.append(optimized_depths[0])
        optimized_points.append(optimized_points[0].copy())

    update_path_payload(path_data, optimized_depths, optimized_points, stats)
    path_file.write_text(json.dumps(path_data, indent=2), encoding="utf-8")
    update_debug_curve(optimized_points)

    initial_p95 = stats["initial_p95_curvature_1_per_mm"]
    final_p95 = stats["final_p95_curvature_1_per_mm"]
    relative_improvement = (initial_p95 - final_p95) / initial_p95 if initial_p95 > 1e-9 else 0.0
    quality_score = max(0.0, min(1.0, relative_improvement))
    output = {
        "source": "ANAMORPHIC_LAMP scripts/08_optimizer.py",
        "status": "curvature-constrained camera-ray optimization",
        "path_point_count": path_data["point_count"],
        "path_length_mm": path_data["path_length_mm"],
        "quality_score_0_1": quality_score,
        "projection_preserved": True,
        "closed_loop": closed_loop,
        "settings": {
            "passes": OPTIMIZER_PASSES,
            "curvature_trigger_1_per_mm": CURVATURE_TRIGGER_1_PER_MM,
            "curvature_energy_cap_1_per_mm": CURVATURE_ENERGY_CAP_1_PER_MM,
            "curvature_blend": CURVATURE_BLEND,
            "max_depth_move_per_pass_mm": MAX_DEPTH_MOVE_PER_PASS_MM,
            "clearance_tolerance_ratio": CLEARANCE_TOLERANCE_RATIO,
        },
        "metrics": stats,
        "notes": [
            "Points move only along privileged-camera rays.",
            "A pass is rejected if curvature energy does not improve or clearance exceeds tolerance.",
        ],
    }
    output_path = debug_dir / target_output_name(project_root, "optimized_solution")
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("STEP 08 - OPTIMIZER")
    print(f"Accepted passes: {stats['accepted_passes']}")
    print(f"P95 curvature: {initial_p95:.4f} -> {final_p95:.4f} 1/mm")
    print(f"Output: {output_path}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
