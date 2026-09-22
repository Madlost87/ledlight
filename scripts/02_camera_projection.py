import json
from pathlib import Path

import bpy
from mathutils import Vector

from al_config import target_output_name

# ============================================================
# ANAMORPHIC LAMP
# STEP 02 - CAMERA PROJECTION
# ============================================================

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
TARGET_OBJECT_NAME = "AL_TARGET_IMAGE"
CAMERA_OBJECT_NAME = "AL_CAMERA_MAIN"
DEBUG_POINTS_NAME = "AL_PROJECTION_SAMPLES"
DEBUG_RAYS_NAME = "AL_CAMERA_PROJECTION_RAYS"

WHITE_THRESHOLD = 0.55
PIXEL_STRIDE = 8
MAX_DEBUG_RAYS = 240


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


def local_target_point(pixel_x, pixel_y, width_px, height_px, width_mm, height_mm):
    u = (pixel_x + 0.5) / width_px
    v = (pixel_y + 0.5) / height_px
    return Vector(((u - 0.5) * width_mm, (v - 0.5) * height_mm, 0.0))


def read_luminance_map(image):
    width_px, height_px = image.size
    pixels = list(image.pixels)
    luminance = []

    for pixel_index in range(width_px * height_px):
        rgba_index = pixel_index * 4
        r = pixels[rgba_index]
        g = pixels[rgba_index + 1]
        b = pixels[rgba_index + 2]
        a = pixels[rgba_index + 3]
        luminance.append(((r + g + b) / 3.0) * a)

    return width_px, height_px, luminance


def is_white(luminance, width_px, height_px, x, y):
    if x < 0 or y < 0 or x >= width_px or y >= height_px:
        return False
    return luminance[(y * width_px) + x] >= WHITE_THRESHOLD


def is_boundary_sample(luminance, width_px, height_px, x, y):
    if not is_white(luminance, width_px, height_px, x, y):
        return False

    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if not is_white(luminance, width_px, height_px, nx, ny):
            return True
    return False


def collect_projection_samples(image, target_obj):
    width_px, height_px, luminance = read_luminance_map(image)
    width_mm = float(target_obj.get("target_width_mm", 0.0))
    height_mm = float(target_obj.get("target_height_mm", 0.0))

    if width_mm <= 0.0 or height_mm <= 0.0:
        raise RuntimeError("AL_TARGET_IMAGE has no target_width_mm/target_height_mm properties.")

    samples = []
    white_count = 0

    for y in range(height_px):
        for x in range(width_px):
            if is_white(luminance, width_px, height_px, x, y):
                white_count += 1

    for y in range(0, height_px, PIXEL_STRIDE):
        for x in range(0, width_px, PIXEL_STRIDE):
            if not is_boundary_sample(luminance, width_px, height_px, x, y):
                continue

            local = local_target_point(x, y, width_px, height_px, width_mm, height_mm)
            world = target_obj.matrix_world @ local
            samples.append(
                {
                    "pixel": [x, y],
                    "uv": [(x + 0.5) / width_px, (y + 0.5) / height_px],
                    "target_local_mm": [local.x, local.y, local.z],
                    "target_world_mm": [world.x, world.y, world.z],
                }
            )

    return {
        "image_width_px": width_px,
        "image_height_px": height_px,
        "target_width_mm": width_mm,
        "target_height_mm": height_mm,
        "white_pixel_count": white_count,
        "samples": samples,
    }


def create_debug_sample_mesh(samples, debug_collection):
    remove_existing_object(DEBUG_POINTS_NAME)

    mesh = bpy.data.meshes.new(f"{DEBUG_POINTS_NAME}_MESH")
    vertices = [sample["target_world_mm"] for sample in samples]
    mesh.from_pydata(vertices, [], [])
    mesh.update()

    obj = bpy.data.objects.new(DEBUG_POINTS_NAME, mesh)
    obj.show_name = False
    obj.display_type = "WIRE"
    obj["role"] = "Boundary samples from the target image; debug only."
    debug_collection.objects.link(obj)
    return obj


