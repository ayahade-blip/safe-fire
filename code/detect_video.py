# -*- coding: utf-8 -*-
"""C3 - run the detector over a folder of videos and dump per-frame detections.

    python detect_video.py <videos_dir> <out_dir> [--conf 0.10] [--stride 1]

Writes one CSV per video:

    frame,time_s,x1,y1,x2,y2,conf,cls

Frames with no detection still get a row (empty box fields) so the CSV records
the full timeline - otherwise a gap is ambiguous between "nothing detected" and
"frame not processed", and false-alarms-per-hour would be computed against the
wrong denominator.

DETECTION IS SEPARATED FROM THE TEMPORAL RULE ON PURPOSE. Inference over the
videos happens once at a LOW confidence (0.10). Every (K, N, IoU, conf) the
sweep tries afterwards reads these CSVs, so the whole parameter search costs
seconds instead of one full inference pass per combination. Set --conf lower
than any threshold you intend to sweep, or the sweep silently cannot reach it.
"""
import os, sys, csv, time, argparse
import cv2
from ultralytics import YOLO

WEIGHTS = r'C:\Users\hp\Desktop\TEMP\SAFE_FIRE\weights\kd__kd6__s42__best.pt'
VIDEO_EXT = ('.avi', '.mp4', '.mov', '.mkv', '.mpg', '.mpeg', '.wmv', '.flv')


def run(video, out_csv, model, conf, stride, imgsz=640):
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        print('  cannot open %s' % video)
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    rows, idx, n_det = [], 0, 0
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if stride > 1 and idx % stride:
            idx += 1
            continue
        r = model.predict(frame, imgsz=imgsz, conf=conf, device=0, verbose=False)[0]
        t = idx / fps
        if len(r.boxes):
            for b, c, k in zip(r.boxes.xyxy.cpu().numpy(),
                               r.boxes.conf.cpu().numpy(),
                               r.boxes.cls.cpu().numpy()):
                rows.append([idx, round(t, 4), round(float(b[0]), 1),
                             round(float(b[1]), 1), round(float(b[2]), 1),
                             round(float(b[3]), 1), round(float(c), 4), int(k)])
                n_det += 1
        else:
            rows.append([idx, round(t, 4), '', '', '', '', '', ''])
        idx += 1
    cap.release()

    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['frame', 'time_s', 'x1', 'y1', 'x2', 'y2', 'conf', 'cls'])
        w.writerows(rows)

    dur = idx / fps
    print('  %-42s %5d frames  %6.1f s  %5d dets  (%.1f s wall)'
          % (os.path.basename(video)[:42], idx, dur, n_det, time.time() - t0))
    return {'video': os.path.basename(video), 'frames': idx, 'fps': fps,
            'duration_s': round(dur, 2), 'detections': n_det}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('videos_dir')
    ap.add_argument('out_dir')
    ap.add_argument('--weights', default=WEIGHTS)
    ap.add_argument('--conf', type=float, default=0.10,
                    help='keep it BELOW every threshold you plan to sweep')
    ap.add_argument('--stride', type=int, default=1)
    ap.add_argument('--imgsz', type=int, default=640)
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    vids = []
    for root, _, files in os.walk(a.videos_dir):
        for f in sorted(files):
            if f.lower().endswith(VIDEO_EXT):
                vids.append(os.path.join(root, f))
    if not vids:
        print('no videos under %s' % a.videos_dir)
        return

    print('model : %s' % os.path.basename(a.weights))
    print('videos: %d   conf=%.2f   stride=%d' % (len(vids), a.conf, a.stride))
    print()
    model = YOLO(a.weights)

    summary = []
    for v in vids:
        rel = os.path.relpath(v, a.videos_dir).replace(os.sep, '__')
        out = os.path.join(a.out_dir, os.path.splitext(rel)[0] + '.csv')
        if os.path.exists(out):
            print('  skip (exists) %s' % os.path.basename(out))
            continue
        s = run(v, out, model, a.conf, a.stride, a.imgsz)
        if s:
            s['rel'] = rel
            summary.append(s)

    if summary:
        with open(os.path.join(a.out_dir, '_index.csv'), 'a', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['rel', 'video', 'frames', 'fps',
                                              'duration_s', 'detections'])
            if f.tell() == 0:
                w.writeheader()
            w.writerows(summary)
    tot = sum(s['duration_s'] for s in summary)
    print()
    print('  %d videos, %.1f minutes of footage -> %s'
          % (len(summary), tot / 60.0, a.out_dir))


if __name__ == '__main__':
    main()
