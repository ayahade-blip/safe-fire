# Results of the revision runs (SFS_01-05)
new runs: 51 | rescored existing models: 50
test instances: 1586 | negatives: hard 500, novel 196, mining-dev 400, cross-corpus 1500, fresh hard 101, fresh novel 61, fresh cross-corpus 1500

## 1. Factorial and controls: three-seed mean ± SD (yolo26n, 640 px, same recipe, same GPU type)
  N0     KD=no  mAP50 0.9086 ± 0.0009   hard 27.07 ± 1.45 novel 18.03 ± 2.06 cross 12.09 ± 0.77 Fcross 11.04 ± 2.02 R@1%hard 0.185 ± 0.016 R@1%pool 0.222 ± 0.023
  N0     KD=yes mAP50 0.9216 ± 0.0055   hard 25.67 ± 1.68 novel 20.58 ± 1.06 cross 9.56 ± 0.47  Fcross 10.31 ± 0.97 R@1%hard 0.145 ± 0.060 R@1%pool 0.232 ± 0.027
  L      KD=no  mAP50 0.9060 ± 0.0071   hard 1.13 ± 0.31  novel 4.25 ± 2.99  cross 7.84 ± 0.60  Fcross 6.96 ± 1.39  R@1%hard 0.814 ± 0.061 R@1%pool 0.501 ± 0.034
  L      KD=yes mAP50 0.9101 ± 0.0037   hard 2.20 ± 0.40  novel 5.44 ± 0.59  cross 7.71 ± 2.47  Fcross 6.87 ± 1.87  R@1%hard 0.685 ± 0.049 R@1%pool 0.551 ± 0.080
  M      KD=no  mAP50 0.8996 ± 0.0092   hard 1.13 ± 0.46  novel 1.53 ± 0.00  cross 3.71 ± 1.30  Fcross 1.56 ± 0.27  R@1%hard 0.801 ± 0.062 R@1%pool 0.685 ± 0.007
  M      KD=yes mAP50 0.9101 ± 0.0043   hard 2.27 ± 0.46  novel 3.74 ± 1.64  cross 3.02 ± 0.63  Fcross 1.84 ± 0.54  R@1%hard 0.701 ± 0.049 R@1%pool 0.662 ± 0.006
  U1638  KD=no  mAP50 0.9040 ± 0.0081   hard 1.00 ± 0.87  novel 1.87 ± 1.06  cross 3.71 ± 0.51  Fcross 1.98 ± 0.34  R@1%hard 0.821 ± 0.037 R@1%pool 0.680 ± 0.022
  U1638  KD=yes mAP50 0.9158 ± 0.0032   hard 1.53 ± 0.50  novel 2.72 ± 0.29  cross 3.22 ± 0.42  Fcross 2.02 ± 0.34  R@1%hard 0.748 ± 0.085 R@1%pool 0.714 ± 0.022
  U3276  KD=no  mAP50 0.9095 ± 0.0033   hard 0.20 ± 0.00  novel 1.02 ± 0.88  cross 3.02 ± 0.58  Fcross 1.64 ± 0.75  R@1%hard 0.888 ± 0.008 R@1%pool 0.702 ± 0.007
  U3276  KD=yes mAP50 0.9087 ± 0.0107   hard 0.87 ± 0.42  novel 2.72 ± 1.06  cross 2.24 ± 0.71  Fcross 1.93 ± 0.27  R@1%hard 0.805 ± 0.029 R@1%pool 0.715 ± 0.038
  R      KD=no  mAP50 0.9036 ± 0.0002   hard 8.93 ± 1.75  novel 5.78 ± 1.56  cross 4.91 ± 0.51  Fcross 4.53 ± 0.35  R@1%hard 0.315 ± 0.062 R@1%pool 0.442 ± 0.064
  R3276  KD=yes mAP50 0.9037 ± 0.0059   hard 7.53 ± 0.61  novel 6.29 ± 1.18  cross 4.07 ± 1.10  Fcross 3.89 ± 0.40  R@1%hard 0.373 ± 0.060 R@1%pool 0.529 ± 0.033
  C      KD=no  mAP50 0.9088 ± 0.0030   hard 4.00 ± 0.53  novel 3.40 ± 0.29  cross 3.82 ± 0.25  Fcross 1.73 ± 0.58  R@1%hard 0.535 ± 0.163 R@1%pool 0.639 ± 0.018
  BG10   KD=no  mAP50 0.9051 ± 0.0039   hard 16.40 ± 3.33 novel 12.07 ± 1.64 cross 7.02 ± 0.53  Fcross 6.33 ± 0.13  R@1%hard 0.230 ± 0.072 R@1%pool 0.319 ± 0.043
  P      KD=no  mAP50 0.9057 ± 0.0059   hard 4.00 ± 0.20  novel 3.91 ± 0.59  cross 3.22 ± 1.04  Fcross 1.33 ± 0.64  R@1%hard 0.508 ± 0.107 R@1%pool 0.641 ± 0.054
  PA     KD=no  mAP50 0.9046 ± 0.0098   hard 1.00 ± 0.53  novel 2.55 ± 0.51  cross 2.67 ± 0.81  Fcross 1.64 ± 0.28  R@1%hard 0.852 ± 0.043 R@1%pool 0.719 ± 0.056
  PA     KD=yes mAP50 0.9127 ± 0.0056   hard 1.47 ± 0.64  novel 3.57 ± 0.51  cross 4.67 ± 1.17  Fcross 2.36 ± 0.42  R@1%hard 0.741 ± 0.111 R@1%pool 0.657 ± 0.016

