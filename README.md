# ANAMORPHIC_LAMP

Blender/Python project for an anamorphic table lamp sculpture generated from one continuous physical profile.

The initial target is the word `LOVE` as a white image on black background. The target image is only a perspective reference: it must not become 3D text, independent letters, or separated pieces.

## Current Scope

- `scripts/00_setup_scene.py` prepares the Blender scene, collections, camera, reference volume, base, table plane, and secondary light direction.
- `scripts/01_target_to_path.py` loads `input/target_LOVE.png` and creates `AL_TARGET_IMAGE` as a visual debug reference oriented toward `AL_CAMERA_MAIN`.
- `scripts/02_camera_projection.py` through `scripts/12_export.py` are architectural placeholders for the future solver pipeline.

No Blender add-on is created yet. No final lamp mesh is created yet.

## Expected Blender File

Save the Blender file manually as:

```text
blender/anamorphic_lamp.blend
```

The scripts derive the project root from `bpy.data.filepath`, so they do not contain machine-specific absolute paths. If the `.blend` is unsaved, scripts stop with a clear error.

## Initial Configuration

- `LAMP_TYPE = TABLE`
- `SECONDARY_LIGHT_DIRECTION = DOWN`
- Maximum lamp volume: `200 x 140 x 300 mm`
- Base reference: `130 mm` diameter, `25 mm` height
- Camera: approximately `(0, -800, 170) mm`, looking toward `(0, 0, 150) mm`
- Target physical width: approximately `170 mm`
