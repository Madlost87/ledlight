import json
import math
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

from al_config import load_autosize_config, nested_get, target_output_name

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
DEBUG_OBJECT_NAME = "AL_ORIENTATION_FRAMES"
FRAME_STEP = 3
FRAME_SIZE = 9.0
CAMERA_ATTRACTION = 0.18
TWIST_LENGTH_FOR_90_DEG_MM = 520.0
FRAME_SMOOTHING_PASSES = 12
FRAME_SMOOTHING_WEIGHT = 0.30
DEFAULT_CAMERA_LOCATION = Vector((0.0, -1050.0, 175.0))


def apply_autosize_config(project_root):
    global DEFAULT_CAMERA_LOCATION, TWIST_LENGTH_FOR_90_DEG_MM

    config = load_autosize_config(project_root)
    distance = float(nested_get(config, ("camera", "distance_mm"), abs(DEFAULT_CAMERA_LOCATION.y)))
    height = float(nested_get(config, ("camera", "height_mm"), DEFAULT_CAMERA_LOCATION.z))
    DEFAULT_CAMERA_LOCATION = Vector((0.0, -distance, height))
    TWIST_LENGTH_FOR_90_DEG_MM = float(
        nested_get(config, ("planner", "twist_length_for_90_deg_mm"), TWIST_LENGTH_FOR_90_DEG_MM)
    )


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


def safe_normalize(vector, fallback):
    if vector.length < 1e-8:
        return fallback.copy()
    return vector.normalized()


def read_points(project_root):
    input_path = project_root / "output" / "debug" / target_output_name(project_root, "continuous_path")
    if not input_path.exists():
        raise FileNotFoundError(f"Missing {input_path}. Run step 04 first.")
    data = json.loads(input_path.read_text(encoding="utf-8"))
    points = [Vector(node["point_world_mm"]) for node in data["nodes"]]
    front_facing = [
        bool(node.get("front_facing_from_previous", node.get("led_on_from_previous", True)))
        for node in data["nodes"]
    ]
    return input_path, points, front_facing


def limited_slerp(start, target, max_angle_rad):
    angle = start.angle(target, 0.0)
    if angle <= max_angle_rad or angle < 1e-8:
        return target.copy()
    return start.slerp(target, max_angle_rad / angle).normalized()


def build_frames(points, front_facing):
    camera = bpy.data.objects.get("AL_CAMERA_MAIN")
    camera_location = camera.location if camera else DEFAULT_CAMERA_LOCATION
    frames = []
    previous_n = None
    previous_t = None
    closed_loop = len(points) > 3 and (points[0] - points[-1]).length < 1.5

    for index, point in enumerate(points):
        if closed_loop:
            previous_index = index - 1 if index > 0 else len(points) - 2
            next_index = index + 1 if index < len(points) - 1 else 1
            tangent = points[next_index] - points[previous_index]
        elif index == 0:
            tangent = points[1] - point
        elif index == len(points) - 1:
            tangent = point - points[index - 1]
        else:
            tangent = points[index + 1] - points[index - 1]
        tangent = safe_normalize(tangent, Vector((1.0, 0.0, 0.0)))

        to_camera = safe_normalize(camera_location - point, Vector((0.0, -1.0, 0.0)))
        camera_normal = to_camera - tangent * to_camera.dot(tangent)
        camera_normal = safe_normalize(camera_normal, previous_n if previous_n else Vector((0.0, -1.0, 0.0)))

        if previous_n is None or previous_t is None:
            normal = camera_normal
        else:
            transported = previous_n - tangent * previous_n.dot(tangent)
            transported = safe_normalize(transported, camera_normal)
            if transported.dot(camera_normal) < 0.0:
                camera_normal.negate()
            attraction = CAMERA_ATTRACTION if front_facing[index] else CAMERA_ATTRACTION * 0.16
            target_normal = transported.lerp(camera_normal, attraction)
            target_normal = safe_normalize(target_normal, transported)
            segment_length = max((point - points[index - 1]).length, 1e-6)
            max_twist = math.radians(90.0) * segment_length / TWIST_LENGTH_FOR_90_DEG_MM
            normal = limited_slerp(transported, target_normal, max_twist)
            normal = safe_normalize(normal, transported)

        binormal = safe_normalize(tangent.cross(normal), Vector((0.0, 0.0, 1.0)))
        normal = safe_normalize(binormal.cross(tangent), normal)

        curvature = 0.0
        if 0 < index < len(points) - 1:
            prev_t = safe_normalize(point - points[index - 1], tangent)
            next_t = safe_normalize(points[index + 1] - point, tangent)
            span = max((points[index + 1] - points[index - 1]).length, 1e-6)
            curvature = (next_t - prev_t).length / span

        twist = math.degrees(previous_n.angle(normal, 0.0)) if previous_n else 0.0
        frames.append(
            {
                "index": index,
                "point_world_mm": [point.x, point.y, point.z],
                "T": [tangent.x, tangent.y, tangent.z],
                "N": [normal.x, normal.y, normal.z],
                "B": [binormal.x, binormal.y, binormal.z],
                "curvature_1_per_mm": curvature,
                "twist_deg_from_previous": twist,
            }
        )
        previous_n = normal
        previous_t = tangent

    return frames


