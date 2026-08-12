# SAFE-Fire

Reliable lightweight fire detection for indoor IoT
alarm arriving on a phone.

**Aya Hadi**, **Mustafa Kamil**
Department of Computer Science, College of Computer Science and Information
Technology, University of Sumer, Thi Qar, Iraq
`ayahade@hs.uos.edu.iq` · ORCID `0009-0004-3051-2004`

---
## Layout

| Path | What |
|---|---|
| `SAFE_FIRE_MASTER_CLEAN.ipynb` | the whole study, both halves |
| `code/edge/` | the four scripts that run on the Jetson |
| `code/firmware/` | what is flashed onto the ESP32 node |
| `code/analysis/` | the three algorithms worth citing on their own |
| `code/app/` | the Android client, source only |
| `results/` | the five tables behind the claims |
| `data/` | SHA-256 of every image in the frozen evaluation suite |
| `figures/` | Grad-CAM attention maps and their focus scores |
| `wiring/` | how the four sensors are wired to one board |

### `results/`

Five files, chosen so that every headline number in the paper can be checked
against the run that produced it, and nothing else.

| File | Checks |
|---|---|
| `master_runs.csv` | 48 runs with every metric, including per-set false alarm rates |
| `e1_8_replication.csv` | the reference protocol reproduced from scratch: 39.4% to 10.4% FPR |
| `conformal_thresholds.csv` | the distribution-free thresholds and their verified coverage |
| `temporal_two_by_two.csv` | the persistence layer over 32.2 minutes of negative video |
| `jetson_pipeline.csv` | the device measurement |

### `code/edge/`

| File | |
|---|---|
| `safefire_run.py` | the deployed system: camera, TensorRT, persistence, fusion, publish |
| `node_reader.py` | reads the node over serial and applies the fusion ladder |
| `publish.py` | writes state, events and readings to Firestore |
| `stream_server.py` | serves the live view on the local network |

### `code/analysis/`

| File | |
|---|---|
| `temporal_alarm.py` | the K-of-N persistence layer, mirrored by the Jetson |
| `c2_conformal.py` | the conformal threshold with its PAC extension |
| `make_eval_manifest.py` | regenerates the fingerprints in `data/`, so the manifest is checkable |

## The evaluation suite is frozen

2,596 images in four sets: `hn_holdout_500` (500), `novel_firelike` (196),
`mined_dev` (400), `dfire_neg_1500` (1,500). Every one is fingerprinted in
`data/eval_suite_manifest.csv`, so a reported rate can be checked against the
exact pixels that produced it.

