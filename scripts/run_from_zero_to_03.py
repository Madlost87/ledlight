from pathlib import Path

import bpy


SCRIPT_ORDER = (
    "00_setup_scene.py",
    "01_target_to_path.py",
    "02_camera_projection.py",
    "03_depth_solver.py",
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


def main():
    project_root = get_project_root()
    scripts_dir = project_root / "scripts"

    print("")
    print("============================================")
    print(" ANAMORPHIC LAMP")
    print(" RUN FROM ZERO TO STEP 03")
    print("============================================")

    for script_name in SCRIPT_ORDER:
        script_path = scripts_dir / script_name
        print(f"Running {script_path}")
        run_script(script_path)

    set_viewport_preview()
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

    print("Pipeline completed: 00 -> 03")
    print("Blender remains open for inspection.")
    print("============================================")


if __name__ == "__main__":
    main()
