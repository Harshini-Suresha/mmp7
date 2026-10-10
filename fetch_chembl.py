import csv, json, urllib.request, urllib.parse

TARGET = "CHEMBL4073"
base = "https://www.ebi.ac.uk/chembl/api/data/activity"
params = {
    "target_chembl_id": TARGET,
    "standard_type__in": "IC50,Ki,Kd",
    "format": "json",
    "limit": 1000,
    "offset": 0,
}

mols = {}
while True:
    url = base + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        d = json.load(r)
    for a in d["activities"]:
        smi = a.get("canonical_smiles")
        if not smi:
            continue
        p = a.get("pchembl_value")
        if p is None:
            continue
        mid = a["molecule_chembl_id"]
        if mid not in mols or float(p) > mols[mid][1]:
            mols[mid] = (smi, float(p), a.get("standard_type"),
                         a.get("standard_value"), a.get("standard_units"))
    if d["page_meta"].get("next"):
        params["offset"] += params["limit"]
    else:
        break

rows = sorted(mols.items(), key=lambda kv: -kv[1][1])
with open("ligands_mmp7.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["name", "smiles"])
    for mid, (smi, p, st, sv, su) in rows:
        w.writerow([mid, smi])

print(f"{len(rows)} unique MMP-7 actives written to ligands_mmp7.csv")
for mid, (smi, p, st, sv, su) in rows[:10]:
    print(f"  {mid}  pChEMBL={p:.1f}  {st}={sv}{su}  {smi[:60]}")
