#!/usr/bin/env python3
"""Export measured MMP-7 potencies (ChEMBL CHEMBL4073) for the ligands in results.csv.

Run in the same folder as results.csv:   python fetch_potency.py
Writes potency.csv with: ligand, pchembl, type, value, units  (best pChEMBL per molecule).
Then upload potency.csv here and I'll add it to the site.
"""
import csv, json, urllib.parse, urllib.request

BASE = "https://www.ebi.ac.uk/chembl/api/data/activity"
params = {"target_chembl_id": "CHEMBL4073", "standard_type__in": "IC50,Ki,Kd",
          "format": "json", "limit": 1000, "offset": 0}
best = {}
while True:
    with urllib.request.urlopen(BASE + "?" + urllib.parse.urlencode(params)) as r:
        d = json.load(r)
    for a in d["activities"]:
        p = a.get("pchembl_value")
        if p is None:
            continue
        m = a["molecule_chembl_id"]
        if m not in best or float(p) > float(best[m][0]):
            best[m] = (p, a.get("standard_type"), a.get("standard_value"), a.get("standard_units"))
    if d["page_meta"].get("next"):
        params["offset"] += params["limit"]
    else:
        break

docked = [r["ligand"] for r in csv.DictReader(open("results.csv"))]
with open("potency.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ligand", "pchembl", "type", "value", "units"])
    for m in docked:
        w.writerow([m, *best.get(m, ("", "", "", ""))])
print(f"{sum(m in best for m in docked)}/{len(docked)} docked ligands have a pChEMBL value -> potency.csv")