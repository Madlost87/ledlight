# ANAMORPHIC_LAMP Roadmap

This document tracks the path from the current Blender/Python prototype to a
physically plausible anamorphic table lamp.

## Goal

Create a table lamp generated from one continuous physical profile and one
continuous LED channel. From the privileged camera view it should read `LOVE`;
from other views it should remain a sculptural lamp, not separated 3D text.

## Current Baseline

Generated from the current `output/export` artifacts:

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