def create_debug_ray_mesh(samples, camera, debug_collection):
    remove_existing_object(DEBUG_RAYS_NAME)

    if not samples:
        return None

    step = max(1, len(samples) // MAX_DEBUG_RAYS)
    selected = samples[::step][:MAX_DEBUG_RAYS]

    vertices = []
    edges = []
    camera_location = camera.location

    for sample in selected:
        target = Vector(sample["target_world_mm"])
        ray_direction = (target - camera_location).normalized()
        ray_end = camera_location + ray_direction * 220.0

        start_index = len(vertices)
        vertices.append((camera_location.x, camera_location.y, camera_location.z))
        vertices.append((ray_end.x, ray_end.y, ray_end.z))
        edges.append((start_index, start_index + 1))

        sample["camera_origin_mm"] = [
            camera_location.x,
            camera_location.y,
            camera_location.z,
        ]
        sample["camera_ray_direction"] = [
            ray_direction.x,
            ray_direction.y,
            ray_direction.z,
        ]

    mesh = bpy.data.meshes.new(f"{DEBUG_RAYS_NAME}_MESH")
    mesh.from_pydata(vertices, edges, [])
    mesh.update()

    obj = bpy.data.objects.new(DEBUG_RAYS_NAME, mesh)
    obj.display_type = "WIRE"
    obj.show_name = False
    obj["role"] = "Camera rays through sampled target boundary points; debug only."
    debug_collection.objects.link(obj)
    return obj


def write_projection_json(project_root, data, camera):
    debug_dir = project_root / "output" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    output_path = debug_dir / target_output_name(project_root, "camera_projection")

    payload = {
        "source": "ANAMORPHIC_LAMP scripts/02_camera_projection.py",
        "camera": {
            "name": camera.name,
            "location_mm": [camera.location.x, camera.location.y, camera.location.z],
        },
        "threshold": WHITE_THRESHOLD,
        "pixel_stride": PIXEL_STRIDE,
        **data,
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def main():
    project_root = get_project_root()
    debug_collection = get_project_child_collection("AL_DEBUG")

    target_obj = bpy.data.objects.get(TARGET_OBJECT_NAME)
    camera = bpy.data.objects.get(CAMERA_OBJECT_NAME)
    if target_obj is None:
        raise RuntimeError("AL_TARGET_IMAGE is missing. Run scripts/01_target_to_path.py first.")
    if camera is None:
        raise RuntimeError("AL_CAMERA_MAIN is missing. Run scripts/00_setup_scene.py first.")

    image_path = target_obj.get("target_image_path")
    if not image_path:
        raise RuntimeError("AL_TARGET_IMAGE has no target_image_path property.")

    image = bpy.data.images.load(str(image_path), check_existing=True)
    projection_data = collect_projection_samples(image, target_obj)
    samples = projection_data["samples"]

    create_debug_sample_mesh(samples, debug_collection)
    create_debug_ray_mesh(samples, camera, debug_collection)
    json_path = write_projection_json(project_root, projection_data, camera)

    print("")
    print("============================================")
    print(" ANAMORPHIC LAMP")
    print(" STEP 02 - CAMERA PROJECTION")
    print("============================================")
    print(f"Project root: {project_root}")
    print(
        "Image resolution: "
        f"{projection_data['image_width_px']} x {projection_data['image_height_px']} px"
    )
    print(f"White pixels: {projection_data['white_pixel_count']}")
    print(f"Boundary samples: {len(samples)}")
    print(f"Debug objects: {DEBUG_POINTS_NAME}, {DEBUG_RAYS_NAME}")
    print(f"Projection data: {json_path}")
    print("Status: SUCCESS")
    print("READY FOR STEP 03")
    print("============================================")


if __name__ == "__main__":
    main()
