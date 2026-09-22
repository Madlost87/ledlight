import math
from pathlib import Path

import bpy
from mathutils import Vector

from al_config import load_autosize_config, nested_get

# ============================================================
# ANAMORPHIC LAMP
# STEP 00 - SETUP SCENE
# ============================================================

LAMP_HEIGHT = 320.0
LAMP_WIDTH = 320.0
LAMP_DEPTH = 220.0

BASE_DIAMETER = 165.0
BASE_HEIGHT = 25.0

CAMERA_DISTANCE = 1050.0
CAMERA_HEIGHT = 175.0

PROFILE_WIDTH = 15.0
PROFILE_HEIGHT = 8.0

LED_WIDTH = 10.0

MIN_BEND_RADIUS = 35.0

RENDER_X = 1000
RENDER_Y = 1000

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
PROJECT_CHILD_COLLECTIONS = ("AL_HELPERS", "AL_GEOMETRY", "AL_DEBUG")


def apply_autosize_config(project_root):
    global LAMP_HEIGHT, LAMP_WIDTH, LAMP_DEPTH
    global BASE_DIAMETER, BASE_HEIGHT, CAMERA_DISTANCE, CAMERA_HEIGHT
    global PROFILE_WIDTH, PROFILE_HEIGHT, LED_WIDTH, MIN_BEND_RADIUS

    config = load_autosize_config(project_root)
    if not config:
        return

    LAMP_WIDTH = float(nested_get(config, ("lamp", "width_mm"), LAMP_WIDTH))
    LAMP_DEPTH = float(nested_get(config, ("lamp", "depth_mm"), LAMP_DEPTH))
    LAMP_HEIGHT = float(nested_get(config, ("lamp", "height_mm"), LAMP_HEIGHT))
    BASE_DIAMETER = float(nested_get(config, ("lamp", "base_diameter_mm"), BASE_DIAMETER))
    BASE_HEIGHT = float(nested_get(config, ("lamp", "base_height_mm"), BASE_HEIGHT))
    PROFILE_WIDTH = float(nested_get(config, ("lamp", "profile_width_mm"), PROFILE_WIDTH))
    PROFILE_HEIGHT = float(nested_get(config, ("lamp", "profile_height_mm"), PROFILE_HEIGHT))
    LED_WIDTH = float(nested_get(config, ("led", "width_mm"), LED_WIDTH))
    MIN_BEND_RADIUS = float(nested_get(config, ("planner", "min_bend_radius_mm"), MIN_BEND_RADIUS))
    CAMERA_DISTANCE = float(nested_get(config, ("camera", "distance_mm"), CAMERA_DISTANCE))
    CAMERA_HEIGHT = float(nested_get(config, ("camera", "height_mm"), CAMERA_HEIGHT))


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


def ensure_project_dirs(project_root):
    for relative in (
        "input",
        "scripts",
        "blender",
        "output/renders",
        "output/debug",
        "output/export",
    ):
        (project_root / relative).mkdir(parents=True, exist_ok=True)


def remove_collection_tree(collection):
    for child in list(collection.children):
        remove_collection_tree(child)
    bpy.data.collections.remove(collection)


