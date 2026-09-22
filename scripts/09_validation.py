import json
from pathlib import Path

import bpy
from mathutils import Vector

from al_config import load_autosize_config, nested_get

PATH_JSON = "continuous_path_LOVE.json"
OPT_JSON = "optimized_solution_LOVE.json"
OUTPUT_JSON = "validation_report_LOVE.json"
OUTPUT_TXT = "validation_report_LOVE.txt"
LAMP_BOUNDS = {"x": (-160.0, 160.0), "y": (-110.0, 110.0), "z": (0.0, 320.0)}
PROFILE_CLEARANCE_MM = 20.0
SELF_CLEARANCE_SKIP_NEIGHBORS = 70


def apply_autosize_config(project_root):
    global LAMP_BOUNDS

    config = load_autosize_config(project_root)
    width = float(nested_get(config, ("lamp", "width_mm"), LAMP_BOUNDS["x"][1] * 2.0))
    depth = float(nested_get(config, ("lamp", "depth_mm"), LAMP_BOUNDS["y"][1] * 2.0))
    height = float(nested_get(config, ("lamp", "height_mm"), LAMP_BOUNDS["z"][1]))
    LAMP_BOUNDS = {
        "x": (-width * 0.5, width * 0.5),
        "y": (-depth * 0.5, depth * 0.5),
        "z": (0.0, height),
    }


def get_project_root():
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender file before running project scripts.")
    blend_dir = Path(bpy.data.filepath).resolve().parent
    return blend_dir.parent if blend_dir.name == "blender" else blend_dir


def in_bounds(point):
    return (
        LAMP_BOUNDS["x"][0] <= point.x <= LAMP_BOUNDS["x"][1]
        and LAMP_BOUNDS["y"][0] <= point.y <= LAMP_BOUNDS["y"][1]
        and LAMP_BOUNDS["z"][0] <= point.z <= LAMP_BOUNDS["z"][1]
    )


def segment_distance(a0, a1, b0, b1):
    u = a1 - a0
    v = b1 - b0
    w = a0 - b0
    a = u.dot(u)
    b = u.dot(v)
    c = v.dot(v)
    d = u.dot(w)
    e = v.dot(w)
    denom = a * c - b * b

    if a < 1e-9 and c < 1e-9:
        return (a0 - b0).length
    if a < 1e-9:
        t = max(0.0, min(1.0, e / c if c else 0.0))
        return (a0 - (b0 + v * t)).length
    if c < 1e-9:
        s = max(0.0, min(1.0, -d / a if a else 0.0))
        return ((a0 + u * s) - b0).length

    if denom < 1e-9:
        s = 0.0
    else:
        s = max(0.0, min(1.0, (b * e - c * d) / denom))
    t = (b * s + e) / c
    if t < 0.0:
        t = 0.0
        s = max(0.0, min(1.0, -d / a))
    elif t > 1.0:
        t = 1.0
        s = max(0.0, min(1.0, (b - d) / a))

    closest_a = a0 + u * s
    closest_b = b0 + v * t
    return (closest_a - closest_b).length


