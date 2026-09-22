import json
import math
from collections import defaultdict, deque
from pathlib import Path

import bpy
from mathutils import Vector
from PIL import Image

from al_config import get_target_image_name, load_autosize_config, nested_get, target_output_name

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
DEBUG_OBJECT_NAME = "AL_CONTINUOUS_PATH"

TARGET_WIDTH_MM = 260.0
TARGET_Z_CENTER = 160.0
TARGET_X_SCALE = 0.96
TARGET_Z_SCALE = 0.96
RESAMPLE_STEP_MM = 1.6
SIMPLIFY_EPSILON_MM = 1.4
CURVE_BEVEL_DEPTH = 0.9
CAMERA_Y = -1050.0
CAMERA_Z = 175.0
TARGET_PLANE_Y = 0.0
MAX_SCULPTURAL_DEPTH = 96.0
LAMP_WIDTH_MM = 320.0
LAMP_HEIGHT_MM = 320.0
SMOOTHING_PASSES = 3
CHAIKIN_PASSES = 2
PATH_MODE = "skeleton_branch_single_profile"
FILL_ROW_STEP_PX = 24
FILL_MIN_RUN_PX = 10
FLOW_ROW_SPACING_MM = 5.5
FLOW_SAMPLE_STEP_MM = 3.0
FLOW_SIDE_MARGIN_MM = 16.0
FLOW_VERTICAL_MARGIN_MM = 8.0
FLOW_WAVE_AMPLITUDE_MM = 1.0
LED_WIDTH_MM = 10.0
LED_MASK_FIT_RADIUS_MM = LED_WIDTH_MM * 0.5
LED_MASK_FIT_MIN_FRACTION = 0.36
LEFT_COMPONENT_RESTORE_MIN_AREA_PX = 900
LEFT_COMPONENT_RESTORE_MIN_MASK_FIT = 0.24
LEFT_COMPONENT_RESTORE_FRONTNESS = 0.58
LEFT_COMPONENT_RESTORE_MARGIN_LED_WIDTHS = 1.0
PATCH_ROW_SPACING_MM = 4.0
PATCH_MIN_RUN_MM = 6.0
PATCH_CONNECTOR_SAMPLES = 36
PATCH_ENTRY_MARGIN_MM = 2.0
CENTERLINE_MIN_STROKE_PX = 5
CENTERLINE_MIN_STROKE_MM = 20.0
CENTERLINE_MAX_STROKES = 9
CENTERLINE_CONNECTOR_SAMPLES = 72
CENTERLINE_DEPTH_LANES_MM = (-92.0, -64.0, -36.0, -12.0, 16.0, 44.0, 72.0, 96.0)
CENTERLINE_CHAIKIN_PASSES = 5
CENTERLINE_CONNECTOR_ESCAPE_MARGIN_MM = 60.0
CENTERLINE_BACKSTAGE_CONNECTOR_SAMPLES = 96
CENTERLINE_BACKSTAGE_SIDE_SWAY_MM = 90.0
CENTERLINE_BACKSTAGE_VERTICAL_SWAY_MM = 85.0
CENTERLINE_BACKSTAGE_DEPTH_BIAS = 0.86
CENTERLINE_BACKSTAGE_DEPTH_SWING = 0.16
CENTERLINE_BACKSTAGE_TANGLE_LOOPS = 3
CLOSED_LOOP_PATH = True
DEPTH_CLEARANCE_MM = 28.0
DEPTH_CLEARANCE_SKIP_NEIGHBORS = 70
DEPTH_CLEARANCE_SOLVER_PASSES = 5
POST_DEPTH_CLEARANCE_MM = 28.0
POST_DEPTH_CLEARANCE_SOLVER_PASSES = 12
POST_DEPTH_CLEARANCE_CYCLES = 3
POST_DEPTH_CLEARANCE_PUSH = 0.32
POST_DEPTH_MAX_STEP_MM = 5.0
FINAL_GEOMETRY_SMOOTHING_PASSES = 8
FINAL_GEOMETRY_SMOOTHING_WEIGHT = 0.22
SINUOUS_LOOP_SMOOTHING_PASSES = 9
SINUOUS_VISIBLE_SMOOTHING_WEIGHT = 0.055
SINUOUS_HIDDEN_SMOOTHING_WEIGHT = 0.24
SINUOUS_DEPTH_SMOOTHING_WEIGHT = 0.30
CURVATURE_SPIKE_SMOOTHING_PASSES = 5
CURVATURE_SPIKE_SMOOTHING_WEIGHT = 0.48
FINAL_LOOP_CLEARANCE_CYCLES = 0


def apply_autosize_config(project_root):
    global TARGET_WIDTH_MM, TARGET_Z_CENTER, TARGET_X_SCALE, TARGET_Z_SCALE
    global CAMERA_Y, CAMERA_Z, MAX_SCULPTURAL_DEPTH, LAMP_WIDTH_MM, LAMP_HEIGHT_MM
    global LED_WIDTH_MM, LED_MASK_FIT_RADIUS_MM
    global CENTERLINE_MIN_STROKE_MM, CENTERLINE_MAX_STROKES, CENTERLINE_DEPTH_LANES_MM
    global CENTERLINE_CONNECTOR_ESCAPE_MARGIN_MM, CENTERLINE_BACKSTAGE_CONNECTOR_SAMPLES
    global CENTERLINE_BACKSTAGE_SIDE_SWAY_MM, CENTERLINE_BACKSTAGE_VERTICAL_SWAY_MM
    global CENTERLINE_BACKSTAGE_DEPTH_BIAS, CENTERLINE_BACKSTAGE_DEPTH_SWING
    global CENTERLINE_BACKSTAGE_TANGLE_LOOPS
    global CLOSED_LOOP_PATH

    config = load_autosize_config(project_root)
    TARGET_WIDTH_MM = float(nested_get(config, ("target", "width_mm"), TARGET_WIDTH_MM))
    TARGET_Z_CENTER = float(nested_get(config, ("target", "z_center_mm"), TARGET_Z_CENTER))
    TARGET_X_SCALE = float(nested_get(config, ("target", "x_scale"), TARGET_X_SCALE))
    TARGET_Z_SCALE = float(nested_get(config, ("target", "z_scale"), TARGET_Z_SCALE))
    CAMERA_Y = -float(nested_get(config, ("camera", "distance_mm"), abs(CAMERA_Y)))
    CAMERA_Z = float(nested_get(config, ("camera", "height_mm"), CAMERA_Z))
    MAX_SCULPTURAL_DEPTH = float(
        nested_get(config, ("lamp", "max_sculptural_depth_mm"), MAX_SCULPTURAL_DEPTH)
    )
    LAMP_WIDTH_MM = float(nested_get(config, ("lamp", "width_mm"), LAMP_WIDTH_MM))
    LAMP_HEIGHT_MM = float(nested_get(config, ("lamp", "height_mm"), LAMP_HEIGHT_MM))
    LED_WIDTH_MM = float(nested_get(config, ("led", "width_mm"), LED_WIDTH_MM))
    LED_MASK_FIT_RADIUS_MM = LED_WIDTH_MM * 0.5
    CENTERLINE_MIN_STROKE_MM = float(
        nested_get(config, ("planner", "centerline_min_stroke_mm"), CENTERLINE_MIN_STROKE_MM)
    )
    CENTERLINE_MAX_STROKES = int(
        nested_get(config, ("planner", "centerline_max_strokes"), CENTERLINE_MAX_STROKES)
    )
    CENTERLINE_DEPTH_LANES_MM = tuple(
        float(value)
        for value in nested_get(config, ("lamp", "depth_lanes_mm"), CENTERLINE_DEPTH_LANES_MM)
    )
    CENTERLINE_CONNECTOR_ESCAPE_MARGIN_MM = float(
        nested_get(
            config,
            ("planner", "connector_escape_margin_mm"),
            CENTERLINE_CONNECTOR_ESCAPE_MARGIN_MM,
        )
    )
    CENTERLINE_BACKSTAGE_CONNECTOR_SAMPLES = int(
        nested_get(
            config,
            ("planner", "backstage_connector_samples"),
            CENTERLINE_BACKSTAGE_CONNECTOR_SAMPLES,
        )
    )
    CENTERLINE_BACKSTAGE_SIDE_SWAY_MM = float(
        nested_get(
            config,
            ("planner", "backstage_side_sway_mm"),
            CENTERLINE_BACKSTAGE_SIDE_SWAY_MM,
        )
    )
    CENTERLINE_BACKSTAGE_VERTICAL_SWAY_MM = float(
        nested_get(
            config,
            ("planner", "backstage_vertical_sway_mm"),
            CENTERLINE_BACKSTAGE_VERTICAL_SWAY_MM,
        )
    )
    CENTERLINE_BACKSTAGE_DEPTH_BIAS = float(
        nested_get(
            config,
            ("planner", "backstage_depth_bias"),
            CENTERLINE_BACKSTAGE_DEPTH_BIAS,
        )
    )
    CENTERLINE_BACKSTAGE_DEPTH_SWING = float(
        nested_get(
            config,
            ("planner", "backstage_depth_swing"),
            CENTERLINE_BACKSTAGE_DEPTH_SWING,
        )
    )
    CENTERLINE_BACKSTAGE_TANGLE_LOOPS = int(
        nested_get(
            config,
            ("planner", "backstage_tangle_loops"),
            CENTERLINE_BACKSTAGE_TANGLE_LOOPS,
        )
    )
    CLOSED_LOOP_PATH = bool(nested_get(config, ("planner", "closed_loop"), CLOSED_LOOP_PATH))


def get_project_root():
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender file before running project scripts.")
    blend_dir = Path(bpy.data.filepath).resolve().parent
    return blend_dir.parent if blend_dir.name == "blender" else blend_dir


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


def load_binary_target(project_root):
    image_path = project_root / "input" / get_target_image_name(project_root)
    if not image_path.exists():
        raise FileNotFoundError(f"Missing target image: {image_path}")

    image = Image.open(image_path).convert("L")
    width, height = image.size
    pixels = image.load()
    binary = [[pixels[x, y] > 140 for x in range(width)] for y in range(height)]
    return image_path, width, height, binary


def neighbors8(x, y):
    return (
        (x, y - 1),
        (x + 1, y - 1),
        (x + 1, y),
        (x + 1, y + 1),
        (x, y + 1),
        (x - 1, y + 1),
        (x - 1, y),
        (x - 1, y - 1),
    )


