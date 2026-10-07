# -*- coding: utf-8 -*-
"""SAFE-Fire: analysis of the extended study (outputs of notebooks SFS_01 to SFS_05).

Input : revision/data       (or the folder named by the environment variable SFS_DATA)
Output: revision/results    (or SFS_RESULTS): *.csv and summary_results.md

Definitions (one for every table):
  * image-level FPR at t   = share of negative images whose max box confidence (extraction 0.01) is >= t
  * instance recall at t   = share of the 1,586 annotated test instances matched by a box of ANY class
                             with IoU >= 0.5 and confidence >= t ("conf_any" in test_pos.csv)
  * R at FPR x%            = instance recall at the LOWEST threshold of the grid 0.01..0.99 whose FPR on the
                             named negative set is <= x%; "no operating point" if no grid value qualifies
  * pooled suite           = hard 500 + novel 196 + mining-dev 400 + cross-corpus 1,500 = 2,596 images
  * fresh suite            = F_hard + F_novel + F_cross, frozen on 2026-10-03 before any model was scored
Statistics: exact Clopper-Pearson 95% intervals, exact two-sided McNemar on paired per-image alarms,
mean and sample SD over three seeds.
"""
import csv, json, math, os, sys, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REV = os.path.dirname(HERE)                       # revision/
REPO = os.path.dirname(REV)
OUT = os.environ.get('SFS_DATA', os.path.join(REV, 'data'))
RES = os.environ.get('SFS_RESULTS', os.path.join(REV, 'results'))
os.makedirs(RES, exist_ok=True)
sys.path.insert(0, os.path.join(REPO, 'code', 'analysis'))   # temporal_alarm.py

GRID = [round(0.01 * i, 2) for i in range(1, 100)]
ORIG = ['hn_holdout', 'novel', 'mined_dev', 'dfire_neg']
FRESH = ['F_hard', 'F_novel', 'F_cross']
NAME = {'hn_holdout': 'hard', 'novel': 'novel', 'mined_dev': 'mining-dev', 'dfire_neg': 'cross-corpus',
        'F_hard': 'fresh hard', 'F_novel': 'fresh novel', 'F_cross': 'fresh cross-corpus'}
SEEDS = (42, 123, 2024)
SUMMARY = []


def say(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    SUMMARY.append(s)


# ------------------------------------------------------------------ statistics
def _logpmf(i, n, p):
    if p <= 0:
        return 0.0 if i == 0 else -math.inf
    if p >= 1:
        return 0.0 if i == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log(1 - p))


def binom_cdf(k, n, p):
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return min(1.0, sum(math.exp(_logpmf(i, n, p)) for i in range(k + 1)))


def binom_sf(m, n, p):
    """P(X >= m)."""
    if m <= 0:
        return 1.0
    if m > n:
        return 0.0
    return min(1.0, sum(math.exp(_logpmf(i, n, p)) for i in range(m, n + 1)))


def clopper_pearson(k, n, a=0.05):
    def bis(f, lo, hi):
        for _ in range(100):
            m = (lo + hi) / 2
            if f(lo) * f(m) <= 0:
                hi = m
            else:
                lo = m
        return (lo + hi) / 2
    lo = 0.0 if k == 0 else bis(lambda p: binom_cdf(k - 1, n, p) - (1 - a / 2), 1e-12, k / n)
    hi = 1.0 if k == n else bis(lambda p: binom_cdf(k, n, p) - a / 2, k / n, 1 - 1e-12)
    return lo, hi


def mcnemar(a, b):
    """a, b: boolean alarm vectors on the same images. Exact two-sided."""
    a = np.asarray(a, bool)
    b = np.asarray(b, bool)
    n01, n10 = int((a & ~b).sum()), int((~a & b).sum())
    m = n01 + n10
    p = 1.0 if m == 0 else min(1.0, 2 * binom_cdf(min(n01, n10), m, 0.5))
    return n01, n10, p


def pct_ci(k, n):
    lo, hi = clopper_pearson(k, n)
    return '%.2f [%.2f, %.2f]' % (100.0 * k / n, 100 * lo, 100 * hi)


