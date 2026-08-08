# -*- coding: utf-8 -*-
"""C3 - the temporal alarm layer, and the metrics that judge it.

Deliberately decoupled from inference. It consumes a per-frame detections CSV

    frame,time_s,x1,y1,x2,y2,conf,cls

so the (K, N, IoU) sweep runs in seconds on a laptop instead of re-running the
detector once per parameter combination. `detect_video.py` produces that CSV,
on the desktop with ultralytics or on the Jetson with TensorRT - either way the
numbers below are computed from exactly the same file.

THE RULE
    1. Associate each detection with an existing track when it overlaps that
       track's last box by IoU >= IOU_MIN, otherwise start a new track.
    2. A track raises an alarm once it has been seen in K of the last N frames.
    3. Tracks with no hit for MAX_MISS frames are dropped.

Step 1 is not decoration. K-of-N alone asks only "how often"; the IoU chain
asks "in the same place". A flickering reflection can satisfy the first and
fail the second, and it is the combination that separates them.

NO TRAINING. Nothing here has parameters fitted to data - K, N and IOU_MIN are
chosen on a development split and then frozen, which is what makes E3.2 a test
rather than a fit.
"""
import csv, os
from collections import defaultdict


def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0.0


class Track(object):
    __slots__ = ('box', 'hits', 'last_frame', 'first_frame', 'alarmed', 'cls')

    def __init__(self, box, frame, cls):
        self.box = box
        self.cls = cls
        self.hits = [frame]
        self.first_frame = frame
        self.last_frame = frame
        self.alarmed = False


class TemporalAlarm(object):
    """K-of-N persistence with spatial association."""

    def __init__(self, K=3, N=5, iou_min=0.30, conf=0.50, max_miss=None):
        self.K, self.N, self.iou_min, self.conf = K, N, iou_min, conf
        self.max_miss = N if max_miss is None else max_miss
        self.tracks = []

    def update(self, frame_idx, dets):
        """dets = [(x1,y1,x2,y2,conf,cls), ...]  ->  list of tracks alarming now."""
        dets = [d for d in dets if d[4] >= self.conf]
        used = set()
        for t in self.tracks:
            best, bi = 0.0, -1
            for j, d in enumerate(dets):
                if j in used or int(d[5]) != t.cls:
                    continue
                v = iou(t.box, d[:4])
                if v > best:
                    best, bi = v, j
            if bi >= 0 and best >= self.iou_min:
                used.add(bi)
                t.box = dets[bi][:4]
                t.hits.append(frame_idx)
                t.last_frame = frame_idx

        for j, d in enumerate(dets):
            if j not in used:
                self.tracks.append(Track(d[:4], frame_idx, int(d[5])))

        self.tracks = [t for t in self.tracks
                       if frame_idx - t.last_frame <= self.max_miss]

        fired = []
        for t in self.tracks:
            t.hits = [h for h in t.hits if h > frame_idx - self.N]
            if not t.alarmed and len(t.hits) >= self.K:
                t.alarmed = True
                fired.append(t)
        return fired


# ---------------------------------------------------------------- evaluation

def read_dets(path):
    """CSV -> {frame: [(x1,y1,x2,y2,conf,cls)]}, plus the frame->time map."""
    per = defaultdict(list)
    times = {}
    with open(path) as f:
        r = csv.DictReader(f)
        if not r.fieldnames or 'frame' not in r.fieldnames:
            return per, times          # not a detections file (e.g. _index.csv)
        for row in r:
            fr = int(row['frame'])
            times[fr] = float(row['time_s'])
            if row.get('conf', '') == '':
                continue                      # a frame with no detections
            per[fr].append((float(row['x1']), float(row['y1']),
                            float(row['x2']), float(row['y2']),
                            float(row['conf']), int(float(row['cls']))))
    return per, times