## 2. Paired comparisons (exact McNemar on per-image alarms at 0.50), per seed
  contrast                         subset             A<B sig  A>B sig  (alarms A vs B, per seed)
  distillation, no negatives       hard               0/3      0/3      138:139(p=1) 123:140(p=0.0639) 124:127(p=0.828)
  distillation, no negatives       novel              0/3      0/3      41:36(p=0.458) 38:31(p=0.265) 42:39(p=0.736)
  distillation, no negatives       cross-corpus       3/3      0/3      151:181(p=0.0451) 142:170(p=0.0358) 137:193(p=0)
  distillation, no negatives       fresh cross-corpus 0/3      0/3      171:200(p=0.0559) 150:143(p=0.643) 143:154(p=0.439)
  distillation, L-ratio            hard               0/3      1/3      9:6(p=0.375) 11:7(p=0.344) 13:4(p=0.0117)
  distillation, L-ratio            novel              0/3      1/3      10:6(p=0.344) 10:15(p=0.359) 12:4(p=0.0215)
  distillation, L-ratio            cross-corpus       0/3      1/3      158:127(p=0.0144) 100:117(p=0.159) 89:109(p=0.0901)
  distillation, L-ratio            fresh cross-corpus 1/3      1/3      135:111(p=0.0416) 83:121(p=0.0012) 91:81(p=0.395)
  distillation, M-top              hard               0/3      1/3      10:7(p=0.607) 14:7(p=0.143) 10:3(p=0.0391)
  distillation, M-top              novel              0/3      1/3      6:3(p=0.375) 5:3(p=0.625) 11:3(p=0.0215)
  distillation, M-top              cross-corpus       1/3      0/3      38:36(p=0.845) 56:75(p=0.0395) 42:56(p=0.0814)
  distillation, M-top              fresh cross-corpus 0/3      0/3      22:24(p=0.864) 37:27(p=0.184) 24:19(p=0.5)
  distillation, union 1,638        hard               0/3      0/3      10:10(p=1) 5:2(p=0.375) 8:3(p=0.18)
  distillation, union 1,638        novel              0/3      0/3      6:3(p=0.453) 5:2(p=0.375) 5:6(p=1)
  distillation, union 1,638        cross-corpus       1/3      0/3      41:64(p=0.0052) 52:49(p=0.791) 52:54(p=0.883)
  distillation, union 1,638        fresh cross-corpus 0/3      0/3      26:29(p=0.766) 36:25(p=0.169) 29:35(p=0.441)
  distillation, union 3,276        hard               0/3      0/3      5:1(p=0.219) 6:1(p=0.125) 2:1(p=1)
  distillation, union 3,276        novel              0/3      0/3      6:1(p=0.0625) 7:4(p=0.375) 3:1(p=0.5)
  distillation, union 3,276        cross-corpus       1/3      0/3      45:43(p=0.851) 32:55(p=0.0038) 24:38(p=0.0869)
  distillation, union 3,276        fresh cross-corpus 0/3      1/3      29:15(p=0.0288) 33:37(p=0.665) 25:22(p=0.761)
  distillation, PA                 hard               0/3      1/3      6:4(p=0.688) 5:8(p=0.581) 11:3(p=0.0215)
  distillation, PA                 novel              0/3      0/3      7:4(p=0.375) 8:6(p=0.688) 6:5(p=1)
  distillation, PA                 cross-corpus       0/3      2/3      88:29(p=0) 69:53(p=0.0519) 53:38(p=0.0237)
  distillation, PA                 fresh cross-corpus 0/3      1/3      28:28(p=1) 39:26(p=0.0789) 39:20(p=0.0054)
  M-top vs L-ratio                 hard               0/3      0/3      7:6(p=1) 7:7(p=1) 3:4(p=1)
  M-top vs L-ratio                 novel              1/3      0/3      3:6(p=0.375) 3:15(p=0.0005) 3:4(p=1)
  M-top vs L-ratio                 cross-corpus       3/3      0/3      36:127(p=0) 75:117(p=0.0001) 56:109(p=0)
  M-top vs L-ratio                 fresh cross-corpus 3/3      0/3      24:111(p=0) 27:121(p=0) 19:81(p=0)
  M-top vs random                  hard               3/3      0/3      7:35(p=0) 7:47(p=0) 3:52(p=0)
  M-top vs random                  novel              2/3      0/3      3:8(p=0.125) 3:12(p=0.0039) 3:14(p=0.0034)
  M-top vs random                  cross-corpus       1/3      0/3      36:67(p=0.0005) 75:82(p=0.538) 56:72(p=0.0888)
  M-top vs random                  fresh cross-corpus 3/3      0/3      24:74(p=0) 27:65(p=0) 19:65(p=0)
  L-ratio vs random                hard               3/3      0/3      6:35(p=0) 7:47(p=0) 4:52(p=0)
  L-ratio vs random                novel              1/3      0/3      6:8(p=0.727) 15:12(p=0.607) 4:14(p=0.0129)
  L-ratio vs random                cross-corpus       0/3      3/3      127:67(p=0) 117:82(p=0.0016) 109:72(p=0.0003)
  L-ratio vs random                fresh cross-corpus 0/3      2/3      111:74(p=0.0006) 121:65(p=0) 81:65(p=0.129)
  M-top vs coverage                hard               3/3      0/3      7:21(p=0.0043) 7:22(p=0.0026) 3:17(p=0.0013)
  M-top vs coverage                novel              0/3      0/3      3:7(p=0.219) 3:7(p=0.219) 3:6(p=0.25)
  M-top vs coverage                cross-corpus       1/3      1/3      36:59(p=0.0004) 75:53(p=0.0103) 56:60(p=0.678)
  M-top vs coverage                fresh cross-corpus 0/3      0/3      24:16(p=0.115) 27:32(p=0.551) 19:30(p=0.0895)
  Places-only vs L-ratio           hard               0/3      3/3      19:6(p=0.0106) 20:7(p=0.0146) 21:4(p=0.0005)
  Places-only vs L-ratio           novel              1/3      0/3      9:6(p=0.508) 7:15(p=0.0386) 7:4(p=0.508)
  Places-only vs L-ratio           cross-corpus       3/3      0/3      53:127(p=0) 61:117(p=0) 31:109(p=0)
  Places-only vs L-ratio           fresh cross-corpus 3/3      0/3      24:111(p=0) 27:121(p=0) 9:81(p=0)
  Places-only vs random            hard               3/3      0/3      19:35(p=0.0113) 20:47(p=0) 21:52(p=0)
  Places-only vs random            novel              1/3      0/3      9:8(p=1) 7:12(p=0.18) 7:14(p=0.0156)
  Places-only vs random            cross-corpus       2/3      0/3      53:67(p=0.161) 61:82(p=0.0275) 31:72(p=0)
  Places-only vs random            fresh cross-corpus 3/3      0/3      24:74(p=0) 27:65(p=0) 9:65(p=0)
  PA vs M-top                      hard               0/3      0/3      4:7(p=0.549) 8:7(p=1) 3:3(p=1)
  PA vs M-top                      novel              0/3      0/3      4:3(p=1) 6:3(p=0.25) 5:3(p=0.625)
  PA vs M-top                      cross-corpus       2/3      0/3      29:36(p=0.382) 53:75(p=0.0141) 38:56(p=0.0133)
  PA vs M-top                      fresh cross-corpus 0/3      0/3      28:24(p=0.608) 26:27(p=1) 20:19(p=1)
  union 3,276 vs union 1,638       hard               1/3      0/3      1:10(p=0.0039) 1:2(p=1) 1:3(p=0.625)
  union 3,276 vs union 1,638       novel              0/3      0/3      1:3(p=0.5) 4:2(p=0.625) 1:6(p=0.0625)
  union 3,276 vs union 1,638       cross-corpus       2/3      0/3      43:64(p=0.0011) 55:49(p=0.451) 38:54(p=0.007)
  union 3,276 vs union 1,638       fresh cross-corpus 1/3      0/3      15:29(p=0.0336) 37:25(p=0.104) 22:35(p=0.0533)
  union+KD vs random 3,276+KD      hard               3/3      0/3      5:35(p=0) 6:37(p=0) 2:41(p=0)
  union+KD vs random 3,276+KD      novel              1/3      0/3      6:11(p=0.18) 7:11(p=0.289) 3:15(p=0.0018)
  union+KD vs random 3,276+KD      cross-corpus       2/3      0/3      45:50(p=0.603) 32:80(p=0) 24:53(p=0.0002)
  union+KD vs random 3,276+KD      fresh cross-corpus 3/3      0/3      29:52(p=0.0032) 33:59(p=0.0011) 25:64(p=0)
  random vs background 10%         hard               3/3      0/3      35:101(p=0) 47:75(p=0.0001) 52:70(p=0.0096)
  random vs background 10%         novel              2/3      0/3      8:26(p=0) 12:25(p=0.001) 14:20(p=0.18)
  random vs background 10%         cross-corpus       3/3      0/3      67:97(p=0.0064) 82:113(p=0.0032) 72:106(p=0.002)
  random vs background 10%         fresh cross-corpus 2/3      0/3      74:93(p=0.0671) 65:95(p=0.0035) 65:97(p=0.002)

## 3. Existing models re-scored with the unified definition (instance recall, grid 0.01-0.99)
  Table 1 (architectures, 3 seeds, unified definition):
   yolo26s  mAP50-95 0.6012 ± 0.0096  mAP50 0.9215 ± 0.0067  FPR hard 26.40 ± 2.03  R@1% 0.128 ± 0.015  thr 0.94/0.94/0.94
   yolov8s  mAP50-95 0.5892 ± 0.0052  mAP50 0.9145 ± 0.0027  FPR hard 30.53 ± 1.17  R@1% 0.164 ± 0.028  thr 0.89/0.88/0.9
   yolo11s  mAP50-95 0.5891 ± 0.0099  mAP50 0.9057 ± 0.0121  FPR hard 33.73 ± 0.99  R@1% 0.094 ± 0.035  thr 0.91/0.91/0.9
   yolo26n  mAP50-95 0.5842 ± 0.0074  mAP50 0.9012 ± 0.0102  FPR hard 26.93 ± 1.17  R@1% 0.140 ± 0.014  thr 0.93/0.92/0.93
   yolo11n  mAP50-95 0.5824 ± 0.0053  mAP50 0.9014 ± 0.0101  FPR hard 32.53 ± 1.17  R@1% 0.123 ± 0.002  thr 0.89/0.89/0.89
   yolov8n  mAP50-95 0.5798 ± 0.0050  mAP50 0.9076 ± 0.0045  FPR hard 32.07 ± 0.31  R@1% 0.133 ± 0.051  thr 0.91/0.89/0.9
  M-top transfer to other nano architectures (old runs; mined runs are seed 42 only):
   yolo26n  FPR hard 26.93 ± 1.17 -> 1.40 [0.56, 2.86] | R@1% 0.140 ± 0.014 -> 0.772 (thr 0.65) | 1:131 p=4.9e-38
   yolo11n  FPR hard 32.53 ± 1.17 -> 2.20 [1.10, 3.90] | R@1% 0.123 ± 0.002 -> 0.755 (thr 0.69) | 4:160 p=2.5e-42
   yolov8n  FPR hard 32.07 ± 0.31 -> 2.80 [1.54, 4.65] | R@1% 0.133 ± 0.051 -> 0.674 (thr 0.73) | 1:149 p=2.1e-43
  Table 4 (seed 42 models re-scored; paper value in brackets):
   Baseline yolo26n (no negatives)  mAP50 0.9049 (0.9049)    hard 27.40 [23.53, 31.54] novel 18.37 [13.21, 24.51] cross 10.73 [9.21, 12.41]  Fcross 9.27 [7.85, 10.85]   R@1% 0.128 at 0.93
   Deployed model kd6               mAP50 0.9195 (0.9325)    hard 1.20 [0.44, 2.59]    novel 1.53 [0.32, 4.41]    cross 1.67 [1.08, 2.45]    Fcross 1.07 [0.61, 1.73]    R@1% 0.803 at 0.51
   Teacher yolo26s@960              mAP50 0.9346 (0.9346)    hard 0.20 [0.01, 1.11]    novel 1.53 [0.32, 4.41]    cross 2.40 [1.69, 3.31]    Fcross 1.60 [1.03, 2.37]    R@1% 0.931 at 0.11

