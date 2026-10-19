# Supplementary Tables

| Table | Content | File |
|---|---|---|
| S1 | Development decisions and the data each consulted | `S1_development_decisions.csv` |
| S2 | Overlap audit of training and evaluation sets; sensitivity to near duplicates | `../data/audit/overlap_report.csv`, `../results/near_duplicate_sensitivity.csv` |
| S3 | The 16 embedding clusters, the images removed from each in the audit, and the FPR on their held-out members | `../data/audit/cluster_table.csv`, `../results/round2/audit_removed_by_cluster.csv`, `../results/per_cluster_mining_dev.csv` |
| S4 | Every valid run (46 earlier, 63 of the factorial study) | `../results/existing_models_rescored.csv`, `../results/round2/runs_all_round2.csv` |
| S5 | Alarms on each video clip, native rate and 16 frames per second; missed positive clips | `../results/round2/video_per_clip_round2.csv`, `../results/round2/video_missed_positives.csv` |
| S6 | Seed-pooled paired tests with Holm adjustment | `../results/round2/mh_mcnemar_holm.csv` |
| S7 | Thresholds of each seed under each budget rule | `../results/round2/budget_variants.csv` |
| S8 | mAP differences with bootstrap intervals | `../results/round2/map_bootstrap.csv` |
| S9 | In-domain D-Fire detection, ROC curves (Fig. S1), indoor share | `../results/round2/dfire_in_domain.csv`, `dfire_roc_curves.csv`, `dfire_in_domain_contrasts.csv`, `dfire_indoor_share.csv` |

The per-seed exact McNemar tests of version 3.0.0 remain in `../results/mcnemar_factorial.csv`.
