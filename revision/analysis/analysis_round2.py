# -*- coding: utf-8 -*-
"""SAFE-Fire extended study, round 2: analyses of SFS_06 and SFS_07 together with every earlier run.

Input : revision/data
Output: revision/results/round2/*.csv and summary_round2_*.md

Definitions are those of analysis_results.py (imported below), plus:
  * domestic set     = 1,500 household images of SUN RGB-D (bedroom, bathroom, living room, kitchen, dining,
                       home office, playroom), a source never used for mining or training; audited
  * MH-McNemar       = exact McNemar on the discordant pairs summed over the three seeds (Mantel-Haenszel for
                       matched pairs, stratified by seed); Holm adjustment over the whole family of tests
  * image bootstrap  = 5,000 resamples of images (the three seeds of an image stay together) of the
                       seed-averaged difference in false positive rate
  * mAP bootstrap    = 1,000 resamples of the 1,300 test images; mAP recomputed from the saved boxes with
                       Ultralytics' own matching and AP code
  * D-Fire in domain = 2,301 D-Fire test images with fire or smoke against the 1,500 + 1,500 D-Fire negatives
"""
import collections
import csv
import gzip
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analysis_results as A  # noqa: E402  (loads every run and rescored model)

RES = os.path.join(A.REV, 'results', 'round2')
os.makedirs(RES, exist_ok=True)
A.RES = RES
OUT, NEW, OLD, SEEDS = A.OUT, A.NEW, A.OLD, A.SEEDS
ORIG, FRESH = A.ORIG, A.FRESH
DOM = 'domestic'
SUBS = ORIG + FRESH + [DOM]
NAME = dict(A.NAME, domestic='domestic (SUN RGB-D)')
A.LABEL.update({'RC': 'Random from the mining corpus (1,638)', 'MC': 'M-top after the audit (1,638)',
                'UC': 'Union after the audit (3,276)'})
SUMMARY = []
RNG = np.random.default_rng(2026)


def say(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    SUMMARY.append(s)


cond, fpr, fmt_ms, r_at, budget_thr, recall_at, write = A.cond, A.fpr, A.fmt_ms, A.r_at, A.budget_thr, A.recall_at, A.write
CONDS2 = A.CONDS + [('RC', False), ('MC', False), ('UC', False), ('UC', True)]
PAPER = [('Deployed kd6 (paper model)', 'kd__kd6__s42'), ('No negatives (paper model)', 'tournament__yolo26n__s42')]


def holm(ps):
    m = len(ps)
    order = np.argsort(ps)
    adj = np.empty(m)
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (m - k) * ps[i]))
        adj[i] = run
    return adj


def exact_two_sided(n01, n10):
    m = n01 + n10
    return 1.0 if m == 0 else min(1.0, 2 * A.binom_cdf(min(n01, n10), m, 0.5))


# ================================================================= 1. every condition, round-2 columns
def part_conditions():
    say('\n## 1. Every condition with the round-2 columns (three-seed mean ± SD; FPR at 0.50 in %)')
    rows = []
    items = [('%s%s' % (A.LABEL[n], ' + KD' if kd else ''), cond(n, kd), n, kd) for n, kd in CONDS2]
    items += [(lab, [OLD[rid]], rid, None) for lab, rid in PAPER]
    for lab, ms, n, kd in items:
        if not ms:
            continue
        r = dict(condition=lab, set=n, distillation='' if kd is None else ('yes' if kd else 'no'), seeds=len(ms),
                 mAP50=fmt_ms([m.val['mAP50'] for m in ms]), mAP50_95=fmt_ms([m.val['mAP5095'] for m in ms]))
        for s in SUBS:
            r['FPR50_' + s] = fmt_ms([fpr(m.neg(s), 0.5) for m in ms], 2)
        r['R_FPR1_hard'] = fmt_ms([r_at(m, m.neg('hn_holdout'), 1.0)[1] for m in ms], 3)
        r['R_FPR1_pooled'] = fmt_ms([r_at(m, m.pool(ORIG), 1.0)[1] for m in ms], 3)
        r['R_FPR1_fresh'] = fmt_ms([r_at(m, m.pool(FRESH), 1.0)[1] for m in ms], 3)
        r['R_FPR1_domestic'] = fmt_ms([r_at(m, m.neg(DOM), 1.0)[1] for m in ms], 3)
        r['recall_0.50'] = fmt_ms([recall_at(m.conf, 0.5) for m in ms], 3)
        r['small_recall_0.50'] = fmt_ms([float((m.conf[m.area <= 0.01] >= 0.5).mean()) for m in ms], 3)
        r['dfire_img_det_0.50'] = fmt_ms([float((m.dfire_img() >= 0.5).mean()) for m in ms], 3)
        rows.append(r)
        say('  %-44s mAP50 %-17s hard %-12s Fhard %-12s Fnovel %-12s Fcross %-12s domestic %-12s R@1%%pool %s'
            % (lab, r['mAP50'], r['FPR50_hn_holdout'], r['FPR50_F_hard'], r['FPR50_F_novel'], r['FPR50_F_cross'],
               r['FPR50_domestic'], r['R_FPR1_pooled']))
    write('conditions_round2.csv', rows)


# ================================================================= 2. seed-pooled paired tests with Holm
CONTRASTS2 = A.CONTRASTS + [
    ('M-top vs random from the mining corpus', ('M', False), ('RC', False)),
    ('random corpus vs random COCO', ('RC', False), ('R', False)),
    ('L-ratio vs random corpus', ('L', False), ('RC', False)),
    ('Places-only vs random corpus', ('P', False), ('RC', False)),
    ('audited M-top vs M-top', ('MC', False), ('M', False)),
    ('audited M-top vs L-ratio', ('MC', False), ('L', False)),
    ('audited M-top vs random corpus', ('MC', False), ('RC', False)),
    ('audited union vs union', ('UC', False), ('U3276', False)),
    ('audited union+KD vs union+KD', ('UC', True), ('U3276', True)),
    ('distillation, audited union', ('UC', True), ('UC', False)),
]