## 4. Recall at a matched false alarm budget (fine grid), three-seed mean ± SD
  pooled 2,596             No negatives                               thr 0.91/0.91/0.93 FPR 0.76 ± 0.23    recall 0.2215 ± 0.0228
  pooled 2,596             Background 10% (433)                       thr 0.89/0.91/0.89 FPR 0.90 ± 0.02    recall 0.3190 ± 0.0431
  pooled 2,596             Random, 1,638                              thr 0.85/0.89/0.86 FPR 0.87 ± 0.16    recall 0.4416 ± 0.0636
  pooled 2,596             L-ratio, 1,638                             thr 0.83/0.86/0.87 FPR 0.87 ± 0.12    recall 0.5008 ± 0.0339
  pooled 2,596             M-top, 1,638                               thr 0.76/0.78/0.76 FPR 0.95 ± 0.02    recall 0.6854 ± 0.0067
  pooled 2,596             Cluster coverage, 1,638                    thr 0.81/0.81/0.82 FPR 0.85 ± 0.04    recall 0.6393 ± 0.0182
  pooled 2,596             Places365-only, 1,638                      thr 0.81/0.82/0.76 FPR 0.90 ± 0.06    recall 0.6410 ± 0.0545
  pooled 2,596             Positive-aware, 1,638                      thr 0.66/0.77/0.81 FPR 0.95 ± 0.02    recall 0.7186 ± 0.0561
  pooled 2,596             Union, 3,276                               thr 0.77/0.72/0.76 FPR 0.94 ± 0.04    recall 0.7016 ± 0.0073
  pooled 2,596             Union, 3,276 + KD                          thr 0.72/0.65/0.57 FPR 0.96 ± 0.00    recall 0.7150 ± 0.0382
  pooled 2,596             Random, 3,276 + KD                         thr 0.82/0.83/0.82 FPR 0.91 ± 0.06    recall 0.5292 ± 0.0331
  pooled 2,596             Background 10% (paper model, batch 128)    thr 0.9            FPR 0.81 ± 0.00    recall 0.2970 ± 0.0000
  pooled 2,596             Deployed kd6 (paper model)                 thr 0.62           FPR 0.92 ± 0.00    recall 0.7598 ± 0.0000
  pooled 2,596             No negatives (paper model)                 thr 0.92           FPR 0.81 ± 0.00    recall 0.1910 ± 0.0000
  fresh 1,662              No negatives                               thr 0.89/0.9/0.92  FPR 0.70 ± 0.30    recall 0.2953 ± 0.0432
  fresh 1,662              Background 10% (433)                       thr 0.88/0.9/0.9   FPR 0.82 ± 0.07    recall 0.3375 ± 0.0437
  fresh 1,662              Random, 1,638                              thr 0.84/0.87/0.84 FPR 0.90 ± 0.10    recall 0.5059 ± 0.0451
  fresh 1,662              L-ratio, 1,638                             thr 0.8/0.86/0.84  FPR 0.92 ± 0.03    recall 0.5553 ± 0.0810
  fresh 1,662              M-top, 1,638                               thr 0.63/0.66/0.57 FPR 0.94 ± 0.03    recall 0.7692 ± 0.0098
  fresh 1,662              Cluster coverage, 1,638                    thr 0.63/0.69/0.75 FPR 0.96 ± 0.00    recall 0.7547 ± 0.0306
  fresh 1,662              Places365-only, 1,638                      thr 0.68/0.72/0.58 FPR 0.96 ± 0.00    recall 0.7623 ± 0.0332
  fresh 1,662              Positive-aware, 1,638                      thr 0.66/0.61/0.59 FPR 0.94 ± 0.03    recall 0.7997 ± 0.0177
  fresh 1,662              Union, 3,276                               thr 0.52/0.69/0.56 FPR 0.84 ± 0.10    recall 0.7886 ± 0.0602
  fresh 1,662              Union, 3,276 + KD                          thr 0.62/0.64/0.6  FPR 0.96 ± 0.00    recall 0.7388 ± 0.0157
  fresh 1,662              Random, 3,276 + KD                         thr 0.78/0.78/0.8  FPR 0.92 ± 0.03    recall 0.5979 ± 0.0415
  fresh 1,662              Background 10% (paper model, batch 128)    thr 0.86           FPR 0.90 ± 0.00    recall 0.4678 ± 0.0000
  fresh 1,662              Deployed kd6 (paper model)                 thr 0.51           FPR 0.90 ± 0.00    recall 0.8026 ± 0.0000
  fresh 1,662              No negatives (paper model)                 thr 0.91           FPR 0.90 ± 0.00    recall 0.2503 ± 0.0000
  by size at the 1% pooled budget:
   No negatives                               small  n=785  recall 0.031 ± 0.021   [0.024, 0.039]
   No negatives                               medium n=440  recall 0.281 ± 0.051   [0.257, 0.306]
   No negatives                               large  n=361  recall 0.563 ± 0.034   [0.533, 0.593]
   Background 10% (433)                       small  n=785  recall 0.091 ± 0.031   [0.080, 0.104]
   Background 10% (433)                       medium n=440  recall 0.449 ± 0.084   [0.422, 0.477]
   Background 10% (433)                       large  n=361  recall 0.656 ± 0.021   [0.626, 0.684]
   Random, 1,638                              small  n=785  recall 0.207 ± 0.070   [0.191, 0.224]
   Random, 1,638                              medium n=440  recall 0.609 ± 0.098   [0.582, 0.636]
   Random, 1,638                              large  n=361  recall 0.747 ± 0.013   [0.720, 0.773]
   L-ratio, 1,638                             small  n=785  recall 0.286 ± 0.011   [0.268, 0.304]
   L-ratio, 1,638                             medium n=440  recall 0.689 ± 0.056   [0.663, 0.714]
   L-ratio, 1,638                             large  n=361  recall 0.740 ± 0.070   [0.712, 0.766]
   M-top, 1,638                               small  n=785  recall 0.549 ± 0.004   [0.529, 0.569]
   M-top, 1,638                               medium n=440  recall 0.797 ± 0.023   [0.774, 0.818]
   M-top, 1,638                               large  n=361  recall 0.846 ± 0.014   [0.823, 0.867]
   Cluster coverage, 1,638                    small  n=785  recall 0.474 ± 0.037   [0.454, 0.495]
   Cluster coverage, 1,638                    medium n=440  recall 0.782 ± 0.004   [0.759, 0.804]
   Cluster coverage, 1,638                    large  n=361  recall 0.825 ± 0.002   [0.801, 0.847]
   Places365-only, 1,638                      small  n=785  recall 0.490 ± 0.075   [0.470, 0.511]
   Places365-only, 1,638                      medium n=440  recall 0.770 ± 0.027   [0.746, 0.792]
   Places365-only, 1,638                      large  n=361  recall 0.812 ± 0.046   [0.787, 0.835]
   Positive-aware, 1,638                      small  n=785  recall 0.600 ± 0.094   [0.580, 0.620]
   Positive-aware, 1,638                      medium n=440  recall 0.814 ± 0.025   [0.792, 0.834]
   Positive-aware, 1,638                      large  n=361  recall 0.861 ± 0.020   [0.839, 0.881]
   Union, 3,276                               small  n=785  recall 0.578 ± 0.011   [0.558, 0.598]
   Union, 3,276                               medium n=440  recall 0.798 ± 0.003   [0.776, 0.820]
   Union, 3,276                               large  n=361  recall 0.852 ± 0.011   [0.830, 0.873]
   Union, 3,276 + KD                          small  n=785  recall 0.614 ± 0.045   [0.594, 0.634]
   Union, 3,276 + KD                          medium n=440  recall 0.804 ± 0.027   [0.781, 0.825]
   Union, 3,276 + KD                          large  n=361  recall 0.826 ± 0.039   [0.803, 0.849]
   Random, 3,276 + KD                         small  n=785  recall 0.328 ± 0.040   [0.309, 0.348]
   Random, 3,276 + KD                         medium n=440  recall 0.708 ± 0.027   [0.683, 0.733]
   Random, 3,276 + KD                         large  n=361  recall 0.748 ± 0.029   [0.721, 0.774]
   Background 10% (paper model, batch 128)    small  n=785  recall 0.085 ± 0.000   [0.067, 0.107]
   Background 10% (paper model, batch 128)    medium n=440  recall 0.386 ± 0.000   [0.341, 0.434]
   Background 10% (paper model, batch 128)    large  n=361  recall 0.648 ± 0.000   [0.596, 0.697]
   Deployed kd6 (paper model)                 small  n=785  recall 0.674 ± 0.000   [0.640, 0.707]
   Deployed kd6 (paper model)                 medium n=440  recall 0.823 ± 0.000   [0.784, 0.857]
   Deployed kd6 (paper model)                 large  n=361  recall 0.870 ± 0.000   [0.831, 0.903]
   No negatives (paper model)                 small  n=785  recall 0.015 ± 0.000   [0.008, 0.027]
   No negatives (paper model)                 medium n=440  recall 0.216 ± 0.000   [0.178, 0.257]
   No negatives (paper model)                 large  n=361  recall 0.543 ± 0.000   [0.490, 0.595]