def zhang_suen_thinning(binary):
    height = len(binary)
    width = len(binary[0])
    image = [[bool(binary[y][x]) for x in range(width)] for y in range(height)]
    changed = True

    def pixel(x, y):
        if x < 0 or y < 0 or x >= width or y >= height:
            return False
        return image[y][x]

    while changed:
        changed = False
        for sub_iteration in (0, 1):
            to_remove = []
            for y in range(1, height - 1):
                for x in range(1, width - 1):
                    if not image[y][x]:
                        continue
                    p = [pixel(nx, ny) for nx, ny in neighbors8(x, y)]
                    count = sum(p)
                    transitions = sum((not p[i]) and p[(i + 1) % 8] for i in range(8))
                    if count < 2 or count > 6 or transitions != 1:
                        continue
                    if sub_iteration == 0:
                        if p[0] and p[2] and p[4]:
                            continue
                        if p[2] and p[4] and p[6]:
                            continue
                    else:
                        if p[0] and p[2] and p[6]:
                            continue
                        if p[0] and p[4] and p[6]:
                            continue
                    to_remove.append((x, y))
            if to_remove:
                changed = True
                for x, y in to_remove:
                    image[y][x] = False
    return image


def downsample_binary(binary, factor=3):
    height = len(binary)
    width = len(binary[0])
    new_w = width // factor
    new_h = height // factor
    result = []
    for y in range(new_h):
        row = []
        for x in range(new_w):
            count = 0
            for yy in range(factor):
                for xx in range(factor):
                    if binary[y * factor + yy][x * factor + xx]:
                        count += 1
            row.append(count >= (factor * factor * 0.28))
        result.append(row)
    return result, factor


def skeleton_graph(skeleton):
    height = len(skeleton)
    width = len(skeleton[0])
    nodes = {(x, y) for y in range(height) for x in range(width) if skeleton[y][x]}
    graph = defaultdict(list)
    for x, y in nodes:
        for nx, ny in neighbors8(x, y):
            if (nx, ny) in nodes:
                graph[(x, y)].append((nx, ny))
    return nodes, graph


def connected_components(nodes, graph):
    unseen = set(nodes)
    components = []
    while unseen:
        start = unseen.pop()
        queue = deque([start])
        component = {start}
        while queue:
            node = queue.popleft()
            for neighbor in graph[node]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    return sorted(components, key=len, reverse=True)


def farthest_node(component, graph, start):
    queue = deque([(start, 0)])
    seen = {start}
    farthest = start
    distance = 0
    while queue:
        node, dist = queue.popleft()
        if dist > distance:
            farthest = node
            distance = dist
        for neighbor in graph[node]:
            if neighbor in component and neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, dist + 1))
    return farthest


def ordered_component_path(component, graph):
    endpoints = [node for node in component if len([n for n in graph[node] if n in component]) <= 1]
    if endpoints:
        start = min(endpoints, key=lambda node: (node[0], node[1]))
    else:
        start = min(component, key=lambda node: (node[0], node[1]))

    start = farthest_node(component, graph, start)
    visited = set()
    path = []
    current = start
    previous = None

    while current is not None:
        path.append(current)
        visited.add(current)
        candidates = [n for n in graph[current] if n in component and n not in visited]
        if not candidates:
            remaining = list(component - visited)
            if not remaining:
                break
            current = min(remaining, key=lambda node: pixel_distance(path[-1], node))
            previous = None
            continue
        if previous is None:
            current_next = min(candidates, key=lambda node: (node[0], node[1]))
        else:
            incoming = (current[0] - previous[0], current[1] - previous[1])
            current_next = min(candidates, key=lambda node: turn_cost(incoming, current, node))
        previous, current = current, current_next
    return path


def pixel_distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def turn_cost(incoming, current, candidate):
    outgoing = (candidate[0] - current[0], candidate[1] - current[1])
    dot = incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
    length = math.hypot(*incoming) * math.hypot(*outgoing)
    angle_cost = 1.0 - (dot / length if length else 1.0)
    return angle_cost + pixel_distance(current, candidate) * 0.02


def bridge_components(paths):
    if not paths:
        return []
    ordered = [paths[0]]
    remaining = paths[1:]
    while remaining:
        end = ordered[-1][-1]
        best_index = min(
            range(len(remaining)),
            key=lambda i: min(pixel_distance(end, remaining[i][0]), pixel_distance(end, remaining[i][-1])),
        )
        candidate = remaining.pop(best_index)
        if pixel_distance(end, candidate[-1]) < pixel_distance(end, candidate[0]):
            candidate = list(reversed(candidate))
        ordered.append(candidate)

    combined = []
    for path in ordered:
        if combined and pixel_distance(combined[-1], path[0]) > 8:
            combined.extend(interpolate_pixels(combined[-1], path[0], 12))
        combined.extend(path)
    return combined


def skeleton_component_strokes(components, graph):
    strokes = []
    visited_edges = set()

    def edge_key(a, b):
        return tuple(sorted((a, b)))

    def component_path_from_loop(component):
        start = min(component, key=lambda node: (node[0], node[1]))
        path = [start]
        previous = None
        current = start
        while True:
            candidates = [n for n in graph[current] if n in component and n != previous]
            if not candidates:
                break
            if previous is None:
                next_node = min(candidates, key=lambda node: (node[0], node[1]))
            else:
                incoming = (current[0] - previous[0], current[1] - previous[1])
                next_node = min(candidates, key=lambda node: turn_cost(incoming, current, node))
            if next_node == start:
                break
            if next_node in path:
                break
            path.append(next_node)
            previous, current = current, next_node
        return path

    for component in components:
        important = {
            node
            for node in component
            if len([neighbor for neighbor in graph[node] if neighbor in component]) != 2
        }

        if not important:
            loop_path = component_path_from_loop(component)
            if len(loop_path) >= CENTERLINE_MIN_STROKE_PX:
                strokes.append(loop_path)
            continue

        starts = sorted(important, key=lambda node: (node[0], node[1]))
        for start in starts:
            neighbors = sorted(
                [neighbor for neighbor in graph[start] if neighbor in component],
                key=lambda node: (node[0], node[1]),
            )
            for first in neighbors:
                key = edge_key(start, first)
                if key in visited_edges:
                    continue

                path = [start, first]
                visited_edges.add(key)
                previous = start
                current = first

                while current not in important:
                    next_candidates = [n for n in graph[current] if n in component and n != previous]
                    if not next_candidates:
                        break
                    if len(next_candidates) == 1:
                        next_node = next_candidates[0]
                    else:
                        incoming = (current[0] - previous[0], current[1] - previous[1])
                        next_node = min(next_candidates, key=lambda node: turn_cost(incoming, current, node))
                    next_key = edge_key(current, next_node)
                    if next_key in visited_edges:
                        break
                    visited_edges.add(next_key)
                    path.append(next_node)
                    previous, current = current, next_node

                if len(path) >= CENTERLINE_MIN_STROKE_PX:
                    strokes.append(path)

    return strokes


def stroke_front_points(pixel_stroke, width, height, factor):
    return pixel_path_to_front_mm(pixel_stroke, width, height, factor)


