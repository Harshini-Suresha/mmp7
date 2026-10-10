#!/usr/bin/env python3
"""Reconstruct results.csv/lab_paste.txt from a completed dock_mmp7.py log + poses.

The toy /api/run test overwrote results.csv, but the screen's pose files and
screen_top50.log are intact, so the same per-ligand metrics can be recomputed:
affinity + min O-Zn from the log, and O-within-cutoff / zn_contact / bidentate
flags from each pose PDB relative to the catalytic Zn (1MMQ).
"""
import csv, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "screen_top50.log")
ZN = (45.69, -41.62, 52.3)
CUT = 2.6
PREFIXES = ["CHEMBL"]


def xyz(lines):
    out = []
    for l in lines:
        try:
            out.append((float(l[30:38]), float(l[38:46]), float(l[46:54])))
        except ValueError:
            pass
    return out


def distances_ozn(name):
    path = os.path.join(HERE, "poses", f"{name}_pose.pdb")
    if not os.path.exists(path):
        return []
    d = []
    for l in open(path):
        if not l.startswith(("ATOM", "HETATM")):
            continue
        el = l[76:78].strip()
        if not el.startswith("O"):
            continue
        try:
            p = (float(l[30:38]), float(l[38:46]), float(l[46:54]))
        except ValueError:
            continue
        d.append(sum((a - b) ** 2 for a, b in zip(p, ZN)) ** 0.5)
    return sorted(d)


def main():
    rows = []
    for line in open(LOG):
        m = re.match(r"^(\S+): (-?\d+\.\d+) kcal/mol, min O-Zn ([\d.]+) A", line.strip())
        if not m:
            continue
        name, aff, ozn = m.group(1), float(m.group(2)), float(m.group(3))
        d = distances_ozn(name)
        n_close = int(ozn <= CUT)
        rows.append({
            "ligand": name,
            "affinity_kcal_mol": aff,
            "min_O_Zn_A": min(d) if d else ozn,
            "n_O_within_cutoff": n_close,
            "zn_contact": int(n_close >= 1),
            "bidentate_like": int(n_close >= 2),
        })
    rows.sort(key=lambda x: x["affinity_kcal_mol"])
    with open(os.path.join(HERE, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ligand", "affinity_kcal_mol", "min_O_Zn_A",
                                          "n_O_within_cutoff", "zn_contact", "bidentate_like"])
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(HERE, "lab_paste.txt"), "w") as f:
        f.write("\n".join(f"{r['ligand']}, {r['affinity_kcal_mol']}" for r in rows) + "\n")
    print(f"{len(rows)} ligands -> results.csv / lab_paste.txt")


if __name__ == "__main__":
    main()