def recompute_frame_metrics(frames):
    closed_loop = (
        len(frames) > 3
        and (Vector(frames[0]["point_world_mm"]) - Vector(frames[-1]["point_world_mm"])).length < 1.5
    )
    for index, frame in enumerate(frames):
        point = Vector(frame["point_world_mm"])
        tangent = Vector(frame["T"]).normalized()
        normal = Vector(frame["N"]).normalized()
        binormal = safe_normalize(tangent.cross(normal), Vector((0.0, 0.0, 1.0)))
        normal = safe_normalize(binormal.cross(tangent), normal)
        if index > 0:
            previous_normal = Vector(frames[index - 1]["N"]).normalized()
            if normal.dot(previous_normal) < 0.0:
                normal.negate()
                binormal = safe_normalize(tangent.cross(normal), binormal)
        frame["N"] = [normal.x, normal.y, normal.z]
        frame["B"] = [binormal.x, binormal.y, binormal.z]

        if closed_loop or 0 < index < len(frames) - 1:
            previous_index = index - 1 if index > 0 else len(frames) - 2
            next_index = index + 1 if index < len(frames) - 1 else 1
            previous_point = Vector(frames[previous_index]["point_world_mm"])
            next_point = Vector(frames[next_index]["point_world_mm"])
            prev_t = safe_normalize(point - previous_point, tangent)
            next_t = safe_normalize(next_point - point, tangent)
            span = max((next_point - previous_point).length, 1e-6)
            frame["curvature_1_per_mm"] = (next_t - prev_t).length / span
        else:
            frame["curvature_1_per_mm"] = 0.0

        if index == 0:
            frame["twist_deg_from_previous"] = 0.0
        else:
            previous_normal = Vector(frames[index - 1]["N"]).normalized()
            frame["twist_deg_from_previous"] = math.degrees(previous_normal.angle(normal, 0.0))


def close_loop_frame_twist(frames):
    if len(frames) < 5:
        return frames, 0.0
    if (Vector(frames[0]["point_world_mm"]) - Vector(frames[-1]["point_world_mm"])).length >= 1.5:
        return frames, 0.0

    unique_frames = [dict(frame) for frame in frames[:-1]]
    first_tangent = Vector(unique_frames[0]["T"]).normalized()
    first_normal = Vector(unique_frames[0]["N"]).normalized()
    last_normal = Vector(unique_frames[-1]["N"]).normalized()
    last_at_seam = last_normal - first_tangent * last_normal.dot(first_tangent)
    last_at_seam = safe_normalize(last_at_seam, first_normal)
    residual_angle = math.atan2(
        first_tangent.dot(last_at_seam.cross(first_normal)),
        max(-1.0, min(1.0, last_at_seam.dot(first_normal))),
    )

    denominator = max(len(unique_frames) - 1, 1)
    for index, frame in enumerate(unique_frames):
        tangent = Vector(frame["T"]).normalized()
        normal = Vector(frame["N"]).normalized()
        normal.rotate(Quaternion(tangent, residual_angle * index / denominator))
        normal = safe_normalize(normal - tangent * normal.dot(tangent), normal)
        binormal = safe_normalize(tangent.cross(normal), Vector((0.0, 0.0, 1.0)))
        frame["N"] = [normal.x, normal.y, normal.z]
        frame["B"] = [binormal.x, binormal.y, binormal.z]

    closing_frame = dict(unique_frames[0])
    closing_frame["index"] = frames[-1]["index"]
    closing_frame["point_world_mm"] = list(frames[-1]["point_world_mm"])
    unique_frames.append(closing_frame)
    return unique_frames, math.degrees(residual_angle)


