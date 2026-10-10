#!/usr/bin/env python3
"""MMP-7 Docking Lab — Streamlit edition.

The same screen as the website overlay + Flask backend, as a Streamlit app.

    streamlit run docking_lab_streamlit.py

Tabs: Results · Run pipeline · Poses · How it works
"""
import csv, glob, os, re, subprocess, sys, urllib.request, urllib.parse

import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results.csv")
LAB = os.path.join(HERE, "lab_paste.txt")
POSES = os.path.join(HERE, "poses")
SCRIPT = os.path.join(HERE, "dock_mmp7.py")
CHEMBL_TARGET = "CHEMBL4073"  # human matrilysin (MMP-7)

st.set_page_config(page_title="MMP-7 Docking Lab", page_icon="\U0001f9ec", layout="wide")
st.title("MMP-7 Docking Lab")
st.caption("Matrilysin (PDB 1MMQ) \u00b7 AutoDock Vina + Meeko/RDKit \u00b7 Zn\u00b2\u207a chelation geometry")


@st.cache_data(show_spinner=False)
def load_results():
    if not os.path.exists(RESULTS):
        return pd.DataFrame(columns=["ligand", "affinity_kcal_mol", "min_O_Zn_A",
                                     "n_O_within_cutoff", "zn_contact", "bidentate_like"])
    return pd.read_csv(RESULTS).sort_values("affinity_kcal_mol")


@st.cache_data(show_spinner=False)
def fetch_chembl_actives(n):
    base = "https://www.ebi.ac.uk/chembl/api/data/activity"
    params = {"target_chembl_id": CHEMBL_TARGET, "standard_type__in": "IC50,Ki,Kd",
              "format": "json", "limit": 1000, "offset": 0}
    mols = {}
    while True:
        with urllib.request.urlopen(base + "?" + urllib.parse.urlencode(params)) as r:
            d = json_load(r)
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
    return sorted(mols.items(), key=lambda kv: -kv[1][1])[:n]


def json_load(f):
    import json
    return json.load(f)


def _run_cmd(cmd):
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, env=env)


def style_row(row):
    color = "#1f6f54" if row["affinity_kcal_mol"] <= -8 else ("#33505c" if row["affinity_kcal_mol"] <= -7 else "#8d8676")
    return [f"color: {color};" for _ in row]


tab_results, tab_run, tab_poses, tab_how = st.tabs(["Results", "Run pipeline", "Poses", "How it works"])

with tab_results:
    df = load_results()
    if df.empty:
        st.info("No results yet \u2014 run the pipeline in the next tab.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ligands docked", len(df))
        c2.metric("Best affinity", f"{df['affinity_kcal_mol'].min():.2f} kcal/mol")
        c3.metric("Zn\u00b2\u207a contacts", int(df["zn_contact"].sum()))
        c4.metric("Bidentate-like", int(df["bidentate_like"].sum()))
        show = df.copy()
        show["ligand"] = show["ligand"].astype(str)
        st.dataframe(show.style.apply(style_row, axis=1),
                     width="stretch", hide_index=True)
        if os.path.exists(LAB):
            with st.expander("lab_paste.txt (copy into the Docking Lab)"):
                st.code(open(LAB).read(), language=None)

with tab_run:
    st.subheader("1. Fetch known MMP-7 actives from ChEMBL")
    f1, f2, _ = st.columns([2, 1, 3])
    n_fetch = f1.slider("Top N actives", 10, 570, 50, step=10)
    if f2.button("Fetch actives"):
        try:
            rows = fetch_chembl_actives(n_fetch)
            with open(os.path.join(HERE, f"ligands_mmp7_top{n_fetch}.csv"), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["name", "smiles"])
                for mid, (smi, _p) in rows:
                    w.writerow([mid, smi])
            st.success(f"Wrote {len(rows)} actives to ligands_mmp7_top{n_fetch}.csv")
        except Exception as e:  # noqa: BLE001
            st.error(str(e))

    st.subheader("2. Run the dock")
    opt_ligands = [f for f in os.listdir(HERE) if f.endswith(".csv")]
    r1, r2, r3, r4, r5 = st.columns([3, 1, 1, 1, 1])
    lig = r1.selectbox("Ligands file", opt_ligands, index=opt_ligands.index("ligands_mmp7_top50.csv") if "ligands_mmp7_top50.csv" in opt_ligands else 0)
    pdb = r2.text_input("PDB", "1MMQ")
    ex = r3.number_input("Exhaustiveness", 1, 32, 8)
    cf = r4.number_input("Conformers", 1, 20, 3)
    if r5.button("Run docking", type="primary"):
        cmd = [sys.executable, SCRIPT, "--pdb", pdb, "--ligands", lig,
               "--exhaustiveness", str(int(ex)), "--confs", str(int(cf))]
        with st.spinner("Docking in progress \u2014 this can take minutes to hours depending on panel size\u2026"):
            p = _run_cmd(cmd)
        if p.returncode == 0:
            st.success("Run finished!")
            st.code((p.stdout or "")[-4000:])
            load_results.clear()
        else:
            st.error(f"Run failed (exit {p.returncode})")
            st.code((p.stderr or p.stdout)[-2000:])

with tab_poses:
    poses = sorted(glob.glob(os.path.join(POSES, "*_complex.pdb")))
    if not poses:
        st.info("No poses yet.")
    else:
        st.write(f"{len(poses)} receptor\u2013ligand complexes in `poses/`")
        st.write("\n".join(os.path.basename(p) for p in poses[:200]))

with tab_how:
    st.markdown(
        f"""
- **Receptor** \u2014 PDB `1MMQ` (human matrilysin, 1.9 \u00c5, hydroxamate inhibitor); grid box centred on
  the co-crystal inhibitor; catalytic Zn expected at the site.
- **Scoring** \u2014 AutoDock Vina `vina` 1.2.5 (no explicit metal term). Use affinity **and** the O\u2013Zn
  columns as separate evidence.
- **Columns** \u2014 `min_O_Zn_A` closest ligand O to catalytic Zn; `n_O_within_cutoff` number \u2264 2.6 \u00c5;
  `zn_contact` \u22651; `bidentate_like` \u22652.
- **ChEMBL** \u2014 target `{CHEMBL_TARGET}` (human matrilysin), best pChEMBL activity per molecule.
- **Web version** \u2014 `python docking_server.py` then open http://127.0.0.1:8765/, or the
  MMP-7 Docking Lab button on the at1r site; Colab notebook in `notebooks/MMP7_docking.ipynb`.
"""
    )