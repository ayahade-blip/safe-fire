# Changelog

## 3.2.0 (2026-10-23)

- `revision/notebooks/SFS_08_hashes_and_frames.ipynb`: SHA-256 and dHash fingerprints of the frozen suite, the domestic set,
  the random-corpus pool and the extra COCO images (`revision/data/round2/hashes/`); frames of two clips for a visual check.
- `revision/analysis/analysis_round3.py` and `revision/results/round3/`: recall at a 1% budget without the mining-development
  subset (pooled 2,196 negatives; equal weight and every subset on the same three subsets; the 3,358 negatives no decision
  consulted); LAMR, FPPI curves and recall by size on the 2,196 pool; every condition with the new pooled columns; the
  vision-language verifier on the new pools; in-domain D-Fire detection for every condition with one threshold rule (grid
  0.001) in tables and bootstrap contrasts, on both D-Fire subsets and on each alone; first-alarm latency of every positive
  clip; the room-trial logs replayed at four thresholds; mAP of the audited union with and without seed 123; the complete
  overlap audit (15 training sets against 11 evaluation sets, SHA-256 and dHash) with the pair list; the yolo26n runs of the
  backbone selection beside the no-negatives runs of the factorial study.
- `revision/results/round3/dfire_fire_images_hashes.csv`: fingerprints of the 2,301 D-Fire fire images.
- `revision/data/room_trials/`: per-frame scores, node readings and run summaries of the six room-trial runs (no images).
- `revision/data/manifests/sm_manifest__round0_selected.json`: the 1,671 earlier negatives of the replication.
- `revision/analysis/video_tags.csv`: the onset of clip FS_smoke__testpos05 set to 0 s after a frame-by-frame check.
- Supplementary list: Table S2 now complete; Tables S5c and S9b added.

## 3.1.0 (2026-10-19)

- `revision/notebooks/SFS_06_round2.ipynb` and `sfs_r2.py`: visual-audit contact sheets of the mined set; a random control
  drawn from the filtered mining corpus; a domestic negative set of 1,500 household images from SUN RGB-D; the indoor share of
  the D-Fire negatives; 12 new training runs (random corpus control, audited M-top, audited union with and without
  distillation, three seeds each); the domestic set scored by every model; re-encoding and evaluation of the six video clips
  the reader could not decode.
- `revision/notebooks/SFS_07_map_stats.ipynb`: per-image validation statistics for bootstrap intervals of mAP.
- `revision/analysis/analysis_round2.py`: seed-pooled McNemar tests of Mantel-Haenszel type with Holm adjustment, bootstrap
  intervals for rate and mAP differences, recall at a 1% budget set per subset and with subsets weighted equally, in-domain
  D-Fire detection and ROC curves, video at the native rate and at 16 frames per second, per-clip analysis of missed clips.
- `revision/data/`: records of the 12 new runs; domestic-set scores of every model; `round2/` with the audit result, the
  manifests of the random corpus control and of the domestic set, the D-Fire indoor labels, the test labels and the per-image
  validation statistics; video detections on every clip for the new runs and on the re-encoded clips for the earlier models.
- `revision/results/round2/`: the output of `analysis_round2.py`.
- `revision/README.md`: the guide to `revision/` (its link in the main README was broken in 3.0.0).
- `code/edge/notify.py`: the optional push sender run on the board (`--notify-edge`), which `safefire_run.py` imports.
- `code/cloud/`: the Cloud Function that sends the push notification for every new ALERT or CONFIRMED event.

## 3.0.0 (2026-10-07)

- `revision/`: the extended study. Notebooks SFS-01 to SFS-05 and their library; the analysis script; the records of 51
  new training runs (17 conditions x 3 seeds) and of every earlier model re-scored with one protocol; negative-set
  manifests with mining scores, cluster labels and fire-like exclusions; a test suite frozen before any model was scored
  on it, with its protocol; overlap audit by SHA-256 and dHash; per-image scores; full threshold sweeps; conformal split
  identities; per-frame video detections; result tables and Supplementary Tables S1 to S6.
- `weights/`: trained weights of the baseline (yolo26n, seed 42), the teacher (yolo26s at 960 pixels) and the deployed
  student (kd6).
- `code/edge/safefire_run.py`: `--hold-s`, a minimum alarm hold; 0 keeps the previous behaviour. Checked by replaying the
  recorded room-trial frames; not yet run on the device.
- `code/analysis/temporal_alarm.py`: `hold_s` in `run_video`; 0 keeps the previous behaviour.
- `code/firmware/safefire_node.ino`: the derived flame fields (`flameDropMv`, `flameIr`) are published as `null`, not `0`,
  when the flame channel is unhealthy or has no baseline. Not yet flashed onto the node.
- README: layout of this version, environment, and dataset preparation.
