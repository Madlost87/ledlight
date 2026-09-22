# ANAMORPHIC_LAMP

Blender/Python project for an anamorphic table lamp sculpture generated from one continuous physical profile.

The initial target is the word `LOVE` as a white image on black background. The target image is only a perspective reference: it must not become 3D text, independent letters, or separated pieces.

## Current Scope

- `scripts/run_all.py` runs the current end-to-end prototype pipeline.
- `scripts/00_autosize_config.py` analyzes the target bitmap and derives working dimensions.
- `scripts/00_setup_scene.py` prepares the Blender scene, collections, camera, reference volume, base, table plane, and secondary light direction.
- `scripts/01_target_to_path.py` loads `input/target_LOVE.png` and creates `AL_TARGET_IMAGE` as a visual debug reference oriented toward `AL_CAMERA_MAIN`.
- `scripts/02_camera_projection.py` through `scripts/13_camera_evaluation.py` generate projection samples, a continuous path, orientation frames, product previews, LED previews, validation reports, and camera readability diagnostics.

No Blender add-on is created yet. The current geometry is a preview/prototype,
not a final manufacturing mesh.

## Current Status

See `ROADMAP.md` for the working baseline and next milestones.

The current prototype already produces a readable `LOVE` projection from the
camera view, but validation still fails because the continuous physical path has
too many self-clearance violations. The next major task is improving the
depth/clearance solver while preserving camera readability.

## Changing The Target Image

The current pipeline is partially automatic:

- If you replace the contents of `input/target_LOVE.png` with another
  white-on-black target image, the autosize and path scripts will analyze the
  new bitmap and regenerate the lamp dimensions, target scale, projection,
  centerline, depth lanes, LED visibility mask, validation, and exports.
- The image should remain a high-contrast white subject on a black background.
  Thin details, disconnected islands, and very dense shapes will strongly affect
  the generated path.
- The system is not fully target-agnostic yet: many script constants and output
  files still use the `LOVE` name, and some debug object labels still mention
  LOVE. So changing the filename itself is not automatic yet.
- Artistic behavior should be parameterized, not manually recalibrated per
  image. The planned next step is to move the target name and style controls
  into one shared config so a future image can be swapped without hunting
  through every script.

## Expected Blender File

Save the Blender file manually as:

```text
blender/anamorphic_lamp.blend
```

The scripts derive the project root from `bpy.data.filepath`, so they do not contain machine-specific absolute paths. If the `.blend` is unsaved, scripts stop with a clear error.

## Initial Configuration

- `LAMP_TYPE = TABLE`
- `SECONDARY_LIGHT_DIRECTION = DOWN`
- Autosized lamp volume for the current target: approximately `610 x 650 x 430 mm`
- Base reference: approximately `295 mm` diameter, `25 mm` height
- Camera: approximately `(0, -1300, 190) mm`
- Target physical width: approximately `370 mm`
