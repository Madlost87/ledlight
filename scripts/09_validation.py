import json
from pathlib import Path

import bpy
from mathutils import Vector

from al_config import load_autosize_config, nested_get
from al_config import target_output_name

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
DEBUG_OBJECT_NAME = "AL_CLEARANCE_HOTSPOTS"
CURVATURE_DEBUG_OBJECT_NAME = "AL_CURVATURE_HOTSPOTS"
LAMP_BOUNDS = {"x": (-160.0, 160.0), "y": (-110.0, 110.0), "z": (0.0, 320.0)}
PROFILE_CLEARANCE_MM = 20.0
SELF_CLEARANCE_SKIP_NEIGHBORS = 70
CLEARANCE_DEBUG_CONFLICTS = 80
CURVATURE_DEBUG_HOTSPOTS = 80


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


def get_debug_collection():
    root = bpy.data.collections.get(PROJECT_COLLECTION)
    if not root:
        raise RuntimeError("Run scripts/00_setup_scene.py first.")
    for child in root.children:
        if child.name.split(".", 1)[0] == "AL_DEBUG":
            return child
    raise RuntimeError("AL_DEBUG collection is missing.")


def remove_existing_object(name):
    obj = bpy.data.objects.get(name)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)


def in_bounds(point):
    return (
        LAMP_BOUNDS["x"][0] <= point.x <= LAMP_BOUNDS["x"][1]
        and LAMP_BOUNDS["y"][0] <= point.y <= LAMP_BOUNDS["y"][1]
        and LAMP_BOUNDS["z"][0] <= point.z <= LAMP_BOUNDS["z"][1]
    )


def segment_closest_points(a0, a1, b0, b1):
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
        return (a0 - b0).length, a0.copy(), b0.copy()
    if a < 1e-9:
        t = max(0.0, min(1.0, e / c if c else 0.0))
        closest_a = a0.copy()
        closest_b = b0 + v * t
        return (closest_a - closest_b).length, closest_a, closest_b
    if c < 1e-9:
        s = max(0.0, min(1.0, -d / a if a else 0.0))
        closest_a = a0 + u * s
        closest_b = b0.copy()
        return (closest_a - closest_b).length, closest_a, closest_b

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
    return (closest_a - closest_b).length, closest_a, closest_b


def segment_distance(a0, a1, b0, b1):
    distance, _closest_a, _closest_b = segment_closest_points(a0, a1, b0, b1)
    return distance


def vector_to_list(vector):
    return [vector.x, vector.y, vector.z]


def create_clearance_debug(points, clearance, collection):
    remove_existing_object(DEBUG_OBJECT_NAME)
    conflicts = clearance.get("closest_conflicts", [])[:CLEARANCE_DEBUG_CONFLICTS]
    if not conflicts:
        return None

    vertices = []
    edges = []
    for conflict in conflicts:
        segment_a = conflict["segment_a"]
        segment_b = conflict["segment_b"]
        closest_a = Vector(conflict["closest_a_mm"])
        closest_b = Vector(conflict["closest_b_mm"])

        base = len(vertices)
        vertices.extend(
            [
                points[segment_a[0]],
                points[segment_a[1]],
                points[segment_b[0]],
                points[segment_b[1]],
                closest_a,
                closest_b,
            ]
        )
        edges.extend(
            [
                (base, base + 1),
                (base + 2, base + 3),
                (base + 4, base + 5),
            ]
        )

    mesh = bpy.data.meshes.new(f"{DEBUG_OBJECT_NAME}_MESH")
    mesh.from_pydata([vector_to_list(vertex) for vertex in vertices], edges, [])
    mesh.update()

    material = bpy.data.materials.get("AL_CLEARANCE_HOTSPOT_MAT")
    if material is None:
        material = bpy.data.materials.new("AL_CLEARANCE_HOTSPOT_MAT")
    material.diffuse_color = (1.0, 0.05, 0.02, 1.0)

    obj = bpy.data.objects.new(DEBUG_OBJECT_NAME, mesh)
    obj.display_type = "WIRE"
    obj.show_in_front = True
    obj["role"] = "Worst self-clearance conflicts under the profile clearance threshold."
    obj["clearance_threshold_mm"] = PROFILE_CLEARANCE_MM
    obj["visualized_conflicts"] = len(conflicts)
    obj.data.materials.append(material)
    collection.objects.link(obj)
    return obj