def part_mh(B=5000):
    global RNG
    RNG = np.random.default_rng(2026)          # every section draws its own resamples
    say('\n## 2. Seed-pooled paired tests at 0.50: MH-McNemar (discordant pairs summed over seeds), Holm over %d contrasts x %d subsets'
        % (len(CONTRASTS2), len(SUBS)))
    rows = []
    for lab, a, b in CONTRASTS2:
        MA, MB = cond(*a), cond(*b)
        if len(MA) != 3 or len(MB) != 3:
            continue
        for s in SUBS:
            for ma, mb in zip(MA, MB):
                assert ma.seed == mb.seed and (ma.neg_names(s) == mb.neg_names(s)).all()
            XA = np.array([m.neg(s) >= 0.5 for m in MA])
            XB = np.array([m.neg(s) >= 0.5 for m in MB])
            n01 = int((XA & ~XB).sum())
            n10 = int((~XA & XB).sum())
            per = [A.mcnemar(xa, xb) for xa, xb in zip(XA, XB)]
            d = XA.mean(0) - XB.mean(0)
            idx = RNG.integers(0, len(d), (B, len(d)))
            bs = 100.0 * d[idx].mean(1)
            rows.append(dict(contrast=lab, A='%s%s' % (a[0], '+KD' if a[1] else ''), B='%s%s' % (b[0], '+KD' if b[1] else ''),
                             subset=NAME[s], n_images=XA.shape[1],
                             FPR_A=round(100 * XA.mean(), 2), FPR_B=round(100 * XB.mean(), 2),
                             diff_pp=round(100 * d.mean(), 2), diff_ci95='[%.2f, %.2f]' % (np.percentile(bs, 2.5), np.percentile(bs, 97.5)),
                             only_A=n01, only_B=n10, OR_MH=round(n01 / n10, 3) if n10 else ('inf' if n01 else 'n/a'),
                             p_MH=exact_two_sided(n01, n10),
                             seeds_A_lower_sig=sum(1 for (x, y, p) in per if p < 0.05 and x < y),
                             seeds_A_higher_sig=sum(1 for (x, y, p) in per if p < 0.05 and x > y)))
    adj = holm(np.array([r['p_MH'] for r in rows]))
    for r, p in zip(rows, adj):
        r['p_Holm'] = float('%.4g' % p)
        r['p_MH'] = float('%.4g' % r['p_MH'])
        r['verdict'] = ('A lower' if r['diff_pp'] < 0 else 'A higher') if p < 0.05 else 'no significant difference'
    write('mh_mcnemar_holm.csv', rows)
    say('  %d tests; significant after Holm: %d' % (len(rows), sum(1 for r in rows if r['p_Holm'] < 0.05)))
    for r in rows:
        if r['subset'] in (NAME['hn_holdout'], NAME['dfire_neg'], NAME['F_hard'], NAME['F_cross'], NAME[DOM]):
            say('  %-40s %-22s A %6.2f%% B %6.2f%% diff %6.2f %-16s pMH %-9.3g Holm %-9.3g %s'
                % (r['contrast'], r['subset'], r['FPR_A'], r['FPR_B'], r['diff_pp'], r['diff_ci95'], r['p_MH'], r['p_Holm'], r['verdict']))


# ================================================================= 3. mAP with bootstrap intervals
def iou_mat(a, b):
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    bb = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.clip(aa[:, None] + bb[None, :] - inter, 1e-9, None)


class MapData(object):
    def __init__(self, imgs, labels):
        self.imgs = imgs
        self.ix = {k: i for i, k in enumerate(imgs)}
        self.tcls = np.array([int(r['cls']) for r in labels])
        self.timg = np.array([self.ix[r['img']] for r in labels])
        xc, yc, w, h = (np.array([float(r[k]) for r in labels]) for k in ('xc', 'yc', 'w', 'h'))
        self.tbox = np.stack([xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2], 1)
        self.iouv = np.linspace(0.5, 0.95, 10)

    def model(self, path):
        with gzip.open(path, 'rt') as f:
            rows = list(csv.DictReader(f))
        pimg = np.array([self.ix[r['img']] for r in rows])
        pcls = np.array([int(r['cls']) for r in rows])
        conf = np.array([float(r['conf']) for r in rows])
        pbox = np.array([[float(r[k]) for k in ('x1', 'y1', 'x2', 'y2')] for r in rows]).reshape(-1, 4)
        tp = np.zeros((len(rows), 10), bool)
        by_t = collections.defaultdict(list)
        for j, i in enumerate(self.timg):
            by_t[i].append(j)
        by_p = collections.defaultdict(list)
        for j, i in enumerate(pimg):
            by_p[i].append(j)
        for i, pj in by_p.items():
            tj = by_t.get(i, [])
            if not tj:
                continue
            pj, tj = np.array(pj), np.array(tj)
            iou = iou_mat(self.tbox[tj], pbox[pj]) * (self.tcls[tj][:, None] == pcls[pj][None, :])
            for k, thr in enumerate(self.iouv):
                mt = np.array(np.nonzero(iou >= thr)).T
                if mt.shape[0]:
                    if mt.shape[0] > 1:
                        mt = mt[iou[mt[:, 0], mt[:, 1]].argsort()[::-1]]
                        mt = mt[np.unique(mt[:, 1], return_index=True)[1]]
                        mt = mt[np.unique(mt[:, 0], return_index=True)[1]]
                    tp[pj[mt[:, 1]], k] = True
        return dict(tp=tp, conf=conf, pcls=pcls, pimg=pimg)

    def ap(self, d, counts=None):
        from ultralytics.utils.metrics import ap_per_class
        if counts is None:
            res = ap_per_class(d['tp'], d['conf'], d['pcls'], self.tcls)
        else:
            idx = np.repeat(np.arange(len(d['conf'])), counts[d['pimg']])
            res = ap_per_class(d['tp'][idx], d['conf'][idx], d['pcls'][idx], np.repeat(self.tcls, counts[self.timg]))
        ap = res[5]
        return float(ap[:, 0].mean()), float(ap.mean())


MAP_CONTRASTS = [('%s vs no negatives' % n, (n, False), ('N0', False)) for n in ('BG10', 'R', 'RC', 'L', 'M', 'MC', 'C', 'P', 'PA', 'U1638', 'U3276', 'UC')]
MAP_CONTRASTS += [('distillation, %s' % n, (n, True), (n, False)) for n in ('N0', 'L', 'M', 'U1638', 'U3276', 'PA', 'UC')]
MAP_CONTRASTS += [('M-top vs L-ratio', ('M', False), ('L', False)), ('M-top vs random corpus', ('M', False), ('RC', False)),
                  ('random corpus vs random COCO', ('RC', False), ('R', False)), ('audited M-top vs M-top', ('MC', False), ('M', False)),
                  ('audited union vs union', ('UC', False), ('U3276', False)), ('audited union+KD vs union+KD', ('UC', True), ('U3276', True)),
                  ('union+KD vs no negatives', ('U3276', True), ('N0', False))]


