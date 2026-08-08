# SAFE-Fire

Code, frozen evaluation records, and figures for **"SAFE-Fire: Bounding False
Alarms in a Deployed Indoor Fire-Detection IoT System."**

Every number and every figure in the paper is produced by something in this
archive. If a number in the paper cannot be traced to a file here, treat that as
a bug and open an issue.

---

## What is here

```
code/       the scripts that produce the numbers, plus the sensor firmware
data/       provenance and manifests for the frozen evaluation sets
results/    every CSV and device log the paper draws on
figures/    the figures as published
```

## Layout in detail

### `code/`

| File | Produces |
|---|---|
| `c2_conformal.py` | the reliability suite, conformal thresholds, PAC certificate |
| `c2_figures.py` | Fig. 4 |
| `detect_video.py` | per-frame detections from video, written once at low confidence |
| `temporal_alarm.py` | the K-of-N layer with IoU association, and its metrics |
| `c3_analysis.py` | the parameter sweep and the two-by-two |
| `c3_figure.py` | Fig. 5 |
| `c3_what_temporal_can_do.py` | the analysis written **before** any video was processed |
| `E1_8_colab_cell.py` | the from-scratch replication of the reference protocol |
| `E1_8_cell2_eval.py` | false-alarm scan for the replication |
| `E1_8_cell3_map.py` | accuracy for the replication |
| `fp16_ref.py`, `fp16_cmp.py` | numerical fidelity of the engine against PyTorch |
| `build_int8.py` | INT8 engine with entropy calibration on real images |
| `engine_cmp.py` | FP16 against INT8, throughput and reliability |
| `bench_engine.py` | engine-only throughput |
| `cam_infer.py`, `cam_infer2.py` | the camera pipeline before and after optimisation |
| `neg_fpr.py` | on-device false-alarm scan |
| `soak.py` | five-minute thermal soak in thirty-second windows |
| `measure_mq2.ino` | gas channel: burn-in logger and measurement |
| `measure_mlx90614.ino` | thermal channel: bring-up, noise floor, measurement |

Inference is deliberately separated from the decision policy. Detections are
extracted once at confidence 0.10 and written to CSV; every subsequent choice of
threshold, K, N and IoU reads those files. A full parameter sweep therefore costs
seconds instead of one inference pass per combination.

### `results/`

Grouped by the table it feeds.

| Files | Table |
|---|---|
| `paper_runs.csv`, `statistical_robustness_*.csv` | 4 |
| `controls_summary.csv`, `fpr_NOVEL_*.csv`, `crossdataset_DFire_*.csv`, `dfire_indomain_*.csv`, `dfire_posonly_*.csv` | 5 |
| `e1_8_results.csv`, `e1_8_deltas.csv` | 6 |
| `E2_1` … `E2_4` | 7 |
| `E3_1_sweep.csv`, `E3_2_two_by_two.csv` | 8 |
| `jetson_pipeline.csv`, `jetson_soak.csv`, `jetson_logs/` | 9 |
| `indoor_suppression.csv` | 10 |
| `mq2_trials.csv`, `mlx90614_trials.csv` | 11 |
| `pareto_FINAL_*.csv` | Fig. 3 |

`jetson_logs/` holds the raw device output rather than a summary, because the
summary is the thing under scrutiny.

### `figures/`

| File | Paper figure |
|---|---|
| `pareto_FINAL.png` | 3 |
| `fig_C2_conformal.png` | 4 |
| `fig_C3_temporal.png` | 5 |
| `fig_indoor_suppression.jpg` | 6 |
| `fig6_qualitative_fp.png`, `recall_at_fpr1_bar.png`, `hn_ratio_curve.png` | supporting |
| `camera_first_light.jpg` | first frame captured on the deployed device |

---

## Reproducing the results

The parts that need no GPU and no hardware:

```bash
python code/c2_conformal.py      # reliability suite, thresholds, PAC certificate
python code/c3_analysis.py       # sweep and two-by-two, from the detection CSVs
python code/c3_figure.py         # Fig. 5
```

The parts that need a GPU: `E1_8_*.py` retrain from scratch, about eight hours on
an L4 for both conditions.

The parts that need the device: everything under `code/` named for the Jetson,
plus the two `.ino` sketches, which need an ESP32 and the wiring described in the
paper.

---

## What is not here, and why

**Raw imagery.** The frozen evaluation sets are built from third-party corpora
under their own licences, and redistributing them here would breach those terms.
`data/` gives the provenance and the reconstruction procedure instead.

**Trained weights.** Available on request. They are large and the archive has a
file-count limit.

---

## Honest notes

The paper reports a result that works against the method: mining fire-like
negatives suppresses detection of small, spatially compact fires in dark rooms.
`results/indoor_suppression.csv` and `figures/fig_indoor_suppression.jpg` are the
evidence for it. They are in this archive on purpose.

Detection accuracy does not transfer across corpora; we measured a drop of about
half on an independent set. Claims in the paper about detection are in-domain.
Claims about false alarms survive the corpus change.

---

## Citation

See `CITATION.cff`. Cite the concept DOI, which always resolves to the latest
version.

## Licence

Code under MIT, see `LICENSE`. Results, figures and documentation under
CC BY 4.0.