def order_centerline_strokes(strokes, width, height, factor):
    if not strokes:
        return []

    front_strokes = []
    for stroke in strokes:
        points = stroke_front_points(stroke, width, height, factor)
        if len(points) < 2:
            continue
        length = sum(math.dist(points[index - 1], points[index]) for index in range(1, len(points)))
        if length < CENTERLINE_MIN_STROKE_MM:
            continue
        center = (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
        front_strokes.append({"points": points, "center": center, "length": length})

    if not front_strokes:
        return []
    if len(front_strokes) > CENTERLINE_MAX_STROKES:
        front_strokes = sorted(front_strokes, key=lambda stroke: stroke["length"], reverse=True)[
            :CENTERLINE_MAX_STROKES
        ]

    remaining = list(front_strokes)
    current = min(remaining, key=lambda stroke: (stroke["center"][0], -stroke["center"][1]))
    remaining.remove(current)
    ordered = [current]
    end = current["points"][-1]
    previous_direction = (
        end[0] - current["points"][-2][0],
        end[1] - current["points"][-2][1],
    )

    while remaining:
        best_index = 0
        best_reverse = False
        best_cost = None
        for index, stroke in enumerate(remaining):
            for reverse in (False, True):
                points = list(reversed(stroke["points"])) if reverse else stroke["points"]
                start = points[0]
                direction = (
                    points[1][0] - points[0][0],
                    points[1][1] - points[0][1],
                )
                distance = math.dist(end, start)
                jump_penalty = max(0.0, distance - 20.0) * 0.65
                dz_penalty = abs(start[1] - end[1]) * 0.20
                prev_len = math.hypot(*previous_direction)
                dir_len = math.hypot(*direction)
                turn_penalty = 0.0
                if prev_len > 1e-6 and dir_len > 1e-6:
                    dot = (
                        previous_direction[0] * direction[0]
                        + previous_direction[1] * direction[1]
                    ) / (prev_len * dir_len)
                    turn_penalty = (1.0 - max(-1.0, min(1.0, dot))) * 18.0
                cost = distance + jump_penalty + dz_penalty + turn_penalty - stroke["length"] * 0.08
                if best_cost is None or cost < best_cost:
                    best_cost = cost
                    best_index = index
                    best_reverse = reverse

        chosen = remaining.pop(best_index)
        if best_reverse:
            chosen = {
                "points": list(reversed(chosen["points"])),
                "center": chosen["center"],
                "length": chosen["length"],
            }
        ordered.append(chosen)
        if len(chosen["points"]) >= 2:
            previous_direction = (
                chosen["points"][-1][0] - chosen["points"][-2][0],
                chosen["points"][-1][1] - chosen["points"][-2][1],
            )
        end = chosen["points"][-1]

    return ordered


def stroke_depth_lane(index):
    return CENTERLINE_DEPTH_LANES_MM[index % len(CENTERLINE_DEPTH_LANES_MM)]


def visible_stroke_depth(base_depth, stroke_index, point_index, point_count):
    if point_count <= 1:
        return base_depth
    u = point_index / (point_count - 1)
    broad = math.sin(u * math.tau * 0.72 + stroke_index * 1.7)
    fine = math.sin(u * math.tau * 1.65 + stroke_index * 0.55)
    depth = base_depth + broad * MAX_SCULPTURAL_DEPTH * 0.12 + fine * MAX_SCULPTURAL_DEPTH * 0.035
    return max(-MAX_SCULPTURAL_DEPTH, min(MAX_SCULPTURAL_DEPTH, depth))


def smooth_depth_values(depths, weights):
    if len(depths) < 5:
        return depths
    result = list(depths)
    next_values = list(result)
    for index in range(1, len(result) - 1):
        if weights[index] >= LED_MASK_FIT_MIN_FRACTION:
            keep = 0.72
        else:
            keep = 0.52
        next_values[index] = (
            result[index] * keep
            + (result[index - 1] + result[index + 1]) * ((1.0 - keep) * 0.5)
        )
    return [max(-MAX_SCULPTURAL_DEPTH, min(MAX_SCULPTURAL_DEPTH, value)) for value in next_values]


def solve_depth_clearance(front_points, fractions, depths):
    if len(front_points) < 4:
        return depths
    result = list(depths)
    for _ in range(DEPTH_CLEARANCE_SOLVER_PASSES):
        for i in range(len(front_points)):
            xi, zi = front_points[i]
            for j in range(i + DEPTH_CLEARANCE_SKIP_NEIGHBORS, len(front_points)):
                if i < DEPTH_CLEARANCE_SKIP_NEIGHBORS and j > len(front_points) - DEPTH_CLEARANCE_SKIP_NEIGHBORS:
                    continue
                xj, zj = front_points[j]
                front_distance = math.hypot(xi - xj, zi - zj)
                if front_distance >= DEPTH_CLEARANCE_MM:
                    continue
                desired_depth_delta = math.sqrt(max(0.0, DEPTH_CLEARANCE_MM * DEPTH_CLEARANCE_MM - front_distance * front_distance))
                current_delta = result[j] - result[i]
                if abs(current_delta) >= desired_depth_delta:
                    continue
                push = (desired_depth_delta - abs(current_delta)) * 0.28
                direction = 1.0 if current_delta >= 0.0 else -1.0
                result[i] = max(-MAX_SCULPTURAL_DEPTH, min(MAX_SCULPTURAL_DEPTH, result[i] - push * direction))
                result[j] = max(-MAX_SCULPTURAL_DEPTH, min(MAX_SCULPTURAL_DEPTH, result[j] + push * direction))
        result = smooth_depth_values(result, fractions)
    return result


def clamp_value(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def catmull_value(v0, v1, v2, v3, t):
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        2.0 * v1
        + (-v0 + v2) * t
        + (2.0 * v0 - 5.0 * v1 + 4.0 * v2 - v3) * t2
        + (-v0 + 3.0 * v1 - 3.0 * v2 + v3) * t3
    )


def backstage_depth_value(connector_index, phase):
    lane_offsets = (-0.24, -0.08, 0.06, 0.16)
    base_fraction = clamp_value(
        CENTERLINE_BACKSTAGE_DEPTH_BIAS + lane_offsets[connector_index % len(lane_offsets)],
        0.46,
        0.96,
    )
    base = MAX_SCULPTURAL_DEPTH * base_fraction
    swing = MAX_SCULPTURAL_DEPTH * CENTERLINE_BACKSTAGE_DEPTH_SWING
    wave = math.sin(phase * math.tau * 1.25 + connector_index * 1.73) * swing
    return clamp_value(base + wave, MAX_SCULPTURAL_DEPTH * 0.42, MAX_SCULPTURAL_DEPTH * 0.98)


def blend_depth_toward_backstage(endpoint_depth, backstage_depth, amount):
    return endpoint_depth * (1.0 - amount) + backstage_depth * amount


def sample_backstage_route(waypoints, samples):
    if len(waypoints) < 2:
        return []

    segment_count = len(waypoints) - 1
    samples_per_segment = max(6, int(math.ceil(samples / max(segment_count, 1))))
    result = []

    for segment_index in range(segment_count):
        p0 = waypoints[max(0, segment_index - 1)]
        p1 = waypoints[segment_index]
        p2 = waypoints[segment_index + 1]
        p3 = waypoints[min(len(waypoints) - 1, segment_index + 2)]
        for sample_index in range(1, samples_per_segment + 1):
            t = sample_index / samples_per_segment
            x = catmull_value(p0[0], p1[0], p2[0], p3[0], t)
            z = catmull_value(p0[1], p1[1], p2[1], p3[1], t)
            depth = catmull_value(p0[2], p1[2], p2[2], p3[2], t)
            result.append(
                (
                    x,
                    z,
                    clamp_value(depth, -MAX_SCULPTURAL_DEPTH, MAX_SCULPTURAL_DEPTH),
                )
            )

    return result


def clamp_target_point_to_lamp_bounds(x_target, z_target, depth):
    denominator = TARGET_PLANE_Y - CAMERA_Y
    factor = (depth - CAMERA_Y) / denominator if abs(denominator) > 1e-6 else 1.0
    if factor <= 1e-6:
        return x_target, z_target

    x_limit = (LAMP_WIDTH_MM * 0.5 * 0.94) / factor
    z_lower = CAMERA_Z + (0.0 - CAMERA_Z) / factor
    z_upper = CAMERA_Z + (LAMP_HEIGHT_MM - CAMERA_Z) / factor
    return (
        clamp_value(x_target, -x_limit, x_limit),
        clamp_value(z_target, z_lower, z_upper),
    )


def sample_tangle_cloud_connector(
    start,
    end,
    start_depth,
    end_depth,
    connector_index,
    x_min,
    x_max,
    z_min,
    z_max,
):
    front_width = max(x_max - x_min, 1.0)
    front_height = max(z_max - z_min, 1.0)
    center_x = (x_min + x_max) * 0.5
    center_z = (z_min + z_max) * 0.5
    radius_x = min(max(CENTERLINE_BACKSTAGE_SIDE_SWAY_MM, front_width * 0.28), front_width * 0.48)
    radius_z = min(max(CENTERLINE_BACKSTAGE_VERTICAL_SWAY_MM, front_height * 0.44), front_height * 0.66)
    loop_count = max(1.5, CENTERLINE_BACKSTAGE_TANGLE_LOOPS + 0.5 * (connector_index % 2))
    phase = connector_index * 0.83
    cloud_offsets = (
        (-0.42 * front_width, -0.18 * front_height),
        (0.00 * front_width, 0.30 * front_height),
        (0.42 * front_width, -0.12 * front_height),
    )
    start_lobe = connector_index % len(cloud_offsets)
    end_lobe = (connector_index + 1 + (connector_index % 2)) % len(cloud_offsets)
    start_center = (
        center_x + cloud_offsets[start_lobe][0],
        center_z + cloud_offsets[start_lobe][1],
    )
    end_center = (
        center_x + cloud_offsets[end_lobe][0],
        center_z + cloud_offsets[end_lobe][1],
    )
    cross_bias = -1.0 if connector_index % 2 else 1.0
    points = []

    for sample_index in range(1, CENTERLINE_BACKSTAGE_CONNECTOR_SAMPLES + 1):
        t = sample_index / CENTERLINE_BACKSTAGE_CONNECTOR_SAMPLES
        envelope = math.sin(math.pi * t)
        envelope = max(0.0, envelope) ** 0.72
        base_x = start[0] * (1.0 - t) + end[0] * t
        base_z = start[1] * (1.0 - t) + end[1] * t
        base_depth = start_depth * (1.0 - t) + end_depth * t
        theta = t * math.tau * loop_count + phase
        lobe_x = start_center[0] * (1.0 - t) + end_center[0] * t
        lobe_z = start_center[1] * (1.0 - t) + end_center[1] * t
        lobe_x += math.sin(math.pi * t) * cross_bias * radius_x * 0.34
        lobe_z += math.sin(math.tau * t + phase) * radius_z * 0.20
        knot_x = (
            lobe_x
            + math.sin(theta) * radius_x * 0.42
            + math.sin(theta * 2.0 + phase * 0.7) * radius_x * 0.16
        )
        knot_z = (
            lobe_z
            + math.sin(theta * 2.0 + math.pi * 0.25) * radius_z * 0.38
            + math.cos(theta * 0.75 + phase) * radius_z * 0.18
        )
        braid = math.sin(theta * 3.0 + connector_index)
        rear_depth = backstage_depth_value(connector_index, t)
        rear_depth += braid * MAX_SCULPTURAL_DEPTH * CENTERLINE_BACKSTAGE_DEPTH_SWING * 0.48
        depth = blend_depth_toward_backstage(base_depth, rear_depth, envelope)
        x = base_x * (1.0 - envelope) + knot_x * envelope
        z = base_z * (1.0 - envelope) + knot_z * envelope
        x, z = clamp_target_point_to_lamp_bounds(x, z, depth)
        points.append((x, z, clamp_value(depth, -MAX_SCULPTURAL_DEPTH, MAX_SCULPTURAL_DEPTH)))

    return points


def add_centerline_connector(
    points,
    fractions,
    depths,
    start,
    end,
    start_depth,
    end_depth,
    connector_index,
    x_min,
    x_max,
    z_min,
    z_max,
):
    if math.dist(start, end) < 1e-6:
        return
    # Hidden connectors now form a compact rear tangle cloud rather than large
    # perimeter arcs. Their LED face remains turned away from the camera.
    connector_points = sample_tangle_cloud_connector(
        start,
        end,
        start_depth,
        end_depth,
        connector_index,
        x_min,
        x_max,
        z_min,
        z_max,
    )
    for x, z, depth in connector_points:
        points.append((x, z))
        fractions.append(0.0)
        depths.append(depth)


def centerline_path_to_front_mm(binary, width, height, factor, components, graph):
    component_strokes = [ordered_component_path(component, graph) for component in components]
    component_strokes = [stroke for stroke in component_strokes if len(stroke) >= CENTERLINE_MIN_STROKE_PX]
    raw_strokes = component_strokes or skeleton_component_strokes(components, graph)
    strokes = order_centerline_strokes(raw_strokes, width, height, factor)
    x_min, x_max, z_min, z_max = white_bounds_front_mm(binary, width, height)
    points = []
    fractions = []
    depths = []

    for index, stroke in enumerate(strokes):
        stroke_points = stroke["points"]
        lane_depth = stroke_depth_lane(index)
        if points:
            add_centerline_connector(
                points,
                fractions,
                depths,
                points[-1],
                stroke_points[0],
                depths[-1],
                lane_depth,
                index,
                x_min,
                x_max,
                z_min,
                z_max,
            )
        else:
            points.append(stroke_points[0])
            fractions.append(0.0)
            depths.append(lane_depth)

        for point_index, point in enumerate(stroke_points):
            points.append(point)
            fractions.append(mask_led_fit_fraction(binary, width, height, point[0], point[1]))
            depths.append(visible_stroke_depth(lane_depth, index, point_index, len(stroke_points)))

    if CLOSED_LOOP_PATH and len(points) > 3:
        add_centerline_connector(
            points,
            fractions,
            depths,
            points[-1],
            points[0],
            depths[-1],
            depths[0],
            len(strokes),
            x_min,
            x_max,
            z_min,
            z_max,
        )

    depths = solve_depth_clearance(points, fractions, depths)
    return points, fractions, depths, len(strokes)


def interpolate_pixels(a, b, steps):
    points = []
    for index in range(1, steps):
        t = index / steps
        points.append((a[0] * (1 - t) + b[0] * t, a[1] * (1 - t) + b[1] * t))
    return points


def pixel_path_to_front_mm(pixel_path, width, height, factor):
    target_height_mm = TARGET_WIDTH_MM * (height / width)
    points = []
    for x_small, y_small in pixel_path:
        x = x_small * factor
        y = y_small * factor
        x_mm = ((x + 0.5) / width - 0.5) * TARGET_WIDTH_MM * TARGET_X_SCALE
        z_mm = (0.5 - (y + 0.5) / height) * target_height_mm * TARGET_Z_SCALE + TARGET_Z_CENTER
        points.append((x_mm, z_mm))
    return points


def pixel_to_front_mm(x, y, width, height):
    target_height_mm = TARGET_WIDTH_MM * (height / width)
    x_mm = ((x + 0.5) / width - 0.5) * TARGET_WIDTH_MM * TARGET_X_SCALE
    z_mm = (0.5 - (y + 0.5) / height) * target_height_mm * TARGET_Z_SCALE + TARGET_Z_CENTER
    return (x_mm, z_mm)


def raster_fill_path_to_front_mm(binary, width, height):
    runs = []
    for y in range(0, height, FILL_ROW_STEP_PX):
        row_runs = []
        x = 0
        while x < width:
            while x < width and not binary[y][x]:
                x += 1
            start = x
            while x < width and binary[y][x]:
                x += 1
            end = x - 1
            if end - start + 1 >= FILL_MIN_RUN_PX:
                row_runs.append((start, end, y))
        if row_runs:
            runs.append(row_runs)

    points = []
    segment_lit_flags = []
    reverse = False
    for row_runs in runs:
        ordered = list(reversed(row_runs)) if reverse else row_runs
        for start, end, y in ordered:
            if reverse:
                start, end = end, start
            points.append(pixel_to_front_mm(start, y, width, height))
            segment_lit_flags.append(False)
            points.append(pixel_to_front_mm(end, y, width, height))
            segment_lit_flags.append(True)
        reverse = not reverse
    return points, segment_lit_flags, sum(len(row) for row in runs)


def front_mm_to_pixel(x_mm, z_mm, width, height):
    target_height_mm = TARGET_WIDTH_MM * (height / width)
    x = ((x_mm / (TARGET_WIDTH_MM * TARGET_X_SCALE)) + 0.5) * width - 0.5
    y = (0.5 - ((z_mm - TARGET_Z_CENTER) / (target_height_mm * TARGET_Z_SCALE))) * height - 0.5
    return x, y


def mask_fill_fraction(binary, width, height, x_mm, z_mm, radius_mm):
    x, y = front_mm_to_pixel(x_mm, z_mm, width, height)
    px_radius = max(2, int(round(radius_mm / TARGET_WIDTH_MM * width)))
    x0 = max(0, int(math.floor(x - px_radius)))
    x1 = min(width - 1, int(math.ceil(x + px_radius)))
    y0 = max(0, int(math.floor(y - px_radius)))
    y1 = min(height - 1, int(math.ceil(y + px_radius)))
    step = max(1, px_radius // 4)
    radius_sq = px_radius * px_radius
    total = 0
    white = 0
    for yy in range(y0, y1 + 1, step):
        dy = yy - y
        for xx in range(x0, x1 + 1, step):
            if (xx - x) * (xx - x) + dy * dy <= radius_sq:
                total += 1
                if binary[yy][xx]:
                    white += 1
    return white / total if total else 0.0


def mask_led_fit(binary, width, height, x_mm, z_mm):
    return (
        mask_fill_fraction(binary, width, height, x_mm, z_mm, LED_MASK_FIT_RADIUS_MM)
        >= LED_MASK_FIT_MIN_FRACTION
    )


def mask_led_fit_fraction(binary, width, height, x_mm, z_mm):
    return mask_fill_fraction(binary, width, height, x_mm, z_mm, LED_MASK_FIT_RADIUS_MM)


def white_bounds_front_mm(binary, width, height):
    xs = []
    zs = []
    for y in range(height):
        for x in range(width):
            if binary[y][x]:
                x_mm, z_mm = pixel_to_front_mm(x, y, width, height)
                xs.append(x_mm)
                zs.append(z_mm)
    if not xs:
        return (-80.0, 80.0, TARGET_Z_CENTER - 40.0, TARGET_Z_CENTER + 40.0)
    return min(xs), max(xs), min(zs), max(zs)


def white_components_with_bounds(binary, width, height, min_area_px):
    seen = [[False for _ in range(width)] for _ in range(height)]
    components = []
    for y in range(height):
        for x in range(width):
            if seen[y][x] or not binary[y][x]:
                continue
            queue = deque([(x, y)])
            seen[y][x] = True
            area = 0
            min_x = max_x = x
            min_y = max_y = y

            while queue:
                cx, cy = queue.popleft()
                area += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in neighbors8(cx, cy):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if seen[ny][nx] or not binary[ny][nx]:
                        continue
                    seen[ny][nx] = True
                    queue.append((nx, ny))

            if area >= min_area_px:
                components.append(
                    {
                        "area_px": area,
                        "bbox_px": [min_x, max_x, min_y, max_y],
                    }
                )

    return sorted(components, key=lambda item: (item["bbox_px"][0], -item["area_px"]))


def component_front_bounds(component, width, height, margin_mm):
    min_x, max_x, min_y, max_y = component["bbox_px"]
    left, top = pixel_to_front_mm(min_x, min_y, width, height)
    right, bottom = pixel_to_front_mm(max_x, max_y, width, height)
    return (
        min(left, right) - margin_mm,
        max(left, right) + margin_mm,
        min(top, bottom) - margin_mm,
        max(top, bottom) + margin_mm,
    )


def restore_left_component_frontness(binary, width, height, front_points, fractions):
    stats = {
        "left_component_frontness_restore_nodes": 0,
        "left_component_frontness_restore_min_mask_fit": LEFT_COMPONENT_RESTORE_MIN_MASK_FIT,
        "left_component_frontness_restore_frontness": LEFT_COMPONENT_RESTORE_FRONTNESS,
    }
    components = white_components_with_bounds(
        binary,
        width,
        height,
        LEFT_COMPONENT_RESTORE_MIN_AREA_PX,
    )
    if not components:
        return fractions, stats

    component = components[0]
    margin_mm = LED_WIDTH_MM * LEFT_COMPONENT_RESTORE_MARGIN_LED_WIDTHS
    x_min, x_max, z_min, z_max = component_front_bounds(component, width, height, margin_mm)
    restored = list(fractions)
    restored_count = 0

    for index, point in enumerate(front_points):
        if index >= len(restored):
            continue
        x, z = point
        if x < x_min or x > x_max or z < z_min or z > z_max:
            continue
        actual_fit = mask_led_fit_fraction(binary, width, height, x, z)
        if actual_fit < LEFT_COMPONENT_RESTORE_MIN_MASK_FIT:
            continue
        previous = max(0.0, min(1.0, restored[index]))
        next_value = min(1.0, max(previous, actual_fit, LEFT_COMPONENT_RESTORE_FRONTNESS))
        if next_value > previous + 1e-6:
            restored[index] = next_value
            restored_count += 1

    stats.update(
        {
            "left_component_frontness_restore_nodes": restored_count,
            "left_component_frontness_restore_area_px": component["area_px"],
            "left_component_frontness_restore_bbox_px": component["bbox_px"],
            "left_component_frontness_restore_margin_mm": margin_mm,
        }
    )
    return restored, stats


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def cubic_bezier(p0, p1, p2, p3, samples):
    points = []
    for index in range(1, samples + 1):
        t = index / samples
        u = 1.0 - t
        x = (
            p0[0] * u * u * u
            + p1[0] * 3.0 * u * u * t
            + p2[0] * 3.0 * u * t * t
            + p3[0] * t * t * t
        )
        z = (
            p0[1] * u * u * u
            + p1[1] * 3.0 * u * u * t
            + p2[1] * 3.0 * u * t * t
            + p3[1] * t * t * t
        )
        points.append((x, z))
    return points


def flowfield_path_to_front_mm(binary, width, height):
    x_min, x_max, z_min, z_max = white_bounds_front_mm(binary, width, height)
    x_min -= FLOW_SIDE_MARGIN_MM
    x_max += FLOW_SIDE_MARGIN_MM
    z_min -= FLOW_VERTICAL_MARGIN_MM
    z_max += FLOW_VERTICAL_MARGIN_MM

    rows = []
    z = z_min
    while z <= z_max + 1e-6:
        rows.append(z)
        z += FLOW_ROW_SPACING_MM

    points = []
    flags = []
    reverse = False
    row_sample_count = max(2, int(math.ceil((x_max - x_min) / FLOW_SAMPLE_STEP_MM)))

    for row_index, row_z in enumerate(rows):
        row_points = []
        for sample_index in range(row_sample_count + 1):
            u = sample_index / row_sample_count
            x = x_max - u * (x_max - x_min) if reverse else x_min + u * (x_max - x_min)
            wave = FLOW_WAVE_AMPLITUDE_MM * math.sin(u * math.tau * 1.5 + row_index * 0.85)
            taper = smoothstep(u) * smoothstep(1.0 - u)
            row_points.append((x, row_z + wave * taper))

        for point in row_points:
            points.append(point)
            flags.append(mask_led_fit_fraction(binary, width, height, point[0], point[1]))

        if row_index < len(rows) - 1:
            next_z = rows[row_index + 1]
            last = row_points[-1]
            side_x = x_min - FLOW_SIDE_MARGIN_MM * 0.45 if reverse else x_max + FLOW_SIDE_MARGIN_MM * 0.45
            next_start = (x_min, next_z) if reverse else (x_max, next_z)
            connector = cubic_bezier(
                last,
                (side_x, last[1]),
                (side_x, next_start[1]),
                next_start,
                max(8, int(FLOW_ROW_SPACING_MM * 1.8)),
            )
            for point in connector:
                points.append(point)
                flags.append(mask_led_fit_fraction(binary, width, height, point[0], point[1]))

        reverse = not reverse

    return points, flags, len(rows)


def front_mm_to_pixel_int(x_mm, z_mm, width, height):
    x, y = front_mm_to_pixel(x_mm, z_mm, width, height)
    return int(round(x)), int(round(y))


def patch_strokes_from_mask(binary, width, height):
    x_min, x_max, z_min, z_max = white_bounds_front_mm(binary, width, height)
    target_height_mm = TARGET_WIDTH_MM * (height / width)
    row_step_px = max(2, int(round(PATCH_ROW_SPACING_MM / (target_height_mm * TARGET_Z_SCALE) * height)))
    min_run_px = max(2, int(round(PATCH_MIN_RUN_MM / (TARGET_WIDTH_MM * TARGET_X_SCALE) * width)))

    y_min = max(0, front_mm_to_pixel_int(0.0, z_max, width, height)[1])
    y_max = min(height - 1, front_mm_to_pixel_int(0.0, z_min, width, height)[1])
    strokes = []

    for y in range(y_min, y_max + 1, row_step_px):
        x = 0
        while x < width:
            while x < width and not binary[y][x]:
                x += 1
            start = x
            while x < width and binary[y][x]:
                x += 1
            end = x - 1
            if end - start + 1 >= min_run_px:
                p0 = pixel_to_front_mm(start, y, width, height)
                p1 = pixel_to_front_mm(end, y, width, height)
                if p1[0] < p0[0]:
                    p0, p1 = p1, p0
                if (p1[0] - p0[0]) > PATCH_ENTRY_MARGIN_MM * 2.0:
                    p0 = (p0[0] + PATCH_ENTRY_MARGIN_MM, p0[1])
                    p1 = (p1[0] - PATCH_ENTRY_MARGIN_MM, p1[1])
                strokes.append({"start": p0, "end": p1, "center": ((p0[0] + p1[0]) * 0.5, p0[1])})

    col_step_px = max(2, int(round(PATCH_ROW_SPACING_MM / (TARGET_WIDTH_MM * TARGET_X_SCALE) * width)))
    min_vertical_run_px = max(2, int(round(PATCH_MIN_RUN_MM / (target_height_mm * TARGET_Z_SCALE) * height)))
    x0_px = max(0, front_mm_to_pixel_int(x_min, TARGET_Z_CENTER, width, height)[0])
    x1_px = min(width - 1, front_mm_to_pixel_int(x_max, TARGET_Z_CENTER, width, height)[0])

    for x in range(x0_px, x1_px + 1, col_step_px):
        y = 0
        while y < height:
            while y < height and not binary[y][x]:
                y += 1
            start = y
            while y < height and binary[y][x]:
                y += 1
            end = y - 1
            if end - start + 1 >= min_vertical_run_px:
                p0 = pixel_to_front_mm(x, start, width, height)
                p1 = pixel_to_front_mm(x, end, width, height)
                if p1[1] < p0[1]:
                    p0, p1 = p1, p0
                if (p1[1] - p0[1]) > PATCH_ENTRY_MARGIN_MM * 2.0:
                    p0 = (p0[0], p0[1] + PATCH_ENTRY_MARGIN_MM)
                    p1 = (p1[0], p1[1] - PATCH_ENTRY_MARGIN_MM)
                strokes.append({"start": p0, "end": p1, "center": (p0[0], (p0[1] + p1[1]) * 0.5)})

    return strokes


def order_patch_strokes(strokes):
    if not strokes:
        return []

    remaining = list(strokes)
    current = min(remaining, key=lambda stroke: (stroke["center"][0], -stroke["center"][1]))
    remaining.remove(current)
    ordered = [current]
    end = current["end"]

    while remaining:
        best_index = 0
        best_reverse = False
        best_cost = None
        for index, stroke in enumerate(remaining):
            for reverse in (False, True):
                start = stroke["end"] if reverse else stroke["start"]
                dz_penalty = abs(start[1] - end[1]) * 0.45
                cost = math.dist(end, start) + dz_penalty
                if best_cost is None or cost < best_cost:
                    best_cost = cost
                    best_index = index
                    best_reverse = reverse

        chosen = remaining.pop(best_index)
        if best_reverse:
            chosen = {"start": chosen["end"], "end": chosen["start"], "center": chosen["center"]}
        ordered.append(chosen)
        end = chosen["end"]

    return ordered


def add_connector(points, fractions, start, end, connector_index):
    if math.dist(start, end) < 1e-6:
        return
    lateral = 18.0 if connector_index % 2 == 0 else -18.0
    vertical = 8.0 if end[1] >= start[1] else -8.0
    p1 = (start[0] + lateral, start[1] + vertical)
    p2 = (end[0] + lateral, end[1] - vertical)
    for point in cubic_bezier(start, p1, p2, end, PATCH_CONNECTOR_SAMPLES):
        points.append(point)
        fractions.append(0.0)


def add_visible_stroke(binary, width, height, points, fractions, start, end):
    length = max(math.dist(start, end), 1e-6)
    samples = max(2, int(math.ceil(length / FLOW_SAMPLE_STEP_MM)))
    for index in range(samples + 1):
        t = index / samples
        x = start[0] * (1.0 - t) + end[0] * t
        z = start[1] * (1.0 - t) + end[1] * t
        points.append((x, z))
        fractions.append(mask_led_fit_fraction(binary, width, height, x, z))


def patch_planner_path_to_front_mm(binary, width, height):
    strokes = order_patch_strokes(patch_strokes_from_mask(binary, width, height))
    points = []
    fractions = []

    for index, stroke in enumerate(strokes):
        if points:
            add_connector(points, fractions, points[-1], stroke["start"], index)
        else:
            points.append(stroke["start"])
            fractions.append(0.0)
        add_visible_stroke(binary, width, height, points, fractions, stroke["start"], stroke["end"])

    return points, fractions, len(strokes)


def chaikin_path_with_values(points, values, passes):
    if len(points) < 3:
        return points, values
    smoothed_points = list(points)
    smoothed_values = list(values)
    for _ in range(passes):
        next_points = [smoothed_points[0]]
        next_values = [smoothed_values[0]]
        for index in range(len(smoothed_points) - 1):
            p0 = smoothed_points[index]
            p1 = smoothed_points[index + 1]
            v0 = smoothed_values[index]
            v1 = smoothed_values[index + 1]
            next_points.append((p0[0] * 0.75 + p1[0] * 0.25, p0[1] * 0.75 + p1[1] * 0.25))
            next_values.append(v0 * 0.75 + v1 * 0.25)
            next_points.append((p0[0] * 0.25 + p1[0] * 0.75, p0[1] * 0.25 + p1[1] * 0.75))
            next_values.append(v0 * 0.25 + v1 * 0.75)
        next_points.append(smoothed_points[-1])
        next_values.append(smoothed_values[-1])
        smoothed_points = next_points
        smoothed_values = next_values
    return smoothed_points, smoothed_values


def chaikin_path_with_two_values(points, values_a, values_b, passes):
    if len(points) < 3:
        return points, values_a, values_b
    smoothed_points = list(points)
    smoothed_a = list(values_a)
    smoothed_b = list(values_b)
    for _ in range(passes):
        next_points = [smoothed_points[0]]
        next_a = [smoothed_a[0]]
        next_b = [smoothed_b[0]]
        for index in range(len(smoothed_points) - 1):
            p0 = smoothed_points[index]
            p1 = smoothed_points[index + 1]
            a0 = smoothed_a[index]
            a1 = smoothed_a[index + 1]
            b0 = smoothed_b[index]
            b1 = smoothed_b[index + 1]
            next_points.append((p0[0] * 0.75 + p1[0] * 0.25, p0[1] * 0.75 + p1[1] * 0.25))
            next_a.append(a0 * 0.75 + a1 * 0.25)
            next_b.append(b0 * 0.75 + b1 * 0.25)
            next_points.append((p0[0] * 0.25 + p1[0] * 0.75, p0[1] * 0.25 + p1[1] * 0.75))
            next_a.append(a0 * 0.25 + a1 * 0.75)
            next_b.append(b0 * 0.25 + b1 * 0.75)
        next_points.append(smoothed_points[-1])
        next_a.append(smoothed_a[-1])
        next_b.append(smoothed_b[-1])
        smoothed_points = next_points
        smoothed_a = next_a
        smoothed_b = next_b
    return smoothed_points, smoothed_a, smoothed_b


def resample_front_path(points, step_mm):
    if len(points) < 2:
        return points
    result = [points[0]]
    carry = 0.0
    previous = points[0]
    for point in points[1:]:
        segment = math.dist(previous, point)
        if segment < 1e-6:
            continue
        direction = ((point[0] - previous[0]) / segment, (point[1] - previous[1]) / segment)
        distance = step_mm - carry
        cursor = previous
        while distance <= segment:
            cursor = (cursor[0] + direction[0] * distance, cursor[1] + direction[1] * distance)
            result.append(cursor)
            segment -= distance
            distance = step_mm
        carry = step_mm - segment
        previous = point
    return result


def resample_front_path_with_values(points, values, step_mm, extra_values=None):
    if len(points) < 2:
        return (points, values, extra_values) if extra_values is not None else (points, values)
    result = [points[0]]
    result_values = [values[0] if values else 0.0]
    result_extra_values = [extra_values[0] if extra_values else 0.0] if extra_values is not None else None
    previous = points[0]
    previous_value = values[0] if values else 0.0
    previous_extra_value = extra_values[0] if extra_values else 0.0
    accumulated_in_segment = 0.0

    for index in range(1, len(points)):
        point = points[index]
        value = values[index] if index < len(values) else previous_value
        extra_value = (
            extra_values[index]
            if extra_values is not None and index < len(extra_values)
            else previous_extra_value
        )
        segment = math.dist(previous, point)
        if segment < 1e-6:
            previous = point
            previous_value = value
            previous_extra_value = extra_value
            continue

        distance = step_mm - accumulated_in_segment
        while distance <= segment:
            t = distance / segment
            x = previous[0] * (1.0 - t) + point[0] * t
            z = previous[1] * (1.0 - t) + point[1] * t
            interpolated_value = previous_value * (1.0 - t) + value * t
            result.append((x, z))
            result_values.append(interpolated_value)
            if result_extra_values is not None:
                interpolated_extra = previous_extra_value * (1.0 - t) + extra_value * t
                result_extra_values.append(interpolated_extra)
            distance += step_mm

        accumulated_in_segment = segment - (distance - step_mm)
        if accumulated_in_segment >= step_mm:
            accumulated_in_segment = 0.0
        previous = point
        previous_value = value
        previous_extra_value = extra_value

    if math.dist(result[-1], points[-1]) > step_mm * 0.4:
        result.append(points[-1])
        result_values.append(values[-1] if values else 0.0)
        if result_extra_values is not None:
            result_extra_values.append(extra_values[-1] if extra_values else 0.0)
    if result_extra_values is not None:
        return result, result_values, result_extra_values
    return result, result_values


def catmull_rom_scalar(v0, v1, v2, v3, t):
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        2.0 * v1
        + (-v0 + v2) * t
        + (2.0 * v0 - 5.0 * v1 + 4.0 * v2 - v3) * t2
        + (-v0 + 3.0 * v1 - 3.0 * v2 + v3) * t3
    )


def catmull_rom_path_with_values(points, values, extra_values, step_mm):
    if len(points) < 4:
        return points, values, extra_values
    result = []
    result_values = []
    result_extra = []
    for index in range(len(points) - 1):
        p0 = points[max(0, index - 1)]
        p1 = points[index]
        p2 = points[index + 1]
        p3 = points[min(len(points) - 1, index + 2)]
        segment_length = max(math.dist(p1, p2), step_mm)
        samples = max(2, int(math.ceil(segment_length / step_mm)))
        for sample in range(samples):
            if index > 0 and sample == 0:
                continue
            t = sample / samples
            x = catmull_rom_scalar(p0[0], p1[0], p2[0], p3[0], t)
            z = catmull_rom_scalar(p0[1], p1[1], p2[1], p3[1], t)
            value = catmull_rom_scalar(
                values[max(0, index - 1)],
                values[index],
                values[index + 1],
                values[min(len(values) - 1, index + 2)],
                t,
            )
            extra = catmull_rom_scalar(
                extra_values[max(0, index - 1)],
                extra_values[index],
                extra_values[index + 1],
                extra_values[min(len(extra_values) - 1, index + 2)],
                t,
            )
            result.append((x, z))
            clamped_value = max(0.0, min(1.0, value))
            if clamped_value < LED_MASK_FIT_MIN_FRACTION:
                clamped_value = 0.0
            result_values.append(clamped_value)
            result_extra.append(max(-MAX_SCULPTURAL_DEPTH, min(MAX_SCULPTURAL_DEPTH, extra)))
    result.append(points[-1])
    result_values.append(values[-1])
    result_extra.append(extra_values[-1])
    return result, result_values, result_extra


def resample_front_path_with_segment_flags(points, segment_lit_flags, step_mm):
    if len(points) < 2:
        return points, segment_lit_flags
    result = [points[0]]
    result_flags = [False]
    for index in range(1, len(points)):
        previous = points[index - 1]
        point = points[index]
        lit = segment_lit_flags[index]
        segment = math.dist(previous, point)
        if segment < 1e-6:
            continue
        direction = ((point[0] - previous[0]) / segment, (point[1] - previous[1]) / segment)
        distance = step_mm
        while distance < segment:
            result.append((previous[0] + direction[0] * distance, previous[1] + direction[1] * distance))
            result_flags.append(lit)
            distance += step_mm
        result.append(point)
        result_flags.append(lit)
    return result, result_flags


def point_line_distance(point, start, end):
    line_length = math.dist(start, end)
    if line_length < 1e-9:
        return math.dist(point, start)
    numerator = abs(
        (end[0] - start[0]) * (start[1] - point[1])
        - (start[0] - point[0]) * (end[1] - start[1])
    )
    return numerator / line_length


def simplify_front_path(points, epsilon):
    if len(points) <= 2:
        return points

    max_distance = -1.0
    max_index = 0
    start = points[0]
    end = points[-1]

    for index in range(1, len(points) - 1):
        distance = point_line_distance(points[index], start, end)
        if distance > max_distance:
            max_distance = distance
            max_index = index

    if max_distance > epsilon:
        left = simplify_front_path(points[: max_index + 1], epsilon)
        right = simplify_front_path(points[max_index:], epsilon)
        return left[:-1] + right

    return [start, end]


def smooth_front_path(points, passes):
    if len(points) < 5:
        return points
    smoothed = list(points)
    for _ in range(passes):
        next_points = [smoothed[0], smoothed[1]]
        for index in range(2, len(smoothed) - 2):
            x = (
                smoothed[index - 2][0]
                + smoothed[index - 1][0] * 2.0
                + smoothed[index][0] * 3.0
                + smoothed[index + 1][0] * 2.0
                + smoothed[index + 2][0]
            ) / 9.0
            z = (
                smoothed[index - 2][1]
                + smoothed[index - 1][1] * 2.0
                + smoothed[index][1] * 3.0
                + smoothed[index + 1][1] * 2.0
                + smoothed[index + 2][1]
            ) / 9.0
            next_points.append((x, z))
        next_points.extend([smoothed[-2], smoothed[-1]])
        smoothed = next_points
    return smoothed


def chaikin_front_path(points, passes):
    if len(points) < 3:
        return points
    rounded = list(points)
    for _ in range(passes):
        next_points = [rounded[0]]
        for index in range(len(rounded) - 1):
            p0 = rounded[index]
            p1 = rounded[index + 1]
            q = (p0[0] * 0.75 + p1[0] * 0.25, p0[1] * 0.75 + p1[1] * 0.25)
            r = (p0[0] * 0.25 + p1[0] * 0.75, p0[1] * 0.25 + p1[1] * 0.75)
            next_points.extend([q, r])
        next_points.append(rounded[-1])
        rounded = next_points
    return rounded


def sculptural_depth_for_point(x, z, t, mask_fit_fraction=0.0):
    # Keep camera readability first: depth is a broad layered drift. Hidden
    # connectors can step backward, but visible strokes should not collapse
    # into a heavy tangled mass when inspected from 3/4.
    broad_wave = math.sin(t * math.tau * 0.48 - 0.35)
    vertical_sway = math.sin((z - TARGET_Z_CENTER) * 0.012 + t * math.tau * 0.18)
    side_sway = math.sin(x * 0.012 - t * math.tau * 0.12)
    hidden = 1.0 - max(0.0, min(1.0, mask_fit_fraction / max(LED_MASK_FIT_MIN_FRACTION, 1e-6)))
    escape_wave = math.sin(t * math.tau * 0.9 + x * 0.014)
    depth = (
        8.0 * broad_wave
        + 3.5 * vertical_sway
        + 2.5 * side_sway
        + hidden * 16.0 * escape_wave
    )
    return max(-MAX_SCULPTURAL_DEPTH, min(MAX_SCULPTURAL_DEPTH, depth))


def project_target_point_to_depth(x_target, z_target, y_depth):
    # Keep the camera projection fixed: move the physical point along the ray
    # from the privileged camera through the target-plane coordinate.
    denominator = TARGET_PLANE_Y - CAMERA_Y
    factor = (y_depth - CAMERA_Y) / denominator
    x_world = x_target * factor
    z_world = CAMERA_Z + (z_target - CAMERA_Z) * factor
    return Vector((x_world, y_depth, z_world))


def solve_projected_point_clearance(front_points, fractions, depths):
    if len(front_points) < 4 or depths is None:
        return depths

    result = list(depths)
    for pass_index in range(POST_DEPTH_CLEARANCE_SOLVER_PASSES):
        projected = [
            project_target_point_to_depth(point[0], point[1], result[index])
            for index, point in enumerate(front_points)
        ]
        offsets = [0.0 for _ in result]
        weights = [0.0 for _ in result]

        for i, point_i in enumerate(projected):
            for j in range(i + DEPTH_CLEARANCE_SKIP_NEIGHBORS, len(projected)):
                if i < DEPTH_CLEARANCE_SKIP_NEIGHBORS and j > len(projected) - DEPTH_CLEARANCE_SKIP_NEIGHBORS:
                    continue

                distance = (point_i - projected[j]).length
                if distance >= POST_DEPTH_CLEARANCE_MM or distance < 1e-6:
                    continue

                depth_delta = result[j] - result[i]
                if abs(depth_delta) < 1e-6:
                    direction = 1.0 if ((i // 17 + j // 17) % 2 == 0) else -1.0
                else:
                    direction = 1.0 if depth_delta > 0.0 else -1.0

                push = (POST_DEPTH_CLEARANCE_MM - distance) * POST_DEPTH_CLEARANCE_PUSH
                offsets[i] -= push * direction
                offsets[j] += push * direction
                weights[i] += 1.0
                weights[j] += 1.0

        moved = False
        for index, offset in enumerate(offsets):
            if weights[index] <= 0.0:
                continue
            scale = max(1.0, weights[index] ** 0.35)
            new_depth = max(
                -MAX_SCULPTURAL_DEPTH,
                min(MAX_SCULPTURAL_DEPTH, result[index] + offset / scale),
            )
            moved = moved or abs(new_depth - result[index]) > 1e-4
            result[index] = new_depth

        if not moved:
            break

        if pass_index % 8 == 7:
            result = smooth_depth_values(result, fractions)

    return result


def limit_depth_steps(depths, max_step):
    if len(depths) < 2:
        return depths

    result = list(depths)
    for index in range(1, len(result)):
        delta = result[index] - result[index - 1]
        if delta > max_step:
            result[index] = result[index - 1] + max_step
        elif delta < -max_step:
            result[index] = result[index - 1] - max_step

    for index in range(len(result) - 2, -1, -1):
        delta = result[index] - result[index + 1]
        if delta > max_step:
            result[index] = result[index + 1] + max_step
        elif delta < -max_step:
            result[index] = result[index + 1] - max_step

    return [max(-MAX_SCULPTURAL_DEPTH, min(MAX_SCULPTURAL_DEPTH, value)) for value in result]


def smooth_solution(front_points, fractions, depths, passes, weight):
    if len(front_points) < 5:
        return front_points, fractions, depths

    points = list(front_points)
    fit_values = list(fractions)
    depth_values = list(depths) if depths is not None else None

    for _ in range(passes):
        next_points = list(points)
        next_fit_values = list(fit_values)
        next_depth_values = list(depth_values) if depth_values is not None else None

        for index in range(1, len(points) - 1):
            previous = points[index - 1]
            current = points[index]
            following = points[index + 1]
            next_points[index] = (
                current[0] * (1.0 - weight) + (previous[0] + following[0]) * (weight * 0.5),
                current[1] * (1.0 - weight) + (previous[1] + following[1]) * (weight * 0.5),
            )
            next_fit_values[index] = (
                fit_values[index] * (1.0 - weight)
                + (fit_values[index - 1] + fit_values[index + 1]) * (weight * 0.5)
            )
            if depth_values is not None and next_depth_values is not None:
                next_depth_values[index] = (
                    depth_values[index] * (1.0 - weight)
                    + (depth_values[index - 1] + depth_values[index + 1]) * (weight * 0.5)
                )

        points = next_points
        fit_values = [max(0.0, min(1.0, value)) for value in next_fit_values]
        if next_depth_values is not None:
            depth_values = limit_depth_steps(next_depth_values, POST_DEPTH_MAX_STEP_MM)

    return points, fit_values, depth_values


def smooth_sinuous_closed_loop(front_points, fractions, depths):
    if len(front_points) < 6:
        return front_points, fractions, depths

    closed = CLOSED_LOOP_PATH and math.dist(front_points[0], front_points[-1]) < RESAMPLE_STEP_MM * 2.0
    if closed:
        points = list(front_points[:-1])
        fit_values = list(fractions[:-1])
        depth_values = list(depths[:-1]) if depths is not None else None
    else:
        points = list(front_points)
        fit_values = list(fractions)
        depth_values = list(depths) if depths is not None else None

    count = len(points)
    if count < 5:
        return front_points, fractions, depths

    for _ in range(SINUOUS_LOOP_SMOOTHING_PASSES):
        next_points = list(points)
        next_fit_values = list(fit_values)
        next_depth_values = list(depth_values) if depth_values is not None else None

        indices = range(count) if closed else range(1, count - 1)
        for index in indices:
            previous = points[(index - 1) % count]
            current = points[index]
            following = points[(index + 1) % count]
            mask_fit = fit_values[index] if index < len(fit_values) else 0.0
            hidden = 1.0 - clamp_value(mask_fit / max(LED_MASK_FIT_MIN_FRACTION, 1e-6), 0.0, 1.0)
            weight = (
                SINUOUS_VISIBLE_SMOOTHING_WEIGHT * (1.0 - hidden)
                + SINUOUS_HIDDEN_SMOOTHING_WEIGHT * hidden
            )
            next_points[index] = (
                current[0] * (1.0 - weight) + (previous[0] + following[0]) * (weight * 0.5),
                current[1] * (1.0 - weight) + (previous[1] + following[1]) * (weight * 0.5),
            )
            next_fit_values[index] = (
                fit_values[index] * 0.86
                + (fit_values[(index - 1) % count] + fit_values[(index + 1) % count]) * 0.07
            )
            if depth_values is not None and next_depth_values is not None:
                depth_weight = max(weight, SINUOUS_DEPTH_SMOOTHING_WEIGHT * hidden)
                next_depth_values[index] = (
                    depth_values[index] * (1.0 - depth_weight)
                    + (depth_values[(index - 1) % count] + depth_values[(index + 1) % count]) * (depth_weight * 0.5)
                )

        points = next_points
        fit_values = [clamp_value(value, 0.0, 1.0) for value in next_fit_values]
        if next_depth_values is not None:
            depth_values = limit_depth_steps(next_depth_values, POST_DEPTH_MAX_STEP_MM)

    if closed:
        points.append(points[0])
        fit_values.append(fit_values[0])
        if depth_values is not None:
            depth_values.append(depth_values[0])

    return points, fit_values, depth_values


def smooth_curvature_spikes(front_points, fractions, depths):
    if len(front_points) < 5:
        return front_points, fractions, depths

    closed = CLOSED_LOOP_PATH and math.dist(front_points[0], front_points[-1]) < RESAMPLE_STEP_MM * 2.0
    if closed:
        points = list(front_points[:-1])
        fit_values = list(fractions[:-1])
        depth_values = list(depths[:-1]) if depths is not None else None
    else:
        points = list(front_points)
        fit_values = list(fractions)
        depth_values = list(depths) if depths is not None else None

    count = len(points)
    for _ in range(CURVATURE_SPIKE_SMOOTHING_PASSES):
        next_points = list(points)
        next_depth_values = list(depth_values) if depth_values is not None else None
        indices = range(count) if closed else range(1, count - 1)
        for index in indices:
            previous = points[(index - 1) % count]
            current = points[index]
            following = points[(index + 1) % count]
            d1 = math.dist(previous, current)
            d2 = math.dist(current, following)
            span = d1 + d2
            if span < 1e-6 or span > RESAMPLE_STEP_MM * 4.2:
                continue
            direct = math.dist(previous, following)
            if direct / span > 0.42:
                continue
            weight = CURVATURE_SPIKE_SMOOTHING_WEIGHT
            next_points[index] = (
                current[0] * (1.0 - weight) + (previous[0] + following[0]) * (weight * 0.5),
                current[1] * (1.0 - weight) + (previous[1] + following[1]) * (weight * 0.5),
            )
            if depth_values is not None and next_depth_values is not None:
                next_depth_values[index] = (
                    depth_values[index] * (1.0 - weight)
                    + (depth_values[(index - 1) % count] + depth_values[(index + 1) % count]) * (weight * 0.5)
                )
        points = next_points
        if next_depth_values is not None:
            depth_values = limit_depth_steps(next_depth_values, POST_DEPTH_MAX_STEP_MM)

    if closed:
        points.append(points[0])
        fit_values.append(fit_values[0])
        if depth_values is not None:
            depth_values.append(depth_values[0])

    return points, fit_values, depth_values


def force_closed_loop(front_points, fractions, depths):
    if not CLOSED_LOOP_PATH or len(front_points) < 3:
        return front_points, fractions, depths

    points = list(front_points)
    fit_values = list(fractions)
    depth_values = list(depths) if depths is not None else None
    first_point = points[0]
    first_fraction = fit_values[0] if fit_values else 0.0
    first_depth = depth_values[0] if depth_values else None
    last_point = points[-1]
    last_fraction = fit_values[-1] if fit_values else 0.0
    last_depth = depth_values[-1] if depth_values else first_depth
    front_gap = math.dist(last_point, first_point)
    depth_gap = abs((first_depth or 0.0) - (last_depth or 0.0))
    if front_gap < 1e-6 and depth_gap < 1e-6:
        points[-1] = first_point
        if fit_values:
            fit_values[-1] = first_fraction
        if depth_values is not None:
            depth_values[-1] = first_depth
        return points, fit_values, depth_values

    steps = max(
        1,
        int(math.ceil(front_gap / max(RESAMPLE_STEP_MM, 1e-6))),
        int(math.ceil(depth_gap / max(POST_DEPTH_MAX_STEP_MM, 1e-6))),
    )

    for step in range(1, steps + 1):
        t = step / steps
        points.append(
            (
                last_point[0] * (1.0 - t) + first_point[0] * t,
                last_point[1] * (1.0 - t) + first_point[1] * t,
            )
        )
        fit_values.append(last_fraction * (1.0 - t) + first_fraction * t)
        if depth_values is not None:
            depth_values.append((last_depth or 0.0) * (1.0 - t) + (first_depth or 0.0) * t)

    return points, fit_values, depth_values


def make_3d_points(front_points, segment_lit_flags, depth_values=None):
    points = []
    projection_targets = []
    led_flags = []
    mask_fit_fractions = []
    total = max(len(front_points) - 1, 1)
    for index, (x, z) in enumerate(front_points):
        t = index / total
        value = segment_lit_flags[index] if index < len(segment_lit_flags) else 1.0
        fraction = float(value) if isinstance(value, (float, int)) else (1.0 if value else 0.0)
        if depth_values is not None and index < len(depth_values):
            depth = max(-MAX_SCULPTURAL_DEPTH, min(MAX_SCULPTURAL_DEPTH, depth_values[index]))
        else:
            depth = sculptural_depth_for_point(x, z, t, fraction)
        point = project_target_point_to_depth(x, z, depth)
        if points and (point - points[-1]).length < 0.35:
            continue
        points.append(point)
        projection_targets.append((x, z, depth))
        mask_fit_fractions.append(fraction)
        led_flags.append(fraction >= LED_MASK_FIT_MIN_FRACTION)
    return points, projection_targets, led_flags, mask_fit_fractions


def create_path_material():
    material = bpy.data.materials.get("AL_CONTINUOUS_PATH_MAT")
    if material is None:
        material = bpy.data.materials.new("AL_CONTINUOUS_PATH_MAT")
    material.diffuse_color = (0.0, 0.78, 1.0, 1.0)
    return material


def create_curve_object(points, debug_collection):
    remove_existing_object(DEBUG_OBJECT_NAME)
    curve = bpy.data.curves.new(DEBUG_OBJECT_NAME, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = 0.9
    curve.bevel_resolution = 2
    spline = curve.splines.new(type="POLY")
    spline.points.add(len(points) - 1)
    for spline_point, point in zip(spline.points, points):
        spline_point.co = (point.x, point.y, point.z, 1.0)
    if len(points) > 3 and (points[0] - points[-1]).length < 1.5:
        spline.use_cyclic_u = True
    obj = bpy.data.objects.new(DEBUG_OBJECT_NAME, curve)
    obj.show_name = False
    obj["role"] = "Algorithmic centerline from target bitmap skeleton; one continuous P(s)."
    obj.data.materials.append(create_path_material())
    debug_collection.objects.link(obj)


def path_length(points):
    return sum((points[index] - points[index - 1]).length for index in range(1, len(points)))


def backstage_profile_stats(points, projection_targets, mask_fit_fractions):
    if len(points) < 2:
        return {
            "backstage_nodes": 0,
            "backstage_weighted_length_mm": 0.0,
            "readable_weighted_length_mm": 0.0,
            "backstage_depth_span_mm": 0.0,
            "backstage_depth_mean_mm": 0.0,
        }

    backstage_length = 0.0
    readable_length = 0.0
    backstage_depths = []
    for index, fit in enumerate(mask_fit_fractions):
        if fit < LED_MASK_FIT_MIN_FRACTION and index < len(projection_targets):
            backstage_depths.append(projection_targets[index][2])

    for index in range(1, len(points)):
        segment_length = (points[index] - points[index - 1]).length
        fit = (mask_fit_fractions[index] + mask_fit_fractions[index - 1]) * 0.5
        readable_weight = clamp_value(fit / max(LED_MASK_FIT_MIN_FRACTION, 1e-6), 0.0, 1.0)
        hidden_weight = 1.0 - readable_weight
        backstage_length += segment_length * hidden_weight
        readable_length += segment_length * readable_weight

    if backstage_depths:
        depth_span = max(backstage_depths) - min(backstage_depths)
        depth_mean = sum(backstage_depths) / len(backstage_depths)
    else:
        depth_span = 0.0
        depth_mean = 0.0

    return {
        "backstage_nodes": len(backstage_depths),
        "backstage_weighted_length_mm": backstage_length,
        "readable_weighted_length_mm": readable_length,
        "backstage_depth_span_mm": depth_span,
        "backstage_depth_mean_mm": depth_mean,
    }


def write_path_json(project_root, image_path, points, projection_targets, led_flags, mask_fit_fractions, stats):
    output_path = project_root / "output" / "debug" / target_output_name(project_root, "continuous_path")
    total_length = path_length(points)
    nodes = []
    accumulated = 0.0
    previous = None
    for index, point in enumerate(points):
        if previous is not None:
            accumulated += (point - previous).length
        x_target, z_target, depth = projection_targets[index]
        nodes.append(
            {
                "kind": "algorithmic_target_centerline",
                "index": index,
                "s_normalized": accumulated / total_length if total_length else 0.0,
                "target_projection_mm": [x_target, TARGET_PLANE_Y, z_target],
                "sculptural_depth_y_mm": depth,
                "point_world_mm": [point.x, point.y, point.z],
                "led_on_from_previous": bool(led_flags[index]),
                "front_facing_from_previous": bool(led_flags[index]),
                "mask_fit_fraction": mask_fit_fractions[index],
            }
        )
        previous = point
    payload = {
        "source": "ANAMORPHIC_LAMP scripts/04_continuous_path.py",
        "mode": PATH_MODE,
        "target_image": str(image_path),
        "camera_ray_depth": {
            "camera_y_mm": CAMERA_Y,
            "camera_z_mm": CAMERA_Z,
            "target_plane_y_mm": TARGET_PLANE_Y,
            "max_sculptural_depth_mm": MAX_SCULPTURAL_DEPTH,
            "meaning": "Physical points move along camera rays, preserving the same front projection.",
        },
        "stats": stats,
        "point_count": len(points),
        "path_length_mm": total_length,
        "nodes": nodes,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def main():
    project_root = get_project_root()
    apply_autosize_config(project_root)
    debug_collection = get_project_child_collection("AL_DEBUG")
    image_path, width, height, binary = load_binary_target(project_root)
    small, factor = downsample_binary(binary, factor=2)
    skeleton = zhang_suen_thinning(small)
    nodes, graph = skeleton_graph(skeleton)
    components = [component for component in connected_components(nodes, graph) if len(component) > 8]
    component_paths = [ordered_component_path(component, graph) for component in components]
    pixel_path = bridge_components(component_paths)
    left_component_restore_stats = {
        "left_component_frontness_restore_nodes": 0,
        "left_component_frontness_restore_min_mask_fit": LEFT_COMPONENT_RESTORE_MIN_MASK_FIT,
        "left_component_frontness_restore_frontness": LEFT_COMPONENT_RESTORE_FRONTNESS,
    }

    if PATH_MODE == "skeleton_branch_single_profile":
        front_points, segment_lit_flags, depth_values, centerline_strokes = centerline_path_to_front_mm(
            binary, width, height, factor, components, graph
        )
        front_points, segment_lit_flags, depth_values = chaikin_path_with_two_values(
            front_points, segment_lit_flags, depth_values, CENTERLINE_CHAIKIN_PASSES
        )
        front_points, segment_lit_flags, depth_values = resample_front_path_with_values(
            front_points, segment_lit_flags, RESAMPLE_STEP_MM, depth_values
        )
        front_points, segment_lit_flags, depth_values = catmull_rom_path_with_values(
            front_points, segment_lit_flags, depth_values, RESAMPLE_STEP_MM
        )
        for _ in range(POST_DEPTH_CLEARANCE_CYCLES):
            depth_values = solve_projected_point_clearance(
                front_points,
                segment_lit_flags,
                depth_values,
            )
            depth_values = limit_depth_steps(depth_values, POST_DEPTH_MAX_STEP_MM)
        front_points, segment_lit_flags, depth_values = smooth_solution(
            front_points,
            segment_lit_flags,
            depth_values,
            FINAL_GEOMETRY_SMOOTHING_PASSES,
            FINAL_GEOMETRY_SMOOTHING_WEIGHT,
        )
        segment_lit_flags = [
            min(
                max(0.0, min(1.0, segment_lit_flags[index] if index < len(segment_lit_flags) else 0.0)),
                mask_led_fit_fraction(binary, width, height, point[0], point[1]),
            )
            for index, point in enumerate(front_points)
        ]
        segment_lit_flags, left_component_restore_stats = restore_left_component_frontness(
            binary,
            width,
            height,
            front_points,
            segment_lit_flags,
        )
        front_points, segment_lit_flags, depth_values = force_closed_loop(
            front_points,
            segment_lit_flags,
            depth_values,
        )
        front_points, segment_lit_flags, depth_values = smooth_sinuous_closed_loop(
            front_points,
            segment_lit_flags,
            depth_values,
        )
        front_points, segment_lit_flags, depth_values = smooth_curvature_spikes(
            front_points,
            segment_lit_flags,
            depth_values,
        )
        for _ in range(FINAL_LOOP_CLEARANCE_CYCLES):
            depth_values = solve_projected_point_clearance(
                front_points,
                segment_lit_flags,
                depth_values,
            )
            depth_values = limit_depth_steps(depth_values, POST_DEPTH_MAX_STEP_MM)
        segment_lit_flags = [
            min(
                max(0.0, min(1.0, segment_lit_flags[index] if index < len(segment_lit_flags) else 0.0)),
                mask_led_fit_fraction(binary, width, height, point[0], point[1]),
            )
            for index, point in enumerate(front_points)
        ]
        front_points, segment_lit_flags, depth_values = force_closed_loop(
            front_points,
            segment_lit_flags,
            depth_values,
        )
        front_points_raw = front_points
        front_points_simplified = front_points
        raster_runs = 0
        flow_rows = 0
        patch_strokes = 0
    elif PATH_MODE == "patch_planner_single_profile":
        front_points, segment_lit_flags, patch_strokes = patch_planner_path_to_front_mm(binary, width, height)
        front_points, segment_lit_flags = chaikin_path_with_values(front_points, segment_lit_flags, 1)
        front_points_raw = front_points
        front_points_simplified = front_points
        raster_runs = 0
        flow_rows = 0
        centerline_strokes = 0
        depth_values = None
    elif PATH_MODE == "smooth_flowfield_single_profile":
        front_points, segment_lit_flags, flow_rows = flowfield_path_to_front_mm(binary, width, height)
        front_points_raw = front_points
        front_points_simplified = front_points
        raster_runs = 0
        patch_strokes = 0
        centerline_strokes = 0
        depth_values = None
    elif PATH_MODE == "raster_fill_single_continuous_path":
        front_points_raw, raw_lit_flags, raster_runs = raster_fill_path_to_front_mm(binary, width, height)
        front_points_simplified = front_points_raw
        front_points, segment_lit_flags = resample_front_path_with_segment_flags(
            front_points_simplified, raw_lit_flags, RESAMPLE_STEP_MM
        )
        flow_rows = 0
        patch_strokes = 0
        centerline_strokes = 0
        depth_values = None
    else:
        flow_rows = 0
        raster_runs = 0
        patch_strokes = 0
        centerline_strokes = 0
        depth_values = None
        front_points_raw = pixel_path_to_front_mm(pixel_path, width, height, factor)
        front_points_simplified = simplify_front_path(front_points_raw, SIMPLIFY_EPSILON_MM)
        front_points = resample_front_path(front_points_simplified, RESAMPLE_STEP_MM)
        front_points = smooth_front_path(front_points, SMOOTHING_PASSES)
        front_points = chaikin_front_path(front_points, CHAIKIN_PASSES)
        segment_lit_flags = [index > 0 for index in range(len(front_points))]

    points, projection_targets, led_flags, mask_fit_fractions = make_3d_points(
        front_points, segment_lit_flags, depth_values
    )
    create_curve_object(points, debug_collection)
    backstage_stats = backstage_profile_stats(points, projection_targets, mask_fit_fractions)
    stats = {
        "path_mode": PATH_MODE,
        "image_px": [width, height],
        "downsample_factor": factor,
        "skeleton_nodes": len(nodes),
        "components": len(components),
        "raw_path_points": len(pixel_path),
        "raster_fill_runs": raster_runs,
        "raster_fill_row_step_px": FILL_ROW_STEP_PX,
        "flow_rows": flow_rows,
        "flow_row_spacing_mm": FLOW_ROW_SPACING_MM,
        "patch_strokes": patch_strokes,
        "centerline_strokes": centerline_strokes,
        "centerline_min_stroke_mm": CENTERLINE_MIN_STROKE_MM,
        "centerline_max_strokes": CENTERLINE_MAX_STROKES,
        "patch_row_spacing_mm": PATCH_ROW_SPACING_MM,
        "patch_min_run_mm": PATCH_MIN_RUN_MM,
        "led_width_mm": LED_WIDTH_MM,
        "led_mask_fit_radius_mm": LED_MASK_FIT_RADIUS_MM,
        "led_mask_fit_min_fraction": LED_MASK_FIT_MIN_FRACTION,
        "led_power_model": "always_on",
        "front_facing_meaning": "True marks where the continuous LED face is aimed at the privileged camera; the LED is never switched off.",
        "closed_loop": CLOSED_LOOP_PATH,
        "depth_strategy": "ordered_centerline_lanes" if depth_values is not None else "procedural_wave",
        "centerline_depth_lanes_mm": list(CENTERLINE_DEPTH_LANES_MM),
        "centerline_connector_escape_margin_mm": CENTERLINE_CONNECTOR_ESCAPE_MARGIN_MM,
        "backstage_route_model": "compact rear tangle cloud connectors",
        "backstage_connector_samples": CENTERLINE_BACKSTAGE_CONNECTOR_SAMPLES,
        "backstage_side_sway_mm": CENTERLINE_BACKSTAGE_SIDE_SWAY_MM,
        "backstage_vertical_sway_mm": CENTERLINE_BACKSTAGE_VERTICAL_SWAY_MM,
        "backstage_depth_bias": CENTERLINE_BACKSTAGE_DEPTH_BIAS,
        "backstage_depth_swing": CENTERLINE_BACKSTAGE_DEPTH_SWING,
        "backstage_tangle_loops": CENTERLINE_BACKSTAGE_TANGLE_LOOPS,
        "centerline_chaikin_passes": CENTERLINE_CHAIKIN_PASSES,
        "post_depth_clearance_mm": POST_DEPTH_CLEARANCE_MM,
        "post_depth_clearance_passes": POST_DEPTH_CLEARANCE_SOLVER_PASSES,
        "post_depth_clearance_cycles": POST_DEPTH_CLEARANCE_CYCLES,
        "post_depth_max_step_mm": POST_DEPTH_MAX_STEP_MM,
        "final_geometry_smoothing_passes": FINAL_GEOMETRY_SMOOTHING_PASSES,
        "final_geometry_smoothing_weight": FINAL_GEOMETRY_SMOOTHING_WEIGHT,
        "sinuous_loop_smoothing_passes": SINUOUS_LOOP_SMOOTHING_PASSES,
        "sinuous_visible_smoothing_weight": SINUOUS_VISIBLE_SMOOTHING_WEIGHT,
        "sinuous_hidden_smoothing_weight": SINUOUS_HIDDEN_SMOOTHING_WEIGHT,
        "sinuous_depth_smoothing_weight": SINUOUS_DEPTH_SMOOTHING_WEIGHT,
        "curvature_spike_smoothing_passes": CURVATURE_SPIKE_SMOOTHING_PASSES,
        "curvature_spike_smoothing_weight": CURVATURE_SPIKE_SMOOTHING_WEIGHT,
        "final_loop_clearance_cycles": FINAL_LOOP_CLEARANCE_CYCLES,
        "simplified_front_points": len(front_points_simplified),
        "chaikin_passes": CHAIKIN_PASSES,
        "front_points": len(front_points),
    }
    stats.update(backstage_stats)
    stats.update(left_component_restore_stats)
    output_path = write_path_json(
        project_root, image_path, points, projection_targets, led_flags, mask_fit_fractions, stats
    )
    print("")
    print("============================================")
    print(" ANAMORPHIC LAMP")
    print(" STEP 04 - CONTINUOUS PATH")
    print("============================================")
    print(f"Algorithm: {PATH_MODE}")
    print(f"Skeleton nodes: {len(nodes)}")
    print(f"Components bridged: {len(components)}")
    print("Depth mode: camera-ray displacement preserving target projection")
    print(f"Path points: {len(points)}")
    print(f"Approx path length: {path_length(points):.2f} mm")
    print(f"Path data: {output_path}")
    print("Status: SUCCESS")
    print("READY FOR STEP 05")
    print("============================================")


if __name__ == "__main__":
    main()
