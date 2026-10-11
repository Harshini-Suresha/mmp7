#!/usr/bin/env python3
"""MMP-7 Docking Lab — Streamlit companion.

Deliberately NOT a copy of the website: the narrative report lives at
https://harshini-suresha.github.io/mmp7/ .

Two interfaces from this one file, switched by the MMP7_MODE env var:
  MMP7_MODE=docker  (set in the Dockerfile) → full local lab:
      Results · Analysis · Run pipeline · Poses, green lab banner.
  anything else (Streamlit Cloud default)   → hosted demo:
      Explore · Poses · Get the pipeline, blue demo banner, no run controls.
"""
import csv, glob, os, re, subprocess, sys, urllib.request, urllib.parse

import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results.csv")
POSES = os.path.join(HERE, "poses")
SCRIPT = os.path.join(HERE, "dock_mmp7.py")
CHEMBL_TARGET = "CHEMBL4073"  # human matrilysin (MMP-7)
COLAB_URL = ("https://colab.research.google.com/github/Harshini-Suresha/"
             "mmp7/blob/main/notebooks/MMP7_docking.ipynb")
SITE_URL = "https://harshini-suresha.github.io/mmp7/"
NOTEBOOK_URL = "https://github.com/Harshini-Suresha/mmp7/blob/main/notebooks/MMP7_docking.ipynb"

IS_DOCKER = os.environ.get("MMP7_MODE", "cloud").lower() == "docker"
ACCENT = "#1f6f54" if IS_DOCKER else "#2563eb"
MODE_LABEL = "Full local lab — docking engine on board" if IS_DOCKER else "Hosted demo — explore & download"
MODE_EMOJI = "🧬" if IS_DOCKER else "☁️"


def _engine():
    """True when the docking stack (Vina/RDKit/Meeko) is importable.

    Streamlit Cloud installs only requirements.txt (pure wheels); the engine
    lives in requirements-dock.txt for Docker/local runs.
    """
    import importlib.util
    return all(importlib.util.find_spec(m) for m in ("vina", "meeko", "rdkit"))