## 5. Miss rate against false positives per image (pooled 2,596 negatives), log-average miss rate over FPPI 0.01-1
  No negatives                 LAMR 0.265 ± 0.005
  Background 10% (433)         LAMR 0.209 ± 0.007
  Random, 1,638                LAMR 0.179 ± 0.001
  L-ratio, 1,638               LAMR 0.169 ± 0.022
  M-top, 1,638                 LAMR 0.136 ± 0.016
  Cluster coverage, 1,638      LAMR 0.127 ± 0.014
  Places365-only, 1,638        LAMR 0.128 ± 0.003
  Positive-aware, 1,638        LAMR 0.114 ± 0.015
  Union, 3,276                 LAMR 0.111 ± 0.009
  Union, 3,276 + KD            LAMR 0.117 ± 0.005
  Random, 3,276 + KD           LAMR 0.175 ± 0.001
  Deployed kd6 (paper model)   LAMR 0.102
  No negatives (paper model)   LAMR 0.284
  Background 10% (paper model) LAMR 0.192

## 6. Detection side: 2,301 D-Fire fire images never used in training, at 0.50 and at each model's 1% budget
  No negatives                 image-level at 0.50 0.430 ± 0.007   at 1% hard budget 0.033 ± 0.005   | instances at 0.50 0.163 ± 0.003   at budget 0.013 ± 0.003
  Background 10% (433)         image-level at 0.50 0.384 ± 0.014   at 1% hard budget 0.036 ± 0.018   | instances at 0.50 0.154 ± 0.003   at budget 0.015 ± 0.007
  Random, 1,638                image-level at 0.50 0.369 ± 0.022   at 1% hard budget 0.062 ± 0.018   | instances at 0.50 0.153 ± 0.010   at budget 0.025 ± 0.007
  L-ratio, 1,638               image-level at 0.50 0.365 ± 0.029   at 1% hard budget 0.367 ± 0.054   | instances at 0.50 0.141 ± 0.009   at budget 0.142 ± 0.020
  M-top, 1,638                 image-level at 0.50 0.188 ± 0.019   at 1% hard budget 0.193 ± 0.055   | instances at 0.50 0.074 ± 0.009   at budget 0.076 ± 0.019
  Cluster coverage, 1,638      image-level at 0.50 0.256 ± 0.018   at 1% hard budget 0.083 ± 0.047   | instances at 0.50 0.102 ± 0.005   at budget 0.033 ± 0.019
  Places365-only, 1,638        image-level at 0.50 0.202 ± 0.025   at 1% hard budget 0.056 ± 0.032   | instances at 0.50 0.078 ± 0.008   at budget 0.021 ± 0.012
  Positive-aware, 1,638        image-level at 0.50 0.249 ± 0.009   at 1% hard budget 0.281 ± 0.062   | instances at 0.50 0.104 ± 0.006   at budget 0.119 ± 0.028
  Union, 3,276                 image-level at 0.50 0.174 ± 0.027   at 1% hard budget 0.290 ± 0.041   | instances at 0.50 0.069 ± 0.013   at budget 0.117 ± 0.017
  Union, 3,276 + KD            image-level at 0.50 0.201 ± 0.013   at 1% hard budget 0.226 ± 0.044   | instances at 0.50 0.076 ± 0.005   at budget 0.086 ± 0.020
  Random, 3,276 + KD           image-level at 0.50 0.319 ± 0.017   at 1% hard budget 0.059 ± 0.014   | instances at 0.50 0.127 ± 0.003   at budget 0.023 ± 0.006
  Deployed kd6 (paper model)   image-level at 0.50 0.202 ± 0.000   at 1% hard budget 0.199 ± 0.000   | instances at 0.50 0.080 ± 0.000   at budget 0.079 ± 0.000
  No negatives (paper model)   image-level at 0.50 0.407 ± 0.000   at 1% hard budget 0.022 ± 0.000   | instances at 0.50 0.161 ± 0.000   at budget 0.009 ± 0.000
  (2301 D-Fire positive images, 5193 annotated instances)

## 7. Fresh untouched suite (frozen 2026-10-03 01:04 UTC, before any model was scored)
  frozen at 2026-10-03T01:04:08+00:00, manifest sha256 20c22b3af19e675e..., counts {'F_hard': 101, 'F_novel': 61, 'F_cross': 1500}
  No negatives                 F_hard 40.26 ± 3.02  F_novel 22.40 ± 6.83  F_cross 11.04 ± 2.02  | at hard-1% thr: F_cross 0.09 ± 0.15  | R@1% F_cross 0.369 ± 0.026
  Background 10% (433)         F_hard 30.69 ± 2.62  F_novel 12.02 ± 3.41  F_cross 6.33 ± 0.13   | at hard-1% thr: F_cross 0.20 ± 0.23  | R@1% F_cross 0.508 ± 0.080
  Random, 1,638                F_hard 23.76 ± 2.97  F_novel 6.01 ± 1.89   F_cross 4.53 ± 0.35   | at hard-1% thr: F_cross 0.04 ± 0.08  | R@1% F_cross 0.644 ± 0.041
  L-ratio, 1,638               F_hard 0.33 ± 0.57   F_novel 4.92 ± 2.84   F_cross 6.96 ± 1.39   | at hard-1% thr: F_cross 7.24 ± 1.73  | R@1% F_cross 0.536 ± 0.058
  M-top, 1,638                 F_hard 1.65 ± 0.57   F_novel 1.64 ± 1.64   F_cross 1.56 ± 0.27   | at hard-1% thr: F_cross 2.18 ± 1.87  | R@1% F_cross 0.772 ± 0.005
  Cluster coverage, 1,638      F_hard 4.95 ± 2.62   F_novel 2.73 ± 0.95   F_cross 1.73 ± 0.58   | at hard-1% thr: F_cross 0.20 ± 0.18  | R@1% F_cross 0.767 ± 0.042
  Places365-only, 1,638        F_hard 12.87 ± 0.99  F_novel 3.28 ± 0.00   F_cross 1.33 ± 0.64   | at hard-1% thr: F_cross 0.02 ± 0.04  | R@1% F_cross 0.815 ± 0.022
  Positive-aware, 1,638        F_hard 0.33 ± 0.57   F_novel 1.09 ± 0.95   F_cross 1.64 ± 0.28   | at hard-1% thr: F_cross 2.20 ± 0.97  | R@1% F_cross 0.800 ± 0.018
  Union, 3,276                 F_hard 0.33 ± 0.57   F_novel 0.55 ± 0.95   F_cross 1.64 ± 0.75   | at hard-1% thr: F_cross 5.53 ± 2.23  | R@1% F_cross 0.791 ± 0.063
  Union, 3,276 + KD            F_hard 0.00 ± 0.00   F_novel 2.73 ± 0.95   F_cross 1.93 ± 0.27   | at hard-1% thr: F_cross 2.56 ± 0.91  | R@1% F_cross 0.741 ± 0.018
  Random, 3,276 + KD           F_hard 14.19 ± 1.51  F_novel 4.37 ± 1.89   F_cross 3.89 ± 0.40   | at hard-1% thr: F_cross 0.09 ± 0.10  | R@1% F_cross 0.651 ± 0.025
  Deployed kd6 (paper model)   F_hard 0.00 ± 0.00   F_novel 1.64 ± 0.00   F_cross 1.07 ± 0.00   | at hard-1% thr: F_cross 0.93 ± 0.00  | R@1% F_cross 0.803 ± 0.000
  No negatives (paper model)   F_hard 38.61 ± 0.00  F_novel 19.67 ± 0.00  F_cross 9.27 ± 0.00   | at hard-1% thr: F_cross 0.07 ± 0.00  | R@1% F_cross 0.344 ± 0.000

