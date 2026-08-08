# -*- coding: utf-8 -*-
"""C2 - alarm-aware evaluation suite + conformal false-alarm thresholding.

Runs entirely on artefacts that already exist: per-image max-confidence scores
on the four frozen negative sets, and the positive-side confidence sweep. No
training, no inference, nothing to re-run on a GPU.

WHAT CONFORMAL BUYS
    Every fire paper picks a confidence threshold and reports the false-alarm
    rate it happened to give. That is a measurement, not a guarantee: it says
    what happened on those images, not what will happen on the next one.

    Split conformal turns it around. Hold out n negative images, sort their
    scores, and take

        k   = ceil((n + 1) * (1 - alpha))
        tau = the k-th smallest calibration score          (alarm iff s > tau)

    Then for a new negative drawn from the same distribution,

        P(false alarm) = P(s_new > tau) <= alpha

    with no assumption about the model, the score distribution, or the data -
    only exchangeability between the calibration images and the next one. The
    threshold stops being a tuning knob and becomes a certificate.

THE FEASIBILITY CONDITION IS THE INTERESTING PART
    k <= n requires n >= 1/alpha - 1. To certify 1 % you need at least 99
    calibration negatives; 50 cannot do it at any threshold. That is not a
    limitation of the method, it is information-theoretic, and it is exactly
    what E2.3 is asked to show.

ON HONESTY OF SCOPE
    The guarantee is with respect to the distribution the calibration set
    represents. This script therefore also applies an hn-calibrated tau to the
    other three negative sets, and reports what happens. It is the same lesson
    C1 already carries - hand-picked categories do not cover the open world -
    arriving here by a completely different route.
"""
import os, math, csv
import numpy as np

ROOT = r'C:\Users\hp\Desktop\TEMP\SAFE_FIRE\results'
SCORES = os.path.join(ROOT, 'scores_v2')
SWEEPS = os.path.join(ROOT, 'sweeps_v2')
OUT = os.path.dirname(os.path.abspath(__file__))

SETS = ['hn_holdout', 'novel', 'mined_dev', 'dfire_neg']
CAL_SET = 'hn_holdout'          # the set we calibrate on
ALPHAS = [0.01, 0.05]
N_GRID = [50, 100, 250]
N_REPEATS = 500                 # random cal/test splits, for the spread
RNG = np.random.RandomState(42)

HEADLINE = 'kd__kd6__s42'       # the deployed model


# ----------------------------------------------------------------- loading

def load_scores(model, setname):
    p = os.path.join(SCORES, '%s__%s.csv' % (model, setname))
    if not os.path.exists(p):
        return None
    v = []
    with open(p) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            if len(row) >= 2:
                v.append(float(row[1]))
    return np.array(v)


def load_sweep(model):
    p = os.path.join(SWEEPS, '%s__test_sweep.csv' % model)
    if not os.path.exists(p):
        return None
    conf, rec = [], []
    with open(p) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            conf.append(float(row[0])); rec.append(float(row[1]))
    return np.array(conf), np.array(rec)


def recall_at(sweep, tau):
    """Recall at an arbitrary threshold, linearly interpolated.

    The saved sweep is a 12-point grid (0.05 .. 0.9), so any tau between grid
    points is interpolated. Stated explicitly because it is an approximation:
    the FPR side is exact (computed from per-image scores) while the recall
    side inherits the grid.
    """
    conf, rec = sweep
    if tau <= conf[0]:  return float(rec[0])
    if tau >= conf[-1]: return float(rec[-1])
    return float(np.interp(tau, conf, rec))


def models_with_everything():
    have = {}
    for f in os.listdir(SCORES):
        for s in SETS:
            suf = '__%s.csv' % s
            if f.endswith(suf):
                have.setdefault(f[:-len(suf)], set()).add(s)
    full = sorted(m for m, v in have.items() if v == set(SETS))
    return [m for m in full if os.path.exists(
        os.path.join(SWEEPS, '%s__test_sweep.csv' % m))]


# -------------------------------------------------------------- statistics

