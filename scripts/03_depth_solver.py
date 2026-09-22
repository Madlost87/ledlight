import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

from al_config import load_autosize_config, nested_get

# ============================================================
# ANAMORPHIC LAMP
# STEP 03 - DEPTH SOLVER
# ============================================================

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
INPUT_JSON_NAME = "camera_projection_LOVE.json"
OUTPUT_JSON_NAME = "depth_candidates_LOVE.json"
DEBUG_OBJECT_NAME = "AL_DEPTH_CANDIDATES"

LAMP_WIDTH = 320.0
LAMP_DEPTH = 220.0
LAMP_HEIGHT = 300.0

VOLUME_MARGIN = 8.0
POINT_MARKER_SIZE = 3.0


def apply_autosize_config(project_root):
    global LAMP_WIDTH, LAMP_DEPTH, LAMP_HEIGHT

    config = load_autosize_config(project_root)
    LAMP_WIDTH = float(nested_get(config, ("lamp", "width_mm"), LAMP_WIDTH))
    LAMP_DEPTH = float(nested_get(config, ("lamp", "depth_mm"), LAMP_DEPTH))
    LAMP_HEIGHT = float(nested_get(config, ("lamp", "height_mm"), LAMP_HEIGHT))


def get_project_root():
    blend_path = bpy.data.filepath
    if not blend_path:
        raise RuntimeError(
            "Save the Blender file first as "
            "ANAMORPHIC_LAMP/blender/anamorphic_lamp.blend, then rerun this script."
        )

    blend_dir = Path(blend_path).resolve().parent
    if blend_dir.name == "blender":
        return blend_dir.parent
    return blend_dir


def get_project_child_collection(name):
    root = bpy.data.collections.get(PROJECT_COLLECTION)
    if not root:
        raise RuntimeError("Project collection is missing. Run scripts/00_setup_scene.py first.")

    for child in root.children:
        if child.name.split(".", 1)[0] == name:
            return child

    raise RuntimeError(f"Collection {name!r} is missing. Run scripts/00_setup_scene.py first.")


def remove_existing_object(name):
    existing = bpy.data.objects.get(name)
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)


def load_projection_data(project_root):
    input_path = project_root / "output" / "debug" / INPUT_JSON_NAME
    if not input_path.exists():
        raise FileNotFoundError(
            f"Projection data not found: {input_path}. Run scripts/02_camera_projection.py first."
        )
    return input_path, json.loads(input_path.read_text(encoding="utf-8"))


def lamp_bounds():
    return {
        "x": (-LAMP_WIDTH / 2.0 + VOLUME_MARGIN, LAMP_WIDTH / 2.0 - VOLUME_MARGIN),
        "y": (-LAMP_DEPTH / 2.0 + VOLUME_MARGIN, LAMP_DEPTH / 2.0 - VOLUME_MARGIN),
        "z": (VOLUME_MARGIN, LAMP_HEIGHT - VOLUME_MARGIN),
    }


def ray_box_interval(origin, direction, bounds):
    t_min = -math.inf
    t_max = math.inf

    for axis_index, axis_name in enumerate(("x", "y", "z")):
        axis_origin = origin[axis_index]
        axis_direction = direction[axis_index]
        lower, upper = bounds[axis_name]

        if abs(axis_direction) < 1e-9:
            if axis_origin < lower or axis_origin > upper:
                return None
            continue

        t0 = (lower - axis_origin) / axis_direction
        t1 = (upper - axis_origin) / axis_direction
        t_axis_min = min(t0, t1)
        t_axis_max = max(t0, t1)

        t_min = max(t_min, t_axis_min)
        t_max = min(t_max, t_axis_max)

        if t_min > t_max:
            return None

    if t_max < 0.0:
        return None

    return max(t_min, 0.0), t_max


def depth_alpha(sample, index, total):
    uv = sample.get("uv", [0.5, 0.5])
    u = float(uv[0])
    v = float(uv[1])
    phase = (index / max(total - 1, 1)) * math.tau
    wave = 0.5 + 0.5 * math.sin((u * 3.7 + v * 2.1) * math.tau + phase)
    return 0.22 + 0.56 * wave


