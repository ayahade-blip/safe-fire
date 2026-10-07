# Fresh negative test suite: pre-specified evaluation protocol

Frozen at (UTC): 2026-10-03T01:04:08+00:00
SHA-256 of manifest.csv: 20c22b3af19e675effa39435c4a01e79d387567d12e1e6115b9510d3df2b4d27

## Purpose
An untouched negative set requested during peer review. No mining choice, model choice, threshold choice or
ablation decision has used, or will use, these images. They are scored once per model and reported as is.

## Composition
- F_hard: Open Images v7 VALIDATION split, labels Lamp / Light bulb / Candle (the original hard holdout used the train split).
- F_novel: Open Images v7 VALIDATION split, labels Lantern / Torch / Street light / Traffic light / Flashlight / Chandelier.
- F_cross: D-Fire negatives never used before (test-split negatives outside dfire_neg_1500, then train-split negatives).
Excluded: any image carrying a fire/flame/smoke label, smaller than 200 px, aspect ratio above 4, or matching any image
already used by the project (identical SHA-256 or dHash Hamming distance <= 4).

## Models to be evaluated (declared before scoring)
Every revision run (SAFE_FIRE_SCOPUS/runs) and every existing run (runs_master_v2.csv), at their own input size.

## Endpoints
1. Image-level false positive rate at confidence 0.50 (max box confidence over the image, extraction 0.01).
2. False positive rate at each model's 1%-budget threshold fixed beforehand on the original hard holdout.
3. Instance-level, class-agnostic recall (home_fire test split) at a 1% budget measured on each fresh subset,
   threshold grid 0.01-0.99.
Statistics: exact Clopper-Pearson 95% intervals; paired comparisons by exact McNemar tests on per-image alarms;
three-seed means with standard deviations. Primary contrasts: M-top vs no negatives, M-top vs L-ratio, M-top vs
random, each negative set with vs without distillation, positive-aware vs M-top.