def clopper_pearson(k, n, alpha=0.05):
    """Exact binomial CI, computed in log space so n=1500 does not overflow."""
    from math import lgamma, exp, log

    def cdf(kk, nn, p):
        if kk < 0:   return 0.0
        if kk >= nn: return 1.0
        if p <= 0:   return 1.0
        if p >= 1:   return 0.0
        tot = 0.0
        for i in range(kk + 1):
            tot += exp(lgamma(nn + 1) - lgamma(i + 1) - lgamma(nn - i + 1)
                       + i * log(p) + (nn - i) * log(1 - p))
        return tot

    def bisect(f, a, b):
        for _ in range(200):
            m = (a + b) / 2.0
            if f(a) * f(m) <= 0: b = m
            else: a = m
        return (a + b) / 2.0

    lo = 0.0 if k == 0 else bisect(lambda p: cdf(k - 1, n, p) - (1 - alpha / 2), 1e-12, k / float(n))
    hi = 1.0 if k == n else bisect(lambda p: cdf(k, n, p) - alpha / 2, k / float(n), 1 - 1e-12)
    return lo, hi


def conformal_tau(cal, alpha):
    """k-th smallest calibration score, or None when n is too small to certify."""
    n = len(cal)
    k = int(math.ceil((n + 1) * (1.0 - alpha)))
    if k > n:
        return None, k, n
    return float(np.sort(cal)[k - 1]), k, n


# ------------------------------------------------- E2.1 reliability suite

