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
    input_path = project_root / "output" / "debug" / target_output_name(project_root, "orientation_frames")
    if not input_path.exists():
        raise FileNotFoundError(f"Missing {input_path}. Run step 05 first.")

    frames = json.loads(input_path.read_text(encoding="utf-8"))["frames"]
    twists = [abs(frame["twist_deg_from_previous"]) for frame in frames[1:]]
    curvatures = [frame["curvature_1_per_mm"] for frame in frames]
    sorted_twists = sorted(twists)
    sorted_curvatures = sorted(curvatures)

    def percentile(values, amount):
        if not values:
            return 0.0
        index = min(len(values) - 1, max(0, int((len(values) - 1) * amount)))
        return values[index]

    output = {
        "source": "ANAMORPHIC_LAMP scripts/06_transition_solver.py",
        "input_frames": str(input_path),
        "frame_count": len(frames),
        "max_twist_deg": max(twists) if twists else 0.0,
        "p95_twist_deg": percentile(sorted_twists, 0.95),
        "avg_twist_deg": sum(twists) / len(twists) if twists else 0.0,
        "max_curvature_1_per_mm": max(curvatures) if curvatures else 0.0,
        "p95_curvature_1_per_mm": percentile(sorted_curvatures, 0.95),
        "min_radius_from_max_curvature_mm": (
            1.0 / max(curvatures) if curvatures and max(curvatures) > 1e-9 else None
        ),
        "p95_radius_mm": (
            1.0 / percentile(sorted_curvatures, 0.95)
            if percentile(sorted_curvatures, 0.95) > 1e-9
            else None
        ),
        "status": "initial analysis only",
        "notes": [
            "No abrupt section rotation is applied.",
            "Future solver should reduce high twist and curvature by moving points/depth.",
        ],
    }
    output_path = project_root / "output" / "debug" / target_output_name(project_root, "transition_analysis")
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("STEP 06 - TRANSITION SOLVER")
    print(f"Max twist: {output['max_twist_deg']:.2f} deg")
    print(f"Output: {output_path}")
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
