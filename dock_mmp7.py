#!/usr/bin/env python3
"""
MMP-7 (matrilysin) docking pipeline: AutoDock Vina + RDKit/Meeko + Zn2+ geometry check.

SETUP (once)
    conda create -n dock python=3.11 -y && conda activate dock
    conda install -c conda-forge openbabel -y
    pip install rdkit meeko vina numpy

INPUT   ligands.csv with a header and two columns:  name,smiles
        e.g.  acetohydroxamic_acid,CC(=O)NO        (format example only; use YOUR panel)

RUN     python dock_mmp7.py --pdb 1MMQ --ligands ligands.csv

OUTPUT  results.csv    ligand, best Vina affinity (kcal/mol), O-Zn distances, Zn-contact flags
        lab_paste.txt  "name, score" lines to paste into the website's Docking Lab
        poses/         best pose + receptor-ligand complex PDB per ligand (feed to PyMOL / LigPlot / PLIP)

NOTES
  * 1MMQ = human matrilysin with a hydroxamate inhibitor (Browner et al., Biochemistry 1995, 1.9 A).
    The co-crystallised inhibitor is used to centre the grid box (override with --center X Y Z).
  * Vina's default scoring has no explicit metal-coordination term. The O-Zn distance columns exist so you
    can check chelation geometry yourself; treat scores and chelation as separate evidence.
  * Interaction counts (H-bonds, hydrophobic, salt bridges) come from PLIP/LigPlot on poses/*_complex.pdb.
"""
import argparse, csv, os, subprocess, sys, urllib.request
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
from meeko import MoleculePreparation, PDBQTWriterLegacy
from vina import Vina

SKIP = {"HOH", "WAT", "ZN", "CA", "NA", "CL", "SO4", "GOL", "EDO", "ACT", "DMS"}


def fetch(pdb, out):
    urllib.request.urlretrieve(f"https://files.rcsb.org/download/{pdb.upper()}.pdb", out)


def split_pdb(path, chain):
    prot, ions, het = [], [], []
    for l in open(path):
        rec = l[:6].strip()
        if rec not in ("ATOM", "HETATM") or l[21] != chain or l[16] not in " A":
            continue
        res = l[17:20].strip()
        if rec == "ATOM":
            prot.append(l)
        elif res in ("ZN", "CA"):
            ions.append(l)
        elif res not in SKIP:
            het.append(l)
    return prot, ions, het


def xyz(lines):
    return np.array([[float(l[30:38]), float(l[38:46]), float(l[46:54])] for l in lines])


def prep_ligand(smiles, n_conf):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("invalid SMILES")
    mol = Chem.AddHs(mol)
    cids = list(AllChem.EmbedMultipleConfs(mol, numConfs=n_conf, randomSeed=42))
    if not cids:
        raise ValueError("conformer embedding failed")
    res = AllChem.MMFFOptimizeMoleculeConfs(mol, maxIters=2000)
    best = cids[min(range(len(cids)), key=lambda i: res[i][1])]
    m = Chem.Mol(mol)
    m.RemoveAllConformers()
    m.AddConformer(mol.GetConformer(best), assignId=True)
    setups = MoleculePreparation().prepare(m)
    pdbqt, ok, err = PDBQTWriterLegacy.write_string(setups[0])
    if not ok:
        raise ValueError(err)
    return pdbqt


def pose_atoms(pdbqt):
    out = []
    for l in pdbqt.splitlines():
        if l.startswith(("ATOM", "HETATM")):
            out.append((l[77:79].strip(), np.array([float(l[30:38]), float(l[38:46]), float(l[46:54])])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdb", default="1MMQ")
    ap.add_argument("--chain", default="A")
    ap.add_argument("--ligands", required=True)
    ap.add_argument("--center", nargs=3, type=float)
    ap.add_argument("--box", type=float, default=22.0, help="cubic box edge in A")
    ap.add_argument("--exhaustiveness", type=int, default=16)
    ap.add_argument("--poses", type=int, default=9)
    ap.add_argument("--confs", type=int, default=10, help="conformers generated per ligand")
    ap.add_argument("--zn-cutoff", type=float, default=2.6, help="O-Zn distance counted as contact (A)")
    a = ap.parse_args()
    os.makedirs("poses", exist_ok=True)

    raw = f"{a.pdb}.pdb"
    if not os.path.exists(raw):
        fetch(a.pdb, raw)
    prot, ions, het = split_pdb(raw, a.chain)
    if a.center:
        centre = np.array(a.center)
    elif het:
        centre = xyz(het).mean(axis=0)
    else:
        sys.exit("No co-crystallised ligand found; pass --center X Y Z")
    zns = [l for l in ions if l[17:20].strip() == "ZN"]
    if not zns:
        sys.exit("No Zn2+ found in the chosen chain")
    zn = min(xyz(zns), key=lambda p: np.linalg.norm(p - centre))  # catalytic Zn = nearest to the site
    print(f"Box centre {np.round(centre, 2)}; catalytic Zn at {np.round(zn, 2)}")

    clean = f"{a.pdb}_clean.pdb"
    open(clean, "w").write("".join(prot + ions))
    subprocess.run(["obabel", clean, "-O", "receptor.pdbqt", "-xr", "-p", "7.4"], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    v = Vina(sf_name="vina", seed=42)
    v.set_receptor("receptor.pdbqt")
    v.compute_vina_maps(center=centre.tolist(), box_size=[a.box] * 3)

    rows = []
    for r in csv.DictReader(open(a.ligands)):
        name, smi = r["name"].strip(), r["smiles"].strip()
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        try:
            v.set_ligand_from_string(prep_ligand(smi, a.confs))
            v.dock(exhaustiveness=a.exhaustiveness, n_poses=a.poses)
            score = float(v.energies(n_poses=1)[0][0])
            pose = v.poses(n_poses=1)
        except Exception as e:
            print(f"SKIP {name}: {e}")
            continue
        d = sorted(np.linalg.norm(p - zn) for el, p in pose_atoms(pose) if el.startswith("O"))
        n_close = sum(x <= a.zn_cutoff for x in d)
        open(f"poses/{safe}_pose.pdbqt", "w").write(pose)
        subprocess.run(["obabel", f"poses/{safe}_pose.pdbqt", "-O", f"poses/{safe}_pose.pdb"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        lig = [l.replace("ATOM  ", "HETATM", 1) for l in open(f"poses/{safe}_pose.pdb")
               if l.startswith(("ATOM", "HETATM"))]
        open(f"poses/{safe}_complex.pdb", "w").write("".join(prot + ions) + "".join(lig) + "END\n")
        rows.append({"ligand": name, "affinity_kcal_mol": round(score, 2),
                     "min_O_Zn_A": round(d[0], 2) if d else "", "n_O_within_cutoff": n_close,
                     "zn_contact": int(n_close >= 1), "bidentate_like": int(n_close >= 2)})
        print(f"{name}: {score:.2f} kcal/mol, min O-Zn {rows[-1]['min_O_Zn_A']} A")

    rows.sort(key=lambda x: x["affinity_kcal_mol"])
    with open("results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    open("lab_paste.txt", "w").write("\n".join(f"{x['ligand']}, {x['affinity_kcal_mol']}" for x in rows) + "\n")
    print("Wrote results.csv, lab_paste.txt and poses/")


if __name__ == "__main__":
    main()
