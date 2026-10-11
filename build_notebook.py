#!/usr/bin/env python3
"""Generate notebooks/MMP7_docking.ipynb (Colab-ready) inside the at1r repo.

Embeds dock_mmp7.py + a ChEMBL fetcher so the notebook is self-contained.
Run: python3 build_notebook.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "dock_mmp7.py")
OUT = os.path.join(HERE, "notebooks", "MMP7_docking.ipynb")

DOCK = open(SCRIPT).read()

FETCH = r'''
import csv, json, urllib.request, urllib.parse

TARGET = "CHEMBL4073"          # human matrilysin (MMP-7)
N = 50                         # dock the N most potent known actives
base = "https://www.ebi.ac.uk/chembl/api/data/activity"
params = {"target_chembl_id": TARGET, "standard_type__in": "IC50,Ki,Kd",
          "format": "json", "limit": 1000, "offset": 0}

mols = {}
while True:
    url = base + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        d = json.load(r)
    for a in d["activities"]:
        smi, p = a.get("canonical_smiles"), a.get("pchembl_value")
        if smi and p is not None:
            mid = a["molecule_chembl_id"]
            if mid not in mols or float(p) > mols[mid][1]:
                mols[mid] = (smi, float(p))
    if d["page_meta"].get("next"):
        params["offset"] += params["limit"]
    else:
        break

rows = sorted(mols.items(), key=lambda kv: -kv[1][1])[:N]
with open("ligands_mmp7.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["name", "smiles"])
    for mid, (smi, p) in rows:
        w.writerow([mid, smi])
print(f"{len(rows)} MMP-7 actives -> ligands_mmp7.csv")
for mid, (smi, p) in rows[:5]:
    print(" ", mid, "pChEMBL=%.1f" % p, smi[:55])
'''

def cell(src, code=True):
    return {"cell_type": "code" if code else "markdown",
            "metadata": {}, "execution_count": None,
            "outputs": [],
            "source": src.splitlines(keepends=True)}

cells = [
    cell("""# MMP-7 (Matrilysin) Docking Lab — run in Colab

Screens known MMP-7 inhibitors (ChEMBL target **CHEMBL4073**) against the
catalytic site of human matrilysin (**PDB 1MMQ**, 1.9 Å, hydroxamate inhibitor)
with **AutoDock Vina**, checking O→Zn chelation geometry.

Repo: https://github.com/Harshini-Suresha/mmp7
Pipeline source: `dock_mmp7.py`

**Run-order note:** the first two cells set up the environment. Cell 1 restarts
the Colab runtime once — just re-run the notebook (or press "run all") after it
finishes, then cells 2+ run normally.

""", code=False),
    cell("""# Cell 1 — install condacolab (restarts the runtime once)
!pip install -q condacolab
import condacolab
condacolab.install()"""),
    cell("""# Cell 2 — install docking stack (conda-forge)
import condacolab
condacolab.check()  # runs after the cell-1 restart
!mamba install -q -c conda-forge openbabel vina rdkit meeko numpy scipy gemmi -y"""),
    cell("# Cell 3 \u2014 write the docking pipeline\n"
         'with open("dock_mmp7.py", "w") as f:\n'
         "    f.write(r'''" + DOCK + "''')\n"),
    cell("""# Cell 4 — fetch known MMP-7 actives from ChEMBL""" + FETCH, ),
    cell("""# Cell 5 — run the docking screen (this takes a while)
import os, subprocess, time
os.makedirs("poses", exist_ok=True)

cmd = ["python", "dock_mmp7.py", "--pdb", "1MMQ",
       "--ligands", "ligands_mmp7.csv", "--exhaustiveness", "8", "--confs", "3"]
t0 = time.time()
p = subprocess.run(cmd, capture_output=True, text=True)
print(p.stdout[-4000:])
if p.stderr: print("STDERR:", p.stderr[-2000:])
print("\\nFinished in %.1f min" % ((time.time() - t0) / 60))"""),
    cell("""# Cell 6 — ranked results
import csv
rows = list(csv.DictReader(open("results.csv")))
print(f"{'Ligand':<22} {'Affinity':>9} {'O-Zn(A)':>8} {'Zn-cont':>7} {'Bidentate':>9}")
for r in rows:
    print(f"{r['ligand']:<22} {float(r['affinity_kcal_mol']):>8.2f} "
          f"{r['min_O_Zn_A']:>8} {r['zn_contact']:>7} {r['bidentate_like']:>9}")"""),
    cell("""# Cell 7 — download results
from google.colab import files
files.download("results.csv")
files.download("lab_paste.txt")   # paste these "name, score" lines into the Docking Lab
# Poses are in ./poses/ (feed *_complex.pdb to PyMOL / LigPlot / PLIP)"""),
]

nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"colab": {"name": "MMP7_docking.ipynb", "provenance": []},
                   "kernelspec": {"display_name": "Python 3", "name": "python3"},
                   "language_info": {"name": "python"}},
      "cells": cells}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump(nb, f, indent=1)
print(f"wrote {OUT} ({len(cells)} cells)")