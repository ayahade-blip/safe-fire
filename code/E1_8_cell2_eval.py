# ==========================================================================
#  E1.8 — الخلية الثانية: التقييم فقط
# ==========================================================================
#  التدريبان انتهيا والأوزان على الدرايف. هذه الخلية لا تدرّب شيئاً.
#
#  لماذا فشلت الخلية الأولى هنا:
#      sitecustomize.py يُصلح torch.load في **العمليات الفرعية** فقط، عبر
#      PYTHONPATH. لكن scan_fpr يعمل داخل عملية النوتبوك نفسها، وهي لم
#      تُرقَّع قط. فاستدعى DetectMultiBackend نسخة torch.load الأصلية،
#      و torch >= 2.6 يرفض تحميل DetectionModel تحت weights_only=True.
#      val.py نجا لأنه عملية فرعية. scan_fpr لا.
#
#  الإصلاح: ترقيع torch.load **في هذه العملية** قبل استيراد أي شيء من
#  المستودع. الملف من تدريبك أنتِ على هذا الجهاز، فلا مسألة ثقة هنا.
# ==========================================================================

import os, sys, json, zipfile, subprocess
from pathlib import Path

try:
    ROOT, D_WEIGHTS, header
except NameError:
    raise RuntimeError("شغّلي S1 قبل هذه الخلية")

E18    = ROOT / "e1_8"
YOLOV5 = Path("/content/yolov5")
IMGSZ  = 640
SEED   = 42
RESULTS = E18 / "e1_8_results.csv"

W_POS = D_WEIGHTS / ("e18__pos__s%d__best.pt" % SEED)
W_NEG = D_WEIGHTS / ("e18__combo__s%d__best.pt" % SEED)
for w in (W_POS, W_NEG):
    assert w.exists(), "الأوزان مفقودة: %s" % w
print("الأوزان موجودة:")
for w in (W_POS, W_NEG):
    print("  %-34s %6.1f MB" % (w.name, w.stat().st_size / 1e6))


# ------------------------------------------- الإصلاح: ترقيع torch.load محلياً
import functools
import numpy as np
import torch

if not getattr(torch.load, "_e18_patched", False):
    _orig_load = torch.load

    @functools.wraps(_orig_load)
    def _patched_load(*a, **k):
        k.setdefault("weights_only", False)
        return _orig_load(*a, **k)

    _patched_load._e18_patched = True
    torch.load = _patched_load
if not hasattr(np, "trapz"):
    np.trapz = np.trapezoid

print("torch.load patched in-process :", getattr(torch.load, "_e18_patched", False))
print("np.trapz available            :", hasattr(np, "trapz"))

ENV = dict(os.environ)
ENV["PYTHONPATH"] = str(YOLOV5) + os.pathsep + ENV.get("PYTHONPATH", "")
if str(YOLOV5) not in sys.path:
    sys.path.insert(0, str(YOLOV5))


# ------------------------------------------------------------------ mAP عبر val.py
def eval_map(weights, data_yaml, tag):
    r = subprocess.run(
        [sys.executable, str(YOLOV5 / "val.py"), "--weights", str(weights),
         "--data", str(data_yaml), "--img", str(IMGSZ), "--task", "test",
         "--name", "val_" + tag, "--exist-ok", "--device", "0"],
        capture_output=True, text=True, cwd=str(YOLOV5), env=ENV)
    if r.returncode != 0:
        print("  ⚠️ val.py رجع %d — آخر ٣٠ سطراً:" % r.returncode)
        for ln in (r.stdout + "\n" + r.stderr).strip().splitlines()[-30:]:
            print("   ", ln)
        return {}
    out = {}
    for ln in r.stdout.splitlines():
        p = ln.split()
        # سطر الملخّص:  all  <images>  <labels>  P  R  mAP50  mAP50-95
        if len(p) >= 7 and p[0] == "all":
            try:
                out = dict(P=float(p[3]), R=float(p[4]),
                           mAP50=float(p[5]), mAP5095=float(p[6]))
            except ValueError:
                pass
        if p and p[0] in ("flame", "smoke") and len(p) >= 7:
            try:
                out["AP50_" + p[0]] = float(p[5])
            except ValueError:
                pass
    if not out:
        print("  ⚠️ لم أستطع قراءة سطر النتائج من val.py — المخرجات الخام:")
        print(r.stdout[-1200:])
    return out


