import json
from pathlib import Path

import bpy
from PIL import Image, ImageDraw

from al_config import load_autosize_config, nested_get

PROJECT_COLLECTION = "ANAMORPHIC_LAMP"
TARGET_IMAGE_NAME = "target_LOVE.png"
PATH_JSON = "continuous_path_LOVE.json"
LED_JSON = "led_channel_preview_LOVE.json"
OUTPUT_JSON = "camera_evaluation_LOVE.json"
OUTPUT_TXT = "camera_evaluation_LOVE.txt"
OUTPUT_LED_MASK = "camera_eval_led_mask.png"
OUTPUT_ERROR_MAP = "camera_eval_error_map.png"

TARGET_WIDTH_MM = 260.0
TARGET_X_SCALE = 0.96
TARGET_Z_SCALE = 0.96
TARGET_Z_CENTER = 145.0
WHITE_THRESHOLD = 140
LED_THRESHOLD = 10


def apply_autosize_config(project_root):
    global TARGET_WIDTH_MM, TARGET_X_SCALE, TARGET_Z_SCALE, TARGET_Z_CENTER

    config = load_autosize_config(project_root)
    TARGET_WIDTH_MM = float(nested_get(config, ("target", "width_mm"), TARGET_WIDTH_MM))
    TARGET_X_SCALE = float(nested_get(config, ("target", "x_scale"), TARGET_X_SCALE))
    TARGET_Z_SCALE = float(nested_get(config, ("target", "z_scale"), TARGET_Z_SCALE))
    TARGET_Z_CENTER = float(nested_get(config, ("target", "z_center_mm"), TARGET_Z_CENTER))


def get_project_root():
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender file before running project scripts.")
    blend_dir = Path(bpy.data.filepath).resolve().parent
    return blend_dir.parent if blend_dir.name == "blender" else blend_dir


def target_projection_to_pixel(x_mm, z_mm, width_px, height_px):
    target_height_mm = TARGET_WIDTH_MM * (height_px / width_px)
    px = (x_mm / (TARGET_WIDTH_MM * TARGET_X_SCALE) + 0.5) * width_px
    py = (0.5 - (z_mm - TARGET_Z_CENTER) / (target_height_mm * TARGET_Z_SCALE)) * height_px
    return px, py


def draw_led_projection(path_data, led_width_mm, width_px, height_px):
    points = []
    flags = []
    for node in path_data["nodes"]:
        x_mm, _y_mm, z_mm = node["target_projection_mm"]
        points.append(target_projection_to_pixel(x_mm, z_mm, width_px, height_px))
        flags.append(bool(node.get("front_facing_from_previous", node.get("led_on_from_previous", True))))

    led_mask = Image.new("L", (width_px, height_px), 0)
    draw = ImageDraw.Draw(led_mask)
    line_width_px = max(1, round(led_width_mm / TARGET_WIDTH_MM * width_px))
    lit_segments = 0

    for index in range(1, len(points)):
        if not flags[index]:
            continue
        draw.line([points[index - 1], points[index]], fill=255, width=line_width_px, joint="curve")
        lit_segments += 1

    return led_mask, line_width_px, lit_segments


def draw_led_projection_with_threshold(path_data, fit_threshold, led_width_mm, width_px, height_px):
    points = []
    fractions = []
    for node in path_data["nodes"]:
        x_mm, _y_mm, z_mm = node["target_projection_mm"]
        points.append(target_projection_to_pixel(x_mm, z_mm, width_px, height_px))
        fractions.append(
            float(
                node.get(
                    "mask_fit_fraction",
                    1.0 if node.get("front_facing_from_previous", node.get("led_on_from_previous", True)) else 0.0,
                )
            )
        )

    led_mask = Image.new("L", (width_px, height_px), 0)
    draw = ImageDraw.Draw(led_mask)
    line_width_px = max(1, round(led_width_mm / TARGET_WIDTH_MM * width_px))
    lit_segments = 0

    for index in range(1, len(points)):
        if fractions[index] < fit_threshold:
            continue
        draw.line([points[index - 1], points[index]], fill=255, width=line_width_px, joint="curve")
        lit_segments += 1

    return led_mask, lit_segments


def compare_masks(target, led_mask):
    width_px, height_px = target.size
    target_pixels = target.load()
    led_pixels = led_mask.load()
    error_map = Image.new("RGB", (width_px, height_px), (0, 0, 0))
    error_pixels = error_map.load()

    true_positive = 0
    false_positive = 0
    false_negative = 0
    true_negative = 0

    for y in range(height_px):
        for x in range(width_px):
            target_on = target_pixels[x, y] > WHITE_THRESHOLD
            front_visible = led_pixels[x, y] > LED_THRESHOLD

            if target_on and front_visible:
                true_positive += 1
                error_pixels[x, y] = (255, 255, 255)
            elif target_on and not front_visible:
                false_negative += 1
                error_pixels[x, y] = (40, 110, 255)
            elif not target_on and front_visible:
                false_positive += 1
                error_pixels[x, y] = (255, 60, 35)
            else:
                true_negative += 1

    target_area = true_positive + false_negative
    led_area = true_positive + false_positive
    union = true_positive + false_positive + false_negative

    coverage = true_positive / target_area if target_area else 0.0
    precision = true_positive / led_area if led_area else 0.0
    overdraw = false_positive / led_area if led_area else 0.0
    iou = true_positive / union if union else 0.0
    missing = false_negative / target_area if target_area else 0.0

    return {
        "target_area_px": target_area,
        "led_area_px": led_area,
        "true_positive_px": true_positive,
        "false_positive_px": false_positive,
        "false_negative_px": false_negative,
        "true_negative_px": true_negative,
        "coverage_0_1": coverage,
        "precision_0_1": precision,
        "overdraw_0_1": overdraw,
        "missing_0_1": missing,
        "iou_0_1": iou,
    }, error_map


