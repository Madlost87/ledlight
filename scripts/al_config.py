import json
import re
from pathlib import Path


DEFAULT_TARGET_ID = "LOVE"
DEFAULT_TARGET_IMAGE_NAME = "target_LOVE.png"
TARGET_CONFIG_JSON_NAME = "target_config.json"


def sanitize_target_id(value):
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip()).strip("_")
    return cleaned.upper() if cleaned else DEFAULT_TARGET_ID


def derive_target_id(image_name):
    stem = Path(image_name).stem
    if stem.lower().startswith("target_"):
        stem = stem[7:]
    return sanitize_target_id(stem)


def load_target_config(project_root):
    config_path = project_root / "input" / TARGET_CONFIG_JSON_NAME
    data = {}
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))

    image_name = str(data.get("target_image_name", DEFAULT_TARGET_IMAGE_NAME))
    target_id = sanitize_target_id(data.get("target_id", derive_target_id(image_name)))
    return {
        "target_id": target_id,
        "target_image_name": image_name,
        "config_path": str(config_path),
    }


def get_target_id(project_root):
    return load_target_config(project_root)["target_id"]


def get_target_image_name(project_root):
    return load_target_config(project_root)["target_image_name"]


def target_output_name(project_root, stem, extension="json"):
    return f"{stem}_{get_target_id(project_root)}.{extension}"


def readable_preview_object_name(project_root):
    return f"AL_READABLE_{get_target_id(project_root)}_PREVIEW"


def load_autosize_config(project_root):
    config_path = project_root / "output" / "debug" / target_output_name(project_root, "autosize_config")
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def nested_get(data, path, fallback):
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return fallback
        current = current[key]
    return current
