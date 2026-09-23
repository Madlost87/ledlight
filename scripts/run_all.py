from pathlib import Path
import sys

import bpy


SCRIPT_ORDER = (
    "00_autosize_config.py",
    "00_setup_scene.py",
    "01_target_to_path.py",
    "02_camera_projection.py",
    "03_depth_solver.py",
    "04_continuous_path.py",
    "05_orientation_frames.py",
    "06_transition_solver.py",
    "08_optimizer.py",
    "05_orientation_frames.py",
    "06_transition_solver.py",
    "07_secondary_light.py",
    "10_build_profile.py",
    "11_led_channel.py",
    "13_camera_evaluation.py",
    "09_validation.py",
    "12_export.py",
)


def get_project_root():
    blend_path = bpy.data.filepath
    if not blend_path:
        raise RuntimeError(
            "Save the Blender file first as "
            "ANAMORPHIC_LAMP/blender/anamorphic_lamp.blend, then rerun this script."
        )

    blend_dir = Path(blend_path).resolve().parent
    if blend_dir.name == "blender":
        return blend_dir.parent
    return blend_dir


def run_script(path):
    namespace = {"__file__": str(path), "__name__": "__main__"}
    code = path.read_text(encoding="utf-8")
    exec(compile(code, str(path), "exec"), namespace)


def set_viewport_preview():
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue

        region = next((item for item in area.regions if item.type == "WINDOW"), None)
        space = area.spaces.active
        if not region or not space:
            continue

        space.shading.type = "MATERIAL"
        override = {
            "window": bpy.context.window,
            "screen": bpy.context.screen,
            "area": area,
            "region": region,
            "space_data": space,
        }

        with bpy.context.temp_override(**override):
            bpy.ops.view3d.view_camera()


def set_default_visibility():
    from al_config import readable_preview_object_name

    project_root = get_project_root()
    for name in (
        "AL_TARGET_IMAGE",
        "AL_PROJECTION_SAMPLES",
        "AL_CAMERA_PROJECTION_RAYS",
        "AL_DEPTH_CANDIDATES",
        "AL_ORIENTATION_FRAMES",
        "AL_SECONDARY_NORMALS",
        "AL_CLEARANCE_HOTSPOTS",
        "AL_CURVATURE_HOTSPOTS",
        readable_preview_object_name(project_root),
        "AL_CAMERA_READABILITY_PREVIEW",
    ):
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_viewport = True
            obj.hide_render = True


def main():
    project_root = get_project_root()
    scripts_dir = project_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    print("")
    print("============================================")
    print(" ANAMORPHIC LAMP")
    print(" RUN ALL CURRENT STEPS")
    print("============================================")

    for script_name in SCRIPT_ORDER:
        script_path = scripts_dir / script_name
        if not script_path.exists():
            raise FileNotFoundError(f"Missing pipeline script: {script_path}")

        print(f"Running {script_path}")
        run_script(script_path)

    set_default_visibility()
    set_viewport_preview()
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

    print("Pipeline completed: 00 -> 12")
    print("Current implementation creates debug/preview artifacts, not a final manufacturing mesh.")
    print("Blender remains open for inspection.")
    print("============================================")


if __name__ == "__main__":
    main()
