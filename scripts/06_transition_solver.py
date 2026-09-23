import json
from pathlib import Path

import bpy

from al_config import load_autosize_config, nested_get, target_output_name

READABLE_FIT_THRESHOLD = 0.36
TRANSITION_FIT_THRESHOLD = 0.12
CURVATURE_HOTSPOT_LIMIT = 80


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

    frame_data = json.loads(input_path.read_text(encoding="utf-8"))
    frames = frame_data["frames"]
    path_data = json.loads(
        (
            project_root
            / "output"
            / "debug"
            / target_output_name(project_root, "continuous_path")
        ).read_text(encoding="utf-8")
    )
    config = load_autosize_config(project_root)
    minimum_bend_radius = float(
        nested_get(config, ("planner", "min_bend_radius_mm"), 180.0)
    )
    maximum_curvature = 1.0 / minimum_bend_radius if minimum_bend_radius > 1e-9 else 0.0
    twists = [abs(frame["twist_deg_from_previous"]) for frame in frames[1:]]
    curvatures = [frame["curvature_1_per_mm"] for frame in frames]
    sorted_twists = sorted(twists)
    sorted_curvatures = sorted(curvatures)

    def percentile(values, amount):
        if not values:
            return 0.0
        index = min(len(values) - 1, max(0, int((len(values) - 1) * amount)))
        return values[index]

    zone_values = {"readable": [], "transition": [], "hidden": []}
    curvature_hotspots = []
    path_nodes = path_data.get("nodes", [])
    for index, frame in enumerate(frames):
        fit = float(path_nodes[index].get("mask_fit_fraction", 0.0)) if index < len(path_nodes) else 0.0
        if fit >= READABLE_FIT_THRESHOLD:
            zone = "readable"
        elif fit >= TRANSITION_FIT_THRESHOLD:
            zone = "transition"
        else:
            zone = "hidden"
        curvature = float(frame["curvature_1_per_mm"])
        zone_values[zone].append(curvature)
        if curvature > maximum_curvature:
            curvature_hotspots.append(
                {
                    "index": index,
                    "zone": zone,
                    "mask_fit_fraction": fit,
                    "curvature_1_per_mm": curvature,
                    "radius_mm": 1.0 / curvature if curvature > 1e-9 else None,
                    "point_world_mm": frame["point_world_mm"],
                }
            )

    curvature_hotspots.sort(key=lambda item: item["curvature_1_per_mm"], reverse=True)
    zone_reports = {}
    for zone, values in zone_values.items():
        ordered = sorted(values)
        violations = sum(value > maximum_curvature for value in values)
        zone_reports[zone] = {
            "point_count": len(values),
            "bend_radius_violation_count": violations,
            "p95_curvature_1_per_mm": percentile(ordered, 0.95),
            "p95_radius_mm": (
                1.0 / percentile(ordered, 0.95)
                if percentile(ordered, 0.95) > 1e-9
                else None
            ),
        }

    bend_radius_violations = len(curvature_hotspots)

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
        "minimum_bend_radius_target_mm": minimum_bend_radius,
        "maximum_allowed_curvature_1_per_mm": maximum_curvature,
        "bend_radius_passed": bend_radius_violations == 0,
        "bend_radius_violation_count": bend_radius_violations,
        "curvature_zones": zone_reports,
        "curvature_hotspots": curvature_hotspots[:CURVATURE_HOTSPOT_LIMIT],
        "status": "curvature and twist analysis",
        "notes": [
            "No abrupt section rotation is applied.",
            "Curvature violations are classified as readable, transition, or hidden.",
            "The camera-ray optimizer runs before this final analysis.",
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