# -------------------------------------------- FPR على المجموعات المجمّدة
def scan_fpr(weights, tag):
    """أعلى ثقة لكل صورة سالبة، بمسار استدلال المستودع نفسه.

    لا يُستخدم ultralytics: أوزان مستودع YOLOv5 صنف مختلف ولا تُحمَّل به،
    وخلط مسارَي استدلال يجعل الأرقام غير قابلة للمقارنة بأرقامك المسجَّلة.
    """
    import cv2
    from models.common import DetectMultiBackend
    from utils.augmentations import letterbox
    from utils.general import non_max_suppression

    dev = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = DetectMultiBackend(str(weights), device=dev, dnn=False, fp16=False)
    model.warmup(imgsz=(1, 3, IMGSZ, IMGSZ))

    out = {}
    for zname, key in (("hn_holdout_500.zip", "hn_holdout"),
                       ("novel_firelike.zip", "novel"),
                       ("mined_dev.zip", "mined_dev"),
                       ("dfire_neg_1500.zip", "dfire_neg")):
        zp = ROOT / "eval_suite_v2" / zname
        if not zp.exists():
            print("  ⚠️ مفقود:", zp); continue
        z = zipfile.ZipFile(zp)
        names = [n for n in z.namelist()
                 if n.lower().endswith((".jpg", ".png", ".jpeg"))]
        mx = []
        for i, n in enumerate(names):
            im0 = cv2.imdecode(np.frombuffer(z.read(n), np.uint8), cv2.IMREAD_COLOR)
            if im0 is None:
                continue
            im = letterbox(im0, IMGSZ, stride=model.stride, auto=False)[0]
            im = im.transpose((2, 0, 1))[::-1]
            im = torch.from_numpy(np.ascontiguousarray(im)).to(dev).float() / 255.0
            with torch.no_grad():
                pred = model(im[None])
            pred = non_max_suppression(pred, conf_thres=0.001, iou_thres=0.45)[0]
            mx.append(float(pred[:, 4].max()) if len(pred) else 0.0)
            if (i + 1) % 250 == 0:
                print("    %s %d/%d" % (key, i + 1, len(names)))
        a = np.array(mx)
        out["FPR25_" + key] = round(100.0 * float((a >= 0.25).mean()), 2)
        out["FPR50_" + key] = round(100.0 * float((a >= 0.50).mean()), 2)
        np.savetxt(str(E18 / ("scores_%s__%s.csv" % (tag, key))), a,
                   fmt="%.6f", header="max_conf", comments="")
        print("  %-14s %-11s FPR@0.50 = %5.2f %%   FPR@0.25 = %5.2f %%"
              % (tag, key, out["FPR50_" + key], out["FPR25_" + key]))
    return out


# ------------------------------------------------------------------- التشغيل
import pandas as pd

rows = []
for tag, w, dy in (("pos_only",      W_POS, E18 / "ds_pos"   / "data.yaml"),
                   ("plus_safemine", W_NEG, E18 / "ds_combo" / "data.yaml")):
    header("تقييم: " + tag, "-")
    r = {"run": tag, "protocol": "YOLO-HF (scratch, SGD, 300ep)",
         "model": "yolov5s", "seed": SEED}
    r.update(eval_map(w, dy, tag))
    r.update(scan_fpr(w, tag))
    rows.append(r)

df = pd.DataFrame(rows)
df.to_csv(RESULTS, index=False)

print("\n" + "=" * 82)
print("  E1.8 — النتيجة")
print("=" * 82)
with pd.option_context("display.width", 200, "display.max_columns", 40):
    print(df.to_string(index=False))
print()
print("  ما تُبلغ عنه الورقة لـYOLOv5s: mAP50 0.904 | mAP50-95 0.603 | P 0.930 | R 0.833")
print()
print("  كيف تُقرأ:")
print("   • pos_only mAP50 قريب من 0.904  →  الاستنساخ صحيح، والأساس مشترك.")
print("   • FPR مرتفع في pos_only          →  المشكلة موجودة ببروتوكولهم أيضاً،")
print("                                       لا بسبب أوزان مدرَّبة مسبقاً.")
print("   • FPR ينهار في plus_safemine     →  والحل يعمل ببروتوكولهم أيضاً.")
print("   • فرق mAP50 بين الصفين            →  ثمن الموثوقية، معروضاً لا مخفياً.")
print()
print("  حُفظ في:", RESULTS)
print("  ودرجات كل صورة في:", E18)