def smooth_frame_normals(frames, passes):
    if len(frames) < 5:
        recompute_frame_metrics(frames)
        return frames

    closed_loop = (
        (Vector(frames[0]["point_world_mm"]) - Vector(frames[-1]["point_world_mm"])).length < 1.5
    )
    source_frames = frames[:-1] if closed_loop else frames
    smoothed = [dict(frame) for frame in source_frames]
    for _ in range(passes):
        next_frames = [dict(frame) for frame in smoothed]
        indices = range(len(smoothed)) if closed_loop else range(1, len(smoothed) - 1)
        for index in indices:
            tangent = Vector(smoothed[index]["T"]).normalized()
            current = Vector(smoothed[index]["N"]).normalized()
            previous = Vector(smoothed[(index - 1) % len(smoothed)]["N"]).normalized()
            following = Vector(smoothed[(index + 1) % len(smoothed)]["N"]).normalized()

            if previous.dot(current) < 0.0:
                previous.negate()
            if following.dot(current) < 0.0:
                following.negate()

            averaged = current * (1.0 - FRAME_SMOOTHING_WEIGHT) + (previous + following) * (FRAME_SMOOTHING_WEIGHT * 0.5)
            averaged = averaged - tangent * averaged.dot(tangent)
            averaged = safe_normalize(averaged, current)
            next_frames[index]["N"] = [averaged.x, averaged.y, averaged.z]
        smoothed = next_frames

    if closed_loop:
        closing_frame = dict(smoothed[0])
        closing_frame["index"] = frames[-1]["index"]
        closing_frame["point_world_mm"] = list(frames[-1]["point_world_mm"])
        smoothed.append(closing_frame)

    recompute_frame_metrics(smoothed)
    return smoothed


def create_debug(frames, collection):
    remove_existing_object(DEBUG_OBJECT_NAME)
    vertices = []
    edges = []
    for frame in frames[::FRAME_STEP]:
        point = Vector(frame["point_world_mm"])
        normal = Vector(frame["N"])
        binormal = Vector(frame["B"])
        base = len(vertices)
        vertices.extend([point, point + normal * FRAME_SIZE, point, point + binormal * FRAME_SIZE])
        edges.extend([(base, base + 1), (base + 2, base + 3)])

    mesh = bpy.data.meshes.new(f"{DEBUG_OBJECT_NAME}_MESH")
    mesh.from_pydata(vertices, edges, [])
    mesh.update()
    obj = bpy.data.objects.new(DEBUG_OBJECT_NAME, mesh)
    obj.show_name = False
    obj["role"] = "Debug orientation frames: N and B markers along P(s)."
    collection.objects.link(obj)


def main():
    project_root = get_project_root()
    apply_autosize_config(project_root)
    input_path, points, front_facing = read_points(project_root)
    frames = build_frames(points, front_facing)
    frames, loop_twist_correction_deg = close_loop_frame_twist(frames)
    frames = smooth_frame_normals(frames, FRAME_SMOOTHING_PASSES)
    create_debug(frames, get_debug_collection())

    output_path = project_root / "output" / "debug" / target_output_name(project_root, "orientation_frames")
    output_path.write_text(
        json.dumps(
            {
                "source": "ANAMORPHIC_LAMP scripts/05_orientation_frames.py",
                "input_path": str(input_path),
                "frame_count": len(frames),
                "twist_length_for_90_deg_mm": TWIST_LENGTH_FOR_90_DEG_MM,
                "front_facing_guided": True,
                "frame_smoothing_passes": FRAME_SMOOTHING_PASSES,
                "frame_smoothing_weight": FRAME_SMOOTHING_WEIGHT,
                "loop_twist_correction_deg": loop_twist_correction_deg,
                "frames": frames,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("STEP 05 - ORIENTATION FRAMES")
    print(f"Frames: {len(frames)}")
    print(f"Output: {output_path}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
