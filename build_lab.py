#!/usr/bin/env python3
"""Build the MMP-7 Docking Lab UI.

Generates:
  docking_lab.html                     self-contained page (served by docking_server.py)
  <at1r>/index.html                    injects a floating launcher + overlay (idempotent)

The at1r index.html is a *bundled* artifact: its real content is swapped in at
runtime, wiping any static nodes. So the injection is a single window-level
script that rebuilds the UI (style + markup) after the bundle finishes
unpacking, detected by the appearance of the template's <x-dc> element.

Inputs: results.csv (from dock_mmp7.py).
Run:    python build_lab.py
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results.csv")
STANDALONE = os.path.join(HERE, "docking_lab.html")
AT1R_INDEX = "/Users/harshinisuresha/Desktop/at1r-nanobody-7T83/index.html"
COLAB_URL = ("https://colab.research.google.com/github/Harshini-Suresha/"
             "mmp7/blob/main/notebooks/MMP7_docking.ipynb")
STREAMLIT_URL = "https://mmp7-inhibition.streamlit.app/"

START = "<!-- MMP7-DOCKING-LAB:START -->"
END = "<!-- MMP7-DOCKING-LAB:END -->"


def load_rows(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("affinity_kcal_mol", "min_O_Zn_A"):
            r[k] = float(r[k]) if r[k] != "" else ""
        for k in ("n_O_within_cutoff", "zn_contact", "bidentate_like"):
            r[k] = int(r[k])
    rows.sort(key=lambda x: x["affinity_kcal_mol"])
    return rows


def stats(rows):
    aff = [r["affinity_kcal_mol"] for r in rows]
    return {
        "n": len(rows),
        "best": min(aff) if aff else 0.0,
        "zn": sum(r["zn_contact"] for r in rows),
        "bi": sum(r["bidentate_like"] for r in rows),
    }


def css():
    return """\
.mmp7-launcher{position:fixed;right:20px;bottom:20px;z-index:2147483000;cursor:pointer;
 font:600 14px/1 -apple-system,BlinkMacSystemFont,"Bricolage Grotesque",sans-serif;color:#fff;
 background:#1f6f54;border:0;border-radius:999px;padding:13px 20px;box-shadow:0 6px 24px rgba(31,111,84,.35);
 display:flex;align-items:center;gap:8px;transition:transform .15s ease,box-shadow .15s ease;}
