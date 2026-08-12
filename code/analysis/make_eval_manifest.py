# -*- coding: utf-8 -*-
"""Generate the per-image manifest for the frozen negative evaluation suite.

The archive documents where each set came from. That is provenance, not
reproducibility: it does not let anyone confirm they rebuilt the same 2,596
images. This produces the file that does, listing every filename with its
SHA-256 so a reconstruction can be checked byte for byte.

The images themselves are not redistributed, because the sets are assembled from
third-party corpora under their own licences. The manifest is the part that can
be shared.

    python make_eval_manifest.py <dir with the four zips> <output csv>
"""
from __future__ import print_function

import csv
import hashlib
import os
import sys
import zipfile

SETS = (("hn_holdout_500.zip", "hn_holdout", 500),
        ("novel_firelike.zip", "novel", 196),
        ("mined_dev.zip", "mined_dev", 400),
        ("dfire_neg_1500.zip", "dfire_neg", 1500))
IMG = (".jpg", ".jpeg", ".png", ".bmp")


def main(src, out):
    rows = []
    print("%-14s %8s %8s  %s" % ("set", "expected", "found", "status"))
    print("-" * 52)
    ok = True
    for zname, setname, expected in SETS:
        p = os.path.join(src, zname)
        if not os.path.isfile(p):
            print("%-14s %8d %8s  MISSING %s" % (setname, expected, "-", p))
            ok = False
            continue
        z = zipfile.ZipFile(p)
        names = [n for n in z.namelist() if n.lower().endswith(IMG)]
        for n in sorted(names):
            data = z.read(n)
            rows.append([setname, zname, n, len(data),
                         hashlib.sha256(data).hexdigest()])
        z.close()
        match = "ok" if len(names) == expected else "COUNT MISMATCH"
        if len(names) != expected:
            ok = False
        print("%-14s %8d %8d  %s" % (setname, expected, len(names), match))

    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["set", "archive", "filename", "bytes", "sha256"])
        w.writerows(rows)

    print()
    print("total images : %d" % len(rows))
    print("written      : %s" % out)
    # A digest of the manifest itself, so the whole suite has one identifier
    # that can be quoted in a paper and checked in one line.
    with open(out, "rb") as f:
        print("manifest sha256: %s" % hashlib.sha256(f.read()).hexdigest())
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
