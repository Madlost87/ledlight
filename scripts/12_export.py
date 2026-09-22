import json
import shutil
from pathlib import Path

import bpy

DEBUG_FILES = (
    "camera_projection_LOVE.json",
    "depth_candidates_LOVE.json",
    "continuous_path_LOVE.json",
    "orientation_frames_LOVE.json",
    "transition_analysis_LOVE.json",
    "secondary_light_LOVE.json",
    "optimized_solution_LOVE.json",
    "validation_report_LOVE.json",
    "validation_report_LOVE.txt",
    "profile_preview_LOVE.json",
    "led_channel_preview_LOVE.json",
    "camera_evaluation_LOVE.json",
    "camera_evaluation_LOVE.txt",
    "camera_eval_led_mask.png",
    "camera_eval_error_map.png",
)


def get_project_root():
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender file before running project scripts.")
    blend_dir = Path(bpy.data.filepath).resolve().parent
    return blend_dir.parent if blend_dir.name == "blender" else blend_dir


def main():
    project_root = get_project_root()
    debug_dir = project_root / "output" / "debug"
    export_dir = project_root / "output" / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    missing = []
    for name in DEBUG_FILES:
        source = debug_dir / name
        if source.exists():
            destination = export_dir / name
            shutil.copy2(source, destination)
            copied.append(str(destination))
        else:
            missing.append(str(source))

    manifest = {
        "source": "ANAMORPHIC_LAMP scripts/12_export.py",
        "blend_file": bpy.data.filepath,
        "copied_count": len(copied),
        "missing_count": len(missing),
        "copied": copied,
        "missing": missing,
        "note": "No final manufacturing mesh is exported yet.",
    }
    manifest_path = export_dir / "export_manifest_LOVE.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("STEP 12 - EXPORT")
    print(f"Copied files: {len(copied)}")
    print(f"Manifest: {manifest_path}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