def score_metrics(metrics):
    coverage = metrics["coverage_0_1"]
    precision = metrics["precision_0_1"]
    iou = metrics["iou_0_1"]
    missing_penalty = metrics["missing_0_1"] * 0.25
    return max(0.0, min(1.0, iou * 0.45 + coverage * 0.35 + precision * 0.20 - missing_penalty))


def threshold_sweep(path_data, target, led_width_mm):
    candidates = []
    for threshold in (0.24, 0.28, 0.32, 0.34, 0.36, 0.38, 0.42, 0.46, 0.50, 0.55, 0.60):
        mask, lit_segments = draw_led_projection_with_threshold(
            path_data, threshold, led_width_mm, target.width, target.height
        )
        metrics, _error_map = compare_masks(target, mask)
        candidates.append(
            {
                "fit_threshold": threshold,
                "visual_score_0_1": score_metrics(metrics),
                "coverage_0_1": metrics["coverage_0_1"],
                "precision_0_1": metrics["precision_0_1"],
                "overdraw_0_1": metrics["overdraw_0_1"],
                "iou_0_1": metrics["iou_0_1"],
                "lit_segments": lit_segments,
            }
        )
    return sorted(candidates, key=lambda item: item["visual_score_0_1"], reverse=True)


def main():
    project_root = get_project_root()
    apply_autosize_config(project_root)
    debug_dir = project_root / "output" / "debug"
    target = Image.open(project_root / "input" / TARGET_IMAGE_NAME).convert("L")
    path_data = json.loads((debug_dir / PATH_JSON).read_text(encoding="utf-8"))
    led_data = json.loads((debug_dir / LED_JSON).read_text(encoding="utf-8"))
    led_width_mm = float(led_data.get("led_width_mm", 10.0))

    led_mask, line_width_px, lit_segments = draw_led_projection(
        path_data, led_width_mm, target.width, target.height
    )
    metrics, error_map = compare_masks(target, led_mask)
    visual_score = score_metrics(metrics)
    sweep = threshold_sweep(path_data, target, led_width_mm)

    led_mask_path = debug_dir / OUTPUT_LED_MASK
    error_map_path = debug_dir / OUTPUT_ERROR_MAP
    led_mask.save(led_mask_path)
    error_map.save(error_map_path)

    report = {
        "source": "ANAMORPHIC_LAMP scripts/13_camera_evaluation.py",
        "status": "diagnostic projection evaluation",
        "target_image": str(project_root / "input" / TARGET_IMAGE_NAME),
        "path_mode": path_data.get("mode"),
        "led_width_mm": led_width_mm,
        "line_width_px": line_width_px,
        "lit_segments": lit_segments,
        "visual_score_0_1": visual_score,
        "metrics": metrics,
        "threshold_sweep": sweep,
        "recommended_fit_threshold": sweep[0]["fit_threshold"] if sweep else None,
        "outputs": {
            "led_mask": str(led_mask_path),
            "error_map": str(error_map_path),
        },
        "legend": {
            "error_map_white": "target and LED overlap",
            "error_map_red": "LED outside target",
            "error_map_blue": "target not covered by LED",
        },
        "limits": [
            "This is a camera-projection diagnostic, not a full Blender light transport render.",
            "It accounts for LED width in camera projection but not yet self-shadowing or material bloom.",
        ],
    }

    output_json = debug_dir / OUTPUT_JSON
    output_txt = debug_dir / OUTPUT_TXT
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output_txt.write_text(
        "\n".join(
            [
                "ANAMORPHIC_LAMP camera evaluation",
                f"visual_score: {visual_score:.3f}",
                f"coverage: {metrics['coverage_0_1']:.3f}",
                f"precision: {metrics['precision_0_1']:.3f}",
                f"overdraw: {metrics['overdraw_0_1']:.3f}",
                f"missing: {metrics['missing_0_1']:.3f}",
                f"iou: {metrics['iou_0_1']:.3f}",
                f"led_mask: {led_mask_path}",
                f"error_map: {error_map_path}",
            ]
        ),
        encoding="utf-8",
    )

    print("STEP 13 - CAMERA EVALUATION")
    print(f"Visual score: {visual_score:.3f}")
    print(f"Coverage: {metrics['coverage_0_1']:.3f}")
    print(f"Overdraw: {metrics['overdraw_0_1']:.3f}")
    print(f"Output: {output_json}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