def self_clearance_report(points):
    if len(points) < 4:
        return {
            "min_nonlocal_distance_mm": None,
            "clearance_violation_count": 0,
            "clearance_hotspots": [],
            "closest_conflicts": [],
        }

    min_distance = None
    violations = 0
    hotspot_counts = {}
    closest_conflicts = []
    segment_count = len(points) - 1
    closed_loop = (points[0] - points[-1]).length < 1.5
    for i in range(segment_count):
        a0 = points[i]
        a1 = points[i + 1]
        for j in range(i + SELF_CLEARANCE_SKIP_NEIGHBORS, segment_count):
            if closed_loop and (i < SELF_CLEARANCE_SKIP_NEIGHBORS or j > segment_count - SELF_CLEARANCE_SKIP_NEIGHBORS):
                continue
            distance = segment_distance(a0, a1, points[j], points[j + 1])
            if min_distance is None or distance < min_distance:
                min_distance = distance
            if distance < PROFILE_CLEARANCE_MM:
                violations += 1
                bucket = ((i // 100) * 100, (j // 100) * 100)
                hotspot_counts[bucket] = hotspot_counts.get(bucket, 0) + 1
                closest_conflicts.append(
                    {
                        "distance_mm": distance,
                        "segment_a": [i, i + 1],
                        "segment_b": [j, j + 1],
                    }
                )

    hotspots = []
    for (start_a, start_b), count in sorted(
        hotspot_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:12]:
        hotspots.append(
            {
                "range_a": [start_a, min(start_a + 99, segment_count)],
                "range_b": [start_b, min(start_b + 99, segment_count)],
                "violation_count": count,
            }
        )

    closest_conflicts = sorted(
        closest_conflicts,
        key=lambda item: item["distance_mm"],
    )[:12]

    return {
        "min_nonlocal_distance_mm": min_distance,
        "clearance_violation_count": violations,
        "clearance_threshold_mm": PROFILE_CLEARANCE_MM,
        "clearance_hotspots": hotspots,
        "closest_conflicts": closest_conflicts,
    }


def main():
    project_root = get_project_root()
    apply_autosize_config(project_root)
    debug_dir = project_root / "output" / "debug"
    path_data = json.loads((debug_dir / PATH_JSON).read_text(encoding="utf-8"))
    opt_data = json.loads((debug_dir / OPT_JSON).read_text(encoding="utf-8"))
    points = [Vector(node["point_world_mm"]) for node in path_data["nodes"]]
    out_of_bounds = [index for index, point in enumerate(points) if not in_bounds(point)]
    segment_lengths = [(points[index] - points[index - 1]).length for index in range(1, len(points))]
    clearance = self_clearance_report(points)
    clearance_passed = clearance["clearance_violation_count"] == 0

    report = {
        "source": "ANAMORPHIC_LAMP scripts/09_validation.py",
        "passed": not out_of_bounds and bool(points) and clearance_passed,
        "point_count": len(points),
        "out_of_bounds_count": len(out_of_bounds),
        "clearance_passed": clearance_passed,
        "self_clearance": clearance,
        "max_segment_length_mm": max(segment_lengths) if segment_lengths else 0.0,
        "path_length_mm": path_data["path_length_mm"],
        "optimizer_quality_score_0_1": opt_data["quality_score_0_1"],
    }
    (debug_dir / OUTPUT_JSON).write_text(json.dumps(report, indent=2), encoding="utf-8")
    (debug_dir / OUTPUT_TXT).write_text(
        "\n".join(
            [
                "ANAMORPHIC_LAMP validation",
                f"passed: {report['passed']}",
                f"points: {report['point_count']}",
                f"out_of_bounds: {report['out_of_bounds_count']}",
                f"clearance_passed: {clearance_passed}",
                f"clearance_violations: {clearance['clearance_violation_count']}",
                f"min_nonlocal_distance_mm: {clearance['min_nonlocal_distance_mm']}",
                "top_clearance_hotspots:",
                *[
                    (
                        f"  {item['range_a'][0]}-{item['range_a'][1]} vs "
                        f"{item['range_b'][0]}-{item['range_b'][1]}: "
                        f"{item['violation_count']}"
                    )
                    for item in clearance["clearance_hotspots"][:5]
                ],
                f"max_segment_mm: {report['max_segment_length_mm']:.2f}",
                f"path_length_mm: {report['path_length_mm']:.2f}",
                f"quality_score: {report['optimizer_quality_score_0_1']:.3f}",
            ]
        ),
        encoding="utf-8",
    )
    print("STEP 09 - VALIDATION")
    print(f"Passed: {report['passed']}")
    print(f"Output: {debug_dir / OUTPUT_JSON}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
