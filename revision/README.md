# Extended study

Everything needed to check or regenerate the numbers of the extended study: the notebooks that trained and scored every
model, the records they wrote, and the analysis that turns those records into tables.

## Contents

| Path | What |
|---|---|
| `notebooks/` | `SFS_01` to `SFS_07`, `sfs_lib.py` and `sfs_r2.py`, the libraries the notebooks write to `/content/sfs/` and import |
| `analysis/analysis_results.py` | regenerates every table value from `data/` into `results/` |
| `analysis/export_sweeps.py` | writes the full threshold sweeps behind every "R at FPR 1%" value |
| `analysis/video_tags.csv` | scene (indoor or outdoor) and annotated fire onset of each video clip |
| `data/config/` | training recipe, seeds and the list of runs |
| `data/runs/<run>/` | one folder per training run: `args.yaml` (full configuration, seed, distillation settings), `results.csv`, `timing.json`, `DONE.json` (hardware, best epoch), `job.json`, and `eval/` (per-image and per-instance scores) |
| `data/scores/<model>/` | the same per-image scores for every earlier model, re-scored with one protocol |
| `data/manifests/neg_sets.json` | the exact images of every training negative set (L-ratio, M-top, cluster coverage, random 1,638 and 3,276, background 10%, union 1,638 and 3,276, Places365-only) |
| `data/manifests/neg_PA.json` | the positive-aware set, with its rule and counts |
| `data/fresh_suite/` | the frozen test suite: `manifest.csv` (SHA-256 per image), `FROZEN.json`, `PROTOCOL.md` |
| `data/audit/hit_clusters.csv` | the 12,052 mining hits: detector score, embedding cluster and label, membership of M-top, coverage, the mining-development subset and the fire-like exclusions |
| `data/audit/` (other files) | cluster table, fire-like exclusion recount, overlap report (SHA-256 and dHash), near-duplicate pairs, positive-aware similarities, union deduplication, mining cost, re-scoring reproducibility, per-image hashes, visual-audit sample lists |
| `data/conformal/conformal_split_identities.csv` | the calibration and verification images of each conformal split of the original analysis |
| `data/video/` | per-frame detections on every video clip and the small-indoor-flame confidences |
| `results/` | the output of the analysis: one CSV per table or figure, and `summary_results.md` |
| `supplementary/` | Supplementary Tables S1 to S9 |

## Evaluation protocol

- **Image-level FPR at t:** the share of negative images whose maximum box confidence (extraction threshold 0.01) is at
  least t; an image without a box scores 0.
- **Instance recall at t:** the share of the 1,586 annotated test instances matched by a box of either class with
  IoU >= 0.5 and confidence >= t (`conf_any` in `test_pos.csv`).
- **R at FPR 1%:** instance recall at the lowest threshold of the grid 0.01..0.99 whose FPR on the named negatives is at
  most 1%; "no operating point" if none qualifies. Sweeps: `results/threshold_sweeps.csv`.
- **Pools:** hard 500 + novel 196 + mining-development 400 + cross-corpus 1,500 = 2,596 images; frozen suite: 101 + 61 + 1,500.
- **Statistics:** exact Clopper-Pearson 95% intervals, exact two-sided McNemar tests on paired per-image alarms, mean and
  sample SD over seeds 42, 123 and 2024, bootstrap over clips for video.

## Where each result is

| Result | File in `results/` |
|---|---|
| Backbone selection (6 architectures x 3 seeds) | `table1_architectures.csv` |
| Factorial study and controls (first 51 runs; all 63 in `round2/`) | `factorial_table.csv`, per run: `runs_all_with_ci.csv` |
| Paired tests | `mcnemar_factorial.csv` |
| Earlier runs re-scored | `existing_models_rescored.csv`; transfer of M-top: `table2_transfer.csv` |
| Deployed model, baseline and teacher | `table4_deployed.csv` |
| Recall at a matched budget | `table5_matched_budget.csv` |
| Miss-rate curves, LAMR, recall by size | `fppi_curves_seed42.csv`, `lamr.csv`, `fig6_recall_by_size.csv` |
| Detection of unseen fire images | `detection_side_dfire.csv` |
| Small indoor fires | `small_indoor_fires_by_condition.csv`, `clip_nn_small_fires.csv` |
| Frozen suite | `fresh_suite_endpoints.csv` |
| Conformal calibration verified on the frozen suite | `conformal_fresh_verification.csv` |
| CLIP verifier baseline | `clip_verifier_baseline.csv` |
| Class-agnostic matching | `class_agnostic_check.csv` |
| Near duplicates, clusters | `near_duplicate_sensitivity.csv`, `per_cluster_mining_dev.csv` |
| Video | `video_summary.csv`, `video_per_clip.csv`, `video_interaction_bootstrap.csv` |
| Threshold sweeps | `threshold_sweeps.csv`, `r_at_fpr1_operating_points.csv` |

## Regenerating the results

