# ==========================================================================
#  E1.8 — الخلية الثالثة: mAP فقط، ودمجها مع نتائج FPR
# ==========================================================================
#  جانب FPR اكتمل في الخلية الثانية. الناقص هو mAP، وقد فشل لسبب في طريقتي:
#
#      كنت أحلّل مخرجات val.py **نصياً**، وجدول النتائج يُطبع عبر LOGGER
#      الذي يكتب في مجرى غير الذي كنت أقرأه، فلم أجد سطر "all" أبداً.
#
#  الحل ليس تخمين المجرى الصحيح ولا قراءة الاثنين — بل إلغاء تحليل النص:
#  val.py يعرّف run() التي **تُرجع الأرقام كقيَم**:
#
#      (mp, mr, map50, map5095, *losses), maps, times = val.run(...)
#
#  فتُستدعى داخل هذه العملية وتؤخذ النتيجة مباشرة. لا نص، لا مجارٍ، لا هشاشة.
#  torch.load مرقَّع أصلاً في هذه العملية من الخلية الثانية — وإن لم تكن
#  شُغّلت، تُعاد الترقيع هنا.
# ==========================================================================

import os, sys, importlib
from pathlib import Path

try:
    ROOT, D_WEIGHTS, header
except NameError:
    raise RuntimeError("شغّلي S1 قبل هذه الخلية")

E18     = ROOT / "e1_8"
YOLOV5  = Path("/content/yolov5")
IMGSZ   = 640
SEED    = 42
RESULTS = E18 / "e1_8_results.csv"

W_POS = D_WEIGHTS / ("e18__pos__s%d__best.pt" % SEED)
W_NEG = D_WEIGHTS / ("e18__combo__s%d__best.pt" % SEED)
for w in (W_POS, W_NEG):
    assert w.exists(), "الأوزان مفقودة: %s" % w

# ------------------------------------------------- الترقيع (إن لم يكن مطبَّقاً)
import functools
import numpy as np
import torch

if not getattr(torch.load, "_e18_patched", False):
    _orig = torch.load

    @functools.wraps(_orig)
    def _patched(*a, **k):
        k.setdefault("weights_only", False)
        return _orig(*a, **k)

    _patched._e18_patched = True
    torch.load = _patched
if not hasattr(np, "trapz"):
    np.trapz = np.trapezoid
print("torch.load patched :", getattr(torch.load, "_e18_patched", False))

if str(YOLOV5) not in sys.path:
    sys.path.insert(0, str(YOLOV5))

_cwd = os.getcwd()
os.chdir(str(YOLOV5))            # val.py يحلّ مسارات نسبية من جذر المستودع
try:
    v5val = importlib.import_module("val")
finally:
    os.chdir(_cwd)


def eval_map(weights, data_yaml, tag):
    """mAP بقيَم مُرجَعة، لا بتحليل نص."""
    _here = os.getcwd()
    os.chdir(str(YOLOV5))
    try:
        res, maps, _t = v5val.run(
            data=str(data_yaml), weights=str(weights), batch_size=16,
            imgsz=IMGSZ, task="test", device=0, plots=False, verbose=True,
            project=str(YOLOV5 / "runs" / "val"), name="v_" + tag, exist_ok=True)
    finally:
        os.chdir(_here)
    mp, mr, map50, map5095 = float(res[0]), float(res[1]), float(res[2]), float(res[3])
    out = {"P": round(mp, 4), "R": round(mr, 4),
           "mAP50": round(map50, 4), "mAP5095": round(map5095, 4)}
    # maps = mAP50-95 لكل صنف، بترتيب names
    for i, nm in enumerate(("flame", "smoke")):
        if i < len(maps):
            out["AP5095_" + nm] = round(float(maps[i]), 4)
    print("  %-14s P %.4f  R %.4f  mAP50 %.4f  mAP50-95 %.4f"
          % (tag, mp, mr, map50, map5095))
    return out


import pandas as pd

df = pd.read_csv(RESULTS) if RESULTS.exists() else pd.DataFrame()

new = {}
for tag, w, dy in (("pos_only",      W_POS, E18 / "ds_pos"   / "data.yaml"),
                   ("plus_safemine", W_NEG, E18 / "ds_combo" / "data.yaml")):
    header("mAP: " + tag, "-")
    new[tag] = eval_map(w, dy, tag)

for tag, vals in new.items():
    for k, v in vals.items():
        df.loc[df["run"] == tag, k] = v
df.to_csv(RESULTS, index=False)

# ----------------------------------------------------------------- العرض
cols_map = [c for c in ("run", "P", "R", "mAP50", "mAP5095",
                        "AP5095_flame", "AP5095_smoke") if c in df.columns]
cols_fpr = ["run"] + [c for c in df.columns if c.startswith("FPR50_")]

print("\n" + "=" * 88)
print("  E1.8 — النتيجة الكاملة   (YOLOv5s، من الصفر، بروتوكول YOLO-HF)")
print("=" * 88)
print("\n  الدقة")
print(df[cols_map].to_string(index=False))
print("\n  الإنذارات الكاذبة عند conf 0.50  (٪)")
print(df[cols_fpr].to_string(index=False))

if len(df) == 2 and "mAP50" in df.columns:
    a = df[df["run"] == "pos_only"].iloc[0]
    b = df[df["run"] == "plus_safemine"].iloc[0]
    print("\n  " + "-" * 84)
    print("  الاستنساخ : mAP50 %.4f مقابل %.3f المُبلَّغ في الورقة  (فرق %+.4f)"
          % (a["mAP50"], 0.904, a["mAP50"] - 0.904))
    print("  ثمن السوالب: mAP50 %.4f -> %.4f  (%+.4f)"
          % (a["mAP50"], b["mAP50"], b["mAP50"] - a["mAP50"]))
    for s in ("hn_holdout", "novel", "mined_dev", "dfire_neg"):
        k = "FPR50_" + s
        if k in df.columns and a[k] > 0:
            print("  %-11s : %.2f %% -> %.2f %%   (%.2fx أقل)"
                  % (s, a[k], b[k], a[k] / b[k] if b[k] > 0 else float("inf")))
    print("  " + "-" * 84)
print("\n  حُفظ في:", RESULTS)