class StatsData(object):
    """Per-image matching statistics captured from Ultralytics' own validation (SFS_07): exact mAP."""

    def __init__(self, files):
        self.d = {}
        names = None
        for rid, f in files.items():
            z = np.load(f)
            tp = np.unpackbits(z['tp'], axis=1)[:, :int(z['n_iou'])].astype(bool)
            nm = [str(x) for x in z['im_name']]
            names = names or sorted(nm)
            ix = {k: i for i, k in enumerate(names)}
            remap = np.array([ix[k] for k in nm])
            self.d[rid] = dict(tp=tp, conf=z['conf'], pcls=z['pred_cls'], pimg=remap[z['pred_img']],
                               tcls=z['target_cls'], timg=remap[z['target_img']], m50=float(z['mAP50']), m95=float(z['mAP5095']))
        self.imgs = names

    def ap(self, d, counts=None):
        from ultralytics.utils.metrics import ap_per_class
        if counts is None:
            res = ap_per_class(d['tp'], d['conf'], d['pcls'], d['tcls'])
        else:
            idx = np.repeat(np.arange(len(d['conf'])), counts[d['pimg']])
            res = ap_per_class(d['tp'][idx], d['conf'][idx], d['pcls'][idx], np.repeat(d['tcls'], counts[d['timg']]))
        ap = res[5]
        return float(ap[:, 0].mean()), float(ap.mean())


def part_map(B=1000):
    global RNG
    RNG = np.random.default_rng(2026)          # every section draws its own resamples
    say('\n## 3. mAP differences with bootstrap intervals over the 1,300 test images (seed-averaged, %d resamples)' % B)
    need = sorted({m.rid for _, a, b in MAP_CONTRASTS for m in cond(*a) + cond(*b)})
    vs = os.path.join(OUT, 'round2', 'val_stats')
    files = {rid: os.path.join(vs, rid + '.npz') for rid in need}
    if all(os.path.exists(f) for f in files.values()):
        sd = StatsData(files)
        say('  source: Ultralytics validation statistics per image (SFS_07), %d images' % len(sd.imgs))
        point = {rid: sd.ap(d) for rid, d in sd.d.items()}
        say('  recomputed vs the same validation run: max |diff| mAP50 %.5f, mAP50-95 %.5f; vs val_test.json of the runs: max |diff| %.4f'
            % (max(abs(point[r][0] - sd.d[r]['m50']) for r in point), max(abs(point[r][1] - sd.d[r]['m95']) for r in point),
               max(abs(point[r][0] - NEW[r].val['mAP50']) for r in point)))
        boots = {rid: [] for rid in sd.d}
        for b in range(B):
            counts = np.bincount(RNG.integers(0, len(sd.imgs), len(sd.imgs)), minlength=len(sd.imgs))
            for rid, d in sd.d.items():
                boots[rid].append(sd.ap(d, counts))
        return _map_contrasts(point, boots)
    say('  source: saved boxes with confidence >= 0.01 (approximate; run SFS_07 for exact values)')
    labels = A.read_csv(os.path.join(OUT, 'round2', 'test_labels.csv'))
    # every test image, including the ones without labels: taken from the boxes of the first model and the labels
    names = set(r['img'] for r in labels)
    need = sorted({rid for _, a, b in MAP_CONTRASTS for rid in [m.rid for m in cond(*a) + cond(*b)]})
    paths = {rid: os.path.join(OUT, 'runs', rid, 'eval', 'test_preds.csv.gz') for rid in need}
    for p in paths.values():
        with gzip.open(p, 'rt') as f:
            names |= {ln.split(',', 1)[0] for ln in f.read().splitlines()[1:]}
    n_test = len(A.read_csv(os.path.join(OUT, 'runs', need[0], 'eval', 'test_pos.csv')))
    md = MapData(sorted(names), labels)
    say('  images with labels or boxes: %d, labelled instances: %d (test_pos rows %d)' % (len(md.imgs), len(md.tcls), n_test))
    data = {rid: md.model(p) for rid, p in paths.items()}
    point = {rid: md.ap(d) for rid, d in data.items()}
    chk = [(point[rid][0] - NEW[rid].val['mAP50'], point[rid][1] - NEW[rid].val['mAP5095']) for rid in point]
    say('  recomputed vs Ultralytics val (conf 0.01 boxes vs 0.001): mean |diff| mAP50 %.4f, mAP50-95 %.4f, max %.4f / %.4f'
        % (np.mean([abs(x[0]) for x in chk]), np.mean([abs(x[1]) for x in chk]), max(abs(x[0]) for x in chk), max(abs(x[1]) for x in chk)))
    # images with neither labels nor boxes do not change any AP, so resampling the listed images is equivalent
    boots = {rid: [] for rid in data}
    for b in range(B):
        counts = np.bincount(RNG.integers(0, len(md.imgs), len(md.imgs)), minlength=len(md.imgs))
        for rid, d in data.items():
            boots[rid].append(md.ap(d, counts))
    return _map_contrasts(point, boots)


