# Trained weights

| File | Model | Training data | SHA-256 |
|---|---|---|---|
| `tournament__yolo26n__s42__best.pt` | baseline: yolo26n, 640 px, seed 42 | positives only (3,900 training images) | `c5f8b26972fa6d35482a052f5b92a706488254d6400fac1db39881bdc922ba11` |
| `showcase__xs960__s42__best.pt` | teacher: yolo26s, 960 px, seed 42 | positives + the 3,276-image L-ratio and M-top union | `0131b48763c4fc3721f87d797b7c6cf965e98364830c29ede8d8efb9d4e3b4fc` |
| `kd__kd6__s42__best.pt` | deployed student: yolo26n, 640 px, seed 42, distilled from the teacher | positives + the same union | `8e3c9ec8e731a8b49874f7065179275ea5c8d7eb2cc323541da442e4d2d27b38` |

- Load with Ultralytics 8.4.90: `YOLO("weights/kd__kd6__s42__best.pt")`. Classes: 0 flame, 1 smoke.
- The baseline was trained with the recipe in the main README (640 pixels, batch 32). The teacher was trained at
  960 pixels with batch 12. The deployed student was distilled from the teacher (`dis = 6`) with batch 64 and patience 30.
- The records of the extended-study runs (configuration, seed, curves and scores) are in `revision/data/runs/`.
- The weights were trained with Ultralytics YOLO from COCO-pretrained weights; Ultralytics software and models are
  released under AGPL-3.0, which may apply to these files.
