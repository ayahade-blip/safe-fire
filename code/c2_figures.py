# -*- coding: utf-8 -*-
"""Figures for C2.

Two panels, because the paper needs to make two separate points:

  (a) what a false-alarm guarantee costs in recall, and how the marginal
      guarantee differs from the one that actually covers a deployed threshold;
  (b) that the certificate is tied to the distribution it was calibrated on -
      the same lesson C1 reaches from the data side.
"""
import os, math, csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r'C:\Users\hp\Desktop\TEMP\SAFE_FIRE\results'
HEADLINE = 'kd__kd6__s42'
SETS = ['hn_holdout', 'novel', 'mined_dev', 'dfire_neg']
NICE = {'hn_holdout': 'hard holdout (500)', 'novel': 'novel fire-like (196)',
        'mined_dev': 'open-world mined (400)', 'dfire_neg': 'D-Fire negatives (1500)'}


def load_scores(setname):
    p = os.path.join(ROOT, 'scores_v2', '%s__%s.csv' % (HEADLINE, setname))
    with open(p) as f:
        r = csv.reader(f); next(r)
        return np.array([float(x[1]) for x in r if len(x) >= 2])


def load_sweep():
    p = os.path.join(ROOT, 'sweeps_v2', '%s__test_sweep.csv' % HEADLINE)
    with open(p) as f:
        r = csv.reader(f); next(r)
        rows = [(float(a), float(b)) for a, b, *_ in r]
    return np.array([x[0] for x in rows]), np.array([x[1] for x in rows])


def binom_sf(m, n, p):
    from math import lgamma, exp, log
    if m <= 0: return 1.0
    if m > n:  return 0.0
    return sum(exp(lgamma(n+1) - lgamma(i+1) - lgamma(n-i+1)
                   + i*log(p) + (n-i)*log(1-p)) for i in range(m, n+1))


cal = np.sort(load_scores('hn_holdout'))
n = len(cal)
conf, rec = load_sweep()
alphas = np.linspace(0.005, 0.15, 60)

tau_marg, tau_pac, rec_marg, rec_pac = [], [], [], []
for a in alphas:
    k = int(math.ceil((n + 1) * (1 - a)))
    tau_marg.append(cal[min(k, n) - 1])
    kp = None
    for kk in range(1, n + 1):
        if binom_sf(n + 1 - kk, n, a) >= 0.95:
            kp = kk; break
    tau_pac.append(cal[kp - 1] if kp else np.nan)
    rec_marg.append(np.interp(tau_marg[-1], conf, rec))
    rec_pac.append(np.interp(tau_pac[-1], conf, rec) if kp else np.nan)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.9))

ax1.plot(alphas * 100, rec_marg, lw=2.2, color='#2979d6',
         label='marginal guarantee (average over calibrations)')
ax1.plot(alphas * 100, rec_pac, lw=2.2, color='#d63031',
         label='holds for the one calibration you run (95% conf.)')
ax1.axhline(np.interp(0.5, conf, rec), ls='--', lw=1.4, color='#7a7a7a')
ax1.text(14.6, np.interp(0.5, conf, rec) + 0.004, 'recall at a hand-picked conf 0.50',
         ha='right', fontsize=9, color='#555')
ax1.set_xlabel('guaranteed false-alarm rate  $\\alpha$  (%)')
ax1.set_ylabel('recall on the frozen test split')
ax1.set_title('(a) what the certificate costs', fontsize=11, loc='left', pad=12)
ax1.grid(alpha=0.25)
ax1.legend(fontsize=8.5, loc='lower right')

# (b) one tau, four distributions
k = int(math.ceil((n + 1) * 0.99))
tau = cal[k - 1]
names, vals = [], []
for s in SETS:
    a = load_scores(s)
    names.append(NICE[s]); vals.append(100.0 * (a > tau).mean())
colors = ['#2979d6' if s == 'hn_holdout' else '#d63031' for s in SETS]
bars = ax2.barh(range(len(names)), vals, color=colors, alpha=.85)
ax2.axvline(1.0, ls='--', lw=1.6, color='#111')
ax2.text(1.05, len(SETS) - 0.35, 'the certified 1 %', fontsize=9, color='#111')
ax2.set_yticks(range(len(names))); ax2.set_yticklabels(names, fontsize=9)
ax2.invert_yaxis()
ax2.set_xlabel('false-alarm rate at the threshold calibrated on the hard holdout (%)')
ax2.set_title('(b) the guarantee travels only with its own distribution',
              fontsize=11, loc='left', pad=12)
for b, v in zip(bars, vals):
    inside = v > 0.6                       # keep the label off the 1 % line
    ax2.text(v - 0.06 if inside else v + 0.06,
             b.get_y() + b.get_height() / 2, '%.2f%%' % v, va='center',
             ha='right' if inside else 'left', fontsize=9,
             color='white' if inside else '#111', fontweight='bold')
ax2.grid(alpha=0.25, axis='x')
ax2.set_xlim(0, max(vals) * 1.25)

plt.tight_layout()
out = os.path.join(HERE, 'fig_C2_conformal.png')
plt.savefig(out, dpi=170)
print('wrote %s' % out)
print('tau at alpha=1%% (marginal, n=%d): %.4f' % (n, tau))