st.set_page_config(page_title="MMP-7 Docking Lab", page_icon=MODE_EMOJI, layout="wide")
st.title(f"{MODE_EMOJI} MMP-7 Docking Lab")
st.caption("Matrilysin (PDB 1MMQ) · AutoDock Vina + Meeko/RDKit · Zn²⁺ chelation geometry")
st.markdown(f"<div style='background:{ACCENT}14;border:1px solid {ACCENT}66;border-radius:10px;"
            f"padding:10px 14px;margin-bottom:6px'><b>{MODE_LABEL}</b> · "
            f"companion to the <a href='{SITE_URL}' target='_blank'>full report</a>.</div>",
            unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_results():
    if not os.path.exists(RESULTS):
        return pd.DataFrame(columns=["ligand", "affinity_kcal_mol", "min_O_Zn_A",
                                     "n_O_within_cutoff", "zn_contact", "bidentate_like"])
    return pd.read_csv(RESULTS).sort_values("affinity_kcal_mol")


@st.cache_data(show_spinner=False)
def load_potency():
    p = os.path.join(HERE, "potency.csv")
    if not os.path.exists(p):
        return pd.DataFrame(columns=["ligand", "pchembl"])
    return pd.read_csv(p)[["ligand", "pchembl"]].drop_duplicates("ligand")


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


def show_results():
    df = load_results()
    if df.empty:
        st.info("No results yet — run the pipeline in the lab.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ligands docked", len(df))
    c2.metric("Best affinity", f"{df['affinity_kcal_mol'].min():.2f} kcal/mol")
    c3.metric("Zn²⁺ contacts", int(df["zn_contact"].sum()))
    c4.metric("Bidentate-like", int(df["bidentate_like"].sum()))
    show = df.copy()
    show["ligand"] = show["ligand"].astype(str)
    st.dataframe(show.style.apply(style_row, axis=1),
                 width="stretch", hide_index=True)
    st.download_button("Download results.csv", df.to_csv(index=False),
                       file_name="results.csv", mime="text/csv")


def show_analysis():
    df = load_results()
    if df.empty:
        st.info("No results yet — run the pipeline in the lab.")
        return
    n = st.slider("Top N ligands", 5, len(df), min(20, len(df)), step=5, key="analysis_n")
    top = df.head(n)
    st.subheader("Ranked affinity")
    st.bar_chart(top.set_index("ligand")["affinity_kcal_mol"])
    st.subheader("Affinity vs closest O–Zn distance")
    d = df.copy()
    d["zn"] = d["zn_contact"].map({1: "Zn contact", 0: "no contact"})
    st.scatter_chart(d, x="min_O_Zn_A", y="affinity_kcal_mol", color="zn")
    st.caption("More negative affinity is stronger. Colour is O within 2.6 Å of the catalytic zinc.")
    pot = load_potency()
    if not pot.empty:
        m = df.merge(pot, on="ligand", how="inner")
        if not m.empty:
            st.subheader("Predicted affinity vs measured potency")
            m["chel"] = m["bidentate_like"].map({1: "bidentate-like", 0: "other"})
            st.scatter_chart(m, x="pchembl", y="affinity_kcal_mol", color="chel")
            st.caption(f"Pearson r = {m['affinity_kcal_mol'].corr(m['pchembl']):.2f} "
                       f"across {len(m)} ligands — docking rank only partly reproduces experiment.")
    st.subheader("Bidentate-like poses")
    bi = df[df["bidentate_like"] == 1]
    st.write(f"{len(bi)} of {len(df)} poses chelate the zinc with 2+ oxygens.")
    if not bi.empty:
        st.dataframe(bi[["ligand", "affinity_kcal_mol", "min_O_Zn_A"]], hide_index=True)


def show_poses():
    poses = sorted(glob.glob(os.path.join(POSES, "*_complex.pdb")))
    if not poses:
        st.info("No poses yet.")
        return
    st.write(f"{len(poses)} receptor–ligand complexes in `poses/`")
    pick = st.selectbox("Download a complex", [os.path.basename(p) for p in poses])
    with open(os.path.join(POSES, pick), "rb") as f:
        st.download_button(f"Download {pick}", f, file_name=pick)


def show_run():
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
    HAS_ENGINE = _engine()
    if not HAS_ENGINE:
        st.warning("Docking engine (Vina/RDKit/Meeko) is not installed here. "
                   "Use the Docker lab, Colab, or a local run instead.")
    opt_ligands = [f for f in os.listdir(HERE) if f.endswith(".csv")]
    r1, r2, r3, r4, r5 = st.columns([3, 1, 1, 1, 1])
    lig = r1.selectbox("Ligands file", opt_ligands, index=opt_ligands.index("ligands_mmp7_top50.csv") if "ligands_mmp7_top50.csv" in opt_ligands else 0)
    pdb = r2.text_input("PDB", "1MMQ")
    ex = r3.number_input("Exhaustiveness", 1, 32, 8)
    cf = r4.number_input("Conformers", 1, 20, 3)
    if r5.button("Run docking", type="primary", disabled=not HAS_ENGINE):
        cmd = [sys.executable, SCRIPT, "--pdb", pdb, "--ligands", lig,
               "--exhaustiveness", str(int(ex)), "--confs", str(int(cf))]
        with st.spinner("Docking in progress — this can take minutes to hours depending on panel size…"):
            p = _run_cmd(cmd)
        if p.returncode == 0:
            st.success("Run finished!")
            st.code((p.stdout or "")[-4000:])
            load_results.clear()
        else:
            st.error(f"Run failed (exit {p.returncode})")
            st.code((p.stderr or p.stdout)[-2000:])


def show_get_pipeline():
    st.write("Docking can't run on this hosted demo — pick a way to run it:")
    st.link_button("▶ Open in Colab (no setup)", COLAB_URL)
    st.link_button("Notebook file on GitHub", NOTEBOOK_URL)
    st.code("docker compose up --build  # full lab at http://localhost:8501", language="bash")
    st.code("pip install -r requirements-dock.txt\nstreamlit run docking_lab_streamlit.py",
            language="bash")


if IS_DOCKER:
    tab_results, tab_analysis, tab_run, tab_poses = st.tabs(
        ["Results", "Analysis", "Run pipeline", "Poses"])
    with tab_results:
        show_results()
    with tab_analysis:
        show_analysis()
    with tab_run:
        show_run()
    with tab_poses:
        show_poses()
else:
    tab_explore, tab_poses, tab_get = st.tabs(
        ["Explore", "Poses", "Get the pipeline"])
    with tab_explore:
        show_results()
        st.divider()
        show_analysis()
    with tab_poses:
        show_poses()
    with tab_get:
        show_get_pipeline()
