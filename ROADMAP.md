# ANAMORPHIC_LAMP Roadmap

This document tracks the path from the current Blender/Python prototype to a
physically plausible anamorphic table lamp.

## Goal

Create a table lamp generated from one continuous physical profile and one
continuous LED channel. From the privileged camera view it should read `LOVE`;
from other views it should remain a sculptural lamp, not separated 3D text.

## Original Baseline

Generated from the `output/export` artifacts before the first clearance pass:

- Path mode: `skeleton_branch_single_profile`
- Path points: `1672`
- Path length: `2358.95 mm`
- Camera visual score: `0.794`
- Camera coverage: `0.873`
- Camera precision: `0.868`
- Camera IoU: `0.771`
- Validation passed: `False`
- Out of bounds points: `0`
- Clearance violations: `2648`
- Minimum non-local clearance: `0.291 mm`
- Optimizer quality score: `0.000`
- Final manufacturing mesh: not created yet

## Progress Log

### First Clearance Pass

Implemented in `scripts/04_continuous_path.py` as a post-depth clearance pass
that preserves the camera projection and separates non-local points along the
camera rays.

Current generated metrics:

- Path points: `1672`
- Path length: `2808.99 mm`
- Camera visual score: `0.794`
- Camera coverage: `0.873`
- Camera precision: `0.868`
- Clearance violations: `738`
- Minimum non-local clearance: `0.326 mm`
- Maximum segment length: `10.15 mm`
- Validation passed: `False`

This is a meaningful reduction in collisions, but the physical path is still
not manufacturable. The next solver pass must address the remaining concentrated
collisions around the `O`, `V`, and `E` while reducing twist and curvature.

Current top clearance hotspots:

- `300-399` vs `500-599`: `334` violations
- `200-299` vs `600-699`: `258` violations
- `800-899` vs `1000-1099`: `111` violations
- `800-899` vs `900-999`: `23` violations
- `200-299` vs `400-499`: `12` violations

### Smoothness-First Pass

The design direction changed after visual inspection: the LED path must flow
smoothly before we optimize the final volume. The solver now prioritizes softer
centerline curvature and slower LED/profile torsion over compactness.

Implemented changes:

- Increased the 90-degree twist length from `150 mm` to `320 mm`.
- Increased centerline Chaikin smoothing from `3` to `5` passes.
- Added final geometry/depth smoothing after clearance solving.
- Reduced maximum depth step from `10 mm` to `4 mm`.
- Reduced clearance push strength so the profile does not form hard kinks.
- Changed the physical LED ribbon frontness from boolean on/off regions to a
  continuous `mask_fit_fraction` smoothing model, so the LED face twists
  gradually instead of snapping between visible and hidden segments.

Current generated metrics:

- Path points: `1252`
- Path length: `2334.79 mm`
- Camera visual score: `0.828`
- Camera coverage: `0.910`
- Camera precision: `0.866`
- Clearance violations: `656`
- Minimum non-local clearance: `0.482 mm`
- Maximum segment length: `4.34 mm`
- P95 twist: `13.70 deg`
- P95 curvature: `0.108 1/mm`
- Validation passed: `False`

Current top clearance hotspots:

- `200-299` vs `400-499`: `471` violations
- `600-699` vs `700-799`: `179` violations
- `200-299` vs `500-599`: `6` violations

This is the preferred new baseline for the next solver pass: smoother, more
readable, and less segmented, even though clearance still needs a dedicated
zone-aware solution.

### Deep-Back Freedom Pass

The rear/depth volume was expanded so the solver can place the hidden/back
portion of the profile more freely instead of forcing tight bends near the
camera-readable silhouette.

Implemented changes:

- Increased autosized lamp depth from about `350 mm` to `650 mm`.
- Increased maximum sculptural depth from `155 mm` to `299 mm`.
- Expanded depth lanes to `[-299.0, -215.3, -137.5, -59.8, 23.9, 107.6, 203.3, 299.0]`.
- Increased minimum bend radius target from `60 mm` to `120 mm`.
- Increased connector escape margin from `60 mm` to `120 mm`.

Current generated metrics:

- Path points: `1501`
- Path length: `2645.63 mm`
- Camera visual score: `0.836`
- Camera coverage: `0.900`
- Camera precision: `0.896`
- Camera IoU: `0.815`
- Clearance violations: `550`
- Minimum non-local clearance: `1.432 mm`
- Maximum segment length: `4.28 mm`
- P95 twist: `9.67 deg`
- P95 curvature: `0.082 1/mm`
- P95 radius: `12.25 mm`
- Validation passed: `False`

Current top clearance hotspots:

- `200-299` vs `500-599`: `267` violations
- `700-799` vs `800-899`: `261` violations
- `700-799` vs `900-999`: `22` violations

This is the best overall baseline so far: smoother torsion, better readability,
lower overdraw, and fewer clearance violations. Remaining work is now mostly a
local/topological separation problem in two path zones.

Rejected alternative:

- `smooth_flowfield_single_profile` was tested as a more serpentine path. It
  produced a readable but overfilled projection: visual score `0.764`, overdraw
  `0.352`, path length `6540.51 mm`, and `43873` clearance violations. It is
  not a good direction for this lamp.

## Work Plan

1. Stabilize the project baseline and documentation.
2. Reduce self-clearance violations in the 3D path while preserving the camera
   projection.
3. Turn `scripts/08_optimizer.py` from pass-through scoring into a real
   optimization step that adjusts depth and transitions.
4. Improve transition smoothness and minimum bend radius so the swept profile is
   physically plausible.
5. Regenerate the Blender preview and exports after each solver change.
6. Keep camera readability above an agreed threshold while improving
   manufacturability.
7. Produce a final manufacturing mesh/export once validation passes.

## Acceptance Targets

Short-term target:

- Validation still allowed to fail, but clearance violations must drop
  materially from the baseline.
- Camera visual score should stay above `0.75`.
- No point may leave the lamp volume.

Manufacturing target:

- Validation passed: `True`
- Clearance violations: `0`
- Minimum non-local clearance: at least `20 mm`
- Camera visual score: at least `0.75`
- Export includes a final mesh, not only preview and diagnostic artifacts.

## Notes

The current camera projection is promising, but the physical path is not yet
safe to build. The next technical bottleneck is depth/clearance solving, not
recognizing the word from the camera.