def mean_sd(v, nd=4):
    v = [x for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not v:
        return None, None
    m = float(np.mean(v))
    s = float(np.std(v, ddof=1)) if len(v) > 1 else 0.0
    return round(m, nd), round(s, nd)


def fmt_ms(v, nd=4, scale=1.0):
    m, s = mean_sd([x * scale for x in v if x is not None], nd)
    if m is None:
        return '-'
    return ('%.' + str(nd) + 'f ± %.' + str(nd) + 'f') % (m, s)


# ------------------------------------------------------------------ io
def read_csv(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write(name, rows, fields=None):
    if not rows:
        return
    fields = fields or list(dict.fromkeys(k for r in rows for k in r.keys()))
    with open(os.path.join(RES, name), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


class Model(object):
    """Every per-image / per-instance score of one model (new run or rescored old run)."""

    def __init__(self, rid, d):
        self.rid, self.d = rid, d
        self._neg, self._box = {}, {}
        self.val = json.load(open(os.path.join(d, 'val_test.json'))) if os.path.exists(os.path.join(d, 'val_test.json')) else {}
        pos = read_csv(os.path.join(d, 'test_pos.csv'))
        self.pos_img = [r['img'] for r in pos]
        self.conf = np.array([float(r['conf_any']) for r in pos])
        self.cls = np.array([int(float(r['cls'])) for r in pos])
        self.area = np.array([float(r['area']) for r in pos])
        # the CLIP-verified copies (scores/<run>__clipverify) keep the detector-only score instead
        self.conf_same = np.array([float(r['conf_same']) for r in pos]) if pos and 'conf_same' in pos[0] else None
        self.best_cls = np.array([int(float(r['best_cls'])) for r in pos]) if pos and 'best_cls' in pos[0] else None
        self.conf_det = (np.array([float(r['conf_any_detector_only']) for r in pos])
                         if pos and 'conf_any_detector_only' in pos[0] else None)

    def neg(self, s):
        if s not in self._neg:
            p = os.path.join(self.d, 'neg_%s.csv' % s)
            rows = read_csv(p) if os.path.exists(p) else []
            rows.sort(key=lambda r: r['image'])
            self._neg[s] = (np.array([r['image'] for r in rows]), np.array([float(r['max_conf']) for r in rows]))
        return self._neg[s][1]

    def neg_names(self, s):
        self.neg(s)
        return self._neg[s][0]

    def pool(self, subsets):
        return np.concatenate([self.neg(s) for s in subsets])

    def boxes(self, s):
        if s not in self._box:
            p = os.path.join(self.d, 'negboxes_%s.csv' % s)
            self._box[s] = np.array([float(r['conf']) for r in read_csv(p)]) if os.path.exists(p) else np.zeros(0)
        return self._box[s]

    def dfire_img(self):
        p = os.path.join(self.d, 'dfire_pos_img.csv')
        return np.array([float(r['max_conf']) for r in read_csv(p)]) if os.path.exists(p) else None

    def dfire_inst(self):
        p = os.path.join(self.d, 'dfire_pos.csv')
        if not os.path.exists(p):
            return None, None
        rows = read_csv(p)
        return np.array([float(r['conf_any']) for r in rows]), np.array([float(r['area']) for r in rows])


def fpr(neg, t):
    return 100.0 * float((neg >= t).mean())


def budget_thr(neg, target_pct):
    for t in GRID:
        if fpr(neg, t) <= target_pct + 1e-9:
            return t
    return None


def recall_at(conf, t):
    return float((conf >= t).mean()) if t is not None else None


def r_at(model, neg, target_pct):
    t = budget_thr(neg, target_pct)
    return t, recall_at(model.conf, t)


# ------------------------------------------------------------------ loading
def load_new():
    runs = {}
    for rid in sorted(os.listdir(os.path.join(OUT, 'runs'))):
        d = os.path.join(OUT, 'runs', rid)
        if not os.path.exists(os.path.join(d, 'DONE.json')):
            continue
        neg, kd, arch, seed = rid.split('__')
        m = Model(rid, os.path.join(d, 'eval'))
        m.neg_set, m.kd, m.arch, m.seed = neg, kd == 'KD', arch, int(seed[1:])
        m.done = json.load(open(os.path.join(d, 'DONE.json')))
        m.job = json.load(open(os.path.join(d, 'job.json')))
        runs[rid] = m
    return runs


def load_old():
    old = {}
    for rid in sorted(os.listdir(os.path.join(OUT, 'scores'))):
        d = os.path.join(OUT, 'scores', rid)
        if os.path.exists(os.path.join(d, 'test_pos.csv')):
            old[rid] = Model(rid, d)
    return old


NEW = load_new()
OLD = load_old()
say('# Results of the revision runs (SFS_01-05)')
say('new runs: %d | rescored existing models: %d' % (len(NEW), len(OLD)))
N_INST = len(next(iter(NEW.values())).conf)
say('test instances: %d | negatives: %s' % (N_INST, ', '.join('%s %d' % (NAME[s], len(next(iter(NEW.values())).neg(s))) for s in ORIG + FRESH)))


def cond(neg, kd):
    return [NEW['%s__%s__yolo26n__s%d' % (neg, 'KD' if kd else 'noKD', s)] for s in SEEDS
            if '%s__%s__yolo26n__s%d' % (neg, 'KD' if kd else 'noKD', s) in NEW]


CONDS = [('N0', False), ('N0', True), ('L', False), ('L', True), ('M', False), ('M', True),
         ('U1638', False), ('U1638', True), ('U3276', False), ('U3276', True), ('R', False), ('R3276', True),
         ('C', False), ('BG10', False), ('P', False), ('PA', False), ('PA', True)]
LABEL = {'N0': 'No negatives', 'L': 'L-ratio (label-retrieved, 1,638)', 'M': 'M-top (mined, 1,638)',
         'U1638': 'Union subsampled (819+819)', 'U3276': 'Union (3,276)', 'R': 'Random COCO (1,638)',
         'R3276': 'Random COCO (3,276)', 'C': 'Cluster coverage (1,638)', 'BG10': 'Background 10% (433 COCO)',
         'P': 'Places365-only mining (1,638)', 'PA': 'Positive-aware mining (1,638)'}


# ================================================================= 1. factorial
def part_factorial():
    say('\n## 1. Factorial and controls: three-seed mean ± SD (yolo26n, 640 px, same recipe, same GPU type)')
    rows = []
    for neg, kd in CONDS:
        ms = cond(neg, kd)
        if not ms:
            continue
        row = {'set': neg, 'label': LABEL[neg], 'distillation': 'yes' if kd else 'no', 'seeds': len(ms),
               'n_negatives': ms[0].job.get('n_negatives'),
               'mAP50': fmt_ms([m.val['mAP50'] for m in ms]), 'mAP50_95': fmt_ms([m.val['mAP5095'] for m in ms])}
        for s in ORIG + FRESH:
            row['FPR50_' + s] = fmt_ms([fpr(m.neg(s), 0.5) for m in ms], 2)
        row['R_FPR1_hard'] = fmt_ms([r_at(m, m.neg('hn_holdout'), 1.0)[1] for m in ms], 3)
        row['thr_FPR1_hard'] = '/'.join(str(r_at(m, m.neg('hn_holdout'), 1.0)[0]) for m in ms)
        row['R_FPR1_pooled'] = fmt_ms([r_at(m, m.pool(ORIG), 1.0)[1] for m in ms], 3)
        row['R_FPR1_fresh'] = fmt_ms([r_at(m, m.pool(FRESH), 1.0)[1] for m in ms], 3)
        row['recall_at_0.50'] = fmt_ms([recall_at(m.conf, 0.5) for m in ms], 3)
        small = [m.conf[m.area <= 0.01] for m in ms]
        row['small_recall_at_0.50'] = fmt_ms([float((c >= 0.5).mean()) for c in small], 3)
        df = [m.dfire_img() for m in ms]
        row['dfire_img_det_0.50'] = fmt_ms([float((x >= 0.5).mean()) for x in df if x is not None], 3)
        row['best_epoch'] = '/'.join(str(m.done.get('best_epoch')) for m in ms)
        row['epochs_run'] = '/'.join(str(m.done.get('epochs_run')) for m in ms)
        rows.append(row)
        say('  %-6s KD=%-3s mAP50 %-17s hard %-12s novel %-12s cross %-12s Fcross %-12s R@1%%hard %-13s R@1%%pool %s'
            % (neg, row['distillation'], row['mAP50'], row['FPR50_hn_holdout'], row['FPR50_novel'],
               row['FPR50_dfire_neg'], row['FPR50_F_cross'], row['R_FPR1_hard'], row['R_FPR1_pooled']))
    write('factorial_table.csv', rows)

    # every run, one row (for the supplementary experiment map)
    per = []
    for rid, m in sorted(NEW.items()):
        r = {'run_id': rid, 'negatives': m.neg_set, 'n_negatives': m.job.get('n_negatives'), 'distillation': m.kd,
             'seed': m.seed, 'mAP50': m.val['mAP50'], 'mAP50_95': m.val['mAP5095'],
             'best_epoch': m.done.get('best_epoch'), 'epochs_run': m.done.get('epochs_run'),
             'train_hours': round(m.done.get('train_wall_s', 0) / 3600, 2), 'gpu': m.done['hardware']['gpu']}
        for s in ORIG + FRESH:
            k = int((m.neg(s) >= 0.5).sum())
            r['FPR50_' + s] = pct_ci(k, len(m.neg(s)))
        t, rc = r_at(m, m.neg('hn_holdout'), 1.0)
        r['R_FPR1_hard'] = round(rc, 4) if rc is not None else 'no operating point'
        r['thr_FPR1_hard'] = t
        per.append(r)
    write('runs_all_with_ci.csv', per)


# ================================================================= 2. paired tests
CONTRASTS = [  # (label, A, B) -> A versus B, same seed, same images
    ('distillation, no negatives', ('N0', True), ('N0', False)),
    ('distillation, L-ratio', ('L', True), ('L', False)),
    ('distillation, M-top', ('M', True), ('M', False)),
    ('distillation, union 1,638', ('U1638', True), ('U1638', False)),
    ('distillation, union 3,276', ('U3276', True), ('U3276', False)),
    ('distillation, PA', ('PA', True), ('PA', False)),
    ('M-top vs L-ratio', ('M', False), ('L', False)),
    ('M-top vs random', ('M', False), ('R', False)),
    ('L-ratio vs random', ('L', False), ('R', False)),
    ('M-top vs coverage', ('M', False), ('C', False)),
    ('Places-only vs L-ratio', ('P', False), ('L', False)),
    ('Places-only vs random', ('P', False), ('R', False)),
    ('PA vs M-top', ('PA', False), ('M', False)),
    ('union 3,276 vs union 1,638', ('U3276', False), ('U1638', False)),
    ('union+KD vs random 3,276+KD', ('U3276', True), ('R3276', True)),
    ('random vs background 10%', ('R', False), ('BG10', False)),
]


def part_mcnemar():
    say('\n## 2. Paired comparisons (exact McNemar on per-image alarms at 0.50), per seed')
    rows = []
    for lab, a, b in CONTRASTS:
        A, B = cond(*a), cond(*b)
        for ma, mb in zip(A, B):
            assert ma.seed == mb.seed
            for s in ORIG + FRESH:
                na, nb = ma.neg_names(s), mb.neg_names(s)
                assert (na == nb).all()
                xa, xb = ma.neg(s) >= 0.5, mb.neg(s) >= 0.5
                n01, n10, p = mcnemar(xa, xb)
                rows.append(dict(contrast=lab, seed=ma.seed, subset=NAME[s], n=len(xa),
                                 A=ma.rid, B=mb.rid, alarms_A=int(xa.sum()), alarms_B=int(xb.sum()),
                                 only_A=n01, only_B=n10, p_two_sided=round(p, 4)))
    write('mcnemar_factorial.csv', rows)
    # compact verdicts: in how many seeds is A significantly lower / higher than B, per subset
    say('  contrast                         subset             A<B sig  A>B sig  (alarms A vs B, per seed)')
    for lab, a, b in CONTRASTS:
        for s in ORIG + FRESH:
            rs = [r for r in rows if r['contrast'] == lab and r['subset'] == NAME[s]]
            lo = sum(1 for r in rs if r['p_two_sided'] < 0.05 and r['alarms_A'] < r['alarms_B'])
            hi = sum(1 for r in rs if r['p_two_sided'] < 0.05 and r['alarms_A'] > r['alarms_B'])
            if s in ('hn_holdout', 'novel', 'dfire_neg', 'F_cross'):
                say('  %-32s %-18s %d/%d      %d/%d      %s' % (lab, NAME[s], lo, len(rs), hi, len(rs),
                    ' '.join('%d:%d(p=%.3g)' % (r['alarms_A'], r['alarms_B'], r['p_two_sided']) for r in rs)))


# ================================================================= 3. existing models, unified definition
ARCHS = ['yolo26s', 'yolov8s', 'yolo11s', 'yolo26n', 'yolo11n', 'yolov8n']


def part_old_tables():
    say('\n## 3. Existing models re-scored with the unified definition (instance recall, grid 0.01-0.99)')
    master = {r['run_id']: r for r in read_csv(os.path.join(REPO, 'results', 'master_runs.csv'))}
    rows = []
    for rid, m in sorted(OLD.items()):
        if rid.endswith('__clipverify'):
            continue
        r = {'run_id': rid, 'mAP50_rescored': m.val.get('mAP50'), 'mAP50_95_rescored': m.val.get('mAP5095'),
             'mAP50_paper': master.get(rid, {}).get('mAP50'), 'mAP50_95_paper': master.get(rid, {}).get('mAP5095')}
        for s in ORIG + FRESH:
            k = int((m.neg(s) >= 0.5).sum())
            r['FPR50_' + s] = pct_ci(k, len(m.neg(s)))
        for grid_name, grid in (('fine', GRID), ('paper', [round(0.05 * i, 2) for i in range(1, 20)])):
            t = next((g for g in grid if fpr(m.neg('hn_holdout'), g) <= 1.0), None)
            r['R_FPR1_hard_' + grid_name] = round(recall_at(m.conf, t), 4) if t is not None else 'no operating point'
            r['thr_' + grid_name] = t
        r['R_FPR1_hard_paper_value'] = master.get(rid, {}).get('recall_at_fpr1')
        rows.append(r)
    write('existing_models_rescored.csv', rows)

    # Table 1 replacement: six architectures x three seeds
    say('  Table 1 (architectures, 3 seeds, unified definition):')
    t1 = []
    for a in ARCHS:
        ms = [OLD['tournament__%s__s%d' % (a, s)] for s in SEEDS if 'tournament__%s__s%d' % (a, s) in OLD]
        hard = [fpr(m.neg('hn_holdout'), 0.5) for m in ms]
        rr = [r_at(m, m.neg('hn_holdout'), 1.0) for m in ms]
        k = sum(int((m.neg('hn_holdout') >= 0.5).sum()) for m in ms)
        n = sum(len(m.neg('hn_holdout')) for m in ms)
        row = dict(model=a, seeds=len(ms), mAP50_95=fmt_ms([m.val['mAP5095'] for m in ms]),
                   mAP50=fmt_ms([m.val['mAP50'] for m in ms]),
                   FPR50_hard_mean_sd=fmt_ms(hard, 2), FPR50_hard_pooled_ci=pct_ci(k, n),
                   R_FPR1_hard=fmt_ms([x[1] for x in rr], 3), thr='/'.join(str(x[0]) for x in rr),
                   FPR50_novel=fmt_ms([fpr(m.neg('novel'), 0.5) for m in ms], 2),
                   FPR50_cross=fmt_ms([fpr(m.neg('dfire_neg'), 0.5) for m in ms], 2),
                   FPR50_F_cross=fmt_ms([fpr(m.neg('F_cross'), 0.5) for m in ms], 2))
        t1.append(row)
        say('   %-8s mAP50-95 %-16s mAP50 %-16s FPR hard %-13s R@1%% %-14s thr %s'
            % (a, row['mAP50_95'], row['mAP50'], row['FPR50_hard_mean_sd'], row['R_FPR1_hard'], row['thr']))
    write('table1_architectures.csv', t1)

    # transfer of M-top (old runs: three-seed no-negative baselines, seed-42 M-top)
    say('  M-top transfer to other nano architectures (old runs; mined runs are seed 42 only):')
    tr = []
    for a in ('yolo26n', 'yolo11n', 'yolov8n'):
        base = [OLD['tournament__%s__s%d' % (a, s)] for s in SEEDS]
        mid = 'safemine__sm_top__s42' if a == 'yolo26n' else 'safemine__sm_top_%s__s42' % a
        mm = OLD[mid]
        bt = [r_at(m, m.neg('hn_holdout'), 1.0)[1] for m in base]
        t_m, r_m = r_at(mm, mm.neg('hn_holdout'), 1.0)
        b42 = OLD['tournament__%s__s42' % a]
        n01, n10, p = mcnemar(mm.neg('hn_holdout') >= 0.5, b42.neg('hn_holdout') >= 0.5)
        row = dict(arch=a, FPR50_hard_baseline_3seed=fmt_ms([fpr(m.neg('hn_holdout'), 0.5) for m in base], 2),
                   FPR50_hard_Mtop_s42=pct_ci(int((mm.neg('hn_holdout') >= 0.5).sum()), 500),
                   R_FPR1_baseline_3seed=fmt_ms(bt, 3), R_FPR1_Mtop_s42=round(r_m, 3), thr_Mtop=t_m,
                   FPR50_cross_baseline=fmt_ms([fpr(m.neg('dfire_neg'), 0.5) for m in base], 2),
                   FPR50_cross_Mtop=round(fpr(mm.neg('dfire_neg'), 0.5), 2),
                   mcnemar_vs_seed42_baseline='%d:%d p=%.2g' % (n01, n10, p),
                   mAP50_baseline=fmt_ms([m.val['mAP50'] for m in base]), mAP50_Mtop=mm.val['mAP50'])
        tr.append(row)
        say('   %-8s FPR hard %s -> %s | R@1%% %s -> %.3f (thr %s) | %s'
            % (a, row['FPR50_hard_baseline_3seed'], row['FPR50_hard_Mtop_s42'], row['R_FPR1_baseline_3seed'],
               r_m, t_m, row['mcnemar_vs_seed42_baseline']))
    write('table2_transfer.csv', tr)

    # deployed model vs its baseline (Table 4), re-scored, plus the three-seed controls
    say('  Table 4 (seed 42 models re-scored; paper value in brackets):')
    t4 = []
    for lab, rid in (('Baseline yolo26n (no negatives)', 'tournament__yolo26n__s42'), ('Deployed model kd6', 'kd__kd6__s42'),
                     ('Teacher yolo26s@960', 'showcase__xs960__s42')):
        m = OLD[rid]
        mrow = master[rid]
        row = dict(model=lab, run_id=rid, mAP50='%.4f (%s)' % (m.val['mAP50'], mrow['mAP50']),
                   mAP50_95='%.4f (%s)' % (m.val['mAP5095'], mrow['mAP5095']),
                   precision=m.val['precision'], recall=m.val['recall'])
        for s in ORIG + FRESH:
            row['FPR50_' + s] = pct_ci(int((m.neg(s) >= 0.5).sum()), len(m.neg(s)))
        t, rc = r_at(m, m.neg('hn_holdout'), 1.0)
        row['R_FPR1_hard'] = '%.3f at %s' % (rc, t)
        t4.append(row)
        say('   %-32s mAP50 %-18s hard %-20s novel %-20s cross %-20s Fcross %-20s R@1%% %s'
            % (lab, row['mAP50'], row['FPR50_hn_holdout'], row['FPR50_novel'], row['FPR50_dfire_neg'],
               row['FPR50_F_cross'], row['R_FPR1_hard']))
    write('table4_deployed.csv', t4)


# ================================================================= 4. matched budget (Table 5, Fig. 6)
T5 = [('No negatives', ('N0', False)), ('Background 10% (433)', ('BG10', False)),
      ('Random, 1,638', ('R', False)), ('L-ratio, 1,638', ('L', False)), ('M-top, 1,638', ('M', False)),
      ('Cluster coverage, 1,638', ('C', False)), ('Places365-only, 1,638', ('P', False)),
      ('Positive-aware, 1,638', ('PA', False)), ('Union, 3,276', ('U3276', False)),
      ('Union, 3,276 + KD', ('U3276', True)), ('Random, 3,276 + KD', ('R3276', True))]
POOLS = [('pooled 2,596', ORIG), ('without mining-dev 2,196', ['hn_holdout', 'novel', 'dfire_neg']),
         ('fresh 1,662', FRESH), ('fresh cross-corpus 1,500', ['F_cross'])]
SIZE_BINS = [('small', 0.0, 0.01), ('medium', 0.01, 0.05), ('large', 0.05, 1.01)]


def size_mask(area, lo, hi):
    return (area >= lo) & (area <= hi) if lo == 0.0 else (area > lo) & (area <= hi)


def part_budget():
    say('\n## 4. Recall at a matched false alarm budget (fine grid), three-seed mean ± SD')
    rows, size_rows = [], []
    extra = [('Background 10% (paper model, batch 128)', OLD['paper__b_ultra_bg']),
             ('Deployed kd6 (paper model)', OLD['kd__kd6__s42']),
             ('No negatives (paper model)', OLD['tournament__yolo26n__s42'])]
    for pool_name, subs in POOLS:
        for lab, c in T5 + [(e[0], None) for e in extra]:
            ms = cond(*c) if c else [dict(extra)[lab]]
            for target in (1.0, 2.0, 5.0):
                res = [r_at(m, m.pool(subs), target) for m in ms]
                row = dict(pool=pool_name, method=lab, seeds=len(ms), budget_pct=target,
                           thr='/'.join(str(x[0]) for x in res),
                           realised_fpr=fmt_ms([fpr(m.pool(subs), x[0]) if x[0] else None for m, x in zip(ms, res)], 2),
                           recall=fmt_ms([x[1] for x in res], 4))
                rows.append(row)
            if pool_name == 'pooled 2,596':
                for sz, lo, hi in SIZE_BINS:
                    vals, ks, ns = [], 0, 0
                    for m in ms:
                        t = budget_thr(m.pool(subs), 1.0)
                        mk = size_mask(m.area, lo, hi)
                        k = int((m.conf[mk] >= t).sum())
                        vals.append(k / mk.sum()); ks += k; ns += int(mk.sum())
                    lo_ci, hi_ci = clopper_pearson(ks, ns)
                    size_rows.append(dict(method=lab, size=sz, n_per_seed=int(size_mask(ms[0].area, lo, hi).sum()),
                                          recall=fmt_ms(vals, 3), pooled_seeds_ci95='[%.3f, %.3f]' % (lo_ci, hi_ci),
                                          recall_mean=round(float(np.mean(vals)), 4), ci_lo=round(lo_ci, 4), ci_hi=round(hi_ci, 4)))
    write('table5_matched_budget.csv', rows)
    write('fig6_recall_by_size.csv', size_rows)
    for r in rows:
        if r['budget_pct'] == 1.0 and r['pool'] in ('pooled 2,596', 'fresh 1,662'):
            say('  %-24s %-42s thr %-14s FPR %-14s recall %s' % (r['pool'], r['method'], r['thr'], r['realised_fpr'], r['recall']))
    say('  by size at the 1% pooled budget:')
    for r in size_rows:
        say('   %-42s %-6s n=%-4d recall %-15s %s' % (r['method'], r['size'], r['n_per_seed'], r['recall'], r['pooled_seeds_ci95']))


# ================================================================= 5. miss rate vs FPPI, LAMR
REFS = np.logspace(-2, 0, 9)


def fppi_curve(m, subs):
    """Miss rate against false positives per negative image, over every threshold in a fine sweep."""
    boxes = np.concatenate([m.boxes(s) for s in subs])
    nimg = sum(len(m.neg(s)) for s in subs)
    ts = np.unique(np.concatenate([[0.01], np.round(np.linspace(0.01, 0.999, 400), 4)]))
    fp = np.array([(boxes >= t).sum() / nimg for t in ts])
    mr = np.array([1.0 - (m.conf >= t).mean() for t in ts])
    return ts, fp, mr


def lamr(fp, mr):
    out = []
    for r in REFS:
        ok = np.where(fp <= r)[0]
        out.append(mr[ok].min() if len(ok) else 1.0)
    return float(np.exp(np.mean(np.log(np.maximum(out, 1e-10))))), out


def part_fppi():
    say('\n## 5. Miss rate against false positives per image (pooled 2,596 negatives), log-average miss rate over FPPI 0.01-1')
    rows, curves = [], []
    for lab, c in T5:
        ms = cond(*c)
        vals = []
        for m in ms:
            ts, fp, mr = fppi_curve(m, ORIG)
            L, pts = lamr(fp, mr)
            vals.append(L)
            if m.seed == 42:
                for t, a, b in zip(ts, fp, mr):
                    curves.append(dict(method=lab, run_id=m.rid, thr=t, fppi=round(a, 5), miss_rate=round(b, 5)))
        rows.append(dict(method=lab, seeds=len(ms), LAMR=fmt_ms(vals, 3), LAMR_mean=round(float(np.mean(vals)), 4)))
        say('  %-28s LAMR %s' % (lab, rows[-1]['LAMR']))
    for lab, rid in (('Deployed kd6 (paper model)', 'kd__kd6__s42'), ('No negatives (paper model)', 'tournament__yolo26n__s42'),
                     ('Background 10% (paper model)', 'paper__b_ultra_bg')):
        ts, fp, mr = fppi_curve(OLD[rid], ORIG)
        L, _ = lamr(fp, mr)
        rows.append(dict(method=lab, seeds=1, LAMR='%.3f' % L, LAMR_mean=round(L, 4)))
        for t, a, b in zip(ts, fp, mr):
            curves.append(dict(method=lab, run_id=rid, thr=t, fppi=round(a, 5), miss_rate=round(b, 5)))
        say('  %-28s LAMR %.3f' % (lab, L))
    write('lamr.csv', rows)
    write('fppi_curves_seed42.csv', curves)


# ================================================================= 6. detection side
def part_detection():
    say('\n## 6. Detection side: 2,301 D-Fire fire images never used in training, at 0.50 and at each model\'s 1% budget')
    rows = []
    items = [(lab, cond(*c)) for lab, c in T5] + [('Deployed kd6 (paper model)', [OLD['kd__kd6__s42']]),
                                                  ('No negatives (paper model)', [OLD['tournament__yolo26n__s42']])]
    for lab, ms in items:
        r = dict(method=lab, seeds=len(ms))
        for tname, tf in (('0.50', lambda m: 0.5), ('budget_hard_1pct', lambda m: budget_thr(m.neg('hn_holdout'), 1.0)),
                          ('budget_pooled_1pct', lambda m: budget_thr(m.pool(ORIG), 1.0))):
            img, inst, small = [], [], []
            for m in ms:
                t = tf(m)
                x = m.dfire_img()
                ci, ca = m.dfire_inst()
                img.append(float((x >= t).mean()))
                inst.append(float((ci >= t).mean()))
                small.append(float((ci[ca <= 0.01] >= t).mean()))
            r['img_detect_' + tname] = fmt_ms(img, 3)
            r['inst_recall_' + tname] = fmt_ms(inst, 3)
            r['small_inst_recall_' + tname] = fmt_ms(small, 3)
        rows.append(r)
        say('  %-28s image-level at 0.50 %-15s at 1%% hard budget %-15s | instances at 0.50 %-15s at budget %s'
            % (lab, r['img_detect_0.50'], r['img_detect_budget_hard_1pct'], r['inst_recall_0.50'], r['inst_recall_budget_hard_1pct']))
    write('detection_side_dfire.csv', rows)
    n_img = len(OLD['kd__kd6__s42'].dfire_img())
    n_inst = len(OLD['kd__kd6__s42'].dfire_inst()[0])
    say('  (%d D-Fire positive images, %d annotated instances)' % (n_img, n_inst))


# ================================================================= 7. fresh suite, endpoints of PROTOCOL.md
def part_fresh():
    say('\n## 7. Fresh untouched suite (frozen 2026-10-03 01:04 UTC, before any model was scored)')
    fz = json.load(open(os.path.join(OUT, 'fresh_suite', 'FROZEN.json')))
    say('  frozen at %s, manifest sha256 %s..., counts %s' % (fz['frozen_at_utc'], fz['manifest_sha256'][:16], fz['counts']))
    rows = []
    items = [(lab, cond(*c)) for lab, c in T5] + [('Deployed kd6 (paper model)', [OLD['kd__kd6__s42']]),
                                                  ('No negatives (paper model)', [OLD['tournament__yolo26n__s42']])]
    for lab, ms in items:
        r = dict(method=lab, seeds=len(ms))
        for s in FRESH:
            k = sum(int((m.neg(s) >= 0.5).sum()) for m in ms)
            n = sum(len(m.neg(s)) for m in ms)
            r['FPR50_' + s + '_seeds_pooled'] = pct_ci(k, n)
            r['FPR50_' + s] = fmt_ms([fpr(m.neg(s), 0.5) for m in ms], 2)
            # endpoint 2: FPR at the 1% threshold fixed beforehand on the original hard holdout
            r['FPR_at_hard1pct_thr_' + s] = fmt_ms([fpr(m.neg(s), budget_thr(m.neg('hn_holdout'), 1.0)) for m in ms], 2)
        # endpoint 3: recall at a 1% budget measured on each fresh subset
        for s in FRESH:
            r['R_FPR1_' + s] = fmt_ms([r_at(m, m.neg(s), 1.0)[1] for m in ms], 3)
        rows.append(r)
        say('  %-28s F_hard %-13s F_novel %-13s F_cross %-13s | at hard-1%% thr: F_cross %-12s | R@1%% F_cross %s'
            % (lab, r['FPR50_F_hard'], r['FPR50_F_novel'], r['FPR50_F_cross'], r['FPR_at_hard1pct_thr_F_cross'], r['R_FPR1_F_cross']))
    write('fresh_suite_endpoints.csv', rows)


# ================================================================= 8. conformal, verified on untouched data
def pac_k(n, alpha, delta):
    for k in range(1, n + 1):
        if binom_sf(n + 1 - k, n, alpha) >= 1.0 - delta:
            return k
    return None


def part_conformal():
    say('\n## 8. Conformal calibration on the 500 hard negatives, verified on the untouched fresh suite')
    rows = []
    models = [('Deployed kd6 (paper model)', OLD['kd__kd6__s42'])] + \
             [('Union 3,276, s%d' % m.seed, m) for m in cond('U3276', False)] + \
             [('Union 3,276 + KD, s%d' % m.seed, m) for m in cond('U3276', True)] + \
             [('Positive-aware, s%d' % m.seed, m) for m in cond('PA', False)]
    for lab, m in models:
        cal = np.sort(m.neg('hn_holdout'))
        n = len(cal)
        for alpha in (0.01, 0.05):
            k_marg = int(math.ceil((n + 1) * (1 - alpha)))
            k_pac = pac_k(n, alpha, 0.05)
            for kind, k in (('marginal', k_marg), ('training-conditional (95%)', k_pac)):
                if k is None or k > n:
                    rows.append(dict(model=lab, target=alpha, kind=kind, n_cal=n, k='infeasible'))
                    continue
                tau = float(cal[k - 1])
                row = dict(model=lab, target=alpha, kind=kind, n_cal=n, k=k, tau=round(tau, 4),
                           recall=round(float((m.conf > tau).mean()), 4))
                for s in FRESH + ['novel', 'dfire_neg']:
                    v = m.neg(s)
                    a = int((v > tau).sum())
                    p = binom_sf(a, len(v), alpha)
                    lo, hi = clopper_pearson(a, len(v))
                    row['realised_' + s] = '%d/%d = %.2f%% [%.2f, %.2f] p=%.3f' % (a, len(v), 100.0 * a / len(v), 100 * lo, 100 * hi, p)
                    row['exceeds_' + s] = 'yes (p<0.05)' if p < 0.05 else 'no'
                rows.append(row)
                say('  %-30s %-4s %-27s tau %.4f recall %.3f | F_hard %s | F_novel %s | F_cross %s'
                    % (lab, '%g%%' % (100 * alpha), kind, tau, row['recall'], row['realised_F_hard'].split(' p=')[0],
                       row['realised_F_novel'].split(' p=')[0], row['realised_F_cross']))
    write('conformal_fresh_verification.csv', rows)


# ================================================================= 9. CLIP verifier baseline
def part_clip():
    say('\n## 9. Contemporary false-alarm baseline: detector + zero-shot CLIP verification, same suite, same protocol')
    rows = []
    items = [('No negatives', OLD['tournament__yolo26n__s42']),
             ('No negatives + CLIP verifier', OLD['tournament__yolo26n__s42__clipverify']),
             ('Deployed kd6', OLD['kd__kd6__s42']), ('Deployed kd6 + CLIP verifier', OLD['kd__kd6__s42__clipverify'])]
    items += [('M-top s42 (trained negatives)', NEW['M__noKD__yolo26n__s42']),
              ('Union 3,276 s42 (trained negatives)', NEW['U3276__noKD__yolo26n__s42'])]
    for lab, m in items:
        r = dict(method=lab)
        for s in ['hn_holdout', 'novel', 'dfire_neg', 'F_cross']:
            r['FPR50_' + s] = pct_ci(int((m.neg(s) >= 0.5).sum()), len(m.neg(s)))
        for pn, subs in (('hard', ['hn_holdout']), ('pooled', ORIG), ('fresh', FRESH)):
            t, rc = r_at(m, m.pool(subs), 1.0)
            r['R_FPR1_' + pn] = '%.3f at %s' % (rc, t) if t is not None else 'no operating point'
        small = m.area <= 0.01
        t = budget_thr(m.pool(ORIG), 1.0)
        r['small_recall_pooled_1pct'] = round(float((m.conf[small] >= t).mean()), 3)
        r['recall_at_0.50'] = round(recall_at(m.conf, 0.5), 3)
        rows.append(r)
        say('  %-38s hard %-20s cross %-20s | R@1%% hard %-12s pooled %-12s fresh %-12s small %s'
            % (lab, r['FPR50_hn_holdout'], r['FPR50_dfire_neg'], r['R_FPR1_hard'], r['R_FPR1_pooled'], r['R_FPR1_fresh'], r['small_recall_pooled_1pct']))
    write('clip_verifier_baseline.csv', rows)
    meta = json.load(open(os.path.join(OUT, 'scores', 'kd__kd6__s42__clipverify', 'SCORED.json')))
    say('  verifier: CLIP ViT-B/32, box crop with context %s, top-%s boxes; score = confidence x P(fire prompts)' % (meta.get('context'), meta.get('topk')))


# ================================================================= 10. class-agnostic matching
def part_classes():
    say('\n## 10. Class-agnostic recall: how often the matching box has the other class (at 0.50)')
    rows = []
    for lab, m in (('No negatives s42', NEW['N0__noKD__yolo26n__s42']), ('M-top s42', NEW['M__noKD__yolo26n__s42']),
                   ('Union 3,276 s42', NEW['U3276__noKD__yolo26n__s42']), ('Deployed kd6', OLD['kd__kd6__s42'])):
        r = dict(model=lab)
        for c, cname in ((0, 'flame'), (1, 'smoke')):
            mk = m.cls == c
            any_hit = m.conf[mk] >= 0.5
            same_hit = m.conf_same[mk] >= 0.5
            r[cname + '_n'] = int(mk.sum())
            r[cname + '_recall_any_class'] = round(float(any_hit.mean()), 4)
            r[cname + '_recall_same_class'] = round(float(same_hit.mean()), 4)
            r[cname + '_hits_only_by_other_class'] = int((any_hit & ~same_hit).sum())
        rows.append(r)
        say('  %-18s flame %d: any %.3f same %.3f (other-class only %d) | smoke %d: any %.3f same %.3f (other-class only %d)'
            % (lab, r['flame_n'], r['flame_recall_any_class'], r['flame_recall_same_class'], r['flame_hits_only_by_other_class'],
               r['smoke_n'], r['smoke_recall_any_class'], r['smoke_recall_same_class'], r['smoke_hits_only_by_other_class']))
    write('class_agnostic_check.csv', rows)


# ================================================================= 11. audit (SFS_01) and per-cluster errors
def part_audit():
    say('\n## 11. Audit of the negative sets')
    ov = read_csv(os.path.join(OUT, 'audit', 'overlap_report.csv'))
    for r in ov:
        if r['training_set'] in ('L-ratio', 'M-top', 'Random') or r['exact_sha256_matches'] != '0':
            say('  %-24s vs %-28s exact %s, near-duplicate (dHash <= 4) %s'
                % (r['training_set'], r['evaluation_set'], r['exact_sha256_matches'], r['near_duplicates_dhash_le4']))
    dd = json.load(open(os.path.join(OUT, 'audit', 'union_content_dedup.json')))
    say('  union L-ratio + M-top by content: %d exact duplicates, %d near duplicates (dHash <= 4) among %d + %d'
        % (dd['exact'], dd['near_le4'], dd['n_L'], dd['n_M']))
    fb = read_csv(os.path.join(OUT, 'audit', 'fireblock_recount.csv'))
    say('  fire-like exclusion recomputed (CLIP ViT-B/32, margin fire-safe > 0.05 and fire similarity > 0.25): %d flagged, %d in fire_block.json, %d in both'
        % (sum(int(x['flagged']) for x in fb), sum(int(x['in_fire_block_json']) for x in fb),
           sum(1 for x in fb if x['flagged'] == '1' and x['in_fire_block_json'] == '1')))
    mc = json.load(open(os.path.join(OUT, 'audit', 'mining_cost.json')))
    say('  mining cost on %s: detector %.1f ms/image -> %.1f min for 76,183 images; CLIP %.1f ms/image -> %.1f min for 9,854 hits; k-means %.1f s'
        % (mc['hardware']['gpu'], mc['detector_ms_per_image'], mc['estimate_score_76183_corpus_min'], mc['clip_ms_per_image'],
           mc['estimate_embed_9854_hits_min'], mc['kmeans_16_seconds']))
    rr = read_csv(os.path.join(OUT, 'audit', 'rescoring_reproducibility.csv'))
    flips = sum(int(r['alarm_flips_at_0.50']) for r in rr)
    n = sum(int(r['n']) for r in rr)
    big = [r for r in rr if float(r['max_abs_diff']) > 0.05]
    say('  re-scoring check: %d (model, subset) pairs, %d of %d image verdicts at 0.50 changed; pairs with a score change > 0.05: %s'
        % (len(rr), flips, n, sorted({r['run_id'] for r in big})))
    pa = json.load(open(os.path.join(OUT, 'manifests', 'neg_PA.json')))
    say('  PA: %d candidates, %d excluded as closer to real small fires than to known confusers (%d of them in M-top); PA shares %d images with M-top'
        % (pa['n_candidates'], pa['n_excluded'], pa['n_excluded_from_M_top'], pa['overlap_with_M_top']))

    # near-duplicate sensitivity: drop every evaluation image that has a near-duplicate in L-ratio or M-top
    nd = read_csv(os.path.join(OUT, 'audit', 'near_duplicate_pairs.csv'))
    key = {'hn_holdout': 'hn_holdout', 'novel': 'novel', 'dfire_neg': 'dfire_neg', 'mined_dev': 'mined_dev'}
    drop = collections.defaultdict(set)
    for r in nd:
        if r['training_set'] in ('L-ratio', 'M-top') and r['evaluation_set'] in key:
            drop[r['evaluation_set']].add(r['eval_image'])
    say('  near-duplicate sensitivity (eval images dropped: %s):' % {k: len(v) for k, v in drop.items()})
    rows = []
    for lab, c in (('L-ratio', ('L', False)), ('M-top', ('M', False)), ('Union 3,276', ('U3276', False)), ('Union 3,276 + KD', ('U3276', True))):
        for s in ('hn_holdout', 'novel', 'dfire_neg'):
            full, kept = [], []
            for m in cond(*c):
                names, v = m.neg_names(s), m.neg(s)
                mk = np.array([nm not in drop[s] for nm in names])
                full.append(fpr(v, 0.5)); kept.append(fpr(v[mk], 0.5))
            rows.append(dict(model=lab, subset=NAME[s], dropped=len(drop[s]), FPR50_full=fmt_ms(full, 2), FPR50_without_near_dups=fmt_ms(kept, 2)))
            say('   %-18s %-13s full %-13s without near-duplicates %s' % (lab, NAME[s], fmt_ms(full, 2), fmt_ms(kept, 2)))
    write('near_duplicate_sensitivity.csv', rows)

    # per-cluster false positive rate on the 400 mining-dev images (25 per cluster)
    say('\n  per-cluster FPR at 0.50 on mining-dev (25 held-out members per cluster):')
    hc = {r['name']: r for r in read_csv(os.path.join(OUT, 'audit', 'hit_clusters.csv'))}
    ct = {r['cluster']: r for r in read_csv(os.path.join(OUT, 'audit', 'cluster_table.csv'))}
    groups = [('No negatives', cond('N0', False)), ('L-ratio', cond('L', False)), ('M-top', cond('M', False)),
              ('Union 3,276', cond('U3276', False)), ('Deployed kd6', [OLD['kd__kd6__s42']]), ('Positive-aware', cond('PA', False))]
    pas = {r['name']: r for r in read_csv(os.path.join(OUT, 'audit', 'pa_similarity.csv'))}
    crow = []
    for c in sorted(ct, key=int):
        row = dict(cluster=int(c), label=ct[c]['label'], size=ct[c]['n'], mean_conf=ct[c]['mean_conf'],
                   in_M_top=ct[c]['n_in_M_top'], fire_like_excluded=ct[c]['n_fire_like_excluded'],
                   PA_excluded=sum(1 for nm, r in pas.items() if r['excluded'] == '1' and hc.get(nm, {}).get('cluster') == c))
        for lab, ms in groups:
            vals = []
            for m in ms:
                names, v = m.neg_names('mined_dev'), m.neg('mined_dev')
                mk = np.array([hc[nm]['cluster'] == c for nm in names])
                vals.append(100.0 * float((v[mk] >= 0.5).mean()))
            row['FPR50_' + lab] = round(float(np.mean(vals)), 1)
        crow.append(row)
        say('   %2s %-30s n=%-5s PA-excl %-4d | %s' % (c, row['label'], row['size'], row['PA_excluded'],
            ' '.join('%s %.0f%%' % (lab.split()[0], row['FPR50_' + lab]) for lab, _ in groups)))
    write('per_cluster_mining_dev.csv', crow)


# ================================================================= 12. video (SFS_05)
VID = os.path.join(OUT, 'video')
VID_MODELS = [('No negatives (paper)', 'tournament__yolo26n__s42'), ('Deployed kd6 (paper)', 'kd__kd6__s42'),
              ('No negatives s42', 'N0__noKD__yolo26n__s42'), ('L-ratio s42', 'L__noKD__yolo26n__s42'),
              ('M-top s42', 'M__noKD__yolo26n__s42'), ('Positive-aware s42', 'PA__noKD__yolo26n__s42'),
              ('Positive-aware + KD s42', 'PA__KD__yolo26n__s42'), ('Union + KD s42', 'U3276__KD__yolo26n__s42'),
              ('Union + KD s123', 'U3276__KD__yolo26n__s123'), ('Union + KD s2024', 'U3276__KD__yolo26n__s2024')]


def part_video():
    import temporal_alarm as TA
    say('\n## 12. Video')
    vl = read_csv(os.path.join(VID, 'video_list.csv'))
    bad = [v['key'] for v in vl if v['readable'] != '1']
    vl = [v for v in vl if v['readable'] == '1']
    tags = {r['key']: r for r in read_csv(os.path.join(HERE, 'video_tags.csv'))} if os.path.exists(os.path.join(HERE, 'video_tags.csv')) else {}
    neg = [v for v in vl if v['role'] == 'negative']
    pos = [v for v in vl if v['role'] == 'positive']
    say('  readable: %d negative clips (%.1f min), %d positive clips; unreadable by the Colab video reader: %s'
        % (len(neg), sum(float(v['seconds']) for v in neg) / 60, len(pos), bad))

    def run(model, v, K, N, hold=0.0):
        p = os.path.join(VID, 'dets', model, v['key'] + '.csv')
        return TA.run_video(p, K, N, 0.30, 0.50, hold_s=hold) if os.path.exists(p) else None

    rows, per_video = [], []
    for lab, mid in VID_MODELS:
        for (K, N) in ((1, 1), (3, 5)):
            for hold in (0.0, 30.0):
                if (K, N) == (1, 1) and hold:
                    continue
                res = {v['key']: run(mid, v, K, N, hold) for v in neg + pos}
                al = sum(res[v['key']]['alarms'] for v in neg if res[v['key']])
                dur = sum(res[v['key']]['duration_s'] for v in neg if res[v['key']])
                fs = [v for v in neg if v['kind'].startswith('FS_')]
                al_fs = sum(res[v['key']]['alarms'] for v in fs if res[v['key']])
                du_fs = sum(res[v['key']]['duration_s'] for v in fs if res[v['key']])
                km = [v for v in neg if v['kind'] == 'KMU_like']
                al_km = sum(res[v['key']]['alarms'] for v in km if res[v['key']])
                du_km = sum(res[v['key']]['duration_s'] for v in km if res[v['key']])
                fired = sum(1 for v in fs if res[v['key']] and res[v['key']]['alarms'] > 0)
                det = sum(1 for v in pos if res[v['key']] and res[v['key']]['alarms'] > 0)
                row = dict(model=lab, run_id=mid, rule='%d-of-%d' % (K, N), hold_s=hold, alarms=al, minutes=round(dur / 60, 2),
                           per_hour=round(3600.0 * al / dur, 1), per_hour_FIRESENSE=round(3600.0 * al_fs / du_fs, 1),
                           per_hour_KMU=round(3600.0 * al_km / du_km, 1),
                           FIRESENSE_neg_clips_with_alarm='%d/%d' % (fired, len(fs)), positives_detected='%d/%d' % (det, len(pos)))
                if tags:
                    for place in ('indoor', 'outdoor'):
                        sel = [v for v in neg if tags.get(v['key'], {}).get('scene') == place]
                        a_ = sum(res[v['key']]['alarms'] for v in sel if res[v['key']])
                        d_ = sum(res[v['key']]['duration_s'] for v in sel if res[v['key']])
                        row['per_hour_' + place] = round(3600.0 * a_ / d_, 1) if d_ else None
                        row['minutes_' + place] = round(d_ / 60, 2)
                tta = [res[v['key']]['first_alarm_s'] - float(tags[v['key']]['onset_s']) for v in pos
                       if res[v['key']] and res[v['key']]['first_alarm_s'] is not None
                       and tags.get(v['key'], {}).get('onset_s') not in (None, '')]
                n_on = sum(1 for v in pos if tags.get(v['key'], {}).get('onset_s') not in (None, ''))
                row['onset_annotated_clips'] = n_on
                row['median_time_to_alarm_s'] = round(float(np.median(tta)), 2) if tta else None
                row['alarm_within_5s_of_onset'] = '%d/%d' % (sum(1 for x in tta if x <= 5.0), n_on)
                lat = [res[v['key']]['layer_delay_s'] for v in pos if res[v['key']] and res[v['key']]['layer_delay_s'] is not None]
                row['median_first_alarm_s'] = round(float(np.median([res[v['key']]['first_alarm_s'] for v in pos
                                                                     if res[v['key']] and res[v['key']]['first_alarm_s'] is not None])), 2) if det else None
                row['median_layer_delay_s'] = round(float(np.median(lat)), 2) if lat else None
                rows.append(row)
                for v in neg + pos:
                    r = res[v['key']]
                    if r:
                        per_video.append(dict(model=lab, rule=row['rule'], hold_s=hold, key=v['key'], kind=v['kind'], role=v['role'],
                                              scene=tags.get(v['key'], {}).get('scene', ''), minutes=round(r['duration_s'] / 60, 2),
                                              alarms=r['alarms'], per_hour=r['alarms_per_hour'], first_alarm_s=r['first_alarm_s']))
                say('  %-26s %-6s hold %-4g %6.1f alarms/h (%3d in %.1f min; FIRESENSE %.1f, KMU %.1f%s) | FIRESENSE negatives firing %s | positives %s'
                    % (lab, row['rule'], hold, row['per_hour'], al, dur / 60, row['per_hour_FIRESENSE'], row['per_hour_KMU'],
                       ('; indoor %s, outdoor %s' % (row.get('per_hour_indoor'), row.get('per_hour_outdoor'))) if tags else '',
                       row['FIRESENSE_neg_clips_with_alarm'], row['positives_detected']))
    write('video_summary.csv', rows)
    write('video_per_clip.csv', per_video)

    # interaction of the two defences, with a bootstrap over negative videos
    def rate(mid, K, N, sample):
        a = d = 0.0
        for v in sample:
            r = run(mid, v, K, N)
            if r:
                a += r['alarms']; d += r['duration_s']
        return 3600.0 * a / d if d else float('nan')
    cache = {(mid, K, N, v['key']): run(mid, v, K, N) for mid in ('tournament__yolo26n__s42', 'kd__kd6__s42')
             for (K, N) in ((1, 1), (3, 5)) for v in neg}

    def rate_c(mid, K, N, sample):
        a = sum(cache[(mid, K, N, v['key'])]['alarms'] for v in sample if cache[(mid, K, N, v['key'])])
        d = sum(cache[(mid, K, N, v['key'])]['duration_s'] for v in sample if cache[(mid, K, N, v['key'])])
        return 3600.0 * a / d if d else float('nan')

    def factors(sample):
        b0, b1 = rate_c('tournament__yolo26n__s42', 1, 1, sample), rate_c('tournament__yolo26n__s42', 3, 5, sample)
        k0, k1 = rate_c('kd__kd6__s42', 1, 1, sample), rate_c('kd__kd6__s42', 3, 5, sample)
        f_neg, f_layer = b0 / k0, b0 / b1
        comb = b0 / k1 if k1 > 0 else float('inf')
        return f_neg, f_layer, comb, comb / (f_neg * f_layer)
    point = factors(neg)
    rng = np.random.RandomState(2026)
    boot = []
    for _ in range(5000):
        smp = [neg[i] for i in rng.randint(0, len(neg), len(neg))]
        f = factors(smp)
        if all(np.isfinite(f)):
            boot.append(f)
    boot = np.array(boot)
    q = lambda col: (np.percentile(boot[:, col], 2.5), np.percentile(boot[:, col], 97.5))
    say('  interaction (paper models, %d readable negatives): negatives alone x%.2f, layer alone x%.2f, together x%.1f, ratio to the product %.2f'
        % (len(neg), point[0], point[1], point[2], point[3]))
    say('   bootstrap over videos (%d resamples): together x%.1f [%.1f, %.1f]; ratio to the product %.2f [%.2f, %.2f] (1 = independent)'
        % (len(boot), point[2], q(2)[0], q(2)[1], point[3], q(3)[0], q(3)[1]))
    write('video_interaction_bootstrap.csv', [dict(neg_factor=round(point[0], 3), layer_factor=round(point[1], 3), combined=round(point[2], 3),
                                                   ratio_to_product=round(point[3], 3), combined_ci='[%.2f, %.2f]' % q(2),
                                                   ratio_ci='[%.3f, %.3f]' % q(3), resamples=len(boot), videos=len(neg))])

    # small indoor fires (KMU flame2-5): highest confidence of every model
    say('\n  small indoor fires (KMU flame2-5): highest flame / any-class confidence over each clip')
    mx = read_csv(os.path.join(VID, 'indoor_small_flames_maxconf.csv'))
    clips = ['KMU_flame__flame%d' % i for i in (2, 3, 4, 5)]
    by = collections.defaultdict(list)
    for r in mx:
        rid = r['run_id']
        if rid in NEW:
            g = '%s %s' % (NEW[rid].neg_set, 'KD' if NEW[rid].kd else 'noKD')
        elif rid.startswith('tournament__'):
            g = 'paper: no negatives (%s)' % rid.split('__')[1]
        elif rid.startswith('kd__'):
            g = 'paper: ' + rid
        elif rid.startswith('showcase__'):
            g = 'paper: teacher ' + rid.split('__')[1]
        else:
            g = 'paper: ' + rid.split('__')[0] + ' ' + rid.split('__')[1]
        by[g].append([float(r[c + '_any_max']) if r.get(c + '_any_max') not in (None, '') else float('nan') for c in clips])
    srows = []
    for g in sorted(by):
        a = np.array(by[g])
        row = dict(group=g, models=len(a))
        for i, c in enumerate(clips):
            row[c.split('__')[1] + '_max_any'] = round(float(np.nanmean(a[:, i])), 3)
        row['clips_reaching_0.50_mean'] = round(float(np.mean((a >= 0.5).sum(1))), 2)
        row['clips_reaching_0.10_mean'] = round(float(np.mean((a >= 0.1).sum(1))), 2)
        srows.append(row)
        say('   %-34s n=%-2d %s | clips >= 0.50: %.1f of 4' % (g, len(a), ' '.join('%.3f' % row[c.split('__')[1] + '_max_any'] for c in clips),
                                                               row['clips_reaching_0.50_mean']))
    write('small_indoor_fires_by_condition.csv', srows)

    nn = read_csv(os.path.join(VID, 'clip_nn_missed_small_fires.csv'))
    say('  CLIP nearest training negatives to small-fire frames (mean cosine similarity, 32 frames):')
    nrows = []
    for g in ('M-top', 'L-ratio', 'PA'):
        t1 = [float(r['top1_sim']) for r in nn if r['negative_set'] == g]
        t5 = [float(r['top5_mean_sim']) for r in nn if r['negative_set'] == g]
        if t1:
            nrows.append(dict(set=g, frames=len(t1), top1=round(float(np.mean(t1)), 4), top5=round(float(np.mean(t5)), 4)))
            say('   %-8s top-1 %.4f  top-5 %.4f' % (g, np.mean(t1), np.mean(t5)))
    write('clip_nn_small_fires.csv', nrows)


PARTS = collections.OrderedDict([('factorial', part_factorial), ('mcnemar', part_mcnemar),
                                 ('old', part_old_tables), ('budget', part_budget), ('fppi', part_fppi),
                                 ('detection', part_detection), ('fresh', part_fresh), ('conformal', part_conformal),
                                 ('clip', part_clip), ('classes', part_classes), ('audit', part_audit),
                                 ('video', part_video)])

if __name__ == '__main__':
    want = sys.argv[1:] or list(PARTS)
    for k in want:
        PARTS[k]()
    with open(os.path.join(RES, 'summary_results.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(SUMMARY) + '\n')
