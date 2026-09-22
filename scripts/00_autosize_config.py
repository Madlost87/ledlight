import json
from collections import deque
from pathlib import Path

import bpy
from PIL import Image

TARGET_IMAGE_NAME = "target_LOVE.png"
OUTPUT_JSON_NAME = "autosize_config_LOVE.json"

LED_WIDTH_MM = 10.0
LED_THICKNESS_MM = 3.0
SCALE_MODE = "balanced"


def get_project_root():
    blend_path = bpy.data.filepath
    if not blend_path:
        raise RuntimeError(
            "Save the Blender file first as "
            "ANAMORPHIC_LAMP/blender/anamorphic_lamp.blend, then rerun this script."
        )
    blend_dir = Path(blend_path).resolve().parent
    return blend_dir.parent if blend_dir.name == "blender" else blend_dir


def connected_components(binary, width, height):
    seen = [[False for _ in range(width)] for _ in range(height)]
    sizes = []
    for y in range(height):
        for x in range(width):
            if seen[y][x] or not binary[y][x]:
                continue
            seen[y][x] = True
            queue = deque([(x, y)])
            size = 0
            while queue:
                cx, cy = queue.popleft()
                size += 1
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if seen[ny][nx] or not binary[ny][nx]:
                        continue
                    seen[ny][nx] = True
                    queue.append((nx, ny))
            sizes.append(size)
    return sizes


def analyze_target(image_path):
    image = Image.open(image_path).convert("L")
    width, height = image.size
    pixels = image.load()
    binary = [[pixels[x, y] > 140 for x in range(width)] for y in range(height)]
    xs = []
    ys = []
    white = 0
    for y in range(height):
        for x in range(width):
            if binary[y][x]:
                xs.append(x)
                ys.append(y)
                white += 1

    if not xs:
        raise RuntimeError(f"Target image has no white mask pixels: {image_path}")

    bbox_w = max(xs) - min(xs) + 1
    bbox_h = max(ys) - min(ys) + 1
    bbox_area = max(1, bbox_w * bbox_h)
    fill_ratio = white / bbox_area

    # Downsample for inexpensive topology hints. This is not geometry output;
    # it only nudges the scale for dense/multi-part logos.
    factor = max(1, min(width, height) // 220)
    small_w = width // factor
    small_h = height // factor
    small = []
    for sy in range(small_h):
        row = []
        for sx in range(small_w):
            count = 0
            total = 0
            for yy in range(factor):
                for xx in range(factor):
                    px = sx * factor + xx
                    py = sy * factor + yy
                    if px >= width or py >= height:
                        continue
                    total += 1
                    if binary[py][px]:
                        count += 1
            row.append(total > 0 and count / total > 0.25)
        small.append(row)
    component_sizes = connected_components(small, small_w, small_h)
    meaningful_components = [size for size in component_sizes if size > 8]

    return {
        "image_px": [width, height],
        "white_bbox_px": [min(xs), min(ys), max(xs), max(ys)],
        "white_bbox_aspect": bbox_w / bbox_h if bbox_h else 1.0,
        "fill_ratio_in_bbox": fill_ratio,
        "component_count": len(meaningful_components),
    }


def autosize(analysis):
    image_w, image_h = analysis["image_px"]
    aspect = image_h / image_w
    bbox_aspect = analysis["white_bbox_aspect"]
    fill_ratio = analysis["fill_ratio_in_bbox"]
    component_count = analysis["component_count"]

    mode_scale = {"compact": 0.92, "balanced": 1.0, "sculptural": 1.12}.get(SCALE_MODE, 1.0)
    density_extra = max(0.0, fill_ratio - 0.30) * 90.0
    component_extra = max(0, component_count - 1) * 10.0
    aspect_extra = max(0.0, 2.1 - bbox_aspect) * 18.0
    target_width = (34.0 * LED_WIDTH_MM + density_extra + component_extra + aspect_extra) * mode_scale
    target_width = max(340.0, min(460.0, round(target_width / 10.0) * 10.0))
    target_height = target_width * aspect

    lamp_width = round(max(target_width * 1.22, target_width + 70.0) / 10.0) * 10.0
    lamp_depth = round(max(target_width * 0.95, 300.0) / 10.0) * 10.0
    lamp_height = round(max(target_height + 185.0, 330.0) / 10.0) * 10.0
    base_diameter = round(max(165.0, lamp_width * 0.48) / 5.0) * 5.0
    camera_distance = round(max(950.0, target_width * 3.5) / 10.0) * 10.0
    camera_height = round((target_height * 0.5 + 95.0) / 5.0) * 5.0
    target_z_center = round((25.0 + target_height * 0.5 + 70.0) / 5.0) * 5.0

    depth_max = min(lamp_depth * 0.46, 155.0)
    lanes = [-0.96, -0.67, -0.38, -0.12, 0.16, 0.46, 0.75, 1.0]
    depth_lanes = [round(depth_max * lane, 1) for lane in lanes]

    return {
        "source": "ANAMORPHIC_LAMP scripts/00_autosize_config.py",
        "scale_mode": SCALE_MODE,
        "target_image_name": TARGET_IMAGE_NAME,
        "analysis": analysis,
        "led": {
            "width_mm": LED_WIDTH_MM,
            "thickness_mm": LED_THICKNESS_MM,
        },
        "target": {
            "width_mm": target_width,
            "height_mm": target_height,
            "z_center_mm": target_z_center,
            "x_scale": 0.96,
            "z_scale": 0.96,
        },
        "lamp": {
            "width_mm": lamp_width,
            "depth_mm": lamp_depth,
            "height_mm": lamp_height,
            "base_diameter_mm": base_diameter,
            "base_height_mm": 25.0,
            "profile_width_mm": 15.0,
            "profile_height_mm": 8.0,
            "max_sculptural_depth_mm": depth_max,
            "depth_lanes_mm": depth_lanes,
        },
        "camera": {
            "distance_mm": camera_distance,
            "height_mm": camera_height,
        },
        "planner": {
            "centerline_min_stroke_mm": max(20.0, LED_WIDTH_MM * 2.0),
            "centerline_max_strokes": 9,
            "min_bend_radius_mm": 60.0,
            "twist_length_for_90_deg_mm": 150.0,
            "connector_escape_margin_mm": 60.0,
            "closed_loop": True,
        },
    }


def main():
    project_root = get_project_root()
    image_path = project_root / "input" / TARGET_IMAGE_NAME
    if not image_path.exists():
        raise FileNotFoundError(f"Missing target image: {image_path}")
    output_dir = project_root / "output" / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis = analyze_target(image_path)
    config = autosize(analysis)
    output_path = output_dir / OUTPUT_JSON_NAME
    output_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print("")
    print("============================================")
    print(" ANAMORPHIC LAMP")
    print(" STEP 00A - AUTOSIZE CONFIG")
    print("============================================")
    print(f"Target image: {image_path}")
    print(f"Target width: {config['target']['width_mm']:.0f} mm")
    print(
        "Lamp: "
        f"{config['lamp']['width_mm']:.0f} x "
        f"{config['lamp']['depth_mm']:.0f} x "
        f"{config['lamp']['height_mm']:.0f} mm"
    )
    print(f"LED: {LED_WIDTH_MM:.1f} x {LED_THICKNESS_MM:.1f} mm")
    print(f"Output: {output_path}")
    print("Status: SUCCESS")
    print("============================================")


if __name__ == "__main__":
    main()
