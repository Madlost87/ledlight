from pathlib import Path

import bpy

from al_config import load_autosize_config, nested_get

# ============================================================
# ANAMORPHIC LAMP
# STEP 01 - TARGET IMAGE TO VISUAL REFERENCE
# ============================================================

TARGET_IMAGE_NAME = "target_LOVE.png"
TARGET_PHYSICAL_WIDTH = 260.0
TARGET_OBJECT_NAME = "AL_TARGET_IMAGE"
PROJECT_COLLECTION = "ANAMORPHIC_LAMP"


def apply_autosize_config(project_root):
    global TARGET_PHYSICAL_WIDTH

    config = load_autosize_config(project_root)
    TARGET_PHYSICAL_WIDTH = float(nested_get(config, ("target", "width_mm"), TARGET_PHYSICAL_WIDTH))


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


def get_collection(name):
    root = bpy.data.collections.get(PROJECT_COLLECTION)
    if root:
        for child in root.children:
            if child.name.split(".", 1)[0] == name:
                return child

    collection = bpy.data.collections.get(name)
    if collection:
        return collection

    if not collection:
        raise RuntimeError(
            f"Collection {name!r} was not found. Run scripts/00_setup_scene.py first."
        )


def unlink_from_current_collections(obj):
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)


def remove_existing_object(name):
    existing = bpy.data.objects.get(name)
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)


def orient_plane_toward_camera(obj, camera):
    direction = camera.location - obj.location
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()


def create_target_material(image):
    material = bpy.data.materials.get("AL_TARGET_IMAGE_MAT")
    if material is None:
        material = bpy.data.materials.new("AL_TARGET_IMAGE_MAT")

    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    for node in list(nodes):
        if node.type not in {"OUTPUT_MATERIAL", "BSDF_PRINCIPLED"}:
            nodes.remove(node)

    principled = nodes.get("Principled BSDF")
    if principled is None:
        principled = nodes.new(type="ShaderNodeBsdfPrincipled")

    image_node = nodes.new(type="ShaderNodeTexImage")
    image_node.name = "AL_TARGET_IMAGE_TEXTURE"
    image_node.image = image

    if "Base Color" in principled.inputs:
        links.new(image_node.outputs["Color"], principled.inputs["Base Color"])
    if "Alpha" in principled.inputs and "Alpha" in image_node.outputs:
        links.new(image_node.outputs["Alpha"], principled.inputs["Alpha"])
    if "Emission Color" in principled.inputs:
        links.new(image_node.outputs["Color"], principled.inputs["Emission Color"])
    if "Emission Strength" in principled.inputs:
        principled.inputs["Emission Strength"].default_value = 1.0

    material.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    material.blend_method = "BLEND"
    return material


def main():
    project_root = get_project_root()
    apply_autosize_config(project_root)
    image_path = project_root / "input" / TARGET_IMAGE_NAME

    print("")
    print("============================================")
    print(" ANAMORPHIC LAMP")
    print(" STEP 01 - TARGET IMAGE")
    print("============================================")
    print(f"Project root: {project_root}")
    print(f"Image path: {image_path}")

    if not image_path.exists():
        raise FileNotFoundError(
            f"Target image not found: {image_path}. "
            "Place target_LOVE.png in ANAMORPHIC_LAMP/input/ and rerun this script."
        )

    camera = bpy.data.objects.get("AL_CAMERA_MAIN")
    target = bpy.data.objects.get("AL_CAMERA_TARGET")
    if camera is None or target is None:
        raise RuntimeError("AL_CAMERA_MAIN or AL_CAMERA_TARGET is missing. Run step 00 first.")

    debug_collection = get_collection("AL_DEBUG")
    remove_existing_object(TARGET_OBJECT_NAME)

    image = bpy.data.images.load(str(image_path), check_existing=True)
    width_px, height_px = image.size
    if width_px <= 0 or height_px <= 0:
        raise RuntimeError(f"Invalid image resolution for {image_path}")

    aspect = height_px / width_px
    target_width = TARGET_PHYSICAL_WIDTH
    target_height = target_width * aspect

    bpy.ops.mesh.primitive_plane_add(size=1.0, location=target.location)
    plane = bpy.context.object
    plane.name = TARGET_OBJECT_NAME
    plane.dimensions = (target_width, target_height, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    orient_plane_toward_camera(plane, camera)

    material = create_target_material(image)
    plane.data.materials.clear()
    plane.data.materials.append(material)
    plane.show_name = False
    plane.hide_render = True
    plane["target_image_path"] = str(image_path)
    plane["target_width_mm"] = target_width
    plane["target_height_mm"] = target_height
    plane["role"] = "Perspective target reference only; not final geometry."

    unlink_from_current_collections(plane)
    debug_collection.objects.link(plane)

    print(f"Image resolution: {width_px} x {height_px} px")
    print(f"Physical target: {target_width:.2f} x {target_height:.2f} mm")
    print("Created: AL_TARGET_IMAGE")
    print("Status: SUCCESS")
    print("============================================")


if __name__ == "__main__":
    main()