def create_curvature_debug(transition, collection):
    remove_existing_object(CURVATURE_DEBUG_OBJECT_NAME)
    hotspots = transition.get("curvature_hotspots", [])[:CURVATURE_DEBUG_HOTSPOTS]
    if not hotspots:
        return None

    vertices = []
    edges = []
    marker_size = 5.0
    for hotspot in hotspots:
        point = Vector(hotspot["point_world_mm"])
        base = len(vertices)
        vertices.extend(
            [
                point + Vector((-marker_size, 0.0, 0.0)),
                point + Vector((marker_size, 0.0, 0.0)),
                point + Vector((0.0, -marker_size, 0.0)),
                point + Vector((0.0, marker_size, 0.0)),
                point + Vector((0.0, 0.0, -marker_size)),
                point + Vector((0.0, 0.0, marker_size)),
            ]
        )
        edges.extend(
            [
                (base, base + 1),
                (base + 2, base + 3),
                (base + 4, base + 5),
            ]
        )

    mesh = bpy.data.meshes.new(f"{CURVATURE_DEBUG_OBJECT_NAME}_MESH")
    mesh.from_pydata([vector_to_list(vertex) for vertex in vertices], edges, [])
    mesh.update()

    material = bpy.data.materials.get("AL_CURVATURE_HOTSPOT_MAT")
    if material is None:
        material = bpy.data.materials.new("AL_CURVATURE_HOTSPOT_MAT")
    material.diffuse_color = (1.0, 0.72, 0.02, 1.0)

    obj = bpy.data.objects.new(CURVATURE_DEBUG_OBJECT_NAME, mesh)
    obj.display_type = "WIRE"
    obj.show_in_front = True
    obj["role"] = "Worst bend-radius violations from final orientation analysis."
    obj["minimum_bend_radius_target_mm"] = transition.get(
        "minimum_bend_radius_target_mm",
        0.0,
    )
    obj["visualized_hotspots"] = len(hotspots)
    obj.data.materials.append(material)
    collection.objects.link(obj)
    return obj


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
            distance, closest_a, closest_b = segment_closest_points(a0, a1, points[j], points[j + 1])
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
                        "closest_a_mm": vector_to_list(closest_a),
                        "closest_b_mm": vector_to_list(closest_b),
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
    )[:CLEARANCE_DEBUG_CONFLICTS]

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
    path_data = json.loads((debug_dir / target_output_name(project_root, "continuous_path")).read_text(encoding="utf-8"))
    opt_data = json.loads((debug_dir / target_output_name(project_root, "optimized_solution")).read_text(encoding="utf-8"))
    transition_data = json.loads(
        (debug_dir / target_output_name(project_root, "transition_analysis")).read_text(encoding="utf-8")
    )
    points = [Vector(node["point_world_mm"]) for node in path_data["nodes"]]
    out_of_bounds = [index for index, point in enumerate(points) if not in_bounds(point)]
    segment_lengths = [(points[index] - points[index - 1]).length for index in range(1, len(points))]
    clearance = self_clearance_report(points)
    debug_collection = get_debug_collection()
    debug_obj = create_clearance_debug(points, clearance, debug_collection)
    curvature_debug_obj = create_curvature_debug(transition_data, debug_collection)
    clearance_passed = clearance["clearance_violation_count"] == 0
    bend_radius_passed = bool(transition_data.get("bend_radius_passed", False))

    report = {
        "source": "ANAMORPHIC_LAMP scripts/09_validation.py",
        "passed": not out_of_bounds and bool(points) and clearance_passed and bend_radius_passed,
        "point_count": len(points),
        "out_of_bounds_count": len(out_of_bounds),
        "clearance_passed": clearance_passed,
        "bend_radius_passed": bend_radius_passed,
        "bend_radius": {
            "target_mm": transition_data.get("minimum_bend_radius_target_mm"),
            "violation_count": transition_data.get("bend_radius_violation_count", 0),
            "p95_radius_mm": transition_data.get("p95_radius_mm"),
            "zones": transition_data.get("curvature_zones", {}),
        },
        "self_clearance": clearance,
        "max_segment_length_mm": max(segment_lengths) if segment_lengths else 0.0,
        "path_length_mm": path_data["path_length_mm"],
        "optimizer_quality_score_0_1": opt_data["quality_score_0_1"],
        "clearance_debug_object": debug_obj.name if debug_obj else None,
        "clearance_debug_conflicts": int(debug_obj.get("visualized_conflicts", 0)) if debug_obj else 0,
        "curvature_debug_object": curvature_debug_obj.name if curvature_debug_obj else None,
        "curvature_debug_hotspots": (
            int(curvature_debug_obj.get("visualized_hotspots", 0))
            if curvature_debug_obj
            else 0
        ),
    }
    output_json = debug_dir / target_output_name(project_root, "validation_report")
    output_txt = debug_dir / target_output_name(project_root, "validation_report", "txt")
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output_txt.write_text(
        "\n".join(
            [
                "ANAMORPHIC_LAMP validation",
                f"passed: {report['passed']}",
                f"points: {report['point_count']}",
                f"out_of_bounds: {report['out_of_bounds_count']}",
                f"clearance_passed: {clearance_passed}",
                f"bend_radius_passed: {bend_radius_passed}",
                f"bend_radius_target_mm: {report['bend_radius']['target_mm']}",
                f"bend_radius_violations: {report['bend_radius']['violation_count']}",
                f"p95_radius_mm: {report['bend_radius']['p95_radius_mm']}",
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
        )
        + "\n",
        encoding="utf-8",
    )
    print("STEP 09 - VALIDATION")
    print(f"Passed: {report['passed']}")
    print(f"Output: {output_json}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