.mmp7-launcher:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(31,111,84,.45);}
.mmp7-launcher .dot{width:8px;height:8px;border-radius:50%;background:#7be0b0;box-shadow:0 0 0 3px rgba(123,224,176,.3);}
.mmp7-overlay{position:fixed;inset:0;z-index:2147483100;background:rgba(24,22,18,.55);backdrop-filter:blur(3px);
 display:flex;align-items:center;justify-content:center;padding:24px;
 font-family:-apple-system,BlinkMacSystemFont,"Bricolage Grotesque",sans-serif;color:#1b1a17;}
.mmp7-overlay[hidden]{display:none;}
.mmp7-panel{background:#faf9f5;width:min(1040px,100%);max-height:90vh;overflow:auto;border-radius:18px;
 box-shadow:0 24px 80px rgba(0,0,0,.35);border:1px solid #e7e2d6;}
.mmp7-head{position:sticky;top:0;background:linear-gradient(180deg,#fffdf8,#faf9f5);padding:22px 26px 16px;
 border-bottom:1px solid #eee7d8;display:flex;align-items:flex-start;gap:16px;z-index:2;}
.mmp7-head h1{margin:0;font-size:22px;font-weight:700;letter-spacing:-.01em;}
.mmp7-head p{margin:5px 0 0;font-size:13px;color:#7a7466;}
.mmp7-close{margin-left:auto;background:#f0ece1;border:0;width:34px;height:34px;border-radius:9px;font-size:18px;
 line-height:1;cursor:pointer;color:#5b564b;flex:none;}
.mmp7-close:hover{background:#e6e0d1;}
.mmp7-body{padding:20px 26px 28px;}
.mmp7-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;}
.mmp7-card{background:#fff;border:1px solid #ece6d8;border-radius:12px;padding:14px 16px;}
.mmp7-card .k{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#948c7b;}
.mmp7-card .v{font-size:24px;font-weight:700;margin-top:4px;}
.mmp7-card .v small{font-size:12px;font-weight:500;color:#948c7b;margin-left:3px;}
.mmp7-run{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:18px;background:#f3f7f4;
 border:1px solid #d9e7de;border-radius:12px;padding:14px 16px;}
.mmp7-run .mmp7-runlabel{font-size:13px;color:#3c4b43;font-weight:600;margin-right:auto;}
.mmp7-btn{font:600 13px/1 inherit;border-radius:9px;padding:10px 15px;cursor:pointer;border:1px solid transparent;
 text-decoration:none;display:inline-flex;align-items:center;gap:7px;}
.mmp7-btn.primary{background:#1f6f54;color:#fff;}
.mmp7-btn.primary:hover{background:#185b45;}
.mmp7-btn.ghost{background:#fff;border-color:#d8d2c4;color:#3c382f;}
.mmp7-btn.ghost:hover{background:#f6f3ea;}
.mmp7-status{font-size:12px;color:#6f6858;flex-basis:100%;margin:0;}
.mmp7-status.err{color:#a33a2c;}
.mmp7-tablewrap{border:1px solid #ece6d8;border-radius:12px;overflow:auto;background:#fff;max-height:52vh;}
.mmp7-table{width:100%;border-collapse:collapse;font-size:13px;}
.mmp7-table th{background:#f6f3ea;text-align:left;padding:10px 12px;font-weight:600;color:#5b564b;position:sticky;
 top:0;cursor:pointer;white-space:nowrap;border-bottom:1px solid #e7e1d2;z-index:1;}
.mmp7-table th:hover{background:#efeade;}
.mmp7-table th .arw{color:#b5ad9a;font-size:10px;margin-left:3px;}
.mmp7-table td{padding:9px 12px;border-bottom:1px solid #f1ede3;white-space:nowrap;}
.mmp7-table tr:hover td{background:#fbfaf6;}
.mmp7-table .lig{font-weight:600;color:#2c5f4c;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}
.mmp7-aff{font-variant-numeric:tabular-nums;font-weight:600;}
.mmp7-pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;}
.mmp7-pill.yes{background:#e2f3ea;color:#1f6f54;}
.mmp7-pill.no{background:#f1eee7;color:#a39b89;}
.mmp7-pill.bi{background:#e7ecfb;color:#35479c;}
.mmp7-foot{margin-top:16px;font-size:12px;color:#8d8676;line-height:1.6;}
.mmp7-foot code{background:#f1ede3;padding:1px 5px;border-radius:5px;font-size:11.5px;}
@media(max-width:640px){.mmp7-stats{grid-template-columns:repeat(2,1fr);}}
.__mmp7-standalone .mmp7-launcher{display:none;}
.__mmp7-standalone .mmp7-overlay{position:static;background:transparent;backdrop-filter:none;padding:0;display:block;}
.__mmp7-standalone .mmp7-overlay[hidden]{display:block;}
.__mmp7-standalone .mmp7-panel{max-height:none;box-shadow:0 10px 40px rgba(0,0,0,.08);width:100%;}
.__mmp7-standalone .mmp7-close{display:none;}
"""


def _pill(on):
    return f'<span class="mmp7-pill {"yes" if on else "no"}">{"yes" if on else "no"}</span>'


def _rows_html(rows):
    out = []
    for i, r in enumerate(rows, 1):
        bi = ('<span class="mmp7-pill bi">bidentate</span>' if r["bidentate_like"]
              else '<span class="mmp7-pill no">&#8212;</span>')
        ozn = f'{r["min_O_Zn_A"]:.2f}' if r["min_O_Zn_A"] != "" else "&#8212;"
        out.append(
            f'<tr><td>{i}</td><td class="lig">{r["ligand"]}</td>'
            f'<td class="mmp7-aff" data-v="{r["affinity_kcal_mol"]}">{r["affinity_kcal_mol"]:.2f}</td>'
            f'<td data-v="{ozn}">{ozn}</td><td data-v="{r["n_O_within_cutoff"]}">{r["n_O_within_cutoff"]}</td>'
            f'<td data-v="{r["zn_contact"]}">{_pill(r["zn_contact"])}</td>'
            f'<td data-v="{r["bidentate_like"]}">{bi}</td></tr>')
    return "\n".join(out)


def section_html(rows, st):
    return f"""\
<button class="mmp7-launcher" id="mmp7-launcher" type="button"><span class="dot"></span> MMP-7 Docking Lab</button>
<div class="mmp7-overlay" id="mmp7-overlay" hidden>
 <div class="mmp7-panel" role="dialog" aria-modal="true" aria-label="MMP-7 Docking Lab">
  <div class="mmp7-head">
   <div><h1>MMP-7 Docking Lab</h1>
    <p>Matrilysin (PDB 1MMQ) &middot; AutoDock Vina + Meeko/RDKit &middot; Zn&#8322;&#8314; chelation geometry</p></div>
   <button class="mmp7-close" id="mmp7-close" type="button" aria-label="Close">&times;</button>
  </div>
  <div class="mmp7-body">
   <div class="mmp7-stats">
    <div class="mmp7-card"><div class="k">Ligands docked</div><div class="v">{st['n']}</div></div>
    <div class="mmp7-card"><div class="k">Best affinity</div><div class="v">{st['best']:.2f}<small>kcal/mol</small></div></div>
    <div class="mmp7-card"><div class="k">Zn&#8322;&#8314; contacts</div><div class="v">{st['zn']}<small>of {st['n']}</small></div></div>
    <div class="mmp7-card"><div class="k">Bidentate-like</div><div class="v">{st['bi']}<small>of {st['n']}</small></div></div>
   </div>
   <div class="mmp7-run">
    <span class="mmp7-runlabel">Run the pipeline</span>
     <a class="mmp7-btn primary" href="{COLAB_URL}" target="_blank" rel="noopener">&#9654; Open in Colab</a>
     <a class="mmp7-btn ghost" href="{STREAMLIT_URL}" target="_blank" rel="noopener">Streamlit lab</a>
     <button class="mmp7-btn ghost" id="mmp7-runlocal" type="button" title="Requires the local Flask backend">Run locally</button>
    <button class="mmp7-btn ghost" id="mmp7-refresh" type="button">Refresh results</button>
    <p class="mmp7-status" id="mmp7-status">Showing precomputed results.</p>
   </div>
   <div class="mmp7-tablewrap">
    <table class="mmp7-table" id="mmp7-table">
     <thead><tr>
      <th data-i="rank">#</th><th data-i="lig">Ligand</th>
      <th data-i="aff">Affinity <span class="arw">(kcal/mol)</span></th>
      <th data-i="ozn">O&#8211;Zn (&Aring;)</th><th data-i="nc">O&#8804;cutoff</th>
      <th data-i="zc">Zn contact</th><th data-i="bi">Chelation</th>
     </tr></thead>
     <tbody>
{_rows_html(rows)}
     </tbody>
    </table>
   </div>
   <div class="mmp7-foot">
    Actives retrieved from ChEMBL target <code>CHEMBL4073</code> (human matrilysin). Scores are Vina affinities
    &mdash; Vina has no explicit metal term, so treat scores and Zn-chelation as separate evidence. The
    &ldquo;Run locally&rdquo; button needs <code>python docking_server.py</code> running in the mmp7 folder.
   </div>
  </div>
 </div>
</div>"""


WIRE = r"""
function __mmp7Wire(){
  var BACKEND="http://127.0.0.1:8765";
  var ov=document.getElementById("mmp7-overlay");
  var launcher=document.getElementById("mmp7-launcher");
  var statusEl=document.getElementById("mmp7-status");
  if(!ov||!launcher||!statusEl) return;
  function setStatus(msg,err){statusEl.textContent=msg;statusEl.className="mmp7-status"+(err?" err":"");}
  function show(){ov.hidden=false;setStatus("Showing precomputed results.");probe();}
  function hide(){ov.hidden=true;}
  launcher.addEventListener("click",show);
  document.getElementById("mmp7-close").addEventListener("click",hide);
  ov.addEventListener("click",function(e){if(e.target===ov)hide();});
  document.addEventListener("keydown",function(e){if(e.key==="Escape"&&!ov.hidden)hide();});
  function probe(){
    var c=new AbortController(),t=setTimeout(function(){c.abort();},2500);
    fetch(BACKEND+"/api/health",{signal:c.signal}).then(function(r){return r.ok?r.json():Promise.reject();})
      .then(function(){setStatus("Local backend connected.");})
      .catch(function(){setStatus("Local backend not running \u2014 use Open in Colab, or start docking_server.py locally.");})
      .finally(function(){clearTimeout(t);});
  }
  window.__mmp7Probe=probe;
  document.getElementById("mmp7-runlocal").addEventListener("click",function(){
    setStatus("Starting docking run\u2026");
    fetch(BACKEND+"/api/run",{method:"POST"}).then(function(r){return r.ok?r.json():Promise.reject(r);})
      .then(function(j){setStatus("Run started ("+j.pdb+", "+j.ligands+"). This can take a while\u2026");poll();})
      .catch(function(){setStatus("Could not reach the backend. Start docking_server.py in the mmp7 folder.",true);});
  });
  function poll(){
    fetch(BACKEND+"/api/status").then(function(r){return r.json();}).then(function(j){
      if(j.running){setStatus("Docking in progress\u2026 "+(j.done||0)+" ligand(s) done.");setTimeout(poll,5000);}
      else if(j.error){setStatus("Run failed: "+j.error,true);}
      else if(j.done>0){setStatus("Run finished: "+j.done+" ligand(s). Reloading table\u2026");refresh();}
      else{setStatus("Ready.");}
    }).catch(function(){});
  }
  document.getElementById("mmp7-refresh").addEventListener("click",refresh);
  function refresh(){
    fetch(BACKEND+"/api/results").then(function(r){return r.ok?r.json():Promise.reject();})
      .then(function(j){renderRows(j.rows);setStatus("Reloaded "+j.rows.length+" results from backend.");})
      .catch(function(){setStatus("Backend not reachable for refresh.",true);});
  }
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c];});}
  function renderRows(rows){
    var tb=document.querySelector("#mmp7-table tbody");
    tb.innerHTML=rows.map(function(r,i){
      var ozn=(r.min_O_Zn_A===""||r.min_O_Zn_A==null)?"\u2014":Number(r.min_O_Zn_A).toFixed(2);
      var zc=r.zn_contact?'<span class="mmp7-pill yes">yes</span>':'<span class="mmp7-pill no">no</span>';
      var bi=r.bidentate_like?'<span class="mmp7-pill bi">bidentate</span>':'<span class="mmp7-pill no">\u2014</span>';
      return '<tr><td>'+(i+1)+'</td><td class="lig">'+esc(r.ligand)+'</td>'+
        '<td class="mmp7-aff" data-v="'+r.affinity_kcal_mol+'">'+Number(r.affinity_kcal_mol).toFixed(2)+'</td>'+
        '<td data-v="'+ozn+'">'+ozn+'</td><td data-v="'+r.n_O_within_cutoff+'">'+r.n_O_within_cutoff+'</td>'+
        '<td data-v="'+r.zn_contact+'">'+zc+'</td><td data-v="'+r.bidentate_like+'">'+bi+'</td></tr>';
    }).join("");
  }
  var table=document.getElementById("mmp7-table");
  Array.prototype.forEach.call(table.querySelectorAll("th"),function(th){
    th.addEventListener("click",function(){
      var idx=Array.prototype.indexOf.call(th.parentNode.children,th);
      var tb=table.querySelector("tbody");
      var dir=th.__asc?-1:1;th.__asc=!th.__asc;
      var rows=Array.prototype.slice.call(tb.querySelectorAll("tr"));
      rows.sort(function(a,b){
        var x=a.children[idx].getAttribute("data-v"),y=b.children[idx].getAttribute("data-v");
        var nx=parseFloat(x),ny=parseFloat(y);
        if(!isNaN(nx)&&!isNaN(ny))return dir*(nx-ny);
        return dir*String(x).localeCompare(String(y));
      });
      rows.forEach(function(r){tb.appendChild(r);});
    });
  });
}
"""


def standalone(rows, st):
    body = section_html(rows, st)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MMP-7 Docking Lab</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#faf9f5;color:#1b1a17;font-family:-apple-system,BlinkMacSystemFont,"Bricolage Grotesque",sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:40px 24px 80px}}
.hdr h1{{font-size:30px;margin:0 0 6px;letter-spacing:-.02em}}
.hdr p{{margin:0 0 26px;color:#7a7466}}
{css()}
</style></head>
<body class="__mmp7-standalone"><div class="wrap">
<div class="hdr"><h1>MMP-7 Docking Lab</h1>
<p>Matrilysin (PDB 1MMQ) &middot; AutoDock Vina + Meeko/RDKit &middot; Zn&#8322;&#8314; chelation geometry</p></div>
{body}
</div>
<script>{WIRE}
__mmp7Wire();
document.getElementById("mmp7-overlay").hidden=false;
</script>
</body></html>"""


def _js_literal(obj):
    return json.dumps(obj).replace("</", "<\\/")


def inject_index(path, rows, st):
    css_lit = _js_literal(css())
    html_lit = _js_literal(section_html(rows, st))
    script = f"""<script>
(function(){{
{ WIRE }
var CSS={css_lit};
var HTML={html_lit};
function ready(){{return !!document.querySelector("x-dc");}}
function mounted(){{return !!document.getElementById("mmp7-overlay");}}
function mount(){{
  if(mounted()||!document.body) return;
  var s=document.createElement("style"); s.id="mmp7-style"; s.textContent=CSS; (document.head||document.documentElement).appendChild(s);
  var holder=document.createElement("div"); holder.id="mmp7-mount"; holder.innerHTML=HTML; document.body.appendChild(holder);
  __mmp7Wire();
}}
if(ready()){{mount();}}
else{{var n=0,t=setInterval(function(){{if(ready()||++n>300){{clearInterval(t);mount();}}}},100);}}
}})();
</script>"""
    block = START + "\n" + script + "\n" + END
    with open(path, encoding="utf-8") as f:
        html = f.read()
    if START in html and END in html:
        html = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda m: block, html, flags=re.S)
    else:
        html = html.replace("</body>", block + "\n</body>", 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    if not os.path.exists(RESULTS):
        sys.exit(f"missing {RESULTS} - run dock_mmp7.py first")
    rows, st = load_rows(RESULTS), None
    st = stats(rows)
    with open(STANDALONE, "w", encoding="utf-8") as f:
        f.write(standalone(rows, st))
    print(f"wrote {STANDALONE} ({st['n']} ligands)")
    if os.path.exists(AT1R_INDEX):
        inject_index(AT1R_INDEX, rows, st)
        print(f"injected Docking Lab into {AT1R_INDEX}")
    else:
        print(f"(at1r index not found at {AT1R_INDEX}; skipped injection)")


if __name__ == "__main__":
    main()
