import json
from pathlib import Path

import bpy
from mathutils import Vector

from al_config import load_autosize_config, nested_get

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
PATH_OBJECT_NAME = "AL_CONTINUOUS_PATH"
FRAMES_JSON = "orientation_frames_LOVE.json"
PREVIEW_OBJECT_NAME = "AL_PROFILE_PREVIEW"
BASE_OBJECT_NAME = "AL_BASE_SOLID"
OUTPUT_JSON = "profile_preview_LOVE.json"
PROFILE_WIDTH = 15.0
PROFILE_HEIGHT = 8.0
BASE_DIAMETER = 165.0
BASE_HEIGHT = 25.0


def apply_autosize_config(project_root):
    global PROFILE_WIDTH, PROFILE_HEIGHT, BASE_DIAMETER, BASE_HEIGHT

    config = load_autosize_config(project_root)
    PROFILE_WIDTH = float(nested_get(config, ("lamp", "profile_width_mm"), PROFILE_WIDTH))
    PROFILE_HEIGHT = float(nested_get(config, ("lamp", "profile_height_mm"), PROFILE_HEIGHT))
    BASE_DIAMETER = float(nested_get(config, ("lamp", "base_diameter_mm"), BASE_DIAMETER))
    BASE_HEIGHT = float(nested_get(config, ("lamp", "base_height_mm"), BASE_HEIGHT))


def get_project_root():
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender file before running project scripts.")
    blend_dir = Path(bpy.data.filepath).resolve().parent
    return blend_dir.parent if blend_dir.name == "blender" else blend_dir


def get_geometry_collection():
    root = bpy.data.collections.get(PROJECT_COLLECTION)
    if not root:
        raise RuntimeError("Run step 00 first.")
    for child in root.children:
        if child.name.split(".", 1)[0] == "AL_GEOMETRY":
            return child
    raise RuntimeError("AL_GEOMETRY collection is missing.")


def remove_existing_object(name):
    obj = bpy.data.objects.get(name)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)


def material(name, color):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = color
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = color[3]
    mat.blend_method = "BLEND" if color[3] < 1.0 else "OPAQUE"
    return mat


def read_frames(project_root):
    data = json.loads((project_root / "output" / "debug" / FRAMES_JSON).read_text(encoding="utf-8"))
    return [
        {
            "point": Vector(frame["point_world_mm"]),
            "N": Vector(frame["N"]).normalized(),
            "B": Vector(frame["B"]).normalized(),
        }
        for frame in data["frames"]
    ]


def make_rectangular_profile(collection, frames):
    remove_existing_object(PREVIEW_OBJECT_NAME)
    closed_loop = len(frames) > 3 and (frames[0]["point"] - frames[-1]["point"]).length < 1.5
    mesh_frames = frames[:-1] if closed_loop else frames
    vertices = []
    faces = []
    half_w = PROFILE_WIDTH * 0.5
    half_h = PROFILE_HEIGHT * 0.5

    for frame in mesh_frames:
        point = frame["point"]
        normal = frame["N"]
        binormal = frame["B"]
        vertices.extend(
            [
                point - binormal * half_w - normal * half_h,
                point + binormal * half_w - normal * half_h,
                point + binormal * half_w + normal * half_h,
                point - binormal * half_w + normal * half_h,
            ]
        )

    segment_count = len(mesh_frames) if closed_loop else max(0, len(mesh_frames) - 1)
    for index in range(segment_count):
        a = index * 4
        b = ((index + 1) % len(mesh_frames)) * 4
        faces.extend(
            [
                (a, a + 1, b + 1, b),
                (a + 1, a + 2, b + 2, b + 1),
                (a + 2, a + 3, b + 3, b + 2),
                (a + 3, a, b, b + 3),
            ]
        )

    if mesh_frames and not closed_loop:
        faces.append((0, 1, 2, 3))
        end = (len(mesh_frames) - 1) * 4
        faces.append((end + 3, end + 2, end + 1, end))

    mesh = bpy.data.meshes.new(f"{PREVIEW_OBJECT_NAME}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(PREVIEW_OBJECT_NAME, mesh)
    obj["role"] = "Rectangular physical profile preview swept along P(s)."
    obj["closed_loop"] = closed_loop
    obj.data.materials.append(material("AL_OPAL_BODY_MAT", (0.74, 0.76, 0.76, 0.58)))
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    collection.objects.link(obj)
    return obj


def make_base(collection):
    remove_existing_object(BASE_OBJECT_NAME)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=96,
        radius=BASE_DIAMETER / 2.0,
        depth=BASE_HEIGHT,
        location=(0.0, 0.0, BASE_HEIGHT / 2.0),
    )
    base = bpy.context.object
    base.name = BASE_OBJECT_NAME
    base.data.materials.append(material("AL_BASE_BLACK_MAT", (0.015, 0.013, 0.011, 1.0)))
    for col in list(base.users_collection):
        col.objects.unlink(base)
    collection.objects.link(base)


def main():
    project_root = get_project_root()
    apply_autosize_config(project_root)
    collection = get_geometry_collection()
    frames = read_frames(project_root)
    if not frames:
        raise RuntimeError("Orientation frames missing. Run step 05 first.")

    make_rectangular_profile(collection, frames)
    make_base(collection)

    output = {
        "source": "ANAMORPHIC_LAMP scripts/10_build_profile.py",
        "status": "product preview",
        "profile_width_mm": PROFILE_WIDTH,
        "profile_height_mm": PROFILE_HEIGHT,
        "profile_shape": "rectangular_swept_mesh",
        "closed_loop": len(frames) > 3 and (frames[0]["point"] - frames[-1]["point"]).length < 1.5,
        "object": PREVIEW_OBJECT_NAME,
        "base_object": BASE_OBJECT_NAME,
        "final_mesh_created": False,
    }
    output_path = project_root / "output" / "debug" / OUTPUT_JSON
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("STEP 10 - BUILD PROFILE")
    print("Created product preview body and base.")
    print(f"Output: {output_path}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