def _map_contrasts(point, boots):
    rows = []
    for lab, a, bb in MAP_CONTRASTS:
        MA, MB = cond(*a), cond(*bb)
        if len(MA) != 3 or len(MB) != 3:
            continue
        r = dict(contrast=lab)
        for k, nm in ((0, 'mAP50'), (1, 'mAP50_95')):
            pa = np.mean([point[m.rid][k] for m in MA])
            pb = np.mean([point[m.rid][k] for m in MB])
            dist = np.mean([[x[k] for x in boots[m.rid]] for m in MA], 0) - np.mean([[x[k] for x in boots[m.rid]] for m in MB], 0)
            lo, hi = np.percentile(dist, 2.5), np.percentile(dist, 97.5)
            r[nm + '_A'] = round(pa, 4)
            r[nm + '_B'] = round(pb, 4)
            r[nm + '_diff'] = round(pa - pb, 4)
            r[nm + '_ci95'] = '[%.4f, %.4f]' % (lo, hi)
            r[nm + '_excludes_0'] = 'yes' if (lo > 0 or hi < 0) else 'no'
            r[nm + '_diff_ultralytics'] = round(np.mean([m.val['mAP50' if k == 0 else 'mAP5095'] for m in MA])
                                                - np.mean([m.val['mAP50' if k == 0 else 'mAP5095'] for m in MB]), 4)
            r[nm + '_seed_sd_A'] = round(float(np.std([point[m.rid][k] for m in MA], ddof=1)), 4)
        rows.append(r)
        say('  %-34s mAP50 %.4f vs %.4f diff %+.4f %s | mAP50-95 diff %+.4f %s'
            % (lab, r['mAP50_A'], r['mAP50_B'], r['mAP50_diff'], r['mAP50_ci95'], r['mAP50_95_diff'], r['mAP50_95_ci95']))
    write('map_bootstrap.csv', rows)
    write('map_recomputed_per_run.csv', [dict(run_id=rid, mAP50_recomputed=round(v[0], 4), mAP50_95_recomputed=round(v[1], 4),
                                              mAP50_ultralytics=NEW[rid].val['mAP50'], mAP50_95_ultralytics=NEW[rid].val['mAP5095'])
                                         for rid, v in sorted(point.items())])


# ================================================================= 4. matched budget: per-subset and equal weighting
T5b = A.T5 + [('Random from the mining corpus, 1,638', ('RC', False)), ('M-top audited, 1,638', ('MC', False)),
              ('Union audited, 3,276', ('UC', False)), ('Union audited, 3,276 + KD', ('UC', True))]


def thr_rule(m, subs, rule, target=1.0):
    for t in A.GRID:
        f = [fpr(m.neg(s), t) for s in subs]
        if rule == 'pooled':
            ok = fpr(m.pool(subs), t) <= target + 1e-9
        elif rule == 'every subset':
            ok = max(f) <= target + 1e-9
        else:
            ok = float(np.mean(f)) <= target + 1e-9
        if ok:
            return t
    return None


def part_budget2():
    say('\n## 4. Recall at a 1% budget: pooled vs every subset vs equal weighting of subsets (three-seed mean ± SD)')
    rows = []
    groups = [('original suite (hard, novel, mining-dev, cross-corpus)', ORIG), ('original without mining-dev', ['hn_holdout', 'novel', 'dfire_neg']),
              ('fresh suite (F_hard, F_novel, F_cross)', FRESH), ('domestic only', [DOM]),
              ('fresh suite + domestic', FRESH + [DOM])]
    items = [(lab, cond(*c)) for lab, c in T5b] + [(lab, [OLD[rid]]) for lab, rid in PAPER]
    for gname, subs in groups:
        for lab, ms in items:
            for rule in ('pooled', 'every subset', 'equal weight'):
                if len(subs) == 1 and rule != 'pooled':
                    continue
                ts = [thr_rule(m, subs, rule) for m in ms]
                rec = [recall_at(m.conf, t) for m, t in zip(ms, ts)]
                small = [float((m.conf[m.area <= 0.01] >= t).mean()) if t is not None else None for m, t in zip(ms, ts)]
                binding = collections.Counter(max(subs, key=lambda s: fpr(m.neg(s), t)) for m, t in zip(ms, ts) if t is not None)
                row = dict(suite=gname, method=lab, rule=rule, seeds=len(ms), thr='/'.join(str(t) for t in ts),
                           recall=fmt_ms(rec, 3), small_recall=fmt_ms(small, 3),
                           highest_subset='/'.join('%s %d' % (NAME[k], v) for k, v in binding.items()))
                for s in subs:
                    row['FPR_' + s] = fmt_ms([fpr(m.neg(s), t) if t is not None else None for m, t in zip(ms, ts)], 2)
                rows.append(row)
    write('budget_variants.csv', rows)
    for r in rows:
        if r['suite'].startswith('original suite') or r['suite'] in ('fresh suite (F_hard, F_novel, F_cross)', 'domestic only'):
            say('  %-40s %-40s %-13s thr %-16s recall %-15s small %s'
                % (r['suite'][:40], r['method'][:40], r['rule'], r['thr'], r['recall'], r['small_recall']))


# ================================================================= 5. D-Fire in domain
FGRID = np.round(np.arange(0.001, 1.0, 0.001), 3)


def tpr_at(pos, neg, target):
    for t in FGRID:
        if 100.0 * (neg >= t).mean() <= target + 1e-9:
            return t, float((pos >= t).mean())
    return None, None


def auc(pos, neg):
    allv = np.concatenate([pos, neg])
    order = allv.argsort()
    ranks = np.empty(len(allv))
    ranks[order] = np.arange(1, len(allv) + 1)
    # average ranks for ties
    vals, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, ranks)
    ranks = (sums / cnt)[inv]
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def roc_points(pos, neg, fmax=0.2):
    ts = np.unique(np.concatenate([FGRID, [0.0]]))
    f = np.array([(neg >= t).mean() for t in ts])
    t_ = np.array([(pos >= t).mean() for t in ts])
    grid = np.round(np.arange(0, fmax + 1e-9, 0.0025), 4)
    out = []
    for g in grid:
        ok = f <= g + 1e-12
        out.append(float(t_[ok].max()) if ok.any() else 0.0)
    return grid, np.array(out)


