# SAFE-Fire

Indoor fire detection engineered to a false alarm budget: code, frozen evaluation records, trained weights and the
records of every training run.

**Aya Hade**, **Mustafa Kamil**
Department of Computer Science, College of Computer Science and Information Technology, University of Sumer, Thi Qar, Iraq
`ayahade@hs.uos.edu.iq` · ORCID `0009-0004-3051-2004`

Archived on Zenodo (all versions): https://doi.org/10.5281/zenodo.21845339

---
## Layout

| Path | What |
|---|---|
| `SAFE_FIRE_MASTER_CLEAN.ipynb` | the original study, both halves |
| `revision/` | the extended study: 51 new training runs (17 conditions x 3 seeds), every earlier run re-scored with one protocol, a test suite frozen before any model was scored, negative-set manifests, per-image scores, threshold sweeps and the scripts that regenerate every table ([details](revision/README.md)) |
| `weights/` | trained weights of the baseline, the teacher and the deployed student ([details](weights/README.md)) |
| `code/edge/` | the four scripts that run on the Jetson |
| `code/firmware/` | what is flashed onto the ESP32 node |
| `code/analysis/` | the three algorithms worth citing on their own |
| `code/app/` | the Android client, source only |
| `results/` | the tables behind the claims of the original study |
| `data/` | SHA-256 of every image in the frozen evaluation suite |
| `figures/` | Grad-CAM attention maps and their focus scores |
| `wiring/` | how the four sensors are wired to one board |

What changed in this version is listed in [`CHANGELOG.md`](CHANGELOG.md).

### `results/`

| File | Checks |
|---|---|
| `master_runs.csv` | 48 runs with every metric, including per-set false alarm rates |
| `e1_8_replication.csv` | the reference protocol reproduced from scratch: 39.4% to 10.4% FPR |
| `conformal_thresholds.csv` | the distribution-free thresholds and their verified coverage |
| `temporal_two_by_two.csv` | the persistence layer over 32.2 minutes of negative video |
| `jetson_pipeline.csv` | the device measurement |

The re-scored values of every earlier run, under the single protocol of `revision/`, are in
`revision/results/existing_models_rescored.csv`.

### `code/edge/`

| File | |
|---|---|
| `safefire_run.py` | the deployed system: camera, TensorRT, persistence, fusion, publish. `--hold-s` sets a minimum alarm hold (0 = previous behaviour) |
| `node_reader.py` | reads the node over serial and applies the fusion ladder |
| `publish.py` | writes state, events and readings to Firestore |
| `stream_server.py` | serves the live view on the local network |

### `code/analysis/`

| File | |
|---|---|
| `temporal_alarm.py` | the K-of-N persistence layer, mirrored by the Jetson, with the minimum alarm hold |
| `c2_conformal.py` | the conformal threshold with its PAC extension |
| `make_eval_manifest.py` | regenerates the fingerprints in `data/`, so the manifest is checkable |

## The evaluation suite is frozen

2,596 images in four sets: `hn_holdout_500` (500), `novel_firelike` (196), `mined_dev` (400), `dfire_neg_1500` (1,500).
Every one is fingerprinted in `data/eval_suite_manifest.csv`, so a reported rate can be checked against the exact pixels
that produced it. A second suite of 1,662 images, frozen on 2026-10-03 with its protocol before any model was scored on
it, is in `revision/data/fresh_suite/`.

## Environment

| | |
|---|---|
| Training and evaluation | Ultralytics 8.4.90, PyTorch 2.11.0, Python 3 on Google Colab. Extended-study runs: NVIDIA RTX PRO 6000 Blackwell Server Edition; the hardware and wall-clock time of every run are in `revision/data/runs/<run>/DONE.json` and `timing.json` |
| Recipe | 640-pixel input, batch 32, AdamW, lr0 0.001 with cosine decay, weight decay 0.05, 3 warm-up epochs, up to 300 epochs, patience 50, mosaic closed for the last 10 epochs, COCO-pretrained, deterministic, seeds 42, 123 and 2024 (`revision/data/config/train_config.json`, `revision/data/runs/<run>/args.yaml`) |
| Distillation | feature distillation of Ultralytics 8.4.90 (`distill_model`, `dis = 6`) on the neck features feeding the detection head; teacher `showcase__xs960__s42` |
| Deployment | Jetson Nano 4 GB, JetPack 4.6, TensorRT 8.2.1 (FP16 engine) |

## Licence

MIT for the code; see `LICENSE`. Files under `results/`, `figures/` and `revision/results/`, and the documentation, are
additionally licensed under CC BY 4.0. The weights are subject to the Ultralytics licence (see `weights/README.md`).
