import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from PIL import Image

from al_config import (
    get_target_image_name,
    load_autosize_config,
    nested_get,
    readable_preview_object_name,
    target_output_name,
)

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
LED_OBJECT = "AL_LED_CHANNEL_PREVIEW"
READABILITY_OBJECT = "AL_CAMERA_READABILITY_PREVIEW"
LED_WIDTH = 10.0
LED_THICKNESS = 3.0
LED_OFFSET = 4.8
READABLE_LED_WIDTH = 3.2
LED_TWIST_TRANSITION_MM = 65.0
COVERAGE_ROW_STEP_PX = 16
COVERAGE_MIN_RUN_PX = 10
COVERAGE_X_SCALE = 0.96
COVERAGE_Z_SCALE = 0.96
COVERAGE_Z_CENTER = 160.0
COVERAGE_DEPTH_MIN = -96.0
COVERAGE_DEPTH_MAX = 96.0
READABILITY_SAMPLE_STEP = 12
READABILITY_Y = -260.0
READABILITY_TILE_MM = 2.6
TARGET_WIDTH_MM = 260.0
CAMERA_Y = -1050.0
CAMERA_Z = 175.0
TARGET_PLANE_Y = 0.0


def apply_autosize_config(project_root):
    global LED_WIDTH, LED_THICKNESS, LED_OFFSET, READABLE_LED_WIDTH, LED_TWIST_TRANSITION_MM
    global COVERAGE_X_SCALE, COVERAGE_Z_SCALE, COVERAGE_Z_CENTER
    global COVERAGE_DEPTH_MIN, COVERAGE_DEPTH_MAX, READABILITY_Y
    global TARGET_WIDTH_MM, CAMERA_Y, CAMERA_Z

    config = load_autosize_config(project_root)
    LED_WIDTH = float(nested_get(config, ("led", "width_mm"), LED_WIDTH))
    LED_THICKNESS = float(nested_get(config, ("led", "thickness_mm"), LED_THICKNESS))
    profile_height = float(nested_get(config, ("lamp", "profile_height_mm"), LED_OFFSET * 2.0))
    LED_OFFSET = float(nested_get(config, ("led", "offset_mm"), profile_height * 0.5 + LED_THICKNESS * 0.25))
    READABLE_LED_WIDTH = float(nested_get(config, ("preview", "readable_led_width_mm"), max(2.6, LED_WIDTH * 0.32)))
    LED_TWIST_TRANSITION_MM = float(
        nested_get(config, ("planner", "twist_length_for_90_deg_mm"), LED_TWIST_TRANSITION_MM)
    )
    COVERAGE_X_SCALE = float(nested_get(config, ("target", "x_scale"), COVERAGE_X_SCALE))
    COVERAGE_Z_SCALE = float(nested_get(config, ("target", "z_scale"), COVERAGE_Z_SCALE))
    COVERAGE_Z_CENTER = float(nested_get(config, ("target", "z_center_mm"), COVERAGE_Z_CENTER))
    max_depth = float(nested_get(config, ("lamp", "max_sculptural_depth_mm"), COVERAGE_DEPTH_MAX))
    COVERAGE_DEPTH_MIN = -max_depth
    COVERAGE_DEPTH_MAX = max_depth
    lamp_depth = float(nested_get(config, ("lamp", "depth_mm"), abs(READABILITY_Y)))
    READABILITY_Y = -lamp_depth * 1.18
    TARGET_WIDTH_MM = float(nested_get(config, ("target", "width_mm"), TARGET_WIDTH_MM))
    CAMERA_Y = -float(nested_get(config, ("camera", "distance_mm"), abs(CAMERA_Y)))
    CAMERA_Z = float(nested_get(config, ("camera", "height_mm"), CAMERA_Z))


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


