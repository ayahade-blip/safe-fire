# -*- coding: utf-8 -*-
"""C3 - E3.1 parameter sweep and the E3.2 2x2, from the extracted detections.

    python c3_analysis.py

E3.2 is a 2x2 because the question is not "does the temporal layer help" - it
obviously helps something - but "does it help ON TOP OF what the mined negatives
already do". Two detectors x two settings answers that; one row answers nothing.

                        no temporal layer   |   K-of-N + association
    no-negatives baseline        A          |            B
    SAFE-Fire (kd6)              C          |            D

If the layer and the data attacked the same failure, D would be no better than
the best of B and C. The prediction registered in c3_what_temporal_can_do.py is
the opposite: they attack disjoint regimes, so B should fall far short of C,
because the baseline's false alarms are persistent objects and no temporal rule
removes those.
"""
import os, csv, glob
from temporal_alarm import run_video, sweep

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = 0.50
MODELS = {'SAFE-Fire (kd6)': 'dets', 'no-negatives baseline': 'dets_baseline'}
# kmu_neg = KMU "smoke or flame-like moving object", 10 clips / 17.7 min. It is
# reported BOTH pooled and per-source below, because it is not the same domain:
# 16.6 of its 17.7 minutes are outdoor fog and cloud, and only 1.1 minutes are
# the indoor fire-like material (red clothing, neon sign, a screen in an office).
# Pooling silently would let outdoor haze dilute the indoor false-alarm rate.
NEG = {'dets': ['fire_neg', 'smoke_neg', 'kmu_neg'],
       'dets_baseline': ['fire_neg', 'smoke_neg', 'kmu_neg']}
SOURCES = {'FIRESENSE': ['fire_neg', 'smoke_neg'], 'KMU': ['kmu_neg']}
POS = {'dets': ['fire_pos', 'smoke_pos'],
       'dets_baseline': ['fire_pos', 'smoke_pos']}


def csvs(root, subs):
    out = []
    for s in subs:
        d = os.path.join(HERE, root, s)
        if not os.path.isdir(d):
            continue
        out += [p for p in sorted(glob.glob(os.path.join(d, '*.csv')))
                if not os.path.basename(p).startswith('_')]
    return out


def aggregate(files, K, N, io_, conf=CONF):
    """Pool the footage before dividing, so a 3-second clip does not weigh the
    same as a three-minute one. Averaging per-video rates would do that."""
    alarms = secs = fired_videos = 0
    for c in files:
        r = run_video(c, K, N, io_, conf)
        if not r:
            continue
        alarms += r['alarms']
        secs += r['duration_s']
        fired_videos += 1 if r['alarms'] else 0
    return {'videos': len(files), 'minutes': round(secs / 60.0, 1),
            'alarms': alarms, 'fired_videos': fired_videos,
            'per_hour': round(alarms / secs * 3600, 2) if secs > 0 else 0.0,
            'rate': round(fired_videos / float(len(files)), 4) if files else 0.0}


def wilson_upper(k, n, z=1.96):
    """Upper 95 % bound on a rate. With zero events the point estimate is 0 and
    reporting it as 0 would overclaim - this is what should be quoted instead."""
    if n == 0:
        return 1.0
    p = k / float(n)
    d = 1 + z*z/n
    c = p + z*z/(2*n)
    r = z * ((p*(1-p)/n + z*z/(4*n*n)) ** 0.5)
    return (c + r) / d


# ------------------------------------------------------------------ E3.1 sweep
print('=' * 92)
print('  E3.1  parameter sweep on the NEGATIVE footage  (SAFE-Fire detector)')
print('=' * 92)
neg = csvs('dets', NEG['dets'])
if not neg:
    raise SystemExit('no detections under dets/ - run detect_video.py first')

print('%3s %3s %5s %9s %9s %14s %13s' %
      ('K', 'N', 'IoU', 'alarms', 'per hour', 'videos firing', 'added delay'))
print('-' * 92)
# IoU = 0.0 is NOT "association off" - it means "associate with anything", so
# every detection joins the first live track and the count collapses. That is
# why the IoU 0.0 row can show FEWER alarms than 0.30 at K=1: with a real
# threshold a detection that jumps position starts a new track and alarms
# again. Association only pays once persistence is also required.
rows = []
for K, N in [(1, 1), (2, 3), (3, 5), (4, 7)]:
    for io_ in (0.0, 0.30):
        a = aggregate(neg, K, N, io_)
        rows.append(dict(K=K, N=N, iou=io_, **a))
        print('%3d %3d %5.2f %9d %9.2f %10d/%-3d %10.2f s'
              % (K, N, io_, a['alarms'], a['per_hour'],
                 a['fired_videos'], a['videos'], (K - 1) / 16.3))