## 8. Conformal calibration on the 500 hard negatives, verified on the untouched fresh suite
  Deployed kd6 (paper model)     1%   marginal                    tau 0.5070 recall 0.803 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 1/61 = 1.64% [0.04, 8.80] | F_cross 14/1500 = 0.93% [0.51, 1.56] p=0.638
  Deployed kd6 (paper model)     1%   training-conditional (95%)  tau 0.7610 recall 0.638 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 0/61 = 0.00% [0.00, 5.87] | F_cross 1/1500 = 0.07% [0.00, 0.37] p=1.000
  Deployed kd6 (paper model)     5%   marginal                    tau 0.0484 recall 0.920 | F_hard 2/101 = 1.98% [0.24, 6.97] | F_novel 6/61 = 9.84% [3.70, 20.19] | F_cross 170/1500 = 11.33% [9.77, 13.05] p=0.000
  Deployed kd6 (paper model)     5%   training-conditional (95%)  tau 0.0931 recall 0.906 | F_hard 2/101 = 1.98% [0.24, 6.97] | F_novel 5/61 = 8.20% [2.72, 18.10] | F_cross 121/1500 = 8.07% [6.74, 9.56] p=0.000
  Union 3,276, s42               1%   marginal                    tau 0.0339 recall 0.898 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 4/61 = 6.56% [1.82, 15.95] | F_cross 115/1500 = 7.67% [6.37, 9.13] p=0.000
  Union 3,276, s42               1%   training-conditional (95%)  tau 0.0522 recall 0.896 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 4/61 = 6.56% [1.82, 15.95] | F_cross 96/1500 = 6.40% [5.21, 7.76] p=0.000
  Union 3,276, s42               5%   marginal                    tau 0.0000 recall 0.912 | F_hard 4/101 = 3.96% [1.09, 9.83] | F_novel 5/61 = 8.20% [2.72, 18.10] | F_cross 201/1500 = 13.40% [11.72, 15.23] p=0.000
  Union 3,276, s42               5%   training-conditional (95%)  tau 0.0000 recall 0.912 | F_hard 4/101 = 3.96% [1.09, 9.83] | F_novel 5/61 = 8.20% [2.72, 18.10] | F_cross 201/1500 = 13.40% [11.72, 15.23] p=0.000
  Union 3,276, s123              1%   marginal                    tau 0.2160 recall 0.878 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 0/61 = 0.00% [0.00, 5.87] | F_cross 81/1500 = 5.40% [4.31, 6.67] p=0.000
  Union 3,276, s123              1%   training-conditional (95%)  tau 0.4651 recall 0.813 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 0/61 = 0.00% [0.00, 5.87] | F_cross 40/1500 = 2.67% [1.91, 3.61] p=0.000
  Union 3,276, s123              5%   marginal                    tau 0.0000 recall 0.936 | F_hard 4/101 = 3.96% [1.09, 9.83] | F_novel 5/61 = 8.20% [2.72, 18.10] | F_cross 338/1500 = 22.53% [20.44, 24.73] p=0.000
  Union 3,276, s123              5%   training-conditional (95%)  tau 0.0239 recall 0.928 | F_hard 2/101 = 1.98% [0.24, 6.97] | F_novel 3/61 = 4.92% [1.03, 13.71] | F_cross 256/1500 = 17.07% [15.20, 19.07] p=0.000
  Union 3,276, s2024             1%   marginal                    tau 0.3453 recall 0.872 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 0/61 = 0.00% [0.00, 5.87] | F_cross 37/1500 = 2.47% [1.74, 3.38] p=0.000
  Union 3,276, s2024             1%   training-conditional (95%)  tau 0.4244 recall 0.858 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 0/61 = 0.00% [0.00, 5.87] | F_cross 30/1500 = 2.00% [1.35, 2.84] p=0.000
  Union 3,276, s2024             5%   marginal                    tau 0.0000 recall 0.933 | F_hard 3/101 = 2.97% [0.62, 8.44] | F_novel 4/61 = 6.56% [1.82, 15.95] | F_cross 314/1500 = 20.93% [18.90, 23.08] p=0.000
  Union 3,276, s2024             5%   training-conditional (95%)  tau 0.0297 recall 0.927 | F_hard 2/101 = 1.98% [0.24, 6.97] | F_novel 3/61 = 4.92% [1.03, 13.71] | F_cross 200/1500 = 13.33% [11.65, 15.16] p=0.000
  Union 3,276 + KD, s42          1%   marginal                    tau 0.5198 recall 0.799 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 2/61 = 3.28% [0.40, 11.35] | F_cross 25/1500 = 1.67% [1.08, 2.45] p=0.011
  Union 3,276 + KD, s42          1%   training-conditional (95%)  tau 0.7945 recall 0.593 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 1/61 = 1.64% [0.04, 8.80] | F_cross 3/1500 = 0.20% [0.04, 0.58] p=1.000
  Union 3,276 + KD, s42          5%   marginal                    tau 0.0667 recall 0.915 | F_hard 2/101 = 1.98% [0.24, 6.97] | F_novel 5/61 = 8.20% [2.72, 18.10] | F_cross 181/1500 = 12.07% [10.46, 13.82] p=0.000
  Union 3,276 + KD, s42          5%   training-conditional (95%)  tau 0.1070 recall 0.905 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 4/61 = 6.56% [1.82, 15.95] | F_cross 135/1500 = 9.00% [7.60, 10.56] p=0.000
  Union 3,276 + KD, s123         1%   marginal                    tau 0.5690 recall 0.756 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 2/61 = 3.28% [0.40, 11.35] | F_cross 24/1500 = 1.60% [1.03, 2.37] p=0.019
  Union 3,276 + KD, s123         1%   training-conditional (95%)  tau 0.6680 recall 0.702 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 1/61 = 1.64% [0.04, 8.80] | F_cross 12/1500 = 0.80% [0.41, 1.39] p=0.817
  Union 3,276 + KD, s123         5%   marginal                    tau 0.1051 recall 0.893 | F_hard 2/101 = 1.98% [0.24, 6.97] | F_novel 4/61 = 6.56% [1.82, 15.95] | F_cross 152/1500 = 10.13% [8.65, 11.77] p=0.000
  Union 3,276 + KD, s123         5%   training-conditional (95%)  tau 0.1844 recall 0.872 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 4/61 = 6.56% [1.82, 15.95] | F_cross 103/1500 = 6.87% [5.64, 8.27] p=0.001
  Union 3,276 + KD, s2024        1%   marginal                    tau 0.3119 recall 0.830 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 2/61 = 3.28% [0.40, 11.35] | F_cross 54/1500 = 3.60% [2.72, 4.67] p=0.000
  Union 3,276 + KD, s2024        1%   training-conditional (95%)  tau 0.6466 recall 0.719 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 1/61 = 1.64% [0.04, 8.80] | F_cross 11/1500 = 0.73% [0.37, 1.31] p=0.883
  Union 3,276 + KD, s2024        5%   marginal                    tau 0.0244 recall 0.921 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 9/61 = 14.75% [6.98, 26.17] | F_cross 288/1500 = 19.20% [17.24, 21.29] p=0.000
  Union 3,276 + KD, s2024        5%   training-conditional (95%)  tau 0.0567 recall 0.903 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 9/61 = 14.75% [6.98, 26.17] | F_cross 194/1500 = 12.93% [11.28, 14.74] p=0.000
  Positive-aware, s42            1%   marginal                    tau 0.4481 recall 0.851 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 1/61 = 1.64% [0.04, 8.80] | F_cross 29/1500 = 1.93% [1.30, 2.76] p=0.001
  Positive-aware, s42            1%   training-conditional (95%)  tau 0.6677 recall 0.781 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 1/61 = 1.64% [0.04, 8.80] | F_cross 14/1500 = 0.93% [0.51, 1.56] p=0.638
  Positive-aware, s42            5%   marginal                    tau 0.0258 recall 0.925 | F_hard 5/101 = 4.95% [1.63, 11.18] | F_novel 3/61 = 4.92% [1.03, 13.71] | F_cross 152/1500 = 10.13% [8.65, 11.77] p=0.000
  Positive-aware, s42            5%   training-conditional (95%)  tau 0.0862 recall 0.909 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 2/61 = 3.28% [0.40, 11.35] | F_cross 92/1500 = 6.13% [4.97, 7.47] p=0.028
  Positive-aware, s123           1%   marginal                    tau 0.6307 recall 0.798 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 1/61 = 1.64% [0.04, 8.80] | F_cross 15/1500 = 1.00% [0.56, 1.64] p=0.535
  Positive-aware, s123           1%   training-conditional (95%)  tau 0.8699 recall 0.467 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 0/61 = 0.00% [0.00, 5.87] | F_cross 1/1500 = 0.07% [0.00, 0.37] p=1.000
  Positive-aware, s123           5%   marginal                    tau 0.0495 recall 0.897 | F_hard 4/101 = 3.96% [1.09, 9.83] | F_novel 6/61 = 9.84% [3.70, 20.19] | F_cross 134/1500 = 8.93% [7.54, 10.49] p=0.000
  Positive-aware, s123           5%   training-conditional (95%)  tau 0.1324 recall 0.883 | F_hard 2/101 = 1.98% [0.24, 6.97] | F_novel 3/61 = 4.92% [1.03, 13.71] | F_cross 95/1500 = 6.33% [5.15, 7.69] p=0.012
  Positive-aware, s2024          1%   marginal                    tau 0.2369 recall 0.882 | F_hard 1/101 = 0.99% [0.03, 5.39] | F_novel 1/61 = 1.64% [0.04, 8.80] | F_cross 44/1500 = 2.93% [2.14, 3.92] p=0.000
  Positive-aware, s2024          1%   training-conditional (95%)  tau 0.8094 recall 0.675 | F_hard 0/101 = 0.00% [0.00, 3.59] | F_novel 0/61 = 0.00% [0.00, 5.87] | F_cross 4/1500 = 0.27% [0.07, 0.68] p=1.000
  Positive-aware, s2024          5%   marginal                    tau 0.0183 recall 0.916 | F_hard 6/101 = 5.94% [2.21, 12.48] | F_novel 6/61 = 9.84% [3.70, 20.19] | F_cross 135/1500 = 9.00% [7.60, 10.56] p=0.000
  Positive-aware, s2024          5%   training-conditional (95%)  tau 0.0411 recall 0.912 | F_hard 5/101 = 4.95% [1.63, 11.18] | F_novel 6/61 = 9.84% [3.70, 20.19] | F_cross 102/1500 = 6.80% [5.58, 8.19] p=0.001

