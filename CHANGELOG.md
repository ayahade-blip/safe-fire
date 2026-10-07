# Changelog

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
