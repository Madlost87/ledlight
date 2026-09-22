import json


CONFIG_JSON_NAME = "autosize_config_LOVE.json"


def load_autosize_config(project_root):
    config_path = project_root / "output" / "debug" / CONFIG_JSON_NAME
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
