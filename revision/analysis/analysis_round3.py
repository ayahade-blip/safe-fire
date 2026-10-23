# -*- coding: utf-8 -*-
"""SAFE-Fire extended study, round 3: recomputations from the released score files. No new training.

Input : revision/data (every bundle); the D-Fire test images only to compute the released fingerprints once;
        the room-trial logs in revision/data/room_trials
Output: revision/results/round3/*.csv

Parts
  budget    recall at a 1% budget on the pooled 2,196 negatives (hard, novel, cross-corpus; mining-development excluded),
            on the 3,358 negatives no decision consulted (novel, cross-corpus, frozen suite), on the frozen suite and on
            the domestic set; rules pooled / every subset / equal weight; thresholds for Table S7
  lamr      log-average miss rate and FPPI curves on the 2,196 pool; recall by fire size at the pooled 1% budget
  cond      every condition with the new pooled columns
  verifier  the vision-language verifier baseline with the new pools
  dfire     in-domain D-Fire for every condition and the paper models, with one threshold rule
            (grid step 0.001) in the tables and in the bootstrap contrasts, on both D-Fire subsets and on each alone
  video     first-alarm latency of every positive clip
  room      replay of the room-trial frames at 0.50, 0.0931, 0.0842 and 0.0484
  map       mAP of the audited union against no negatives with and without seed 123
  overlap   SHA-256 and dHash overlap of every training set with every evaluation set
  t1t2      the backbone-selection yolo26n runs beside the factorial no-negatives runs (same recipe and seeds)
"""
import collections
import csv
import hashlib
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analysis_results as A  # noqa: E402
import analysis_round2 as R2  # noqa: E402

RES = os.path.join(A.REV, 'results', 'round3')
os.makedirs(RES, exist_ok=True)
A.RES = RES
OUT, NEW, OLD = A.OUT, A.NEW, A.OLD
ORIG, FRESH, DOM = A.ORIG, A.FRESH, R2.DOM
NAME = R2.NAME
cond, fpr, fmt_ms, r_at, budget_thr, recall_at, write = A.cond, A.fpr, A.fmt_ms, A.r_at, A.budget_thr, A.recall_at, A.write
T5b, PAPER, CONDS2 = R2.T5b, R2.PAPER, R2.CONDS2
P3 = ['hn_holdout', 'novel', 'dfire_neg']                        # pooled 2,196: the three original subsets that generalise
UNC = ['novel', 'dfire_neg', 'F_hard', 'F_novel', 'F_cross']     # 3,358 negatives that no development decision consulted
PROJ = os.path.dirname(HERE)
DFIRE_LOCAL = os.path.join(A.REV, 'data', 'dfire_test_images')   # only needed to recompute the released fingerprints
ROOM = os.path.join(A.REV, 'data', 'room_trials')
SUMMARY = []
RNG = np.random.default_rng(2026)


