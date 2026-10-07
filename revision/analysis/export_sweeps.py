# -*- coding: utf-8 -*-
"""Full threshold sweeps behind every "R at FPR 1%" value.

For every model (the 51 new runs and the re-scored earlier runs) and three negative pools, it writes the image-level
false positive rate and the instance-level recall at every threshold of the grid 0.01..0.99, and the operating point
chosen for a 1% budget (the lowest grid threshold whose FPR is at most 1%).
Output: <results>/threshold_sweeps.csv and <results>/r_at_fpr1_operating_points.csv
"""
import csv, os
import analysis_results as A

POOLS = {'hard (500)': ['hn_holdout'], 'pooled (2,596)': A.ORIG, 'frozen (1,662)': A.FRESH}


def main():
    rows, picks = [], []
    models = dict(A.OLD)
    models.update(A.NEW)
    for rid in sorted(models):
        m = models[rid]
        for pool, subs in POOLS.items():
            neg = m.pool(subs)
            if len(neg) == 0:
                continue
            for t in A.GRID:
                rows.append([rid, pool, '%.2f' % t, len(neg), int((neg >= t).sum()), '%.4f' % A.fpr(neg, t),
                             '%.4f' % A.recall_at(m.conf, t)])
            t1 = A.budget_thr(neg, 1.0)
            picks.append([rid, pool, '%.2f' % t1 if t1 is not None else 'no operating point',
                          '%.4f' % A.fpr(neg, t1) if t1 is not None else '', '%.4f' % A.recall_at(m.conf, t1) if t1 is not None else ''])
    with open(os.path.join(A.RES, 'threshold_sweeps.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['model', 'negative_pool', 'threshold', 'n_negatives', 'alarms', 'fpr_pct', 'instance_recall'])
        w.writerows(rows)
    with open(os.path.join(A.RES, 'r_at_fpr1_operating_points.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['model', 'negative_pool', 'threshold', 'fpr_pct', 'instance_recall'])
        w.writerows(picks)
    print('%d sweep rows, %d operating points' % (len(rows), len(picks)))


if __name__ == '__main__':
    main()