## 9. Contemporary false-alarm baseline: detector + zero-shot CLIP verification, same suite, same protocol
  No negatives                           hard 27.40 [23.53, 31.54] cross 10.73 [9.21, 12.41]  | R@1% hard 0.128 at 0.93 pooled 0.191 at 0.92 fresh 0.250 at 0.91 small 0.015
  No negatives + CLIP verifier           hard 1.20 [0.44, 2.59]    cross 3.27 [2.43, 4.30]    | R@1% hard 0.579 at 0.59 pooled 0.347 at 0.79 fresh 0.605 at 0.55 small 0.159
  Deployed kd6                           hard 1.20 [0.44, 2.59]    cross 1.67 [1.08, 2.45]    | R@1% hard 0.803 at 0.51 pooled 0.760 at 0.62 fresh 0.803 at 0.51 small 0.674
  Deployed kd6 + CLIP verifier           hard 0.00 [0.00, 0.74]    cross 0.20 [0.04, 0.58]    | R@1% hard 0.869 at 0.04 pooled 0.723 at 0.3 fresh 0.772 at 0.2 small 0.638
  M-top s42 (trained negatives)          hard 1.40 [0.56, 2.86]    cross 2.40 [1.69, 3.31]    | R@1% hard 0.730 at 0.7 pooled 0.688 at 0.76 fresh 0.758 at 0.63 small 0.546
  Union 3,276 s42 (trained negatives)    hard 0.20 [0.01, 1.11]    cross 2.87 [2.08, 3.84]    | R@1% hard 0.897 at 0.04 pooled 0.709 at 0.77 fresh 0.829 at 0.52 small 0.59
  verifier: CLIP ViT-B/32, box crop with context 2.0, top-10 boxes; score = confidence x P(fire prompts)

## 10. Class-agnostic recall: how often the matching box has the other class (at 0.50)
  No negatives s42   flame 897: any 0.860 same 0.860 (other-class only 0) | smoke 689: any 0.811 same 0.811 (other-class only 0)
  M-top s42          flame 897: any 0.795 same 0.795 (other-class only 0) | smoke 689: any 0.813 same 0.813 (other-class only 0)
  Union 3,276 s42    flame 897: any 0.843 same 0.843 (other-class only 0) | smoke 689: any 0.820 same 0.820 (other-class only 0)
  Deployed kd6       flame 897: any 0.806 same 0.806 (other-class only 0) | smoke 689: any 0.805 same 0.805 (other-class only 0)

## 11. Audit of the negative sets
  L-ratio                  vs hn_holdout                   exact 0, near-duplicate (dHash <= 4) 4
  L-ratio                  vs novel                        exact 0, near-duplicate (dHash <= 4) 0
  L-ratio                  vs dfire_neg                    exact 0, near-duplicate (dHash <= 4) 9
  L-ratio                  vs mined_dev                    exact 0, near-duplicate (dHash <= 4) 3
  L-ratio                  vs home_fire test (positives)   exact 0, near-duplicate (dHash <= 4) 3
  L-ratio                  vs home_fire val (positives)    exact 0, near-duplicate (dHash <= 4) 3
  M-top                    vs hn_holdout                   exact 0, near-duplicate (dHash <= 4) 3
  M-top                    vs novel                        exact 0, near-duplicate (dHash <= 4) 2
  M-top                    vs dfire_neg                    exact 0, near-duplicate (dHash <= 4) 7
  M-top                    vs mined_dev                    exact 0, near-duplicate (dHash <= 4) 1
  M-top                    vs home_fire test (positives)   exact 0, near-duplicate (dHash <= 4) 2
  M-top                    vs home_fire val (positives)    exact 0, near-duplicate (dHash <= 4) 2
  Random                   vs hn_holdout                   exact 0, near-duplicate (dHash <= 4) 0
  Random                   vs novel                        exact 0, near-duplicate (dHash <= 4) 0
  Random                   vs dfire_neg                    exact 0, near-duplicate (dHash <= 4) 0
  Random                   vs mined_dev                    exact 0, near-duplicate (dHash <= 4) 0
  Random                   vs home_fire test (positives)   exact 0, near-duplicate (dHash <= 4) 0
  Random                   vs home_fire val (positives)    exact 0, near-duplicate (dHash <= 4) 0
  E1.8 negatives           vs mined_dev                    exact 32, near-duplicate (dHash <= 4) 34
  union L-ratio + M-top by content: 0 exact duplicates, 9 near duplicates (dHash <= 4) among 1638 + 1638
  fire-like exclusion recomputed (CLIP ViT-B/32, margin fire-safe > 0.05 and fire similarity > 0.25): 52 flagged, 52 in fire_block.json, 52 in both
  mining cost on NVIDIA L4: detector 20.9 ms/image -> 26.6 min for 76,183 images; CLIP 13.9 ms/image -> 2.3 min for 9,854 hits; k-means 6.3 s
  re-scoring check: 184 (model, subset) pairs, 90 of 119416 image verdicts at 0.50 changed; pairs with a score change > 0.05: ['showcase__xm960__s42', 'showcase__xs960__s123', 'showcase__xs960__s2024', 'showcase__xs960__s42', 'tournament__yolo26n__s42']
  PA: 11600 candidates, 2826 excluded as closer to real small fires than to known confusers (412 of them in M-top); PA shares 1226 images with M-top
  near-duplicate sensitivity (eval images dropped: {'hn_holdout': 2, 'dfire_neg': 9, 'mined_dev': 2, 'novel': 1}):
   L-ratio            hard          full 1.13 ± 0.31   without near-duplicates 1.14 ± 0.31
   L-ratio            novel         full 4.25 ± 2.99   without near-duplicates 4.27 ± 3.00
   L-ratio            cross-corpus  full 7.84 ± 0.60   without near-duplicates 7.82 ± 0.64
   M-top              hard          full 1.13 ± 0.46   without near-duplicates 1.14 ± 0.46
   M-top              novel         full 1.53 ± 0.00   without near-duplicates 1.54 ± 0.00
   M-top              cross-corpus  full 3.71 ± 1.30   without near-duplicates 3.62 ± 1.18
   Union 3,276        hard          full 0.20 ± 0.00   without near-duplicates 0.20 ± 0.00
   Union 3,276        novel         full 1.02 ± 0.88   without near-duplicates 1.03 ± 0.89
   Union 3,276        cross-corpus  full 3.02 ± 0.58   without near-duplicates 3.02 ± 0.61
   Union 3,276 + KD   hard          full 0.87 ± 0.42   without near-duplicates 0.87 ± 0.42
   Union 3,276 + KD   novel         full 2.72 ± 1.06   without near-duplicates 2.74 ± 1.07
   Union 3,276 + KD   cross-corpus  full 2.24 ± 0.71   without near-duplicates 2.26 ± 0.71

  per-cluster FPR at 0.50 on mining-dev (25 held-out members per cluster):
    0 reflection or glare            n=775   PA-excl 254  | No 37% L-ratio 15% M-top 0% Union 1% Deployed 4% Positive-aware 0%
    1 reflection or glare            n=1108  PA-excl 424  | No 28% L-ratio 9% M-top 0% Union 1% Deployed 4% Positive-aware 1%
    2 orange vehicle or object       n=681   PA-excl 142  | No 27% L-ratio 17% M-top 0% Union 1% Deployed 4% Positive-aware 1%
    3 bright window or indoor light  n=626   PA-excl 174  | No 23% L-ratio 16% M-top 0% Union 3% Deployed 4% Positive-aware 9%
    4 red or orange flower           n=624   PA-excl 36   | No 31% L-ratio 3% M-top 0% Union 0% Deployed 0% Positive-aware 0%
    5 person                         n=871   PA-excl 144  | No 35% L-ratio 7% M-top 0% Union 4% Deployed 4% Positive-aware 3%
    6 person                         n=664   PA-excl 78   | No 29% L-ratio 8% M-top 0% Union 1% Deployed 0% Positive-aware 0%
    7 person                         n=693   PA-excl 207  | No 25% L-ratio 16% M-top 0% Union 1% Deployed 0% Positive-aware 4%
    8 glowing screen or monitor      n=1092  PA-excl 165  | No 24% L-ratio 8% M-top 1% Union 0% Deployed 4% Positive-aware 4%
    9 lamp or light fixture          n=636   PA-excl 180  | No 19% L-ratio 3% M-top 1% Union 1% Deployed 8% Positive-aware 3%
   10 orange or red clothing         n=632   PA-excl 91   | No 35% L-ratio 8% M-top 0% Union 1% Deployed 0% Positive-aware 0%
   11 orange vehicle or object       n=415   PA-excl 149  | No 28% L-ratio 9% M-top 1% Union 0% Deployed 0% Positive-aware 0%
   12 orange vehicle or object       n=886   PA-excl 186  | No 27% L-ratio 13% M-top 0% Union 0% Deployed 0% Positive-aware 0%
   13 person                         n=833   PA-excl 189  | No 23% L-ratio 5% M-top 1% Union 0% Deployed 4% Positive-aware 1%
   14 orange vehicle or object       n=922   PA-excl 339  | No 33% L-ratio 20% M-top 4% Union 5% Deployed 8% Positive-aware 3%
   15 food or fruit                  n=594   PA-excl 68   | No 21% L-ratio 3% M-top 0% Union 0% Deployed 0% Positive-aware 0%