```
pip install numpy
python revision/analysis/analysis_results.py        # every table, into revision/results/
python revision/analysis/export_sweeps.py           # the threshold sweeps
```

## Re-running the experiments

The notebooks run on Google Colab in the order SFS_01 -> SFS_02 -> SFS_03 and SFS_04 -> SFS_05 -> SFS_06 -> SFS_07. They read the prepared
datasets from `SFS_SRC` (default `/content/drive/MyDrive/SAFE_FIRE`) and write every output to `SFS_OUT` (default
`/content/drive/MyDrive/SAFE_FIRE_SCOPUS`); both can be changed with environment variables. Interrupted notebooks resume
where they stopped.

### Dataset preparation

The notebooks expect these files under `SFS_SRC`. Each one can be rebuilt from public sources with the image lists of
this repository.

| File | Content | Source and image list |
|---|---|---|
| `datasets/home_fire.zip` | the two-class indoor fire dataset (classes 0 flame, 1 smoke), split 3,900 / 1,300 / 1,300 | the public dataset of Peng and Kim, YOLO-HF (IEEE Access, 2025, doi:10.1109/ACCESS.2025.3566907), used as distributed |
| `datasets/dfire_raw.zip` | D-Fire (class indices 0 smoke, 1 fire; remapped on loading) | https://github.com/gaiasd/DFireDataset |
| `eval_suite_v2/hn_holdout_500.zip`, `novel_firelike.zip`, `mined_dev.zip`, `dfire_neg_1500.zip` | the four evaluation subsets | `data/eval_suite_manifest.csv` and `revision/data/audit/hashes/suite_*.csv` (names and SHA-256) |
| `train_neg_v2/hn_train_pool.zip` | the 1,638 label-retrieved negatives | Open Images v7 training split, labels Lamp, Light bulb and Candle; file names `<Label>_<image id>.jpg`, list in `neg_sets.json` (set `L`) |
| `train_neg_v2/randbg_pool.zip` | random backgrounds | COCO 2017 validation images; file names `rbg_<12-digit COCO id>.jpg` |
| `safemine_v2/mining/round0_hits.zip`, `round0_hits.csv` | the 12,052 mining hits and their scores | Open Images v7 test split (`<image id>.jpg`) and Places365 validation (`Places365_val_<8 digits>.jpg`); list and scores in `data/audit/hit_clusters.csv` |
| `safemine_v2/manifests/*.json` | the selections of the original study | the same lists are in `data/manifests/neg_sets.json` |
| `weights/` | earlier trained weights (baseline and teacher) | `weights/` of this repository |

D-Fire negatives are named `dfneg_<D-Fire name>.jpg`. The frozen suite and the extra COCO images of R3276
(`rbgx_<COCO id>.jpg`) are downloaded and built by SFS-01. Video: FIRESENSE (https://doi.org/10.5281/zenodo.836749) and
the KMU fire and smoke clips (https://cvpr.kmu.ac.kr/dataset/dataset.htm), downloaded by SFS-05.

## Round 2

| Path | What |
|---|---|
| `notebooks/SFS_06_round2.ipynb`, `notebooks/sfs_r2.py` | audit sheets, random corpus control, domestic set, D-Fire indoor share, the 12 new runs and their scoring |
| `notebooks/SFS_07_map_stats.ipynb` | per-image validation statistics for bootstrap intervals of mAP |
| `analysis/analysis_round2.py` | every round-2 table, into `results/round2/` |
| `data/round2/audit_M.csv`, `mtop_audit_result.csv` | the audit sheets' labels and which images were removed or used as replacements |
| `data/round2/rc_manifest.csv`, `data/manifests/neg_RC.json` | the random corpus control: every candidate, its CLIP scores and why it was kept or not |
| `data/manifests/neg_MC.json`, `neg_UC.json` | audited M-top and audited union |
| `data/round2/domestic_manifest.csv`, `domestic_used.csv` | the 1,500 household images (SUN RGB-D sample folder, scene, SHA-256) |
| `data/round2/dfire_indoor.csv` | CLIP indoor/outdoor label of every D-Fire negative |
| `data/round2/val_stats/*.npz`, `test_labels.csv` | per-image validation statistics of every model; test labels |
| `data/round2/video_list_round2.csv` | every clip with its native frame rate and whether it was re-encoded |
| `data/runs/*/eval/neg_domestic.csv`, `data/scores/*/neg_domestic.csv` | domestic-set scores of every model |

Statistics of round 2: paired comparisons pool the discordant per-image alarms of the three seed pairs (McNemar test of
Mantel-Haenszel type, exact), Holm-adjusted across all 208 tests; rate differences carry 95% bootstrap intervals over images
and mAP differences 95% bootstrap intervals over the 1,300 test images. Video is evaluated at the native frame rate and after
resampling to 16 frames per second.

```
python revision/analysis/analysis_round2.py          # every round-2 table, into revision/results/round2/
```
