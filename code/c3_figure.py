# -*- coding: utf-8 -*-
"""C3 figure: the sweep, and the 2x2 that shows the two factors do not overlap."""
import os, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from temporal_alarm import run_video

HERE = os.path.dirname(os.path.abspath(__file__))


def files(root):
    out = []
    for s in ('fire_neg', 'smoke_neg', 'kmu_neg'):
        out += [p for p in sorted(glob.glob(os.path.join(HERE, root, s, '*.csv')))
                if not os.path.basename(p).startswith('_')]
    return out


def agg(fs, K, N, io_):
    a = s = 0
    for c in fs:
        r = run_video(c, K, N, io_, 0.50)
        if r:
            a += r['alarms']; s += r['duration_s']
    return a, (a / s * 3600 if s else 0.0)


fs_sf, fs_bl = files('dets'), files('dets_baseline')
GRID = [(1, 1), (2, 3), (3, 5), (4, 7), (5, 9)]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 4.9))

# ---- (a) the sweep, both detectors, against the independence prediction
for fs, lab, col in ((fs_bl, 'no-negatives baseline', '#d63031'),
                     (fs_sf, 'SAFE-Fire (mined negatives)', '#2979d6')):
    y = [agg(fs, K, N, 0.30)[1] for K, N in GRID]
    ax1.plot(range(len(GRID)), y, 'o-', lw=2.2, ms=7, color=col, label=lab)
    for i, v in enumerate(y):
        ax1.annotate('%.0f' % v, (i, v), textcoords='offset points',
                     xytext=(0, 9), ha='center', fontsize=8, color=col)

# what the usual independence argument predicts for the SAFE-Fire detector
from math import comb
p = 0.0120
pred = []
for K, N in GRID:
    q = p if N == 1 else sum(comb(N, i) * p**i * (1-p)**(N-i) for i in range(K, N+1))
    pred.append(q * 16.3 * 3600)
ax1.plot(range(len(GRID)), pred, '--', lw=1.8, color='#666',
         label='what independence predicts (SAFE-Fire)')

ax1.set_yscale('log')
# headroom, or the +9pt annotation on the highest point is clipped by the axes
ax1.set_ylim(top=ax1.get_ylim()[1] * 3.0)
ax1.set_xticks(range(len(GRID)))
ax1.set_xticklabels(['%d-of-%d' % g for g in GRID])
ax1.set_ylabel('false alarms per hour  (log scale)')
ax1.set_xlabel('persistence rule,  IoU association $\\geq$ 0.30')
ax1.set_title('(a) the independence argument is wrong by two orders',
              fontsize=11, loc='left', pad=12)
ax1.grid(alpha=0.25, which='both')
ax1.legend(fontsize=8.5)

# ---- (b) the 2x2
# the "no layer" column uses the SAME association threshold as the "with layer"
# one. IoU = 0.0 would mean "associate with anything", silently merging tracks,
# and the two panels would then disagree on what the baseline row is.
cells = np.array([[agg(fs_bl, 1, 1, 0.30)[1], agg(fs_bl, 3, 5, 0.30)[1]],
                  [agg(fs_sf, 1, 1, 0.30)[1], agg(fs_sf, 3, 5, 0.30)[1]]])
im = ax2.imshow(cells, cmap='Reds', norm=matplotlib.colors.LogNorm())
ax2.set_xticks([0, 1]); ax2.set_xticklabels(['no temporal layer', '3-of-5 + IoU'])
ax2.set_yticks([0, 1]); ax2.set_yticklabels(['no-negatives\nbaseline', 'SAFE-Fire\n(kd6)'])
for i in range(2):
    for j in range(2):
        ax2.text(j, i, '%.0f' % cells[i, j], ha='center', va='center',
                 fontsize=19, fontweight='bold',
                 color='white' if cells[i, j] > 300 else '#111')
ax2.set_title('(b) false alarms per hour - the layer does not replace the data',
              fontsize=11, loc='left', pad=12)
ax2.annotate('', xy=(0.80, 0.84), xytext=(0.20, 0.16),
             arrowprops=dict(arrowstyle='->', lw=2.6, color='#111',
                             shrinkA=0, shrinkB=0))
both = cells[0, 0] / cells[1, 1]
indep = (cells[0, 0] / cells[1, 0]) * (cells[0, 0] / cells[0, 1])
ax2.text(0.5, 1.72,
         '%.1fx together      %.1fx if the two factors were independent'
         % (both, indep), ha='center', fontsize=10, fontweight='bold',
         bbox=dict(boxstyle='round,pad=0.4', fc='#fff8f0', ec='#111', alpha=.97))
ax2.set_xlim(-0.5, 1.5); ax2.set_ylim(1.95, -0.5)

fig.text(0.5, 0.005,
         '32.2 min of negative footage: FIRESENSE 14.5 min + KMU flame-like 17.7 min. '
         'Absolute rates are pooled over two corpora of unequal difficulty and are '
         'reported per source in E3_2_two_by_two.csv; the RATIOS are what compare.',
         ha='center', fontsize=7.4, color='#555')

plt.tight_layout(rect=[0, 0.03, 1, 1])
out = os.path.join(HERE, 'fig_C3_temporal.png')
plt.savefig(out, dpi=170)
print('wrote', out)
print('cells (per hour):\n', np.round(cells, 1))
