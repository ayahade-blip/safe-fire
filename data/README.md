# Evaluation data: provenance and reconstruction

The raw images are not in this archive. They come from third-party corpora under
their own licences, and redistributing them here would breach those terms. What
follows is enough to rebuild every frozen set exactly.

---

## The four frozen negative sets

Frozen once, never touched again. Nothing in them appears in any training set.

| Set | n | Source | Selection rule |
|---|---|---|---|
| `hn_holdout` | 500 | Open Images V7, classes Lamp / Light bulb / Candle, **train** split | Disjoint by filename from the 3,308-image mining pool |
| `novel` | 196 | Open Images V7: Lantern, Traffic light, Street light, Christmas lights, Torch | Categories absent from every training set |
| `mined_dev` | 400 | Open-world retrieval by the mining pipeline | Held out from training from the start |
| `dfire_neg` | 1,500 | D-Fire test split, negatives only | Independent corpus, camera, geography, annotation policy |

**Total 3,396 fire-free images.**

An image counts as a false alarm if **any** predicted box on it exceeds the
operating threshold, regardless of class or location. That is the decision an
alarm system actually makes.

---

## Video

| Set | Source | Content |
|---|---|---|
| Negative | FIRESENSE, `10.5281/zenodo.836749`, CC BY 4.0 | 16 flame-negative and 9 smoke-negative clips, 14.5 min |
| Negative | KMU Fire and Smoke Database, "smoke or flame-like moving object" | 10 clips, 17.7 min. Of these, 16.6 min are outdoor haze and about 1.1 min are indoor fire-like |
| Positive | FIRESENSE | 24 clips |
| Positive | KMU, "indoor and outdoor short-distance flame" | 22 clips, 44.5 min, of which **4 are room-scale indoor fires** |

The four indoor clips are `flame2`, `flame3`, `flame4` and `flame5` in the KMU
flame archive. They are the basis of the suppression result in Table 10.

---

## Positive training data

Indoor fire and smoke, two classes: flame and smoke. For the replication in
Section 6.2 we follow the split and recipe of the reference work exactly, using
its published dataset.

---

## Reconstructing a set

1. Obtain the source corpus from its own distributor under its own licence.
2. Filter to the filenames listed in the corresponding manifest.
3. Verify each file against its checksum in the manifest.
4. Score with `code/neg_fpr.py` or the scan inside `code/E1_8_cell2_eval.py`.

---

## ⚠️ Manifests are not yet generated

The manifest files with filenames and SHA-256 checksums must be produced on the
machine that holds the frozen archives, which is the Colab environment where the
zips live. They are not in this archive yet.

**Until they are, this directory documents provenance but does not enable exact
reconstruction.** Generating them is a required step before the DOI is minted;
it is one pass over four zip files.

```python
import zipfile, hashlib, csv
rows = []
for zname, setname in (("hn_holdout_500.zip", "hn_holdout"),
                       ("novel_firelike.zip", "novel"),
                       ("mined_dev.zip", "mined_dev"),
                       ("dfire_neg_1500.zip", "dfire_neg")):
    z = zipfile.ZipFile(ROOT / "eval_suite_v2" / zname)
    for n in z.namelist():
        if n.lower().endswith((".jpg", ".jpeg", ".png")):
            rows.append([setname, n, hashlib.sha256(z.read(n)).hexdigest()])
with open("eval_suite_manifest.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["set", "filename", "sha256"])
    w.writerows(rows)
```
