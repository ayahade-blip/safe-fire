# -*- coding: utf-8 -*-
"""Build the PyTorch reference for the FP16 fidelity check.

The comparison is only meaningful if both sides see byte-identical input, so
the letterboxing happens ONCE here and the result is written as lossless PNG.
Ultralytics then letterboxes a 640x640 image to 640x640, which is a no-op, and
the Jetson reads the same PNG. Any difference that survives is quantisation,
not preprocessing.
"""
import os, io, json, zipfile
import numpy as np, cv2
from ultralytics import YOLO

SF = r'C:\Users\hp\Desktop\TEMP\SAFE_FIRE'
HF_ZIP = os.path.join(SF, 'datasets', 'home_fire.zip')
WEIGHTS = os.path.join(SF, 'weights', 'kd__kd6__s42__best.pt')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fp16_check')
NET = 640
CONF = 0.25

# frames the Grad-CAM sweep already showed carry clear fire or smoke
PICKS = ['test_10', 'test_1070', 'test_224', 'test_390', 'test_505',
         'test_895', 'test_952', 'test_577', 'test_1068', 'test_582',
         'test_558', 'test_318']


def letterbox(bgr, net=NET):
    h, w = bgr.shape[:2]
    r = min(net / h, net / w)
    nh, nw = int(round(h * r)), int(round(w * r))
    resized = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((net, net, 3), 114, np.uint8)
    top, left = (net - nh) // 2, (net - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    return canvas


os.makedirs(OUT, exist_ok=True)
z = zipfile.ZipFile(HF_ZIP)
names = [n for n in z.namelist() if n.startswith('test/images/')]
print('test images in zip: %d' % len(names))

made = []
for p in PICKS:
    hit = [n for n in names if n.endswith('/%s.jpg' % p)]
    if not hit:
        print('  missing %s' % p); continue
    bgr = cv2.imdecode(np.frombuffer(z.read(hit[0]), np.uint8), cv2.IMREAD_COLOR)
    lb = letterbox(bgr)
    dst = os.path.join(OUT, '%s.png' % p)
    cv2.imwrite(dst, lb)
    made.append((p, dst))
print('letterboxed %d images -> %s' % (len(made), OUT))

model = YOLO(WEIGHTS)
ref = {}
for name, path in made:
    r = model.predict(path, imgsz=NET, conf=CONF, device=0, verbose=False)[0]
    boxes = r.boxes.xyxy.cpu().numpy().tolist()
    confs = r.boxes.conf.cpu().numpy().tolist()
    clss = r.boxes.cls.cpu().numpy().astype(int).tolist()
    ref[name] = [{'box': [round(v, 2) for v in b], 'conf': round(c, 4), 'cls': k}
                 for b, c, k in zip(boxes, confs, clss)]
    print('  %-12s %d detections  %s' % (name, len(boxes),
          ' '.join('%.3f' % c for c in confs[:5])))

with open(os.path.join(OUT, 'pytorch_ref.json'), 'w') as f:
    json.dump({'conf': CONF, 'imgsz': NET, 'weights': os.path.basename(WEIGHTS),
               'names': model.names, 'ref': ref}, f, indent=1)
print('\nclass names from the checkpoint: %s' % model.names)
print('wrote pytorch_ref.json')