def part_dfire(B=2000):
    global RNG
    RNG = np.random.default_rng(2026)          # every section draws its own resamples
    say('\n## 5. In-domain D-Fire: 2,301 positive images vs D-Fire negatives (image level, any box)')
    items = [(lab, cond(*c)) for lab, c in T5b] + [(lab, [OLD[rid]]) for lab, rid in PAPER]
    negsets = [('D-Fire negatives 1,500 (frozen suite)', ['dfire_neg']), ('fresh D-Fire negatives 1,500', ['F_cross']),
               ('both, 3,000', ['dfire_neg', 'F_cross'])]
    rows, curves = [], []
    for lab, ms in items:
        r = dict(method=lab, seeds=len(ms), n_pos=len(ms[0].dfire_img()))
        for nname, subs in negsets:
            res = [tpr_at(m.dfire_img(), m.pool(subs), 1.0) for m in ms]
            r['TPR_at_FPR1_' + nname] = fmt_ms([x[1] for x in res], 3)
            r['thr_' + nname] = '/'.join(str(x[0]) for x in res)
        both = lambda m: m.pool(['dfire_neg', 'F_cross'])
        for tgt in (0.5, 2.0, 5.0):
            r['TPR_at_FPR%g_both' % tgt] = fmt_ms([tpr_at(m.dfire_img(), both(m), tgt)[1] for m in ms], 3)
        r['AUC_both'] = fmt_ms([auc(m.dfire_img(), both(m)) for m in ms], 4)
        pa = []
        for m in ms:
            g, tp = roc_points(m.dfire_img(), both(m), 0.05)
            pa.append(float(getattr(np, "trapezoid", getattr(np, "trapz", None))(tp, g) / 0.05))
        r['pAUC_FPR_le_5pct_norm'] = fmt_ms(pa, 4)
        r['TPR_at_0.50'] = fmt_ms([float((m.dfire_img() >= 0.5).mean()) for m in ms], 3)
        r['FPR_at_0.50_both'] = fmt_ms([fpr(both(m), 0.5) for m in ms], 2)
        rows.append(r)
        g, tp = zip(*[roc_points(m.dfire_img(), both(m), 0.2) for m in ms])
        mean_tp = np.mean(tp, 0)
        for x, y in zip(g[0], mean_tp):
            curves.append(dict(method=lab, fpr=x, tpr_mean=round(float(y), 4)))
        say('  %-42s TPR@1%% (frozen) %-14s (fresh) %-14s (both) %-14s AUC %-16s pAUC5 %s'
            % (lab, r['TPR_at_FPR1_D-Fire negatives 1,500 (frozen suite)'], r['TPR_at_FPR1_fresh D-Fire negatives 1,500'],
               r['TPR_at_FPR1_both, 3,000'], r['AUC_both'], r['pAUC_FPR_le_5pct_norm']))
    write('dfire_in_domain.csv', rows)
    write('dfire_roc_curves.csv', curves)

    # paired contrasts: bootstrap positives and negatives, threshold re-chosen in every resample
    say('  contrasts (seed-averaged TPR at 1% FPR on the 3,000 D-Fire negatives; bootstrap over images, threshold re-chosen):')
    cons = [('M-top vs L-ratio', ('M', False), ('L', False)), ('M-top vs random', ('M', False), ('R', False)),
            ('M-top vs random corpus', ('M', False), ('RC', False)), ('M-top vs no negatives', ('M', False), ('N0', False)),
            ('L-ratio vs no negatives', ('L', False), ('N0', False)), ('audited M-top vs M-top', ('MC', False), ('M', False)),
            ('union+KD vs union', ('U3276', True), ('U3276', False)), ('union vs M-top', ('U3276', False), ('M', False))]
    crow = []
    for lab, a, b in cons:
        MA, MB = cond(*a), cond(*b)
        P = np.array([m.dfire_img() for m in MA + MB])
        N = np.array([m.pool(['dfire_neg', 'F_cross']) for m in MA + MB])

        def stat(pi, ni):
            v = []
            for k in range(len(MA) + len(MB)):
                pos, neg = P[k][pi], N[k][ni]
                t = np.quantile(neg, 0.99, method='higher') + 1e-9
                t = max(t, 0.001)
                v.append(float((pos >= t).mean()))
            return np.mean(v[:len(MA)]) - np.mean(v[len(MA):])
        pt = stat(np.arange(P.shape[1]), np.arange(N.shape[1]))
        bs = [stat(RNG.integers(0, P.shape[1], P.shape[1]), RNG.integers(0, N.shape[1], N.shape[1])) for _ in range(B)]
        lo, hi = np.percentile(bs, 2.5), np.percentile(bs, 97.5)
        crow.append(dict(contrast=lab, TPR_diff=round(pt, 4), ci95='[%.4f, %.4f]' % (lo, hi), excludes_0='yes' if lo > 0 or hi < 0 else 'no'))
        say('   %-28s TPR difference %+.4f [%.4f, %.4f]' % (lab, pt, lo, hi))
    write('dfire_in_domain_contrasts.csv', crow)

    ind = A.read_csv(os.path.join(OUT, 'round2', 'dfire_indoor.csv'))
    rows = []
    for s in ('dfire_neg', 'F_cross'):
        sub = [r for r in ind if r['subset'] == s]
        k = sum(r['label'] == 'indoor' for r in sub)
        lo, hi = A.clopper_pearson(k, len(sub))
        rows.append(dict(subset=s, n=len(sub), indoor=k, share=A.pct_ci(k, len(sub))))
        say('  indoor share (CLIP zero-shot, checked on 48 tiles per subset) %-10s %d of %d = %s' % (s, k, len(sub), A.pct_ci(k, len(sub))))
    write('dfire_indoor_share.csv', rows)


# ================================================================= 6. video with every clip, native rate and 16 fps
VID = os.path.join(OUT, 'video')
VM2 = A.VID_MODELS + [('Random corpus s42', 'RC__noKD__yolo26n__s42'), ('Audited M-top s42', 'MC__noKD__yolo26n__s42'),
                      ('Audited union s42', 'UC__noKD__yolo26n__s42'), ('Audited union + KD s42', 'UC__KD__yolo26n__s42'),
                      ('Audited union + KD s123', 'UC__KD__yolo26n__s123'), ('Audited union + KD s2024', 'UC__KD__yolo26n__s2024')]
TMP16 = os.path.join(os.environ.get('TEMP', HERE), 'sfs_dets16')


def resample16(src, key, model):
    """Detections of the frames a 16 fps camera would have delivered (nearest earlier frame in time)."""
    dst = os.path.join(TMP16, model, key + '.csv')
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return dst
    rows = A.read_csv(src)
    by = collections.defaultdict(list)
    times = {}
    for r in rows:
        f = int(r['frame'])
        times[f] = float(r['time_s'])
        by[f].append(r)
    frames = sorted(times)
    t_end = times[frames[-1]]
    ts = [times[f] for f in frames]
    if len(ts) > 1 and float(np.median(np.diff(ts))) >= 1 / 16.5:
        return src                       # native rate at or below 16 fps: no frames can be added, keep the clip as it is
    out, k, j = [], 0, 0
    while k / 16.0 <= t_end + 1e-9:
        t = k / 16.0
        while j + 1 < len(frames) and ts[j + 1] <= t + 1e-9:
            j += 1
        for r in by[frames[j]]:
            out.append(dict(r, frame=k, time_s=round(t, 4)))
        k += 1
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['frame', 'time_s', 'x1', 'y1', 'x2', 'y2', 'conf', 'cls'])
        w.writeheader()
        w.writerows(out)
    return dst


