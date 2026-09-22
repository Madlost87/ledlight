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

### Backstage Sculptural Pass

The design direction shifted from "one ribbon drawing the word" toward "one
sculptural lamp profile whose hidden rear movements reveal the word only from
the privileged camera." Connectors between readable strokes now become
multi-waypoint backstage routes instead of short bridges.

Implemented changes:

- Increased autosized lamp width/height to `610 x 430 mm` while keeping depth
  at `650 mm`.
- Raised the target center to create safer top/bottom re-entry room.
- Replaced simple cubic stroke connectors with multi-waypoint rear routes that
  leave the target mask, travel behind it, and re-enter the next readable
  stroke.
- Added backstage connector controls for side sway, vertical sway, depth bias,
  depth swing, and connector samples.
- Added camera-ray-aware clamping so hidden route points stay inside the lamp
  volume after projection.
- Spread backstage routes across multiple rear depth lanes before the clearance
  solver, reducing hidden-route clustering.
- Added backstage length/depth stats to `continuous_path_LOVE.json`.

Current generated metrics:

- Path points: `2748`
- Path length: `6921.65 mm`
- Backstage weighted length: `5253.47 mm`
- Readable weighted length: `1668.18 mm`
- Backstage nodes: `2028`
- Backstage depth span: `525.53 mm`
- Camera visual score: `0.827`
- Camera coverage: `0.890`
- Camera precision: `0.896`
- Camera IoU: `0.807`
- Out of bounds points: `0`
- Clearance violations: `517`
- Minimum non-local clearance: `1.791 mm`
- Maximum segment length: `5.53 mm`
- P95 twist: `8.67 deg`
- P95 curvature: `0.074 1/mm`
- Validation passed: `False`

Current top clearance hotspots:

- `1500-1599` vs `1700-1799`: `127` violations
- `1600-1699` vs `1700-1799`: `113` violations
- `2100-2199` vs `2200-2299`: `80` violations
- `600-699` vs `900-999`: `67` violations
- `600-699` vs `2700-2747`: `59` violations

This pass is technically useful but visually rejected after side-view
inspection. It keeps readability and volume under control, but it still reads
as a few large clean arcs, not as an intentional rear tangle. The next design
step is a compact `tangle_cloud` connector mode: fewer elegant perimeter arcs,
more dense looped rear motion behind the readable target.

### Structured Tangle Cloud Pass

Implemented a structured `tangle_cloud` connector mode. Hidden connectors no
longer route around the target with large clean arcs; they now pass through
distributed rear tangle pockets using loop/figure-eight motion, alternating
depth, and camera-ray bounds clamping.

Important behavior change:

- Backstage points keep their hidden/frontness intent even if their projection
  falls over the white target mask. This prevents the rear tangle from becoming
  part of the camera-readable LED word.
- The first compact-tangle attempt was too dense and unreadable from the back
  view. It was replaced with fewer loop samples, wider side/vertical spread,
  and three distributed tangle pockets.
- The profile is now an actual closed loop: the final path point returns to the
  first point, the closing segment is sampled smoothly, and both the body
  preview and LED preview report `closed_loop: true`.

Current generated metrics:

- Path points: `2193`
- Path length: `6426.89 mm`
- Backstage weighted length: `4864.77 mm`
- Readable weighted length: `1562.12 mm`
- Backstage route model: `compact rear tangle cloud connectors`
- Backstage connector samples: `112`
- Backstage side sway: `125.0 mm`
- Backstage vertical sway: `95.0 mm`
- Backstage tangle loops: `2`
- Camera visual score: `0.848`
- Camera coverage: `0.883`
- Camera precision: `0.947`
- Camera IoU: `0.841`
- Overdraw: `0.054`
- Out of bounds points: `0`
- Clearance violations: `2500`
- Minimum non-local clearance: `0.536 mm`
- Maximum segment length: `5.41 mm`
- Validation passed: `False`

This is a better balance than the first tangle attempt: the hidden route is
still dominant, the camera view remains clean, and the rear shape is less
compressed. It still needs visual approval from back/side views before the next
technical step, which is a tangle-aware clearance/separation pass.