def say(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    SUMMARY.append(s)


def items_t5():
    return [(lab, cond(*c)) for lab, c in T5b] + [(lab, [OLD[rid]]) for lab, rid in PAPER]


def items_all():
    out = [('%s%s' % (A.LABEL[n], ' + KD' if kd else ''), cond(n, kd)) for n, kd in CONDS2]
    return [x for x in out if x[1]] + [(lab, [OLD[rid]]) for lab, rid in PAPER]


# ================================================================= 1. budgets without the mining-development subset
GROUPS = [('pooled 2,196 (hard, novel, cross-corpus)', P3, ('pooled', 'every subset', 'equal weight')),
          ('unconsulted 3,358 (novel, cross-corpus, frozen suite)', UNC, ('pooled', 'every subset', 'equal weight')),
          ('frozen suite 1,662', FRESH, ('pooled',)), ('domestic 1,500', [DOM], ('pooled',)),
          ('pooled 2,596 (with mining-dev)', ORIG, ('pooled',))]


def part_budget3():
    say('\n## 1. Recall at a 1% budget without the mining-development subset (three-seed mean ± SD)')
    rows = []
    for gname, subs, rules in GROUPS:
        for lab, ms in items_t5():
            for rule in rules:
                ts = [R2.thr_rule(m, subs, rule) for m in ms]
                rec = [recall_at(m.conf, t) for m, t in zip(ms, ts)]
                small = [float((m.conf[m.area <= 0.01] >= t).mean()) if t is not None else None for m, t in zip(ms, ts)]
                binding = collections.Counter(max(subs, key=lambda s: fpr(m.neg(s), t)) for m, t in zip(ms, ts) if t is not None)
                row = dict(suite=gname, method=lab, rule=rule, seeds=len(ms), thr='/'.join(str(t) for t in ts),
                           recall=fmt_ms(rec, 3), recall_mean=round(float(np.mean(rec)), 4), small_recall=fmt_ms(small, 3),
                           highest_subset='/'.join('%s %d' % (NAME[k], v) for k, v in binding.items()))
                for s in subs:
                    row['FPR_' + s] = fmt_ms([fpr(m.neg(s), t) if t is not None else None for m, t in zip(ms, ts)], 2)
                rows.append(row)
                if rule == 'pooled' or gname.startswith('pooled 2,196'):
                    say('  %-44s %-40s %-13s thr %-16s recall %-15s small %s' % (gname[:44], lab[:40], rule, row['thr'], row['recall'], row['small_recall']))
    write('budget_round3.csv', rows)


# ================================================================= 2. LAMR and curves on the 2,196 pool
def part_lamr3():
    say('\n## 2. Log-average miss rate on the pooled 2,196 negatives; FPPI curves (seed 42); recall by size at the pooled 1% budget')
    rows, curves, size_rows = [], [], []
    for lab, ms in items_t5():
        vals, ends = [], []
        for m in ms:
            ts, fp, mr = A.fppi_curve(m, P3)
            L, _ = A.lamr(fp, mr)
            vals.append(L)
            ends.append(float(fp.max()))
            if getattr(m, 'seed', 42) == 42 or len(ms) == 1:
                for t, a, b in zip(ts, fp, mr):
                    curves.append(dict(method=lab, run_id=m.rid, thr=t, fppi=round(float(a), 5), miss_rate=round(float(b), 5)))
        rows.append(dict(method=lab, seeds=len(ms), LAMR=fmt_ms(vals, 3), LAMR_mean=round(float(np.mean(vals)), 4),
                         curve_end_FPPI=fmt_ms(ends, 3), LAMR_seed42='%.3f' % vals[0]))
        say('  %-44s LAMR %-16s curve ends at FPPI %s' % (lab, rows[-1]['LAMR'], rows[-1]['curve_end_FPPI']))
        for sz, lo, hi in A.SIZE_BINS:
            v, ks, ns = [], 0, 0
            for m in ms:
                t = budget_thr(m.pool(P3), 1.0)
                mk = A.size_mask(m.area, lo, hi)
                k = int((m.conf[mk] >= t).sum())
                v.append(k / mk.sum()); ks += k; ns += int(mk.sum())
            lo_ci, hi_ci = A.clopper_pearson(ks, ns)
            size_rows.append(dict(method=lab, size=sz, n_per_seed=int(A.size_mask(ms[0].area, lo, hi).sum()), recall=fmt_ms(v, 3),
                                  pooled_seeds_ci95='[%.3f, %.3f]' % (lo_ci, hi_ci), recall_mean=round(float(np.mean(v)), 4),
                                  ci_lo=round(lo_ci, 4), ci_hi=round(hi_ci, 4)))
    write('lamr_round3.csv', rows)
    write('fppi_curves_round3.csv', curves)
    write('fig6_recall_by_size_round3.csv', size_rows)
    say('  LAMR convention: for a reference FPPI beyond the end of a curve (extraction threshold 0.01) the miss rate of the '
        'curve end is used; for a reference FPPI below the start of a curve the miss rate is 1.')


# ================================================================= 3. every condition with the new pooled columns
def part_cond3():
    say('\n## 3. Every condition: recall at the 1% budget on the 2,196 pool and on the 3,358 unconsulted negatives')
    base = {r['condition']: r for r in A.read_csv(os.path.join(A.REV, 'results', 'round2', 'conditions_round2.csv'))}
    rows = []
    for lab, ms in items_all():
        r = dict(base[lab])
        res = [r_at(m, m.pool(P3), 1.0) for m in ms]
        r['R_FPR1_pooled2196'] = fmt_ms([x[1] for x in res], 3)
        r['thr_pooled2196'] = '/'.join(str(x[0]) for x in res)
        r['small_recall_pooled2196'] = fmt_ms([float((m.conf[m.area <= 0.01] >= x[0]).mean()) for m, x in zip(ms, res)], 3)
        res = [r_at(m, m.pool(UNC), 1.0) for m in ms]
        r['R_FPR1_unconsulted3358'] = fmt_ms([x[1] for x in res], 3)
        r['thr_unconsulted3358'] = '/'.join(str(x[0]) for x in res)
        rows.append(r)
        say('  %-44s R@1%% pooled 2,196 %-15s (thr %s)  unconsulted %-15s' % (lab, r['R_FPR1_pooled2196'], r['thr_pooled2196'], r['R_FPR1_unconsulted3358']))
    write('conditions_round3.csv', rows)


# ================================================================= 4. verifier baseline with the new pools
def part_verifier3():
    say('\n## 4. Detector + zero-shot CLIP verifier on the new pools (single seed-42 models)')
    items = [('No negatives', OLD['tournament__yolo26n__s42']), ('No negatives + CLIP verifier', OLD['tournament__yolo26n__s42__clipverify']),
             ('Deployed kd6', OLD['kd__kd6__s42']), ('Deployed kd6 + CLIP verifier', OLD['kd__kd6__s42__clipverify']),
             ('M-top s42 (trained negatives)', NEW['M__noKD__yolo26n__s42']), ('Union 3,276 s42 (trained negatives)', NEW['U3276__noKD__yolo26n__s42'])]
    rows = []
    for lab, m in items:
        r = dict(method=lab)
        for s in ['hn_holdout', 'novel', 'dfire_neg', 'F_hard', 'F_cross', DOM]:
            v = m.neg(s)
            r['FPR50_' + s] = A.pct_ci(int((v >= 0.5).sum()), len(v)) if len(v) else '-'
        for pn, subs in (('hard', ['hn_holdout']), ('pooled2196', P3), ('unconsulted3358', UNC), ('fresh', FRESH), ('pooled2596', ORIG)):
            t, rc = r_at(m, m.pool(subs), 1.0)
            r['R_FPR1_' + pn] = '%.3f' % rc if t is not None else 'no operating point'
            r['thr_' + pn] = t
        t = budget_thr(m.pool(P3), 1.0)
        r['small_recall_pooled2196_1pct'] = round(float((m.conf[m.area <= 0.01] >= t).mean()), 3)
        r['recall_at_0.50'] = round(recall_at(m.conf, 0.5), 3)
        rows.append(r)
        say('  %-38s hard %-20s | R@1%% hard %s (%s) pooled 2,196 %s (%s) unconsulted %s fresh %s | small %s'
            % (lab, r['FPR50_hn_holdout'], r['R_FPR1_hard'], r['thr_hard'], r['R_FPR1_pooled2196'], r['thr_pooled2196'],
               r['R_FPR1_unconsulted3358'], r['R_FPR1_fresh'], r['small_recall_pooled2196_1pct']))
    write('clip_verifier_round3.csv', rows)


# ================================================================= 5. in-domain D-Fire, one threshold rule everywhere
NEGSETS = [('both', ['dfire_neg', 'F_cross']), ('cross', ['dfire_neg']), ('frozen', ['F_cross'])]


def grid_thr(neg, target=0.01):
    """Lowest value of the 0.001 grid whose FPR on neg is at most target (None if 0.999 does not reach it)."""
    n = len(neg)
    k = int(math.floor(n * target + 1e-9))          # at most k images may reach the threshold
    if k >= n:
        return 0.001
    s = np.sort(neg)[::-1]
    v = s[k]                                         # the (k+1)-th largest score must stay below the threshold
    t = (math.floor(v * 1000 + 1e-9) + 1) / 1000.0
    t = max(t, 0.001)
    return round(t, 3) if t <= 0.999 + 1e-9 else None


def tpr_grid(pos, neg, target=0.01):
    t = grid_thr(neg, target)
    return t, (float((pos >= t).mean()) if t is not None else None)


def kmu_clips(m):
    clips = ['KMU_flame__flame%d' % i for i in (2, 3, 4, 5)]
    v = []
    for k in clips:
        p = os.path.join(R2.VID, 'indoor_maxconf', m.rid, k + '.csv')
        if not os.path.exists(p):
            return None
        rr = A.read_csv(p)
        v.append(max(max(float(x['flame_max']), float(x['smoke_max'])) for x in rr))
    return v


def part_dfire3(B=2000):
    global RNG
    RNG = np.random.default_rng(2026)
    say('\n## 5. In-domain D-Fire for every condition: 2,301 fire images against D-Fire negatives, threshold grid 0.001')
    vid = {(r['run_id'], r['rate'], r['rule'], r['hold_s']): r for r in A.read_csv(os.path.join(A.REV, 'results', 'round2', 'video_summary_round2.csv'))}
    rows = []
    for lab, ms in items_all():
        r = dict(method=lab, seeds=len(ms), n_pos=len(ms[0].dfire_img()))
        for nname, subs in NEGSETS:
            res = [tpr_grid(m.dfire_img(), m.pool(subs), 0.01) for m in ms]
            chk = [R2.tpr_at(m.dfire_img(), m.pool(subs), 1.0) for m in ms]
            assert all(abs((a[0] or 0) - (b[0] or 0)) < 1e-9 for a, b in zip(res, chk)), (lab, nname, res, chk)
            r['TPR_at_FPR1_' + nname] = fmt_ms([x[1] for x in res], 3)
            r['thr_FPR1_' + nname] = '/'.join(str(x[0]) for x in res)
        both = lambda m: m.pool(['dfire_neg', 'F_cross'])
        for tgt in (0.005, 0.02, 0.05):
            r['TPR_at_FPR%g_both' % (100 * tgt)] = fmt_ms([tpr_grid(m.dfire_img(), both(m), tgt)[1] for m in ms], 3)
        r['AUC_both'] = fmt_ms([R2.auc(m.dfire_img(), both(m)) for m in ms], 4)
        pa = []
        for m in ms:
            g, tp = R2.roc_points(m.dfire_img(), both(m), 0.05)
            pa.append(float(getattr(np, 'trapezoid', getattr(np, 'trapz', None))(tp, g) / 0.05))
        r['pAUC_FPR_le_5pct_norm'] = fmt_ms(pa, 4)
        r['TPR_at_0.50'] = fmt_ms([float((m.dfire_img() >= 0.5).mean()) for m in ms], 3)
        r['FPR_at_0.50_both'] = fmt_ms([fpr(both(m), 0.5) for m in ms], 2)
        r['TPR_at_hard_budget_1pct'] = fmt_ms([float((m.dfire_img() >= budget_thr(m.neg('hn_holdout'), 1.0)).mean()) for m in ms], 3)
        r['thr_hard_budget_1pct'] = '/'.join(str(budget_thr(m.neg('hn_holdout'), 1.0)) for m in ms)
        r['small_recall_0.50'] = fmt_ms([float((m.conf[m.area <= 0.01] >= 0.5).mean()) for m in ms], 3)
        km = [kmu_clips(m) for m in ms]
        if all(k is not None for k in km):
            arr = np.array(km)
            r['KMU_clips_reaching_0.50_of_4'] = fmt_ms(list((arr >= 0.5).sum(1).astype(float)), 2)
            r['KMU_max_conf_per_clip'] = ' / '.join('%.2f' % x for x in arr.mean(0))
        else:
            r['KMU_clips_reaching_0.50_of_4'] = '-'
            r['KMU_max_conf_per_clip'] = '-'
        v = next((vid.get((m.rid, 'native', '3-of-5', '0.0')) for m in ms if (m.rid, 'native', '3-of-5', '0.0') in vid), None)
        r['positive_clips_detected_3of5_native_s42'] = v['positives_detected'] if v else '-'
        rows.append(r)
        say('  %-44s TPR@1%% both %-14s cross %-14s frozen %-14s AUC %-16s | 0.50 %-14s hard budget %-14s KMU %s | clips %s'
            % (lab, r['TPR_at_FPR1_both'], r['TPR_at_FPR1_cross'], r['TPR_at_FPR1_frozen'], r['AUC_both'], r['TPR_at_0.50'],
               r['TPR_at_hard_budget_1pct'], r['KMU_clips_reaching_0.50_of_4'], r['positive_clips_detected_3of5_native_s42']))
    write('dfire_round3.csv', rows)

    # ---- contrasts: the same grid rule, bootstrap over images (positives and negatives resampled, threshold re-chosen)
    say('  contrasts (seed-averaged TPR at 1%% FPR; point value on the full data; %d resamples of images):' % B)
    cons = [('M-top vs no negatives', ('M', False), ('N0', False)), ('M-top vs L-ratio', ('M', False), ('L', False)),
            ('M-top vs random COCO', ('M', False), ('R', False)), ('M-top vs random corpus', ('M', False), ('RC', False)),
            ('L-ratio vs no negatives', ('L', False), ('N0', False)), ('random COCO vs no negatives', ('R', False), ('N0', False)),
            ('audited M-top vs M-top', ('MC', False), ('M', False)), ('union vs M-top', ('U3276', False), ('M', False)),
            ('union + KD vs union', ('U3276', True), ('U3276', False)), ('audited union + KD vs audited union', ('UC', True), ('UC', False)),
            ('no negatives + KD vs no negatives', ('N0', True), ('N0', False)), ('M-top + KD vs M-top', ('M', True), ('M', False)),
            ('deployed model vs its baseline (single models)', 'kd__kd6__s42', 'tournament__yolo26n__s42')]
    crow = []
    for nname, subs in NEGSETS:
        for lab, a, b in cons:
            MA = [OLD[a]] if isinstance(a, str) else cond(*a)
            MB = [OLD[b]] if isinstance(b, str) else cond(*b)
            P = np.array([m.dfire_img() for m in MA + MB])
            N = np.array([m.pool(subs) for m in MA + MB])
            nA = len(MA)

            def stat(pi, ni):
                v, au = [], []
                for k in range(P.shape[0]):
                    pos, neg = P[k][pi], N[k][ni]
                    t = grid_thr(neg, 0.01)
                    v.append(float((pos >= t).mean()) if t is not None else 0.0)
                    au.append(R2.auc(pos, neg))
                return np.mean(v[:nA]) - np.mean(v[nA:]), np.mean(au[:nA]) - np.mean(au[nA:]), np.mean(v[:nA]), np.mean(v[nA:])
            pt = stat(np.arange(P.shape[1]), np.arange(N.shape[1]))
            bs = np.array([stat(RNG.integers(0, P.shape[1], P.shape[1]), RNG.integers(0, N.shape[1], N.shape[1]))[:2] for _ in range(B)])
            lo, hi = np.percentile(bs[:, 0], 2.5), np.percentile(bs[:, 0], 97.5)
            alo, ahi = np.percentile(bs[:, 1], 2.5), np.percentile(bs[:, 1], 97.5)
            crow.append(dict(negatives=nname, contrast=lab, TPR_A=round(pt[2], 4), TPR_B=round(pt[3], 4), TPR_diff=round(pt[0], 4),
                             ci95='[%.4f, %.4f]' % (lo, hi), excludes_0='yes' if lo > 0 or hi < 0 else 'no',
                             AUC_diff=round(pt[1], 4), AUC_ci95='[%.4f, %.4f]' % (alo, ahi), AUC_excludes_0='yes' if alo > 0 or ahi < 0 else 'no'))
            say('   %-8s %-46s TPR %.3f vs %.3f: %+.4f [%.4f, %.4f] | AUC %+.4f [%.4f, %.4f]'
                % (nname, lab, pt[2], pt[3], pt[0], lo, hi, pt[1], alo, ahi))
    write('dfire_contrasts_round3.csv', crow)


# ================================================================= 6. first-alarm latency of every positive clip
def part_video3():
    say('\n## 6. First alarm on every positive clip (3-of-5 rule), from the per-clip results of round 2')
    per = A.read_csv(os.path.join(A.REV, 'results', 'round2', 'video_per_clip_round2.csv'))
    tags = {r['key']: r for r in A.read_csv(os.path.join(HERE, 'video_tags.csv'))}
    rows, summ = [], []
    for lab, rid in (('Baseline, no negatives', 'tournament__yolo26n__s42'), ('Deployed model', 'kd__kd6__s42'),
                     ('Audited union + KD s42', 'UC__KD__yolo26n__s42')):
        for rate in ('native', '16 fps'):
            for hold in ('0.0', '30.0'):
                sel = [r for r in per if r['run_id'] == rid and r['rate'] == rate and r['rule'] == '3-of-5' and r['hold_s'] == hold and r['role'] == 'positive']
                lat = []
                for r in sorted(sel, key=lambda x: x['key']):
                    tg = tags.get(r['key'], {})
                    onset = float(tg['onset_s']) if tg.get('onset_s') not in (None, '') else None
                    fa = float(r['first_alarm_s']) if r['first_alarm_s'] not in ('', None) else None
                    fd = float(r['first_det_s']) if r['first_det_s'] not in ('', None) else None
                    L = (fa - onset) if (fa is not None and onset is not None) else None
                    if L is not None:
                        lat.append(L)
                    rows.append(dict(model=lab, run_id=rid, rate=rate, hold_s=hold, clip=r['key'], scene=r['scene'], content=tg.get('note', ''),
                                     seconds=r['seconds'], fps=r['fps'], onset_s=onset, first_detection_s=fd, first_alarm_s=fa,
                                     latency_s=round(L, 2) if L is not None else None, detected='yes' if fa is not None else 'no'))
                n = len(sel)
                det = sum(1 for r in sel if r['first_alarm_s'] not in ('', None))
                summ.append(dict(model=lab, rate=rate, hold_s=hold, positive_clips=n, detected=det, within_5s=sum(1 for x in lat if x <= 5),
                                 between_5_and_30s=sum(1 for x in lat if 5 < x <= 30), after_30s=sum(1 for x in lat if x > 30),
                                 median_latency_s=round(float(np.median(lat)), 2) if lat else None,
                                 max_latency_s=round(max(lat), 2) if lat else None, missed=n - det))
                say('  %-24s %-6s hold %-4s detected %d/%d: within 5 s %d, 5-30 s %d, after 30 s %d; median %.2f s, max %.1f s'
                    % (lab, rate, hold, det, n, summ[-1]['within_5s'], summ[-1]['between_5_and_30s'], summ[-1]['after_30s'],
                       summ[-1]['median_latency_s'] or 0, summ[-1]['max_latency_s'] or 0))
    write('video_latency_round3.csv', rows)
    write('video_latency_summary_round3.csv', summ)


# ================================================================= 7. room trials replayed at four thresholds
def part_room3():
    say('\n## 7. Room trials: the logged per-frame scores replayed at four thresholds (upper bound on 3-of-5 episodes)')
    trials = sorted(d for d in os.listdir(ROOM) if os.path.isdir(os.path.join(ROOM, d)) and not d.startswith('P0'))
    rows = []
    for d in trials:
        fr = A.read_csv(os.path.join(ROOM, d, 'frames.csv'))
        t = np.array([float(r['t_s']) for r in fr])
        fmax = np.array([float(r['flame_max'] or 0) for r in fr])
        smax = np.array([float(r['smoke_max'] or 0) for r in fr])
        sm = json.load(open(os.path.join(ROOM, d, 'summary.json')))
        live_thr = sm['config']['threshold']
        for tau in (0.50, 0.0931, 0.0842, 0.0484):
            hit = np.maximum(fmax, smax) >= tau
            ep, in_ep, miss, first = 0, False, 0, None
            for i in range(len(hit)):
                w = hit[max(0, i - 4):i + 1].sum()
                if w >= 3 and not in_ep:
                    ep += 1; in_ep = True; miss = 0
                    if first is None:
                        first = float(t[i])
                if in_ep:
                    miss = 0 if hit[i] else miss + 1
                    if miss > 5:
                        in_ep = False
            rows.append(dict(trial=d, live_threshold=live_thr, tau=tau, frames=len(fr), duration_s=round(float(t[-1] - t[0]), 1),
                             frames_any_score_ge_tau=int(hit.sum()), upper_bound_3of5_episodes=ep,
                             first_episode_s=round(first, 2) if first is not None else None,
                             peak_flame=round(float(fmax.max()), 3), peak_smoke=round(float(smax.max()), 3)))
            say('  %-30s live thr %-7s tau %.4f frames>=tau %4d  episodes <= %2d  first %s  peaks flame %.2f smoke %.2f'
                % (d, live_thr, tau, int(hit.sum()), ep, rows[-1]['first_episode_s'], fmax.max(), smax.max()))
    write('room_threshold_replay_round3.csv', rows)


# ================================================================= 8. mAP of the audited union without seed 123
def part_map3(B=1000):
    global RNG
    RNG = np.random.default_rng(2026)
    say('\n## 8. mAP50 of the audited union against no negatives, with and without seed 123 (%d resamples of test images)' % B)
    vs = os.path.join(OUT, 'round2', 'val_stats')
    rids = [m.rid for m in cond('UC', False) + cond('N0', False)]
    sd = R2.StatsData({rid: os.path.join(vs, rid + '.npz') for rid in rids})
    point = {rid: sd.ap(sd.d[rid]) for rid in rids}
    boots = {rid: [] for rid in rids}
    for b in range(B):
        counts = np.bincount(RNG.integers(0, len(sd.imgs), len(sd.imgs)), minlength=len(sd.imgs))
        for rid in rids:
            boots[rid].append(sd.ap(sd.d[rid], counts))
    rows = []
    for rid in rids:
        rows.append(dict(item='per run', run_id=rid, mAP50=round(point[rid][0], 4), mAP50_95=round(point[rid][1], 4)))
        say('  %-28s mAP50 %.4f  mAP50-95 %.4f' % (rid, point[rid][0], point[rid][1]))
    uc = [m.rid for m in cond('UC', False)]
    n0 = [m.rid for m in cond('N0', False)]
    for lab, a_, b_ in (('audited union (3 seeds) vs no negatives (3 seeds)', uc, n0),
                        ('audited union without seed 123 vs no negatives (3 seeds)', [r for r in uc if 's123' not in r], n0),
                        ('audited union without seed 123 vs no negatives without seed 123', [r for r in uc if 's123' not in r], [r for r in n0 if 's123' not in r])):
        for k, nm in ((0, 'mAP50'), (1, 'mAP50_95')):
            pa = np.mean([point[r][k] for r in a_]); pb = np.mean([point[r][k] for r in b_])
            dist = np.mean([[x[k] for x in boots[r]] for r in a_], 0) - np.mean([[x[k] for x in boots[r]] for r in b_], 0)
            lo, hi = np.percentile(dist, 2.5), np.percentile(dist, 97.5)
            rows.append(dict(item=lab, run_id=nm, mAP50=round(pa, 4), mAP50_95=round(pb, 4), diff=round(pa - pb, 4),
                             ci95='[%.4f, %.4f]' % (lo, hi), excludes_0='yes' if lo > 0 or hi < 0 else 'no'))
            say('  %-70s %-9s %.4f vs %.4f: %+.4f [%.4f, %.4f]' % (lab, nm, pa, pb, pa - pb, lo, hi))
    write('map_audited_union_round3.csv', rows)


# ================================================================= 9. overlap of every training set with every evaluation set
def dhash_bits(p, size=8):
    from PIL import Image
    lanczos = getattr(Image, 'Resampling', Image).LANCZOS
    a = np.asarray(Image.open(p).convert('L').resize((size + 1, size), lanczos), dtype=np.int16)
    bits = 0
    for b in (a[:, :-1] > a[:, 1:]).ravel():
        bits = (bits << 1) | int(b)
    return bits


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load_hashes(path):
    return {r['name']: (r['sha256'], r['dhash']) for r in A.read_csv(path)}


def dfire_pos_hashes():
    out = os.path.join(RES, 'dfire_fire_images_hashes.csv')
    if os.path.exists(out):
        return load_hashes(out)
    names = [r['image'] for r in A.read_csv(os.path.join(OUT, 'scores', 'kd__kd6__s42', 'dfire_pos_img.csv'))]
    rows = []
    for n in names:
        p = os.path.join(DFIRE_LOCAL, n)
        rows.append(dict(name=n, sha256=sha256_file(p), dhash='%016x' % dhash_bits(p)))
    write('dfire_fire_images_hashes.csv', rows)
    return {r['name']: (r['sha256'], r['dhash']) for r in rows}


def part_overlap3():
    say('\n## 9. Overlap audit: every training set against every evaluation set (identical SHA-256; dHash Hamming distance <= 4)')
    H = os.path.join(OUT, 'audit', 'hashes')
    H2 = os.path.join(OUT, 'round2', 'hashes')
    src = {'hn_pool': load_hashes(os.path.join(H, 'src_hn_pool.csv')), 'hits': load_hashes(os.path.join(H, 'src_hits.csv')),
           'randbg': load_hashes(os.path.join(H, 'src_randbg.csv')), 'coco_extra': load_hashes(os.path.join(H2, 'coco_extra.csv')),
           'rc': load_hashes(os.path.join(H2, 'rc_pool.csv')), 'e18': load_hashes(os.path.join(H, 'e18_hits.csv'))}
    ns = json.load(open(os.path.join(OUT, 'manifests', 'neg_sets.json')))
    man = {k: v['items'] for k, v in ns.items()}
    for k in ('MC', 'UC', 'PA', 'RC'):
        man[k] = json.load(open(os.path.join(OUT, 'manifests', 'neg_%s.json' % k)))['items']
    e18 = json.load(open(os.path.join(OUT, 'manifests', 'sm_manifest__round0_selected.json')))
    train = collections.OrderedDict()
    train['Positives, home_fire training split (3,900)'] = list(load_hashes(os.path.join(H, 'hf_train.csv')).values())
    for key, lab in (('L', 'L-ratio (1,638)'), ('M', 'M-top (1,638)'), ('MC', 'M-top, audited (1,638)'), ('C', 'Cluster coverage (1,638)'),
                     ('P', 'Places365-only (1,638)'), ('PA', 'Positive-aware (1,638)'), ('R', 'Random COCO (1,638)'),
                     ('R3276', 'Random COCO (3,276)'), ('BG10', 'Background 10% (433)'), ('RC', 'Random, mining corpus (1,638)'),
                     ('U1638', 'Union, subsampled (1,638)'), ('U3276', 'Union (3,276)'), ('UC', 'Union, audited (3,276)')):
        vals = [src[s][n] for s, n in man[key]]
        assert len(vals) == len(man[key]), key
        train[lab] = vals
    train['E1.8 negatives (1,671)'] = [src['e18'][n] for n in e18]
    ev = collections.OrderedDict()
    ev['hard (500)'] = list(load_hashes(os.path.join(H, 'suite_hn_holdout.csv')).values())
    ev['novel (196)'] = list(load_hashes(os.path.join(H, 'suite_novel.csv')).values())
    ev['mining-dev (400)'] = list(load_hashes(os.path.join(H, 'suite_mined_dev.csv')).values())
    ev['cross-corpus (1,500)'] = list(load_hashes(os.path.join(H, 'suite_dfire_neg.csv')).values())
    ev['frozen hard (101)'] = list(load_hashes(os.path.join(H2, 'fresh_F_hard.csv')).values())
    ev['frozen novel (61)'] = list(load_hashes(os.path.join(H2, 'fresh_F_novel.csv')).values())
    ev['frozen cross-corpus (1,500)'] = list(load_hashes(os.path.join(H2, 'fresh_F_cross.csv')).values())
    used = {r['image'] for r in A.read_csv(os.path.join(OUT, 'round2', 'domestic_used.csv')) if r['used'] == '1'}
    dom = load_hashes(os.path.join(H2, 'domestic.csv'))
    ev['domestic (1,500)'] = [dom[n] for n in used]
    ev['home_fire validation split (1,300)'] = list(load_hashes(os.path.join(H, 'hf_val.csv')).values())
    ev['home_fire test split (1,300)'] = list(load_hashes(os.path.join(H, 'hf_test.csv')).values())
    ev['D-Fire fire images (2,301)'] = list(dfire_pos_hashes().values())

    def arr(vals):
        sh = [v[0] for v in vals]
        dh = np.array([int(v[1], 16) for v in vals], dtype=np.uint64)
        return sh, dh

    rows, pairs = [], []
    for tl, tv in train.items():
        tsh, tdh = arr(tv)
        tset = set(tsh)
        for el, evv in ev.items():
            esh, edh = arr(evv)
            exact = sum(1 for s in esh if s in tset)
            near_pairs, near_imgs, near_train = 0, set(), 0
            for i0 in range(0, len(tdh), 2048):
                x = np.bitwise_xor(tdh[i0:i0 + 2048][:, None], edh[None, :])
                ham = np.bitwise_count(x)
                near_train += int((ham.min(1) <= 4).sum())          # one count per training image, as in the first audit
                ii, jj = np.nonzero(ham <= 4)
                near_pairs += len(ii)
                near_imgs.update(jj.tolist())
                for a_, b_ in zip(ii, jj):
                    pairs.append(dict(training_set=tl, evaluation_set=el, train_index=int(i0 + a_), eval_index=int(b_), hamming=int(ham[a_, b_])))
            rows.append(dict(training_set=tl, evaluation_set=el, n_train=len(tv), n_eval=len(evv), identical_sha256=exact,
                             near_duplicate_training_images_dhash_le4=near_train, near_duplicate_pairs_dhash_le4=near_pairs,
                             evaluation_images_with_a_near_duplicate=len(near_imgs)))
        say('  %-44s ' % tl + ' '.join('%s:%d/%d/%d' % (el.split(' (')[0][:9], r['identical_sha256'], r['near_duplicate_training_images_dhash_le4'],
                                                           r['evaluation_images_with_a_near_duplicate']) for el, r in zip(ev, rows[-len(ev):])))
    write('overlap_round3.csv', rows)
    write('overlap_pairs_round3.csv', pairs)
    # the two halves of the union, and the audited sets against their originals
    for a_, b_, lab in (('L-ratio (1,638)', 'M-top (1,638)', 'L-ratio vs M-top'), ('L-ratio (1,638)', 'M-top, audited (1,638)', 'L-ratio vs audited M-top')):
        ash, adh = arr(train[a_]); bsh, bdh = arr(train[b_])
        exact = len(set(ash) & set(bsh))
        ham = np.bitwise_count(np.bitwise_xor(adh[:, None], bdh[None, :]))
        say('  %-28s identical %d, images of the first set with a near duplicate in the second %d (pairs %d)'
            % (lab, exact, int((ham.min(1) <= 4).sum()), int((ham <= 4).sum())))


# ================================================================= 10. Table 1 runs beside the factorial runs
def part_t1t2():
    say('\n## 10. The yolo26n runs of the backbone selection beside the no-negatives runs of the factorial study, same recipe and seeds')
    rows = []
    for s in A.SEEDS:
        old = OLD['tournament__yolo26n__s%d' % s]
        new = NEW['N0__noKD__yolo26n__s%d' % s]
        rows.append(dict(seed=s, table1_run='tournament__yolo26n__s%d' % s, table1_mAP50=old.val.get('mAP50'), table1_mAP50_95=old.val.get('mAP5095'),
                         table1_FPR50_hard=round(fpr(old.neg('hn_holdout'), 0.5), 2), table1_R_FPR1_hard=round(r_at(old, old.neg('hn_holdout'), 1.0)[1], 3),
                         table2_run=new.rid, table2_mAP50=new.val['mAP50'], table2_mAP50_95=new.val['mAP5095'],
                         table2_FPR50_hard=round(fpr(new.neg('hn_holdout'), 0.5), 2), table2_R_FPR1_hard=round(r_at(new, new.neg('hn_holdout'), 1.0)[1], 3),
                         table2_gpu=new.done['hardware']['gpu'], table2_ultralytics=new.done['hardware']['ultralytics'],
                         table2_torch=new.done['hardware']['torch'], table2_epochs=new.done.get('epochs_run'), table2_best_epoch=new.done.get('best_epoch')))
        say('  seed %-5d Table 1: mAP50 %.4f hard %.2f%% | Table 2: mAP50 %.4f hard %.2f%% (%s, epochs %s)'
            % (s, rows[-1]['table1_mAP50'], rows[-1]['table1_FPR50_hard'], rows[-1]['table2_mAP50'], rows[-1]['table2_FPR50_hard'],
               rows[-1]['table2_gpu'], rows[-1]['table2_epochs']))
    write('table1_vs_table2_round3.csv', rows)


PARTS = collections.OrderedDict([('budget', part_budget3), ('lamr', part_lamr3), ('cond', part_cond3), ('verifier', part_verifier3),
                                 ('dfire', part_dfire3), ('video', part_video3), ('room', part_room3), ('map', part_map3),
                                 ('overlap', part_overlap3), ('t1t2', part_t1t2)])

if __name__ == '__main__':
    want = sys.argv[1:] or list(PARTS)
    for k in want:
        PARTS[k]()
    tag = '_'.join(want) if sys.argv[1:] else 'all'
    with open(os.path.join(RES, 'summary_round3_%s.md' % tag), 'w', encoding='utf-8') as f:
        f.write('\n'.join(SUMMARY) + '\n')