def solve_depth_candidates(projection_data):
    bounds = lamp_bounds()
    samples = projection_data.get("samples", [])
    candidates = []
    rejected = []

    for index, sample in enumerate(samples):
        origin = Vector(sample["camera_origin_mm"])
        direction = Vector(sample["camera_ray_direction"]).normalized()
        interval = ray_box_interval(origin, direction, bounds)

        if interval is None:
            rejected.append(
                {
                    "index": index,
                    "pixel": sample.get("pixel"),
                    "reason": "ray misses lamp volume",
                }
            )
            continue

        t_enter, t_exit = interval
        alpha = depth_alpha(sample, index, len(samples))
        t_value = t_enter + (t_exit - t_enter) * alpha
        point = origin + direction * t_value

        candidates.append(
            {
                "source_index": index,
                "pixel": sample.get("pixel"),
                "uv": sample.get("uv"),
                "ray_t_enter": t_enter,
                "ray_t_exit": t_exit,
                "ray_t": t_value,
                "depth_alpha": alpha,
                "point_world_mm": [point.x, point.y, point.z],
                "camera_ray_direction": [direction.x, direction.y, direction.z],
            }
        )

    return bounds, candidates, rejected


def create_debug_material():
    material = bpy.data.materials.get("AL_DEPTH_CANDIDATES_MAT")
    if material is None:
        material = bpy.data.materials.new("AL_DEPTH_CANDIDATES_MAT")
    material.diffuse_color = (0.1, 0.85, 0.45, 1.0)
    return material


def create_candidate_debug_mesh(candidates, debug_collection):
    remove_existing_object(DEBUG_OBJECT_NAME)

    vertices = []
    edges = []
    size = POINT_MARKER_SIZE

    for candidate in candidates:
        point = Vector(candidate["point_world_mm"])
        base_index = len(vertices)
        vertices.extend(
            [
                (point.x - size, point.y, point.z),
                (point.x + size, point.y, point.z),
                (point.x, point.y - size, point.z),
                (point.x, point.y + size, point.z),
                (point.x, point.y, point.z - size),
                (point.x, point.y, point.z + size),
            ]
        )
        edges.extend(
            [
                (base_index, base_index + 1),
                (base_index + 2, base_index + 3),
                (base_index + 4, base_index + 5),
            ]
        )

    mesh = bpy.data.meshes.new(f"{DEBUG_OBJECT_NAME}_MESH")
    mesh.from_pydata(vertices, edges, [])
    mesh.update()

    obj = bpy.data.objects.new(DEBUG_OBJECT_NAME, mesh)
    obj.display_type = "WIRE"
    obj.show_name = False
    obj["role"] = "Initial depth candidates constrained to the lamp volume; debug only."
    obj.data.materials.append(create_debug_material())
    debug_collection.objects.link(obj)
    return obj


def write_depth_json(project_root, projection_path, bounds, candidates, rejected):
    output_path = project_root / "output" / "debug" / OUTPUT_JSON_NAME
    payload = {
        "source": "ANAMORPHIC_LAMP scripts/03_depth_solver.py",
        "input_projection_data": str(projection_path),
        "lamp_bounds_mm": bounds,
        "volume_margin_mm": VOLUME_MARGIN,
        "candidate_count": len(candidates),
        "rejected_count": len(rejected),
        "candidates": candidates,
        "rejected": rejected,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def main():
    project_root = get_project_root()
    apply_autosize_config(project_root)
    debug_collection = get_project_child_collection("AL_DEBUG")
    projection_path, projection_data = load_projection_data(project_root)

    bounds, candidates, rejected = solve_depth_candidates(projection_data)
    create_candidate_debug_mesh(candidates, debug_collection)
    output_path = write_depth_json(project_root, projection_path, bounds, candidates, rejected)

    print("")
    print("============================================")
    print(" ANAMORPHIC LAMP")
    print(" STEP 03 - DEPTH SOLVER")
    print("============================================")
    print(f"Project root: {project_root}")
    print(f"Input projection data: {projection_path}")
    print(f"Candidates: {len(candidates)}")
    print(f"Rejected rays: {len(rejected)}")
    print(f"Debug object: {DEBUG_OBJECT_NAME}")
    print(f"Depth data: {output_path}")
    print("Status: SUCCESS")
    print("READY FOR STEP 04")
    print("============================================")


if __name__ == "__main__":
    main()
