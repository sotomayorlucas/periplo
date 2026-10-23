"""Resumen de results/*.jsonl: fracciones del botín sin defensa (V/V0) y tiempos."""
import json, glob, sys
from collections import defaultdict
import numpy as np

KEYS = ["Vmix", "Vvis", "top_valor", "intermediacion", "chokepoint", "uniforme", "naive_vs_mix"]


def load(path_glob="results/*.jsonl"):
    rows = []
    for f in sorted(glob.glob(path_glob)):
        for line in open(f):
            r = json.loads(line)
            if "error" not in r and r.get("V0", 0) > 0:
                rows.append(r)
    return rows


def table(rows, by):
    g = defaultdict(list)
    for r in rows:
        g[tuple(r[b] for b in by)].append(r)
    out = []
    for key in sorted(g, key=lambda k: tuple(str(x) for x in k)):
        rs = g[key]
        d = {b: k for b, k in zip(by, key)}
        d["inst"] = len(rs)
        d["n"] = int(np.mean([r["n"] for r in rs]))
        for k in KEYS:
            d[k] = float(np.mean([r[k] / r["V0"] for r in rs]))
        d["mix/vis"] = float(np.mean([r["Vmix"] / r["Vvis"] if r["Vvis"] > 1e-9 else 1.0 for r in rs]))
        d["t_do"] = float(np.mean([r["t_do"] for r in rs]))
        d["t_total"] = float(np.mean([r["t_total"] for r in rs]))
        if any(r.get("Vmix_UB") is not None for r in rs):
            d["gap_cert"] = float(np.mean([(r["Vmix_UB"] - r["Vmix"]) / r["V0"] for r in rs if r.get("Vmix_UB") is not None]))
            # certificado = brecha UB - V despreciable (el flag de las corridas viejas confiaba en PuLP)
            d["certified"] = sum(1 for r in rs if r.get("Vmix_UB") is not None and r["Vmix_UB"] - r["Vmix"] <= 1e-4 * r["V0"])
        out.append(d)
    return out


if __name__ == "__main__":
    rows = load()
    for exp, by in [("escala", ["scale"]), ("delta", ["delta"]), ("redundancia", ["redundancy"]), ("cert", ["scale"])]:
        rs = [r for r in rows if r["exp"] == exp]
        if not rs:
            continue
        print(f"\n== {exp} ==")
        for d in table(rs, by):
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()})