def clip_stats(path):
    rows = A.read_csv(path)
    c = [float(r['conf']) for r in rows if r['conf'] != '']
    frames = {}
    for r in rows:
        if r['conf'] != '':
            frames[r['frame']] = max(frames.get(r['frame'], 0.0), float(r['conf']))
    nfr = len({r['frame'] for r in rows})
    return {'max_conf': round(max(c), 3) if c else 0.0, 'frames': nfr,
            'frames_ge_0.30': sum(1 for v in frames.values() if v >= 0.3),
            'frames_ge_0.50': sum(1 for v in frames.values() if v >= 0.5)}


def part_video2():
    sys.path.insert(0, os.path.join(A.REPO, 'code', 'analysis'))
    import temporal_alarm as TA
    say('\n## 6. Video with every clip (six clips re-encoded), native frame rate and resampled to 16 fps')
    vl = A.read_csv(os.path.join(OUT, 'round2', 'video_list_round2.csv'))
    tags = {r['key']: r for r in A.read_csv(os.path.join(HERE, 'video_tags.csv'))}
    neg = [v for v in vl if v['role'] == 'negative' and v['readable'] == '1']
    pos = [v for v in vl if v['role'] == 'positive' and v['readable'] == '1']
    say('  readable now: %d negative clips (%.1f min), %d positive clips; re-encoded: %s'
        % (len(neg), sum(float(v['seconds']) for v in neg) / 60, len(pos), [v['key'] for v in vl if v['reencoded'] == '1']))
    fps = collections.Counter(round(float(v['fps'])) for v in neg + pos)
    say('  native frame rates of the clips: %s' % dict(sorted(fps.items())))
    rows, per = [], []
    for lab, mid in VM2:
        for rate in ('native', '16 fps'):
            for (K, N, hold) in ((1, 1, 0.0), (3, 5, 0.0), (3, 5, 30.0)):
                res = {}
                for v in neg + pos:
                    p = os.path.join(VID, 'dets', mid, v['key'] + '.csv')
                    if not os.path.exists(p):
                        res[v['key']] = None
                        continue
                    if rate == '16 fps':
                        p = resample16(p, v['key'], mid)
                    on = tags.get(v['key'], {}).get('onset_s')
                    res[v['key']] = TA.run_video(p, K, N, 0.30, 0.50, onset_s=float(on) if on not in (None, '') else None, hold_s=hold)
                miss = [v['key'] for v in neg + pos if res[v['key']] is None]
                al = sum(res[v['key']]['alarms'] for v in neg if res[v['key']])
                dur = sum(res[v['key']]['duration_s'] for v in neg if res[v['key']])
                ind = [v for v in neg if tags.get(v['key'], {}).get('scene') == 'indoor']
                al_i = sum(res[v['key']]['alarms'] for v in ind if res[v['key']])
                du_i = sum(res[v['key']]['duration_s'] for v in ind if res[v['key']])
                src = {}
                for nm, kinds in (('FIRESENSE', ('FS_fire', 'FS_smoke')), ('KMU', ('KMU_like',))):
                    sel = [v for v in neg if v['kind'] in kinds and res[v['key']]]
                    a_ = sum(res[v['key']]['alarms'] for v in sel)
                    d_ = sum(res[v['key']]['duration_s'] for v in sel)
                    src[nm] = (round(3600.0 * a_ / d_, 1) if d_ else None, round(d_ / 60, 2))
                fs_neg = [v for v in neg if v['kind'].startswith('FS_')]
                det = [v for v in pos if res[v['key']] and res[v['key']]['alarms'] > 0]
                tta = [res[v['key']]['tta_s'] for v in pos if res[v['key']] and res[v['key']]['tta_s'] is not None]
                row = dict(model=lab, run_id=mid, rate=rate, rule='%d-of-%d' % (K, N), hold_s=hold, missing_files=len(miss),
                           negative_minutes=round(dur / 60, 2), alarms=al, per_hour=round(3600 * al / dur, 1),
                           per_day_of_this_footage=round(24 * 3600 * al / dur, 0),
                           indoor_minutes=round(du_i / 60, 2), indoor_alarms=al_i,
                           per_hour_indoor=round(3600.0 * al_i / du_i, 1) if du_i else None,
                           per_hour_FIRESENSE=src['FIRESENSE'][0], minutes_FIRESENSE=src['FIRESENSE'][1],
                           per_hour_KMU=src['KMU'][0], minutes_KMU=src['KMU'][1],
                           FIRESENSE_neg_clips_with_alarm='%d/%d' % (sum(1 for v in fs_neg if res[v['key']] and res[v['key']]['alarms'] > 0), len(fs_neg)),
                           neg_clips_with_alarm='%d/%d' % (sum(1 for v in neg if res[v['key']] and res[v['key']]['alarms'] > 0), len(neg)),
                           positives_detected='%d/%d' % (len(det), len(pos)),
                           missed_positives=' '.join(v['key'] for v in pos if v not in det),
                           median_tta_s=round(float(np.median(tta)), 2) if tta else None,
                           within_5s='%d/%d' % (sum(1 for x in tta if x <= 5), sum(1 for v in pos if tags.get(v['key'], {}).get('onset_s') not in (None, ''))))
                rows.append(row)
                for v in neg + pos:
                    r = res[v['key']]
                    if r:
                        per.append(dict(model=lab, run_id=mid, rate=rate, rule='%d-of-%d' % (K, N), hold_s=hold, key=v['key'],
                                        kind=v['kind'], role=v['role'], fps=v['fps'], scene=tags.get(v['key'], {}).get('scene', ''),
                                        reencoded=v['reencoded'], seconds=r['duration_s'], alarms=r['alarms'],
                                        first_alarm_s=r['first_alarm_s'], first_det_s=r['first_det_s']))
                say('  %-28s %-6s %-6s hold %-3g %6.1f alarms/h (%3d in %.1f min; %s neg clips firing) | positives %s %s'
                    % (lab, rate, row['rule'], hold, row['per_hour'], al, dur / 60, row['neg_clips_with_alarm'], row['positives_detected'],
                       ('missed: ' + row['missed_positives']) if row['missed_positives'] else ''))
    write('video_summary_round2.csv', rows)
    write('video_per_clip_round2.csv', per)

    # interaction of negatives and the temporal layer, bootstrap over the 35 negative clips (paper models)
    for rate in ('native', '16 fps'):
        cache = {}
        for mid in ('tournament__yolo26n__s42', 'kd__kd6__s42'):
            for (K, N) in ((1, 1), (3, 5)):
                for v in neg:
                    p = os.path.join(VID, 'dets', mid, v['key'] + '.csv')
                    if rate == '16 fps':
                        p = resample16(p, v['key'], mid)
                    cache[(mid, K, N, v['key'])] = TA.run_video(p, K, N, 0.30, 0.50)

        def rate_c(mid, K, N, sample):
            a = sum(cache[(mid, K, N, v['key'])]['alarms'] for v in sample)
            d = sum(cache[(mid, K, N, v['key'])]['duration_s'] for v in sample)
            return 3600.0 * a / d if d else float('nan')

        def factors(sample):
            b0, b1 = rate_c('tournament__yolo26n__s42', 1, 1, sample), rate_c('tournament__yolo26n__s42', 3, 5, sample)
            k0, k1 = rate_c('kd__kd6__s42', 1, 1, sample), rate_c('kd__kd6__s42', 3, 5, sample)
            comb = b0 / k1 if k1 > 0 else float('inf')
            return b0 / k0, b0 / b1, comb, comb / ((b0 / k0) * (b0 / b1))
        point = factors(neg)
        rng = np.random.RandomState(2026)
        boot = []
        for _ in range(5000):
            f = factors([neg[i] for i in rng.randint(0, len(neg), len(neg))])
            if all(np.isfinite(f)):
                boot.append(f)
        boot = np.array(boot)
        q = lambda c: (np.percentile(boot[:, c], 2.5), np.percentile(boot[:, c], 97.5))
        say('  interaction (%s, %d negative clips): negatives x%.2f, layer x%.2f, together x%.1f [%.1f, %.1f], ratio to product %.2f [%.2f, %.2f]'
            % (rate, len(neg), point[0], point[1], point[2], q(2)[0], q(2)[1], point[3], q(3)[0], q(3)[1]))
        write('video_interaction_%s.csv' % rate.replace(' ', ''), [dict(rate=rate, neg_factor=round(point[0], 3), layer_factor=round(point[1], 3),
                                                                    combined=round(point[2], 3), combined_ci='[%.1f, %.1f]' % q(2),
                                                                    ratio_to_product=round(point[3], 3), ratio_ci='[%.2f, %.2f]' % q(3),
                                                                    resamples=len(boot), videos=len(neg))])

    # every missed positive clip of the paper's two models and of the audited union + KD, with what the detector saw
    say('  missed positive clips (3-of-5, native rate), with the detector output on them:')
    mrows = []
    for lab, mid in [('No negatives (paper)', 'tournament__yolo26n__s42'), ('Deployed kd6 (paper)', 'kd__kd6__s42'),
                     ('Audited union + KD s42', 'UC__KD__yolo26n__s42'), ('Audited union + KD s123', 'UC__KD__yolo26n__s123'),
                     ('Audited union + KD s2024', 'UC__KD__yolo26n__s2024')]:
        for v in pos:
            p = os.path.join(VID, 'dets', mid, v['key'] + '.csv')
            r = TA.run_video(p, 3, 5, 0.30, 0.50)
            if r['alarms'] == 0:
                st = clip_stats(p)
                mrows.append(dict(model=lab, key=v['key'], note=tags.get(v['key'], {}).get('note', ''), seconds=r['duration_s'],
                                  first_det_s=r['first_det_s'], **st))
                say('   %-26s %-26s %-50s max conf %.3f, frames >= 0.50: %d of %d, >= 0.30: %d'
                    % (lab, v['key'], tags.get(v['key'], {}).get('note', '')[:50], st['max_conf'], st['frames_ge_0.50'], st['frames'], st['frames_ge_0.30']))
    write('video_missed_positives.csv', mrows)


