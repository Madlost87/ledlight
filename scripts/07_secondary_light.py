import json
from pathlib import Path

import bpy
from mathutils import Vector

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
INPUT_JSON_NAME = "orientation_frames_LOVE.json"
OUTPUT_JSON_NAME = "secondary_light_LOVE.json"
DEBUG_OBJECT_NAME = "AL_SECONDARY_NORMALS"
NORMAL_STEP = 6
NORMAL_SIZE = 12.0


def get_project_root():
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender file before running project scripts.")
    blend_dir = Path(bpy.data.filepath).resolve().parent
    return blend_dir.parent if blend_dir.name == "blender" else blend_dir


def get_debug_collection():
    root = bpy.data.collections.get(PROJECT_COLLECTION)
    if not root:
        raise RuntimeError("Run step 00 first.")
    for child in root.children:
        if child.name.split(".", 1)[0] == "AL_DEBUG":
            return child
    raise RuntimeError("AL_DEBUG collection is missing.")


def remove_existing_object(name):
    obj = bpy.data.objects.get(name)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)


def create_debug(frames, collection):
    remove_existing_object(DEBUG_OBJECT_NAME)
    vertices = []
    edges = []
    down = Vector((0.0, 0.0, -1.0))
    for frame in frames[::NORMAL_STEP]:
        point = Vector(frame["point_world_mm"])
        tangent = Vector(frame["T"]).normalized()
        normal = down - tangent * down.dot(tangent)
        if normal.length < 1e-6:
            normal = Vector(frame["N"])
        normal.normalize()
        base = len(vertices)
        vertices.extend([point, point + normal * NORMAL_SIZE])
        edges.append((base, base + 1))

    mesh = bpy.data.meshes.new(f"{DEBUG_OBJECT_NAME}_MESH")
    mesh.from_pydata(vertices, edges, [])
    mesh.update()
    obj = bpy.data.objects.new(DEBUG_OBJECT_NAME, mesh)
    obj.show_name = False
    obj["role"] = "Preferred secondary normals for table lamp mode: DOWN."
    collection.objects.link(obj)


def main():
    project_root = get_project_root()
    input_path = project_root / "output" / "debug" / INPUT_JSON_NAME
    if not input_path.exists():
        raise FileNotFoundError(f"Missing {input_path}. Run step 05 first.")
    frames = json.loads(input_path.read_text(encoding="utf-8"))["frames"]
    create_debug(frames, get_debug_collection())

    output = {
        "source": "ANAMORPHIC_LAMP scripts/07_secondary_light.py",
        "lamp_type": "TABLE",
        "secondary_light_direction": "DOWN",
        "frame_count": len(frames),
        "debug_object": DEBUG_OBJECT_NAME,
    }
    output_path = project_root / "output" / "debug" / OUTPUT_JSON_NAME
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("STEP 07 - SECONDARY LIGHT")
    print("Direction: DOWN")
    print(f"Output: {output_path}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
