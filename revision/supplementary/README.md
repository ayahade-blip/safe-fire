# Supplementary Tables

| Table | Content | File |
|---|---|---|
| S1 | Development decisions and the data each consulted | `S1_development_decisions.csv` |
| S2 | Overlap audit of every training set against every evaluation set (SHA-256 and dHash); S2b: sensitivity to near duplicates | `../results/round3/overlap_round3.csv`, `overlap_pairs_round3.csv`, `../results/near_duplicate_sensitivity.csv` |
| S3 | The 16 embedding clusters, the images removed from each in the verification check, and the FPR on their held-out members | `../data/audit/cluster_table.csv`, `../results/round2/audit_removed_by_cluster.csv`, `../results/per_cluster_mining_dev.csv` |
| S4 | Every valid run (46 single-seed runs, 63 of the factorial study) | `../results/existing_models_rescored.csv`, `../results/round2/runs_all_round2.csv` |
| S5 | Alarms on each video clip, native rate and 16 frames per second; S5b: missed positive clips; S5c: first alarm on every positive clip | `../results/round2/video_per_clip_round2.csv`, `video_missed_positives.csv`, `../results/round3/video_latency_round3.csv` |
| S6 | Seed-pooled paired tests with Holm adjustment | `../results/round2/mh_mcnemar_holm.csv` |
| S7 | Thresholds of each seed under each budget rule (without the mining-development subset) | `../results/round3/budget_round3.csv` |
| S8 | mAP differences with bootstrap intervals; the audited union with and without seed 123 | `../results/round2/map_bootstrap.csv`, `../results/round3/map_audited_union_round3.csv` |
| S9 | In-domain D-Fire detection for every condition, one threshold rule; S9b: contrasts by threshold-setting negatives; ROC curves (Fig. S1); indoor share | `../results/round3/dfire_round3.csv`, `dfire_contrasts_round3.csv`, `../results/round2/dfire_roc_curves.csv`, `dfire_indoor_share.csv` |

The per-seed exact McNemar tests of version 3.0.0 remain in `../results/mcnemar_factorial.csv`; the budgets of version 3.1.0,
which included the mining-development subset, remain in `../results/round2/budget_variants.csv`.