# ================================================================= 7. small fires and KMU clips for the audited sets
def part_small():
    say('\n## 7. Detection side for every Table 5 row: unseen D-Fire fire images, small fires, KMU clips (three-seed mean ± SD)')
    clips = ['KMU_flame__flame%d' % i for i in (2, 3, 4, 5)]
    rows = []
    items = [(lab, cond(*c)) for lab, c in T5b] + [(lab, [OLD[rid]]) for lab, rid in PAPER]
    for lab, ms in items:
        r = dict(condition=lab, seeds=len(ms))
        r['small_recall_0.50'] = fmt_ms([float((m.conf[m.area <= 0.01] >= 0.5).mean()) for m in ms], 3)
        r['small_recall_pooled1pct'] = fmt_ms([float((m.conf[m.area <= 0.01] >= budget_thr(m.pool(ORIG), 1.0)).mean()) for m in ms], 3)
        ci = [m.dfire_inst() for m in ms]
        r['dfire_small_inst_recall_0.50'] = fmt_ms([float((x[0][x[1] <= 0.01] >= 0.5).mean()) for x in ci], 3)
        r['dfire_img_det_0.50'] = fmt_ms([float((m.dfire_img() >= 0.5).mean()) for m in ms], 3)
        r['dfire_img_det_hard1pct'] = fmt_ms([float((m.dfire_img() >= budget_thr(m.neg('hn_holdout'), 1.0)).mean()) for m in ms], 3)
        mx = []
        for m in ms:
            v = []
            for k in clips:
                p = os.path.join(VID, 'indoor_maxconf', m.rid, k + '.csv')
                if os.path.exists(p):
                    rr = A.read_csv(p)
                    v.append(max(max(float(x['flame_max']), float(x['smoke_max'])) for x in rr))
            mx.append(v)
        if all(len(v) == 4 for v in mx):
            arr = np.array(mx)
            for i, k in enumerate(clips):
                r[k.split('__')[1] + '_max'] = fmt_ms(list(arr[:, i]), 3)
            r['clips_reaching_0.50'] = fmt_ms(list((arr >= 0.5).sum(1).astype(float)), 2)
        rows.append(r)
        say('  %-40s small 0.50 %-14s at 1%% %-14s | D-Fire images 0.50 %-14s at hard 1%% %-14s | KMU clips >= 0.50: %s'
            % (lab, r['small_recall_0.50'], r['small_recall_pooled1pct'], r['dfire_img_det_0.50'], r['dfire_img_det_hard1pct'],
               r.get('clips_reaching_0.50', 'n/a')))
    write('small_fires_round2.csv', rows)