def e2_1():
    rows = []
    for m in models_with_everything():
        sw = load_sweep(m)
        sc = {s: load_scores(m, s) for s in SETS}
        row = {'model': m}
        for s in SETS:
            a = sc[s]
            row['FPR25_' + s] = 100.0 * (a >= 0.25).mean()
            row['FPR50_' + s] = 100.0 * (a >= 0.50).mean()

        # smallest tau giving FPR <= 1 % on the hard holdout, then recall there
        a = np.sort(sc[CAL_SET])
        n = len(a)
        allowed = int(math.floor(0.01 * n))          # images permitted to fire
        tau1 = 0.0 if allowed >= n else float(a[n - allowed - 1]) + 1e-9
        row['tau_FPR1'] = round(tau1, 4)
        row['recall_at_FPR1'] = round(recall_at(sw, tau1), 4)
        row['recall_at_050'] = round(recall_at(sw, 0.50), 4)
        rows.append(row)

    rows.sort(key=lambda r: -r['recall_at_FPR1'])
    p = os.path.join(OUT, 'E2_1_reliability_suite.csv')
    with open(p, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print('=' * 78)
    print('E2.1  RELIABILITY SUITE  (%d models)' % len(rows))
    print('=' * 78)
    print('%-30s %7s %7s %7s %7s  %6s %8s' %
          ('model', 'hn', 'novel', 'mined', 'dfire', 'tau1%', 'R@FPR1'))
    print('-' * 78)
    for r in rows[:14]:
        print('%-30s %6.2f%% %6.2f%% %6.2f%% %6.2f%%  %6.3f %7.4f' %
              (r['model'], r['FPR50_hn_holdout'], r['FPR50_novel'],
               r['FPR50_mined_dev'], r['FPR50_dfire_neg'],
               r['tau_FPR1'], r['recall_at_FPR1']))
    print('   ... full table in E2_1_reliability_suite.csv')
    print('   FPR columns are at conf 0.50. R@FPR1 = recall at the threshold')
    print('   that holds FPR <= 1 % on the hard holdout.')
    print()
    return rows


# ------------------------------------- E2.2 conformal calibration + check

def e2_2():
    sw = load_sweep(HEADLINE)
    scores = {s: load_scores(HEADLINE, s) for s in SETS}
    cal_all = scores[CAL_SET]
    n_all = len(cal_all)
    half = n_all // 2

    print('=' * 78)
    print('E2.2  CONFORMAL THRESHOLD  -  %s' % HEADLINE)
    print('      calibrate on %d of %d %s images, verify on the other %d'
          % (half, n_all, CAL_SET, n_all - half))
    print('=' * 78)

    out = []
    for alpha in ALPHAS:
        idx = RNG.permutation(n_all)
        cal, tst = cal_all[idx[:half]], cal_all[idx[half:]]
        tau, k, n = conformal_tau(cal, alpha)
        if tau is None:
            print('  alpha=%.0f%%  INFEASIBLE at n=%d' % (100 * alpha, n)); continue

        fired = int((tst > tau).sum())
        emp = fired / float(len(tst))
        lo, hi = clopper_pearson(fired, len(tst))
        rec = recall_at(sw, tau)

        print()
        print('  alpha = %.0f %%   ->   tau = %.4f      (order statistic k=%d of n=%d)'
              % (100 * alpha, tau, k, n))
        print('     held-out negatives that fire : %d / %d = %.2f %%'
              % (fired, len(tst), 100 * emp))
        print('     exact 95%% CI                : [%.2f %%, %.2f %%]'
              % (100 * lo, 100 * hi))
        print('     guarantee alpha respected    : %s'
              % ('YES' if emp <= alpha else 'NO  <-- look at this'))
        print('     recall paid at this tau      : %.4f  (vs %.4f at conf 0.50)'
              % (rec, recall_at(sw, 0.50)))

        # does the certificate survive a change of distractor distribution?
        print('     the same tau on other sets:')
        for s in SETS:
            if s == CAL_SET: continue
            a = scores[s]
            f_ = int((a > tau).sum())
            print('        %-12s %4d/%4d = %6.2f %%   %s'
                  % (s, f_, len(a), 100.0 * f_ / len(a),
                     'within alpha' if f_ / float(len(a)) <= alpha else 'EXCEEDS alpha'))
            out.append({'alpha': alpha, 'tau': round(tau, 4), 'set': s,
                        'n': len(a), 'fired': f_,
                        'fpr': round(100.0 * f_ / len(a), 3)})
        out.append({'alpha': alpha, 'tau': round(tau, 4), 'set': CAL_SET + '_heldout',
                    'n': len(tst), 'fired': fired, 'fpr': round(100 * emp, 3)})

    with open(os.path.join(OUT, 'E2_2_conformal.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['alpha', 'tau', 'set', 'n', 'fired', 'fpr'])
        w.writeheader(); w.writerows(out)
    print()
    return out


# ------------------------------------------ E2.3 sensitivity to n, repeated

def e2_3():
    scores = load_scores(HEADLINE, CAL_SET)
    n_all = len(scores)
    print('=' * 78)
    print('E2.3  HOW MANY CALIBRATION IMAGES ARE ENOUGH?  (%d random splits each)'
          % N_REPEATS)
    print('=' * 78)
    print('%6s %7s %10s %22s %20s' %
          ('n', 'alpha', 'feasible', 'tau  mean [min,max]', 'realised FPR mean'))
    print('-' * 78)

    rows = []
    for n in N_GRID:
        for alpha in ALPHAS:
            k = int(math.ceil((n + 1) * (1.0 - alpha)))
            if k > n:
                print('%6d %6.0f%% %10s   %-22s %s' %
                      (n, 100 * alpha, 'NO',
                       'k=%d > n=%d' % (k, n), 'cannot be certified'))
                rows.append({'n': n, 'alpha': alpha, 'feasible': 0,
                             'tau_mean': '', 'fpr_mean': '', 'exceed_rate': ''})
                continue
            taus, fprs = [], []
            for _ in range(N_REPEATS):
                idx = RNG.permutation(n_all)
                cal = scores[idx[:n]]
                tst = scores[idx[n:]]
                tau, _, _ = conformal_tau(cal, alpha)
                taus.append(tau)
                fprs.append((tst > tau).mean())
            taus, fprs = np.array(taus), np.array(fprs)
            exceed = 100.0 * (fprs > alpha).mean()
            print('%6d %6.0f%% %10s   %6.4f [%6.4f,%6.4f]   %6.3f %%  (exceeds alpha in %4.1f %% of splits)'
                  % (n, 100 * alpha, 'yes', taus.mean(), taus.min(), taus.max(),
                     100 * fprs.mean(), exceed))
            rows.append({'n': n, 'alpha': alpha, 'feasible': 1,
                         'tau_mean': round(float(taus.mean()), 4),
                         'fpr_mean': round(float(100 * fprs.mean()), 4),
                         'exceed_rate': round(float(exceed), 2)})

    with open(os.path.join(OUT, 'E2_3_n_sensitivity.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['n', 'alpha', 'feasible', 'tau_mean',
                                          'fpr_mean', 'exceed_rate'])
        w.writeheader(); w.writerows(rows)
    print()
    print('  The guarantee is MARGINAL: averaged over calibration draws the')
    print('  false-alarm rate is at or under alpha. Any single split can land')
    print('  above it, which is why the "exceeds alpha" column is reported')
    print('  rather than hidden. n >= 1/alpha - 1 is the hard floor: 99 images')
    print('  to certify 1 %, and no threshold can do it with 50.')
    print()
    return rows


# ------------------------------- E2.4 a certificate for the ONE calibration
#                                  you will actually perform

def binom_sf(m, n, p):
    """P(Binom(n, p) >= m), in log space."""
    from math import lgamma, exp, log
    if m <= 0: return 1.0
    if m > n:  return 0.0
    tot = 0.0
    for i in range(m, n + 1):
        tot += exp(lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1)
                   + i * log(p) + (n - i) * log(1 - p))
    return tot


def pac_k(n, alpha, delta):
    """Smallest order statistic k whose CONDITIONAL false-alarm rate is <= alpha
    with confidence 1-delta over the calibration draw.

    For a continuous score distribution, 1 - F(s_(k)) ~ Beta(n+1-k, k), and for
    integer parameters P(Beta(a,b) <= alpha) = P(Binom(n, alpha) >= a). So the
    requirement is simply P(Binom(n, alpha) >= n+1-k) >= 1 - delta.

    Marginal conformal answers "on average over calibrations". This answers
    "for the single calibration I am about to run", which is the question a
    deployed threshold actually poses.
    """
    for k in range(1, n + 1):
        if binom_sf(n + 1 - k, n, alpha) >= 1.0 - delta:
            return k
    return None


def min_n_for(alpha, delta):
    """Fewest calibration negatives that can certify alpha at confidence 1-delta.

    The best case is k = n (threshold = the largest calibration score), which
    needs P(Binom(n, alpha) >= 1) >= 1 - delta, i.e. 1 - (1-alpha)^n >= 1-delta.
    """
    n = 1
    while n < 100000:
        if 1.0 - (1.0 - alpha) ** n >= 1.0 - delta:
            return n
        n += 1
    return None


def e2_4(delta=0.05):
    sw = load_sweep(HEADLINE)
    scores = {s: load_scores(HEADLINE, s) for s in SETS}
    cal_all = np.sort(scores[CAL_SET])
    n_all = len(cal_all)

    print('=' * 78)
    print('E2.4  TRAINING-CONDITIONAL CERTIFICATE  (confidence %.0f %%)'
          % (100 * (1 - delta)))
    print('=' * 78)
    print('  Marginal conformal is an average over calibration draws. You will')
    print('  calibrate ONCE, and that one threshold is what ships. This asks')
    print('  instead: how many negatives are needed so the threshold I obtain')
    print('  has conditional FPR <= alpha with %.0f %% confidence?' % (100 * (1 - delta)))
    print()
    print('%8s %14s %38s' % ('alpha', 'min n needed', 'with the %d hn_holdout images we have' % n_all))
    print('-' * 78)

    rows = []
    for alpha in ALPHAS:
        nmin = min_n_for(alpha, delta)
        k = pac_k(n_all, alpha, delta)
        if k is None:
            print('%7.0f%% %14d   not achievable even with all %d' % (100 * alpha, nmin, n_all))
            rows.append({'alpha': alpha, 'min_n': nmin, 'k': '', 'tau': '',
                         'recall': '', 'note': 'infeasible at n=%d' % n_all})
            continue
        tau = float(cal_all[k - 1])
        rec = recall_at(sw, tau)
        print('%7.0f%% %14d   k=%d of %d  ->  tau = %.4f   recall %.4f'
              % (100 * alpha, nmin, k, n_all, tau, rec))
        rows.append({'alpha': alpha, 'min_n': nmin, 'k': k, 'tau': round(tau, 4),
                     'recall': round(rec, 4), 'note': ''})

        for s in SETS:
            if s == CAL_SET: continue
            a = scores[s]
            f_ = int((a > tau).sum())
            print('             %-12s %4d/%4d = %6.2f %%   %s'
                  % (s, f_, len(a), 100.0 * f_ / len(a),
                     'holds' if f_ / float(len(a)) <= alpha else 'EXCEEDS - different distribution'))

    with open(os.path.join(OUT, 'E2_4_pac_certificate.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['alpha', 'min_n', 'k', 'tau', 'recall', 'note'])
        w.writeheader(); w.writerows(rows)

    print()
    print('  Reading it: certifying 1 %% at %.0f %% confidence needs %d negatives,'
          % (100 * (1 - delta), min_n_for(0.01, delta)))
    print('  so the frozen 500-image holdout is enough and 250 is not. That is a')
    print('  concrete design rule for anyone repeating this, and it is the kind')
    print('  of number the field currently never states.')
    print()
    return rows


if __name__ == '__main__':
    e2_1()
    e2_2()
    e2_3()
    e2_4()
    print('written to %s' % OUT)
