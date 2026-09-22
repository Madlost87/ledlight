import json
from pathlib import Path

import bpy

from al_config import target_output_name


def get_project_root():
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender file before running project scripts.")
    blend_dir = Path(bpy.data.filepath).resolve().parent
    return blend_dir.parent if blend_dir.name == "blender" else blend_dir


def main():
    project_root = get_project_root()
    debug_dir = project_root / "output" / "debug"
    path_data = json.loads((debug_dir / target_output_name(project_root, "continuous_path")).read_text(encoding="utf-8"))
    frame_data = json.loads((debug_dir / target_output_name(project_root, "orientation_frames")).read_text(encoding="utf-8"))
    transition_data = json.loads((debug_dir / target_output_name(project_root, "transition_analysis")).read_text(encoding="utf-8"))
    camera_eval_path = debug_dir / target_output_name(project_root, "camera_evaluation")
    camera_eval_data = None
    if camera_eval_path.exists():
        camera_eval_data = json.loads(camera_eval_path.read_text(encoding="utf-8"))

    twist_penalty = transition_data.get("p95_twist_deg", transition_data["max_twist_deg"]) / 180.0
    curvature_penalty = transition_data.get(
        "p95_curvature_1_per_mm", transition_data["max_curvature_1_per_mm"]
    ) * 35.0
    score = max(0.0, 1.0 - min(1.0, twist_penalty + curvature_penalty))
    output = {
        "source": "ANAMORPHIC_LAMP scripts/08_optimizer.py",
        "status": "initial pass-through optimization",
        "path_point_count": path_data["point_count"],
        "frame_count": frame_data["frame_count"],
        "path_length_mm": path_data["path_length_mm"],
        "quality_score_0_1": score,
        "score_inputs": {
            "twist_metric_deg": transition_data.get("p95_twist_deg", transition_data["max_twist_deg"]),
            "curvature_metric_1_per_mm": transition_data.get(
                "p95_curvature_1_per_mm", transition_data["max_curvature_1_per_mm"]
            ),
            "camera_visual_score_0_1": camera_eval_data.get("visual_score_0_1")
            if camera_eval_data
            else None,
        },
        "camera_evaluation_available": camera_eval_data is not None,
        "notes": [
            "This pass preserves P(s).",
            "Future optimizer should adjust depth and transitions to improve score.",
        ],
    }
    output_path = debug_dir / target_output_name(project_root, "optimized_solution")
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("STEP 08 - OPTIMIZER")
    print(f"Quality score: {score:.3f}")
    print(f"Output: {output_path}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