### Sinuous Curve And Torsion Pass

The structured tangle/loop baseline was visually promising but still too tense:
some curves and LED/profile torsions read as abrupt. This pass keeps the same
closed-loop tangle concept and softens the motion.

Implemented changes:

- Increased target minimum bend radius from `120 mm` to `180 mm`.
- Increased 90-degree twist length from `320 mm` to `520 mm`.
- Reduced camera-frame attraction and increased frame smoothing.
- Added cyclic loop-aware tangents/curvature for orientation frames, so the
  closed loop is not treated like an open path at the seam.
- Added sinuous closed-loop smoothing: stronger on hidden/backstage sections,
  light on readable sections.
- Added an anti-spike smoother for tiny local reversals that create harsh
  visible kinks.

Current generated metrics:

- Path points: `2191`
- Path length: `6288.52 mm`
- Camera visual score: `0.844`
- Camera coverage: `0.879`
- Camera precision: `0.947`
- Camera IoU: `0.838`
- Overdraw: `0.053`
- Out of bounds points: `0`
- Profile/LED closed loop: `true`
- Maximum segment length: `5.40 mm`
- Max twist: `47.07 deg`
- P95 twist: `12.39 deg`
- Max curvature: `11.645 1/mm`
- P95 curvature: `0.097 1/mm`
- P95 radius: `10.36 mm`
- Clearance violations: `2514`
- Minimum non-local clearance: `0.352 mm`
- Validation passed: `False`

This is the preferred baseline for visual inspection now: still a closed
structured groviglio, but with softer movement and fewer abrupt torsion/curve
events. The next physical step remains self-clearance separation.

Clearance note:

- A global final clearance pass after smoothing was tested. It reduced
  collision count modestly, but it increased twist/curvature and damaged the
  desired softness. It is currently disabled (`final_loop_clearance_cycles: 0`).
  The next clearance solver should be local/zone-aware, not a broad global
  depth push.

### Left Letter Readability Restore

The `L` in `LOVE` was weaker than the other letters after the sinuous/groviglio
pass. A targeted restore now finds the leftmost large white component in the
target image and raises frontness only for nearby points that still fit the
target mask. This keeps the correction image-driven instead of manually tuned to
the word `LOVE`.

Current generated metrics after restore:

- Path points: `2191`
- Path length: `6296.44 mm`
- Left component restore nodes: `114`
- Camera visual score: `0.842`
- Camera coverage: `0.893`
- Camera precision: `0.919`
- Camera IoU: `0.828`
- Overdraw: `0.081`
- Per-letter coverage: `L 0.886`, `O 0.930`, `V 0.880`, `E 0.866`
- Profile/LED closed loop: `true`
- Clearance violations: `2514`
- Minimum non-local clearance: `0.352 mm`
- Validation passed: `False`

This trades a little extra overdraw for a much clearer first letter while
keeping the closed-loop groviglio and soft-curve work intact.

### Target Config Plumbing

Target image selection is now centralized in `input/target_config.json`.
Pipeline scripts derive the active image name, target id, output JSON/TXT names,
export manifest name, and readable preview object name from that config.

Current config:

```json
{
  "target_id": "LOVE",
  "target_image_name": "target_LOVE.png"
}
```

This means changing the image no longer requires hunting through script
constants. The geometry and style algorithms are still only partially generic:
difficult logos may need future config-level controls for stroke selection,
tangle density, and readability restoration.

## Work Plan

1. Stabilize the project baseline and documentation.
2. Visually inspect the compact rear `tangle_cloud` baseline from side and
   three-quarter views.
3. Add a tangle-aware clearance solver that separates apparent crossings in
   depth without destroying the groviglio look or camera projection.
4. Turn `scripts/08_optimizer.py` from pass-through scoring into a real
   optimization step that adjusts depth and transitions.
5. Improve transition smoothness and minimum bend radius so the swept profile is
   physically plausible.
6. Regenerate the Blender preview and exports after each solver change.
7. Keep camera readability above an agreed threshold while improving
   manufacturability.
8. Produce a final manufacturing mesh/export once validation passes.

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
