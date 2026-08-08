# -*- coding: utf-8 -*-
"""C3 - what a temporal rule can and cannot remove, decided before any video.

A K-of-N persistence rule is usually justified with an independence argument:
if a frame false-alarms with probability p, then K of the last N frames doing
so has probability P(Binom(N, p) >= K), which is tiny. That argument is wrong
for this problem, and building the layer without saying so would be building
it on a false premise.

False alarms in a fixed indoor scene are not independent draws. A lamp is a
lamp in every frame. If the detector fires on it, it fires on all N frames and
K-of-N passes it through untouched - the rule cannot see the difference between
a persistent lamp and a persistent fire.

So the two regimes have to be separated, and the honest claim is narrower than
the usual one. This script quantifies both ends using kd6's measured per-frame
false-alarm rate, so the design decision rests on numbers rather than on the
independence story.
"""
import os, csv, math
import numpy as np

ROOT = r'C:\Users\hp\Desktop\TEMP\SAFE_FIRE\results'
HEADLINE = 'kd__kd6__s42'
FPS = 16.3                      # measured end-to-end on the Jetson, MAXN
SETS = ['hn_holdout', 'novel', 'mined_dev', 'dfire_neg']


def load(setname):
    p = os.path.join(ROOT, 'scores_v2', '%s__%s.csv' % (HEADLINE, setname))
    with open(p) as f:
        r = csv.reader(f); next(r)
        return np.array([float(x[1]) for x in r if len(x) >= 2])


def binom_sf(k, n, p):
    """P(Binom(n, p) >= k)"""
    if k <= 0: return 1.0
    if k > n:  return 0.0
    return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))


print('=' * 76)
print('  C3  -  the two regimes of a false alarm, and which one K-of-N removes')
print('=' * 76)
print()

p = float((load('hn_holdout') >= 0.50).mean())
print('  measured per-frame false-alarm rate of kd6 at conf 0.50 : %.4f  (%.2f %%)'
      % (p, 100 * p))
print('  measured pipeline rate on the Jetson                    : %.1f FPS' % FPS)
print()

print('  REGIME 1 - independent, momentary false alarms')
print('  (sensor noise, a reflection sweeping past, one bad frame)')
print()
print('    %3s %3s %14s %16s %14s' % ('K', 'N', 'P(alarm)/frame', 'alarms per hour', 'added delay'))
print('    ' + '-' * 66)
for K, N in [(1, 1), (2, 3), (3, 5), (4, 7), (5, 9)]:
    q = binom_sf(K, N, p) if N > 1 else p
    per_hour = q * FPS * 3600
    delay = (K - 1) / FPS
    print('    %3d %3d %13.2e %16.3f %11.2f s' % (K, N, q, per_hour, delay))

print()
print('    2-of-3 takes a nominal 704 false alarms an hour down to 25;')
print('    3-of-5 takes it to 1.0. That is the regime the rule is for,')
print('    and it is cheap: 3-of-5')
print('    costs %.2f s of extra latency at %.1f FPS.' % (2 / FPS, FPS))
print()

print('  REGIME 2 - a persistent confuser in the field of view')
print('  (a lamp, a heater, fire on a television screen)')
print()
print('    %3s %3s %14s %16s' % ('K', 'N', 'P(alarm)/frame', 'alarms per hour'))
print('    ' + '-' * 42)
for K, N in [(1, 1), (2, 3), (3, 5), (5, 9)]:
    print('    %3d %3d %13.2f %16s' % (K, N, 1.0, 'continuous'))
print()
print('    The object is there in every frame, so every window is full and the')
print('    rule passes it straight through. NO value of K or N helps.')
print('    Temporal logic cannot fix a detector that believes a lamp is fire.')
print()

print('=' * 76)
print('  CONSEQUENCE FOR THE THESIS')
print('=' * 76)
print("""
  The two contributions are not alternatives and not redundant - they act on
  disjoint failure modes:

     mined hard negatives  ->  remove REGIME 2 (persistent confusers)
     K-of-N + association  ->  remove REGIME 1 (momentary detections)

  That is a real argument for having both, and it is stronger than the usual
  "we also added temporal smoothing". It also predicts the 2x2 experiment
  (E3.2) result before it is run: the temporal layer should help the
  negative-free baseline far less than the independence maths suggests,
  because the baseline's false alarms are mostly lamps, and lamps persist.

  If E3.2 comes out otherwise, this reasoning is wrong and that is worth
  knowing. Writing the prediction down first is what makes it a test.
""")

print('=' * 76)
print('  WHAT SPATIAL ASSOCIATION ADDS')
print('=' * 76)
print("""
  Requiring detections to overlap across frames (IoU >= 0.3) separates the two
  regimes further, and on a different axis from persistence:

     a real fire   grows and stays in place       -> boxes overlap frame to frame
     a reflection  flickers and jumps             -> boxes do not
     a screen fire moves with the video content   -> boxes wander

  So association is not a duplicate of K-of-N. K-of-N asks "how often", the
  IoU chain asks "in the same place". A confuser can satisfy one and fail the
  other, which is exactly why both belong in the rule.
""")