def delete_collection(name):
    collection = bpy.data.collections.get(name)
    if not collection:
        return

    for obj in list(collection.all_objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    remove_collection_tree(collection)


def delete_stale_project_collections():
    delete_collection(PROJECT_COLLECTION)

    for collection in list(bpy.data.collections):
        base_name = collection.name.split(".", 1)[0]
        if base_name in PROJECT_CHILD_COLLECTIONS:
            remove_collection_tree(collection)


def create_child_collection(name, parent):
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


def move_to_collection(obj, collection):
    for old_collection in list(obj.users_collection):
        old_collection.objects.unlink(obj)
    collection.objects.link(obj)


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def main():
    project_root = get_project_root()
    ensure_project_dirs(project_root)
    apply_autosize_config(project_root)

    delete_stale_project_collections()

    root = bpy.data.collections.new(PROJECT_COLLECTION)
    bpy.context.scene.collection.children.link(root)

    helpers = create_child_collection("AL_HELPERS", root)
    create_child_collection("AL_GEOMETRY", root)
    create_child_collection("AL_DEBUG", root)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001

    lamp_center = Vector((0.0, 0.0, LAMP_HEIGHT / 2.0))

    bpy.ops.mesh.primitive_cube_add(location=lamp_center)
    volume = bpy.context.object
    volume.name = "AL_LAMP_VOLUME"
    volume.dimensions = (LAMP_WIDTH, LAMP_DEPTH, LAMP_HEIGHT)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    volume.display_type = "WIRE"
    volume.hide_render = True
    move_to_collection(volume, helpers)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,
        radius=BASE_DIAMETER / 2.0,
        depth=BASE_HEIGHT,
        location=(0.0, 0.0, BASE_HEIGHT / 2.0),
    )
    base = bpy.context.object
    base.name = "AL_BASE_REFERENCE"
    base.display_type = "WIRE"
    base.hide_render = True
    move_to_collection(base, helpers)

    camera_data = bpy.data.cameras.new("AL_CAMERA_MAIN_DATA")
    camera = bpy.data.objects.new("AL_CAMERA_MAIN", camera_data)
    helpers.objects.link(camera)
    camera.location = (0.0, -CAMERA_DISTANCE, CAMERA_HEIGHT)
    look_at(camera, (0.0, 0.0, 150.0))
    camera.data.type = "PERSP"
    camera.data.lens = 50.0
    scene.camera = camera

    bpy.ops.object.empty_add(type="SPHERE", radius=5.0, location=(0.0, 0.0, 150.0))
    target = bpy.context.object
    target.name = "AL_CAMERA_TARGET"
    move_to_collection(target, helpers)

    bpy.ops.mesh.primitive_plane_add(size=600.0, location=(0.0, 0.0, 0.0))
    table = bpy.context.object
    table.name = "AL_TABLE_TARGET"
    table.display_type = "WIRE"
    table.hide_render = True
    move_to_collection(table, helpers)

    bpy.ops.object.empty_add(type="SINGLE_ARROW", location=(120.0, 0.0, 150.0))
    secondary = bpy.context.object
    secondary.name = "AL_SECONDARY_LIGHT_DIRECTION"
    secondary.empty_display_size = 50.0
    secondary.rotation_euler = (math.radians(180.0), 0.0, 0.0)
    secondary["direction"] = "DOWN"
    move_to_collection(secondary, helpers)

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
    origin = bpy.context.object
    origin.name = "AL_WORLD_ORIGIN"
    origin.empty_display_size = 30.0
    move_to_collection(origin, helpers)

    scene.render.resolution_x = RENDER_X
    scene.render.resolution_y = RENDER_Y
    scene.render.resolution_percentage = 100

    root["project_root"] = str(project_root)
    root["lamp_height"] = LAMP_HEIGHT
    root["lamp_width"] = LAMP_WIDTH
    root["lamp_depth"] = LAMP_DEPTH
    root["base_diameter"] = BASE_DIAMETER
    root["base_height"] = BASE_HEIGHT
    root["profile_width"] = PROFILE_WIDTH
    root["profile_height"] = PROFILE_HEIGHT
    root["led_width"] = LED_WIDTH
    root["min_bend_radius"] = MIN_BEND_RADIUS
    root["camera_distance"] = CAMERA_DISTANCE
    root["camera_height"] = CAMERA_HEIGHT
    root["lamp_type"] = "TABLE"
    root["secondary_light_direction"] = "DOWN"
    root["project_version"] = "0.01"

    print("")
    print("============================================")
    print(" ANAMORPHIC LAMP")
    print(" STEP 00 COMPLETED")
    print("============================================")
    print(f"Project root: {project_root}")
    print(f"Volume: {LAMP_WIDTH:.0f} x {LAMP_DEPTH:.0f} x {LAMP_HEIGHT:.0f} mm")
    print(f"Camera: (0, {-CAMERA_DISTANCE:.0f}, {CAMERA_HEIGHT:.0f}) mm")
    print(f"Minimum bend radius: {MIN_BEND_RADIUS:.0f} mm")
    print("Secondary light direction: DOWN")
    print("READY FOR STEP 01")
    print("============================================")


if __name__ == "__main__":
    main()