# ================================================================= 8. audit and corpus facts
def part_audit2():
    say('\n## 8. Audit and corpus facts')
    au = A.read_csv(os.path.join(OUT, 'round2', 'mtop_audit_result.csv'))
    mc = json.load(open(os.path.join(OUT, 'manifests', 'neg_MC.json')))
    rc = json.load(open(os.path.join(OUT, 'manifests', 'neg_RC.json')))
    say('  M sheets: %d images (%d M-top + %d reserve); marked %d (%d in M-top, %d in the reserve); M-top refilled from the reserve: %d'
        % (len(au), sum(r['set'] == 'M-top' for r in au), sum(r['set'] == 'reserve' for r in au), sum(r['marked'] == '1' for r in au),
           sum(r['marked'] == '1' and r['set'] == 'M-top' for r in au), sum(r['marked'] == '1' and r['set'] == 'reserve' for r in au), len(mc['refill'])))
    hc = {r['name']: r for r in A.read_csv(os.path.join(OUT, 'audit', 'hit_clusters.csv'))}
    ct = {r['cluster']: r for r in A.read_csv(os.path.join(OUT, 'audit', 'cluster_table.csv'))}
    removed = collections.Counter(hc[n]['cluster'] for n in mc['removed'] if n in hc)
    src = collections.Counter(hc[n]['source'] for n in mc['removed'] if n in hc)
    rows = []
    for c in sorted(ct, key=int):
        rows.append(dict(cluster=int(c), label=ct[c]['label'], hits=ct[c]['n'], in_M_top=ct[c]['n_in_M_top'], removed_in_audit=removed.get(c, 0)))
    write('audit_removed_by_cluster.csv', rows)
    say('  removed M-top images by source: %s; by cluster: %s' % (dict(src), ', '.join('%s (%s) %d' % (c, ct[c]['label'], v) for c, v in removed.most_common())))
    lights = [c for c in ct if any(w in ct[c]['label'].lower() for w in ('lamp', 'light', 'candle', 'bulb'))]
    nh = sum(int(ct[c]['n']) for c in ct)
    nm = sum(int(ct[c]['n_in_M_top']) for c in ct)
    say('  clusters labelled as lights: %d of %d (%s): %.1f%% of the hits, %.1f%% of M-top'
        % (len(lights), len(ct), [ct[c]['label'] for c in lights], 100.0 * sum(int(ct[c]['n']) for c in lights) / nh,
           100.0 * sum(int(ct[c]['n_in_M_top']) for c in lights) / nm))
    say('  random corpus control: %d images = %d Open Images + %d Places365; %d of them are mining hits, %d also in M-top; %d removed in the audit'
        % (rc['n'], rc['n_openimages'], rc['n_places365'], rc['n_mining_hits'], rc['n_in_mtop'], len(rc['flagged'])))
    rm = A.read_csv(os.path.join(OUT, 'round2', 'rc_manifest.csv'))
    say('  RC candidates: %d sampled, fire-like rule %d, near-duplicates of evaluation images %d'
        % (len(rm), sum(r['fire_like'] == '1' for r in rm), sum(r['near_dup_eval'] == '1' for r in rm)))
    du = A.read_csv(os.path.join(OUT, 'round2', 'domestic_used.csv'))
    sc = collections.Counter(r['scene'] for r in du if r['used'] == '1')
    say('  domestic set: %d images used; scenes %s' % (sum(r['used'] == '1' for r in du), dict(sc.most_common())))


def part_lamr():
    say('\n## 9. Log-average miss rate on the pooled 2,596 negatives for every Table 5 row (three-seed mean ± SD)')
    rows = []
    for lab, c in T5b:
        vals = [A.lamr(*A.fppi_curve(m, ORIG)[1:])[0] for m in cond(*c)]
        rows.append(dict(method=lab, seeds=len(vals), LAMR=fmt_ms(vals, 3)))
        say('  %-40s LAMR %s' % (lab, rows[-1]['LAMR']))
    write('lamr_round2.csv', rows)


def part_runs():
    say('\n## 10. Every run of the factorial study, one row (Supplementary Table S4)')
    rows = []
    for rid, m in sorted(NEW.items()):
        r = {'run_id': rid, 'negatives': m.neg_set, 'n_negatives': m.job.get('n_negatives'), 'distillation': m.kd, 'seed': m.seed,
             'mAP50': m.val['mAP50'], 'mAP50_95': m.val['mAP5095'], 'best_epoch': m.done.get('best_epoch'),
             'epochs_run': m.done.get('epochs_run'), 'train_hours': round(m.done.get('train_wall_s', 0) / 3600, 2)}
        for s_ in SUBS:
            r['FPR50_' + s_] = A.pct_ci(int((m.neg(s_) >= 0.5).sum()), len(m.neg(s_)))
        t, rc = r_at(m, m.neg('hn_holdout'), 1.0)
        r['R_FPR1_hard'] = round(rc, 4) if rc is not None else 'no operating point'
        r['thr_FPR1_hard'] = t
        rows.append(r)
    write('runs_all_round2.csv', rows)
    say('  %d runs' % len(rows))


PARTS = collections.OrderedDict([('runs', part_runs), ('lamr', part_lamr),('conditions', part_conditions), ('mh', part_mh), ('map', part_map), ('budget', part_budget2),
                                 ('dfire', part_dfire), ('video', part_video2), ('small', part_small), ('audit', part_audit2)])

if __name__ == '__main__':
    want = sys.argv[1:] or list(PARTS)
    for k in want:
        PARTS[k]()
    tag = '_'.join(want) if sys.argv[1:] else 'all'
    with open(os.path.join(RES, 'summary_round2_%s.md' % tag), 'w', encoding='utf-8') as f:
        f.write('\n'.join(SUMMARY) + '\n')