def make_led_material():
    mat = bpy.data.materials.get("AL_LED_WARM_MAT")
    if mat is None:
        mat = bpy.data.materials.new("AL_LED_WARM_MAT")
    mat.diffuse_color = (1.0, 0.72, 0.34, 1.0)
    mat.use_backface_culling = True
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (1.0, 0.58, 0.22, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = 7.0
    return mat


def make_readability_material():
    mat = bpy.data.materials.get("AL_READABILITY_WARM_MAT")
    if mat is None:
        mat = bpy.data.materials.new("AL_READABILITY_WARM_MAT")
    mat.diffuse_color = (1.0, 0.76, 0.36, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (1.0, 0.76, 0.36, 1.0)
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (1.0, 0.58, 0.20, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = 4.0
    return mat


def make_led_side_material():
    mat = bpy.data.materials.get("AL_LED_HOUSING_DARK_MAT")
    if mat is None:
        mat = bpy.data.materials.new("AL_LED_HOUSING_DARK_MAT")
    mat.diffuse_color = (0.18, 0.18, 0.16, 1.0)
    mat.use_backface_culling = True
    return mat


def read_led_points(project_root):
    frame_data = json.loads(
        (project_root / "output" / "debug" / target_output_name(project_root, "orientation_frames")).read_text(
            encoding="utf-8"
        )
    )
    path_data = json.loads(
        (project_root / "output" / "debug" / target_output_name(project_root, "continuous_path")).read_text(
            encoding="utf-8"
        )
    )
    points = []
    flags = []
    path_nodes = path_data.get("nodes", [])
    for index, frame in enumerate(frame_data["frames"]):
        point = Vector(frame["point_world_mm"])
        normal = Vector(frame["N"]).normalized()
        points.append(point + normal * LED_OFFSET)
        if index < len(path_nodes):
            flags.append(bool(path_nodes[index].get("front_facing_from_previous", path_nodes[index].get("led_on_from_previous", True))))
        else:
            flags.append(True)
    return points, flags


def read_led_frames(project_root):
    frame_data = json.loads(
        (project_root / "output" / "debug" / target_output_name(project_root, "orientation_frames")).read_text(
            encoding="utf-8"
        )
    )
    path_data = json.loads(
        (project_root / "output" / "debug" / target_output_name(project_root, "continuous_path")).read_text(
            encoding="utf-8"
        )
    )
    path_nodes = path_data.get("nodes", [])
    frames = []
    for index, frame in enumerate(frame_data["frames"]):
        frames.append(
            {
                "point": Vector(frame["point_world_mm"]),
                "T": Vector(frame["T"]).normalized(),
                "N": Vector(frame["N"]).normalized(),
                "B": Vector(frame["B"]).normalized(),
                "front_facing": bool(
                    path_nodes[index].get("front_facing_from_previous", path_nodes[index].get("led_on_from_previous", True))
                )
                if index < len(path_nodes)
                else True,
                "mask_fit_fraction": float(path_nodes[index].get("mask_fit_fraction", 1.0))
                if index < len(path_nodes)
                else 1.0,
            }
        )
    return frames


def read_projection_points(project_root):
    data = json.loads(
        (project_root / "output" / "debug" / target_output_name(project_root, "continuous_path")).read_text(
            encoding="utf-8"
        )
    )
    points = []
    flags = []
    for node in data["nodes"]:
        projection = node.get("target_projection_mm")
        if projection:
            points.append(Vector(projection))
            flags.append(bool(node.get("front_facing_from_previous", node.get("led_on_from_previous", True))))
    return points, flags


def project_target_to_y(x_target, z_target, y_depth):
    factor = (y_depth - CAMERA_Y) / (TARGET_PLANE_Y - CAMERA_Y)
    x_world = x_target * factor
    z_world = CAMERA_Z + (z_target - CAMERA_Z) * factor
    return Vector((x_world, y_depth, z_world))


def coverage_depth_for_curve(curve_index, curve_count, x_mid):
    if curve_count <= 1:
        t = 0.5
    else:
        t = curve_index / (curve_count - 1)
    sweep = (t - 0.5) * (COVERAGE_DEPTH_MAX - COVERAGE_DEPTH_MIN)
    local = 10.0 * math.sin(x_mid * 0.055 + t * math.tau)
    return max(COVERAGE_DEPTH_MIN, min(COVERAGE_DEPTH_MAX, sweep + local))


def target_pixel_to_mm(x, y, width_px, height_px):
    target_height_mm = TARGET_WIDTH_MM * (height_px / width_px)
    x_target = ((x + 0.5) / width_px - 0.5) * TARGET_WIDTH_MM * COVERAGE_X_SCALE
    z_target = (
        (0.5 - (y + 0.5) / height_px) * target_height_mm * COVERAGE_Z_SCALE
        + COVERAGE_Z_CENTER
    )
    return x_target, z_target


def read_coverage_segments(project_root):
    image_path = project_root / "input" / get_target_image_name(project_root)
    image = Image.open(image_path).convert("L")
    width_px, height_px = image.size
    pixels = image.load()
    target_segments = []

    for y in range(0, height_px, COVERAGE_ROW_STEP_PX):
        row_segments = []
        x = 0
        while x < width_px:
            while x < width_px and pixels[x, y] < 150:
                x += 1
            start = x
            while x < width_px and pixels[x, y] >= 150:
                x += 1
            end = x - 1
            if end - start + 1 >= COVERAGE_MIN_RUN_PX:
                row_segments.append((start, end, y))
        target_segments.extend(row_segments)

    segments = []
    total = len(target_segments)
    for index, (start, end, y) in enumerate(target_segments):
        x0, z0 = target_pixel_to_mm(start, y, width_px, height_px)
        x1, z1 = target_pixel_to_mm(end, y, width_px, height_px)
        depth = coverage_depth_for_curve(index, total, (x0 + x1) * 0.5)
        segments.append([project_target_to_y(x0, z0, depth), project_target_to_y(x1, z1, depth)])
    return segments


def create_readability_preview(project_root):
    remove_existing_object(READABILITY_OBJECT)
    image_path = project_root / "input" / get_target_image_name(project_root)
    image = Image.open(image_path).convert("L")
    width_px, height_px = image.size
    pixels = image.load()
    target_height_mm = TARGET_WIDTH_MM * (height_px / width_px)

    vertices = []
    faces = []
    half = READABILITY_TILE_MM / 2.0

    for y in range(0, height_px, READABILITY_SAMPLE_STEP):
        for x in range(0, width_px, READABILITY_SAMPLE_STEP):
            if pixels[x, y] < 150:
                continue

            x_target = ((x + 0.5) / width_px - 0.5) * TARGET_WIDTH_MM
            z_target = (0.5 - (y + 0.5) / height_px) * target_height_mm + 145.0
            center = project_target_to_y(x_target, z_target, READABILITY_Y)

            base = len(vertices)
            vertices.extend(
                [
                    (center.x - half, center.y, center.z - half),
                    (center.x + half, center.y, center.z - half),
                    (center.x + half, center.y, center.z + half),
                    (center.x - half, center.y, center.z + half),
                ]
            )
            faces.append((base, base + 1, base + 2, base + 3))

    mesh = bpy.data.meshes.new(f"{READABILITY_OBJECT}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(READABILITY_OBJECT, mesh)
    obj["role"] = "Camera readability preview sampled from target bitmap; diagnostic, not final geometry."
    obj.data.materials.append(make_readability_material())
    get_geometry_collection().objects.link(obj)
    return obj, len(faces)


def create_curve_object(name, points, bevel_depth, material):
    remove_existing_object(name)
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 5
    spline = curve.splines.new(type="POLY")
    spline.points.add(len(points) - 1)
    for spline_point, point in zip(spline.points, points):
        spline_point.co = (point.x, point.y, point.z, 1.0)

    obj = bpy.data.objects.new(name, curve)
    obj.data.materials.append(material)
    get_geometry_collection().objects.link(obj)
    return obj


def split_lit_segments(points, flags):
    segments = []
    current = []
    for index in range(1, len(points)):
        if index >= len(flags) or not flags[index]:
            if len(current) >= 2:
                segments.append(current)
            current = []
            continue
        if not current:
            current = [points[index - 1]]
        current.append(points[index])
    if len(current) >= 2:
        segments.append(current)
    return segments


def create_multi_curve_object(name, segments, bevel_depth, material):
    remove_existing_object(name)
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 5
    for segment in segments:
        spline = curve.splines.new(type="POLY")
        spline.points.add(len(segment) - 1)
        for spline_point, point in zip(spline.points, segment):
            spline_point.co = (point.x, point.y, point.z, 1.0)

    obj = bpy.data.objects.new(name, curve)
    obj.data.materials.append(material)
    get_geometry_collection().objects.link(obj)
    return obj


def arc_lengths(frames):
    lengths = [0.0]
    for index in range(1, len(frames)):
        lengths.append(lengths[-1] + (frames[index]["point"] - frames[index - 1]["point"]).length)
    return lengths


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def frontness_profile(frames, transition_mm):
    lengths = arc_lengths(frames)
    if not frames:
        return [], lengths

    raw_values = []
    for frame in frames:
        fraction = float(frame.get("mask_fit_fraction", 1.0 if frame["front_facing"] else 0.0))
        # A broad ramp keeps the physical LED face from snapping when the
        # projected path grazes the target mask edge.
        raw_values.append(smoothstep((fraction - 0.12) / 0.76))

    smoothing_radius = max(transition_mm * 0.45, 1.0)
    smoothed = []
    for index, length in enumerate(lengths):
        weighted_sum = 0.0
        total_weight = 0.0
        for other_index, other_length in enumerate(lengths):
            distance = abs(other_length - length)
            if distance > smoothing_radius:
                continue
            weight = 1.0 - distance / smoothing_radius
            weighted_sum += raw_values[other_index] * weight
            total_weight += weight
        smoothed.append(weighted_sum / total_weight if total_weight else raw_values[index])

    return smoothed, lengths


def safe_normalized(vector, fallback):
    if vector.length < 1e-8:
        return fallback.copy()
    return vector.normalized()


def create_continuous_led_ribbon(name, frames, led_width, led_offset, led_material, side_material):
    remove_existing_object(name)
    closed_loop = len(frames) > 3 and (frames[0]["point"] - frames[-1]["point"]).length < 1.5
    mesh_frames = frames[:-1] if closed_loop else frames
    vertices = []
    faces = []
    material_indices = []
    frontness_values, lengths = frontness_profile(mesh_frames, LED_TWIST_TRANSITION_MM)

    for index, frame in enumerate(mesh_frames):
        frontness = frontness_values[index]
        tangent = frame["T"]
        normal = frame["N"]
        binormal = frame["B"]

        # The LED face is always emissive. On white-mask portions it turns
        # toward the camera; between them it twists away, so it stays physically
        # on but contributes little from the privileged view.
        side_face_normal = binormal
        visible_face_normal = normal
        face_normal = safe_normalized(side_face_normal.lerp(visible_face_normal, frontness), visible_face_normal)
        width_axis = safe_normalized(tangent.cross(face_normal), binormal)
        front_center = frame["point"] + face_normal * led_offset
        back_center = front_center - face_normal * LED_THICKNESS
        vertices.append(front_center - width_axis * (led_width * 0.5))
        vertices.append(front_center + width_axis * (led_width * 0.5))
        vertices.append(back_center - width_axis * (led_width * 0.5))
        vertices.append(back_center + width_axis * (led_width * 0.5))

    segment_count = len(mesh_frames) if closed_loop else max(0, len(mesh_frames) - 1)
    for index in range(segment_count):
        a = index * 4
        b = ((index + 1) % len(mesh_frames)) * 4
        faces.append((a, a + 1, b + 1, b))
        material_indices.append(0)
        faces.append((a + 2, b + 2, b + 3, a + 3))
        material_indices.append(1)
        faces.append((a, b, b + 2, a + 2))
        material_indices.append(1)
        faces.append((a + 1, a + 3, b + 3, b + 1))
        material_indices.append(1)

    if len(mesh_frames) >= 2 and not closed_loop:
        faces.append((2, 3, 1, 0))
        material_indices.append(1)
        end = (len(mesh_frames) - 1) * 4
        faces.append((end, end + 1, end + 3, end + 2))
        material_indices.append(1)

    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(led_material)
    obj.data.materials.append(side_material)
    for polygon, material_index in zip(obj.data.polygons, material_indices):
        polygon.material_index = material_index
        polygon.use_smooth = True
    obj["role"] = "One continuous always-on LED ribbon. It turns front-facing only where P(s) projects onto the white target mask."
    obj["twist_transition_mm"] = LED_TWIST_TRANSITION_MM
    obj["closed_loop"] = closed_loop
    get_geometry_collection().objects.link(obj)
    lit_equivalent = sum(1 for value in frontness_values if value >= 0.5)
    obj["frontness_model"] = "continuous mask-fit smoothing"
    return obj, lit_equivalent, lengths[-1] if lengths else 0.0


def main():
    project_root = get_project_root()
    apply_autosize_config(project_root)
    led_material = make_led_material()
    side_material = make_led_side_material()
    led_frames = read_led_frames(project_root)
    readable_object = readable_preview_object_name(project_root)
    led, lit_nodes, led_length = create_continuous_led_ribbon(
        LED_OBJECT, led_frames, LED_WIDTH, LED_OFFSET, led_material, side_material
    )

    readable_points, readable_flags = read_projection_points(project_root)
    readable_segments = split_lit_segments(readable_points, readable_flags)
    readable = create_multi_curve_object(readable_object, readable_segments, READABLE_LED_WIDTH / 2.0, led_material)
    readable["role"] = "Camera-readable anamorphic preview generated from target projection."
    readability, readability_tiles = create_readability_preview(project_root)

    output = {
        "source": "ANAMORPHIC_LAMP scripts/11_led_channel.py",
        "status": "product preview",
        "led_width_mm": LED_WIDTH,
        "led_thickness_mm": LED_THICKNESS,
        "led_offset_mm": LED_OFFSET,
        "twist_transition_mm": LED_TWIST_TRANSITION_MM,
        "continuous_led_length_mm": led_length,
        "object": LED_OBJECT,
        "continuous_led_profile": True,
        "closed_loop": bool(led.get("closed_loop")),
        "front_facing_nodes": lit_nodes,
        "frontness_model": "continuous mask-fit smoothing",
        "led_power_model": "always_on",
        "front_facing_rule": "The LED is always on; it becomes visible from camera where the profile twists its luminous face toward the target mask.",
        "camera_readable_object": readable_object,
        "camera_readability_preview": READABILITY_OBJECT,
        "camera_readability_tiles": readability_tiles,
    }
    output_path = project_root / "output" / "debug" / target_output_name(project_root, "led_channel_preview")
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("STEP 11 - LED CHANNEL")
    print(f"Preview object: {LED_OBJECT}")
    print(f"Output: {output_path}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