with open(os.path.join(HERE, 'E3_1_sweep.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# ------------------------------------------------------------------- E3.2 2x2
CFG = (3, 5, 0.30)
print()
print('=' * 92)
print('  E3.2  the 2x2      temporal setting = %d-of-%d, IoU >= %.2f, conf %.2f'
      % (CFG[0], CFG[1], CFG[2], CONF))
print('=' * 92)

have = {k: v for k, v in MODELS.items() if csvs(v, NEG[v])}
if len(have) < 2:
    print('  the no-negatives baseline has not been run over the videos yet.')
    print('  Only %s is available, so the 2x2 cannot be filled in.' % list(have))

print()
# What "no layer" means, precisely. It is K=1, N=1: a single frame above the
# threshold raises an alarm, and the track latches so a continuously-firing
# object counts once rather than once per frame. That is the honest baseline
# for an ALARM - no real system re-alarms 16 times a second - but it is not
# "raw per-frame detections", and calling it that would inflate the reduction.
print('  FALSE ALARMS PER HOUR  (negative footage - lower is better)')
print('  no layer = K1/N1: one frame fires, the alarm latches until the object')
print('             leaves. Not "detections per frame" - alarms per hour.')
print()
print('  %-24s %14s %14s %12s' % ('detector', 'no layer', 'with layer', 'reduction'))
print('  ' + '-' * 68)
out = []
for name, root in MODELS.items():
    files = csvs(root, NEG[root])
    if not files:
        continue
    a = aggregate(files, 1, 1, CFG[2])
    b = aggregate(files, *CFG)
    red = ('%.1f %%' % (100.0 * (1 - b['per_hour'] / a['per_hour']))
           if a['per_hour'] > 0 else 'n/a (already 0)')
    print('  %-24s %14.2f %14.2f %12s' % (name, a['per_hour'], b['per_hour'], red))
    out.append({'detector': name, 'side': 'negative', 'minutes': a['minutes'],
                'no_layer_per_hour': a['per_hour'], 'with_layer_per_hour': b['per_hour'],
                'no_layer_alarms': a['alarms'], 'with_layer_alarms': b['alarms']})
    if b['alarms'] == 0:
        hrs = a['minutes'] / 60.0
        print('  %-24s   zero alarms in %.2f h -> true rate < %.2f /h (95 %% upper)'
              % ('', hrs, wilson_upper(0, max(int(hrs * 3600 * 16.3), 1)) * 3600 * 16.3))

print()
print('  PER SOURCE  -  pooled numbers hide which corpus the alarms come from')
print('  %-24s %-11s %8s %10s %12s' %
      ('detector', 'source', 'minutes', 'alarms', 'per hour'))
print('  ' + '-' * 70)
for name, root in MODELS.items():
    for src, subs in SOURCES.items():
        files = csvs(root, subs)
        if not files:
            continue
        a = aggregate(files, *CFG)
        print('  %-24s %-11s %8.1f %10d %12.2f'
              % (name, src, a['minutes'], a['alarms'], a['per_hour']))
        out.append({'detector': name, 'side': 'negative/' + src,
                    'minutes': a['minutes'], 'no_layer_per_hour': '',
                    'with_layer_per_hour': a['per_hour'],
                    'no_layer_alarms': '', 'with_layer_alarms': a['alarms']})

print()
print('  EVENT DETECTION RATE  (positive footage - higher is better)')
print('  %-24s %14s %14s' % ('detector', 'no layer', 'with layer'))
print('  ' + '-' * 54)
for name, root in MODELS.items():
    files = csvs(root, POS[root])
    if not files:
        continue
    a = aggregate(files, 1, 1, CFG[2])
    b = aggregate(files, *CFG)
    print('  %-24s %11.3f %3s %11.3f %3s'
          % (name, a['rate'], '(%d/%d)' % (a['fired_videos'], a['videos']),
             b['rate'], '(%d/%d)' % (b['fired_videos'], b['videos'])))
    out.append({'detector': name, 'side': 'positive', 'minutes': a['minutes'],
                'no_layer_per_hour': a['rate'], 'with_layer_per_hour': b['rate'],
                'no_layer_alarms': a['fired_videos'], 'with_layer_alarms': b['fired_videos']})

with open(os.path.join(HERE, 'E3_2_two_by_two.csv'), 'w', newline='') as f:
    if out:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

print()
print('  ' + '-' * 88)
print('  READ WITH CARE. This footage is FIRESENSE, which is largely outdoor.')
print('  The event-detection column therefore measures the domain gap as much')
print('  as the temporal layer, and XD2 already showed detection halves out of')
print('  domain (8.6 sigma). The false-alarm column is the defensible one here;')
print('  the detection column needs indoor video before it means anything.')
print('  ' + '-' * 88)