## 12. Video
  readable: 30 negative clips (31.6 min), 23 positive clips; unreadable by the Colab video reader: ['FS_fire__negsVideo10.1072', 'FS_fire__negsVideo11.1073', 'FS_fire__negsVideo13.1075', 'FS_fire__negsVideo14.1076', 'FS_fire__negsVideo15.1078', 'FS_smoke__testpos03.819']
  No negatives (paper)       1-of-1 hold 0     817.6 alarms/h (431 in 31.6 min; FIRESENSE 1823.0, KMU 27.1; indoor 2028.6, outdoor 753.1) | FIRESENSE negatives firing 13/20 | positives 23/23
  No negatives (paper)       3-of-5 hold 0     166.9 alarms/h ( 88 in 31.6 min; FIRESENSE 366.3, KMU 10.2; indoor 520.9, outdoor 141.5) | FIRESENSE negatives firing 9/20 | positives 23/23
  No negatives (paper)       3-of-5 hold 30     22.8 alarms/h ( 12 in 31.6 min; FIRESENSE 43.1, KMU 6.8; indoor 82.2, outdoor 16.0) | FIRESENSE negatives firing 9/20 | positives 23/23
  Deployed kd6 (paper)       1-of-1 hold 0     220.0 alarms/h (116 in 31.6 min; FIRESENSE 495.6, KMU 3.4; indoor 685.3, outdoor 203.1) | FIRESENSE negatives firing 6/20 | positives 22/23
  Deployed kd6 (paper)       3-of-5 hold 0      32.2 alarms/h ( 17 in 31.6 min; FIRESENSE 69.0, KMU 3.4; indoor 164.5, outdoor 22.8) | FIRESENSE negatives firing 5/20 | positives 20/23
  Deployed kd6 (paper)       3-of-5 hold 30     13.3 alarms/h (  7 in 31.6 min; FIRESENSE 25.9, KMU 3.4; indoor 54.8, outdoor 9.1) | FIRESENSE negatives firing 5/20 | positives 20/23
  No negatives s42           1-of-1 hold 0    1022.4 alarms/h (539 in 31.6 min; FIRESENSE 2210.9, KMU 88.1; indoor 1672.3, outdoor 965.4) | FIRESENSE negatives firing 15/20 | positives 23/23
  No negatives s42           3-of-5 hold 0     212.5 alarms/h (112 in 31.6 min; FIRESENSE 443.9, KMU 30.5; indoor 383.8, outdoor 203.1) | FIRESENSE negatives firing 12/20 | positives 23/23
  No negatives s42           3-of-5 hold 30     34.1 alarms/h ( 18 in 31.6 min; FIRESENSE 56.0, KMU 16.9; indoor 82.2, outdoor 29.7) | FIRESENSE negatives firing 12/20 | positives 23/23
  L-ratio s42                1-of-1 hold 0     726.5 alarms/h (383 in 31.6 min; FIRESENSE 1232.6, KMU 328.6; indoor 657.9, outdoor 755.4) | FIRESENSE negatives firing 10/20 | positives 23/23
  L-ratio s42                3-of-5 hold 0     140.4 alarms/h ( 74 in 31.6 min; FIRESENSE 237.0, KMU 64.4; indoor 246.7, outdoor 134.6) | FIRESENSE negatives firing 8/20 | positives 22/23
  L-ratio s42                3-of-5 hold 30     32.2 alarms/h ( 17 in 31.6 min; FIRESENSE 43.1, KMU 23.7; indoor 54.8, outdoor 29.7) | FIRESENSE negatives firing 8/20 | positives 22/23
  M-top s42                  1-of-1 hold 0      81.6 alarms/h ( 43 in 31.6 min; FIRESENSE 185.3, KMU 0.0; indoor 356.4, outdoor 61.6) | FIRESENSE negatives firing 9/20 | positives 20/23
  M-top s42                  3-of-5 hold 0      11.4 alarms/h (  6 in 31.6 min; FIRESENSE 25.9, KMU 0.0; indoor 82.2, outdoor 6.8) | FIRESENSE negatives firing 3/20 | positives 20/23
  M-top s42                  3-of-5 hold 30      5.7 alarms/h (  3 in 31.6 min; FIRESENSE 12.9, KMU 0.0; indoor 27.4, outdoor 4.6) | FIRESENSE negatives firing 3/20 | positives 20/23
  Positive-aware s42         1-of-1 hold 0     258.0 alarms/h (136 in 31.6 min; FIRESENSE 560.3, KMU 20.3; indoor 877.2, outdoor 225.9) | FIRESENSE negatives firing 7/20 | positives 21/23
  Positive-aware s42         3-of-5 hold 0      68.3 alarms/h ( 36 in 31.6 min; FIRESENSE 137.9, KMU 13.6; indoor 329.0, outdoor 54.8) | FIRESENSE negatives firing 4/20 | positives 19/23
  Positive-aware s42         3-of-5 hold 30      9.5 alarms/h (  5 in 31.6 min; FIRESENSE 17.2, KMU 3.4; indoor 82.2, outdoor 4.6) | FIRESENSE negatives firing 4/20 | positives 19/23
  Positive-aware + KD s42    1-of-1 hold 0     149.9 alarms/h ( 79 in 31.6 min; FIRESENSE 340.5, KMU 0.0; indoor 109.7, outdoor 162.0) | FIRESENSE negatives firing 5/20 | positives 22/23
  Positive-aware + KD s42    3-of-5 hold 0      13.3 alarms/h (  7 in 31.6 min; FIRESENSE 30.2, KMU 0.0; indoor 27.4, outdoor 11.4) | FIRESENSE negatives firing 4/20 | positives 19/23
  Positive-aware + KD s42    3-of-5 hold 30      7.6 alarms/h (  4 in 31.6 min; FIRESENSE 17.2, KMU 0.0; indoor 27.4, outdoor 4.6) | FIRESENSE negatives firing 4/20 | positives 19/23
  Union + KD s42             1-of-1 hold 0     157.4 alarms/h ( 83 in 31.6 min; FIRESENSE 357.7, KMU 0.0; indoor 301.6, outdoor 157.5) | FIRESENSE negatives firing 8/20 | positives 20/23
  Union + KD s42             3-of-5 hold 0      36.0 alarms/h ( 19 in 31.6 min; FIRESENSE 81.9, KMU 0.0; indoor 27.4, outdoor 38.8) | FIRESENSE negatives firing 6/20 | positives 20/23
  Union + KD s42             3-of-5 hold 30     11.4 alarms/h (  6 in 31.6 min; FIRESENSE 25.9, KMU 0.0; indoor 27.4, outdoor 9.1) | FIRESENSE negatives firing 6/20 | positives 20/23
  Union + KD s123            1-of-1 hold 0     233.3 alarms/h (123 in 31.6 min; FIRESENSE 530.1, KMU 0.0; indoor 356.4, outdoor 241.9) | FIRESENSE negatives firing 10/20 | positives 21/23
  Union + KD s123            3-of-5 hold 0      26.6 alarms/h ( 14 in 31.6 min; FIRESENSE 60.3, KMU 0.0; indoor 109.7, outdoor 20.5) | FIRESENSE negatives firing 7/20 | positives 19/23
  Union + KD s123            3-of-5 hold 30     15.2 alarms/h (  8 in 31.6 min; FIRESENSE 34.5, KMU 0.0; indoor 54.8, outdoor 11.4) | FIRESENSE negatives firing 7/20 | positives 19/23
  Union + KD s2024           1-of-1 hold 0     189.7 alarms/h (100 in 31.6 min; FIRESENSE 431.0, KMU 0.0; indoor 246.7, outdoor 196.3) | FIRESENSE negatives firing 8/20 | positives 21/23
  Union + KD s2024           3-of-5 hold 0      30.4 alarms/h ( 16 in 31.6 min; FIRESENSE 69.0, KMU 0.0; indoor 27.4, outdoor 32.0) | FIRESENSE negatives firing 4/20 | positives 19/23
  Union + KD s2024           3-of-5 hold 30      7.6 alarms/h (  4 in 31.6 min; FIRESENSE 17.2, KMU 0.0; indoor 27.4, outdoor 4.6) | FIRESENSE negatives firing 4/20 | positives 19/23
  interaction (paper models, 30 readable negatives): negatives alone x3.72, layer alone x4.90, together x25.4, ratio to the product 1.39
   bootstrap over videos (4991 resamples): together x25.4 [10.2, 59.7]; ratio to the product 1.39 [0.61, 1.83] (1 = independent)

  small indoor fires (KMU flame2-5): highest flame / any-class confidence over each clip
   BG10 noKD                          n=3  0.962 0.517 0.717 0.771 | clips >= 0.50: 3.7 of 4
   C noKD                             n=3  0.953 0.012 0.112 0.375 | clips >= 0.50: 1.3 of 4
   L KD                               n=3  0.952 0.335 0.780 0.479 | clips >= 0.50: 2.3 of 4
   L noKD                             n=3  0.960 0.354 0.749 0.260 | clips >= 0.50: 2.7 of 4
   M KD                               n=3  0.950 0.005 0.094 0.291 | clips >= 0.50: 1.3 of 4
   M noKD                             n=3  0.958 0.001 0.056 0.401 | clips >= 0.50: 1.3 of 4
   N0 KD                              n=3  0.960 0.784 0.869 0.807 | clips >= 0.50: 4.0 of 4
   N0 noKD                            n=3  0.963 0.767 0.892 0.855 | clips >= 0.50: 4.0 of 4
   P noKD                             n=3  0.945 0.006 0.331 0.300 | clips >= 0.50: 1.3 of 4
   PA KD                              n=3  0.954 0.032 0.174 0.282 | clips >= 0.50: 1.3 of 4
   PA noKD                            n=3  0.956 0.003 0.111 0.026 | clips >= 0.50: 1.0 of 4
   R noKD                             n=3  0.945 0.388 0.595 0.363 | clips >= 0.50: 2.0 of 4
   R3276 KD                           n=3  0.948 0.124 0.646 0.329 | clips >= 0.50: 2.3 of 4
   U1638 KD                           n=3  0.952 0.021 0.244 0.262 | clips >= 0.50: 1.3 of 4
   U1638 noKD                         n=3  0.950 0.000 0.249 0.032 | clips >= 0.50: 1.3 of 4
   U3276 KD                           n=3  0.941 0.009 0.217 0.209 | clips >= 0.50: 1.0 of 4
   U3276 noKD                         n=3  0.946 0.001 0.007 0.184 | clips >= 0.50: 1.0 of 4
   paper: accuracy res768             n=1  0.963 0.868 0.911 0.783 | clips >= 0.50: 4.0 of 4
   paper: accuracy res960             n=1  0.953 0.816 0.852 0.888 | clips >= 0.50: 4.0 of 4
   paper: hero combo                  n=3  0.951 0.005 0.107 0.034 | clips >= 0.50: 1.0 of 4
   paper: hnratio hn15                n=1  0.958 0.788 0.875 0.834 | clips >= 0.50: 4.0 of 4
   paper: hnratio hn30                n=3  0.959 0.412 0.821 0.733 | clips >= 0.50: 3.0 of 4
   paper: hnratio hn30rand            n=1  0.964 0.101 0.248 0.050 | clips >= 0.50: 1.0 of 4
   paper: hnratio hn45                n=1  0.957 0.346 0.847 0.872 | clips >= 0.50: 3.0 of 4
   paper: kd__kd12__s42               n=1  0.930 0.136 0.811 0.347 | clips >= 0.50: 2.0 of 4
   paper: kd__kd6__s42                n=1  0.936 0.005 0.025 0.019 | clips >= 0.50: 1.0 of 4
   paper: no negatives (yolo11n)      n=3  0.917 0.556 0.815 0.829 | clips >= 0.50: 3.7 of 4
   paper: no negatives (yolo11s)      n=3  0.920 0.832 0.875 0.848 | clips >= 0.50: 4.0 of 4
   paper: no negatives (yolo26n)      n=3  0.962 0.745 0.821 0.851 | clips >= 0.50: 4.0 of 4
   paper: no negatives (yolo26s)      n=3  0.957 0.791 0.897 0.905 | clips >= 0.50: 4.0 of 4
   paper: no negatives (yolov8n)      n=3  0.931 0.670 0.861 0.852 | clips >= 0.50: 3.7 of 4
   paper: no negatives (yolov8s)      n=3  0.930 0.778 0.839 0.712 | clips >= 0.50: 4.0 of 4
   paper: safemine lbg05              n=1  0.943 0.027 0.071 0.033 | clips >= 0.50: 1.0 of 4
   paper: safemine lbg10              n=1  0.946 0.006 0.040 0.380 | clips >= 0.50: 1.0 of 4
   paper: safemine lbg20              n=3  0.948 0.006 0.009 0.025 | clips >= 0.50: 1.0 of 4
   paper: safemine sm_cov             n=1  0.963 0.008 0.850 0.048 | clips >= 0.50: 2.0 of 4
   paper: safemine sm_top             n=3  0.951 0.004 0.060 0.256 | clips >= 0.50: 1.3 of 4
   paper: safemine sm_top_yolo11n     n=1  0.901 0.007 0.114 0.634 | clips >= 0.50: 2.0 of 4
   paper: safemine sm_top_yolov8n     n=1  0.926 0.008 0.790 0.036 | clips >= 0.50: 2.0 of 4
   paper: teacher xm960               n=1  0.937 0.011 0.208 0.002 | clips >= 0.50: 1.0 of 4
   paper: teacher xs960               n=3  0.922 0.087 0.119 0.145 | clips >= 0.50: 1.0 of 4
  CLIP nearest training negatives to small-fire frames (mean cosine similarity, 32 frames):
   M-top    top-1 0.7541  top-5 0.7294
   L-ratio  top-1 0.7642  top-5 0.7500
   PA       top-1 0.7537  top-5 0.7265