def run_video(det_csv, K, N, iou_min, conf, onset_s=None):
    """Play one video through the layer.

    onset_s = the second at which fire first becomes visible, from the video's
    annotation. Required for time-to-alarm; leave None for negative clips.
    """
    per, times = read_dets(det_csv)
    if not times:
        return None
    frames = sorted(times)
    layer = TemporalAlarm(K, N, iou_min, conf)

    alarms = []                                # (frame, time_s)
    for fr in frames:
        for t in layer.update(fr, per.get(fr, [])):
            alarms.append((fr, times[fr]))

    dur = times[frames[-1]] - times[frames[0]]
    raw = sum(1 for fr in frames
              if any(d[4] >= conf for d in per.get(fr, [])))

    # First frame the DETECTOR alone would have fired on. Absolute time-to-alarm
    # needs a hand-annotated ignition instant, which most corpora do not ship;
    # this needs none, and answers the question the layer is actually on trial
    # for: how many seconds of latency does persistence buy its false-alarm
    # reduction with? Reported alongside TTA, never as a substitute for it.
    first_det = next((times[fr] for fr in frames
                      if any(d[4] >= conf for d in per.get(fr, []))), None)

    out = {'video': os.path.basename(det_csv), 'frames': len(frames),
           'duration_s': round(dur, 2),
           'raw_frames_firing': raw,
           'alarms': len(alarms),
           'alarms_per_hour': round(len(alarms) / dur * 3600, 3) if dur > 0 else 0.0,
           'first_det_s': round(first_det, 3) if first_det is not None else None,
           'first_alarm_s': round(alarms[0][1], 3) if alarms else None,
           'layer_delay_s': None,
           'tta_s': None}
    if first_det is not None and alarms:
        out['layer_delay_s'] = round(alarms[0][1] - first_det, 3)
    if onset_s is not None and alarms:
        out['tta_s'] = round(alarms[0][1] - onset_s, 3)
    return out


def sweep(det_csvs, onsets=None, Ks=(1, 2, 3, 4), Ns=(1, 3, 5, 7),
          ious=(0.0, 0.3, 0.5), conf=0.50):
    """Grid over (K, N, IoU). Use this on a DEV split only, then freeze."""
    onsets = onsets or {}
    rows = []
    for K in Ks:
        for N in Ns:
            if K > N:
                continue
            for io_ in ious:
                per_hour, ttas, detected = [], [], 0
                for c in det_csvs:
                    r = run_video(c, K, N, io_, conf,
                                  onsets.get(os.path.basename(c)))
                    if r is None:
                        continue
                    per_hour.append(r['alarms_per_hour'])
                    if r['alarms']:
                        detected += 1
                    if r['tta_s'] is not None:
                        ttas.append(r['tta_s'])
                rows.append({
                    'K': K, 'N': N, 'iou': io_,
                    'videos': len(det_csvs),
                    'detected': detected,
                    'EDR': round(detected / float(len(det_csvs)), 4) if det_csvs else 0,
                    'FA_per_hour': round(sum(per_hour) / len(per_hour), 3) if per_hour else 0,
                    'TTA_mean_s': round(sum(ttas) / len(ttas), 3) if ttas else None,
                    'added_delay_s': round((K - 1) / 16.3, 3)})
    return rows


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        print('usage: python temporal_alarm.py <dets_dir> [K N iou conf]')
        raise SystemExit(0)
    d = sys.argv[1]
    csvs = [os.path.join(d, f) for f in sorted(os.listdir(d))
            if f.endswith('.csv') and not f.startswith('_')]
    if len(sys.argv) >= 6:
        K, N, io_, cf = int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
        print('%-34s %7s %9s %8s %12s' % ('video', 'frames', 'raw fires', 'alarms', 'per hour'))
        print('-' * 74)
        for c in csvs:
            r = run_video(c, K, N, io_, cf)
            if r:
                print('%-34s %7d %9d %8d %12.3f'
                      % (r['video'][:34], r['frames'], r['raw_frames_firing'],
                         r['alarms'], r['alarms_per_hour']))
    else:
        rows = sweep(csvs)
        print('%3s %3s %5s %8s %6s %12s %11s %12s'
              % ('K', 'N', 'IoU', 'videos', 'EDR', 'FA/hour', 'TTA mean', 'added delay'))
        print('-' * 70)
        for r in rows:
            print('%3d %3d %5.2f %8d %6.3f %12.3f %11s %10.2f s'
                  % (r['K'], r['N'], r['iou'], r['videos'], r['EDR'],
                     r['FA_per_hour'],
                     '%.2f' % r['TTA_mean_s'] if r['TTA_mean_s'] is not None else '-',
                     r['added_delay_s']))
