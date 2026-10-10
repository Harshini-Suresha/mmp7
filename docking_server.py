#!/usr/bin/env python3
"""Local backend for the MMP-7 Docking Lab.

Serves docking_lab.html and a tiny JSON API so the "Run locally" button in the
web UI (both the standalone page and the injected overlay on the at1r site) can
drive dock_mmp7.py.

    python docking_server.py                 # http://127.0.0.1:8765
    python docking_server.py --port 5000

Endpoints:
    GET  /              the Docking Lab page
    GET  /api/health    {ok, python, obabel}
    GET  /api/results   {rows:[...]} from results.csv
    GET  /api/status    {running, done, error, log_tail}
    POST /api/run       start a docking run (JSON: pdb, ligands, exhaustiveness, confs)
"""
import argparse, csv, glob, json, os, subprocess, sys, threading

from flask import Flask, Response, jsonify, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results.csv")
POSES = os.path.join(HERE, "poses")
SCRIPT = os.path.join(HERE, "dock_mmp7.py")
LOG = os.path.join(HERE, "server_run.log")

app = Flask(__name__)
_state = {"proc": None, "error": None}


def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.after_request
def _after(resp):
    return _cors(resp)


@app.route("/api/<path:_any>", methods=["OPTIONS"])
def _preflight(_any):
    return _cors(Response(status=204))


def _read_results():
    if not os.path.exists(RESULTS):
        return []
    with open(RESULTS, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("affinity_kcal_mol", "min_O_Zn_A"):
            try:
                r[k] = float(r[k])
            except (KeyError, ValueError):
                pass
        for k in ("n_O_within_cutoff", "zn_contact", "bidentate_like"):
            try:
                r[k] = int(r[k])
            except (KeyError, ValueError):
                pass
    rows.sort(key=lambda x: x.get("affinity_kcal_mol", 0))
    return rows


def _done_count():
    return len(glob.glob(os.path.join(POSES, "*_complex.pdb")))


@app.route("/")
def index():
    return send_from_directory(HERE, "docking_lab.html")


@app.route("/api/health")
def health():
    from shutil import which
    return jsonify(ok=True, python=sys.executable, obabel=which("obabel") or None)


@app.route("/api/results")
def results():
    return jsonify(rows=_read_results())


@app.route("/api/status")
def status():
    proc = _state["proc"]
    running = bool(proc and proc.poll() is None)
    log_tail = ""
    if os.path.exists(LOG):
        with open(LOG, errors="replace") as f:
            log_tail = "".join(f.readlines()[-8:])
    return jsonify(running=running, done=_done_count(), error=_state["error"], log_tail=log_tail)


@app.route("/api/run", methods=["POST"])
def run():
    proc = _state["proc"]
    if proc and proc.poll() is None:
        return jsonify(started=False, already_running=True,
                       pdb=_state.get("pdb", ""), ligands=_state.get("ligands", "")), 409
    body = request.get_json(silent=True) or {}
    pdb = str(body.get("pdb", "1MMQ"))
    ligands = str(body.get("ligands", "ligands_mmp7_top50.csv"))
    exh = str(body.get("exhaustiveness", 4))
    confs = str(body.get("confs", 1))
    if not os.path.exists(os.path.join(HERE, ligands)):
        return jsonify(started=False, error=f"ligand file not found: {ligands}"), 400
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [sys.executable, SCRIPT, "--pdb", pdb, "--ligands", ligands,
           "--exhaustiveness", exh, "--confs", confs]
    _state["error"] = None
    _state["pdb"], _state["ligands"] = pdb, ligands
    logf = open(LOG, "w")
    _state["proc"] = subprocess.Popen(cmd, cwd=HERE, stdout=logf, stderr=subprocess.STDOUT, env=env)

    def _watch():
        _state["proc"].wait()
        logf.close()
        if _state["proc"].returncode != 0:
            _state["error"] = f"exit code {_state['proc'].returncode}"
    threading.Thread(target=_watch, daemon=True).start()
    return jsonify(started=True, pdb=pdb, ligands=ligands)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    print(f"MMP-7 Docking Lab backend -> http://{a.host}:{a.port}/")
    app.run(host=a.host, port=a.port, threaded=True)


if __name__ == "__main__":
    main()
