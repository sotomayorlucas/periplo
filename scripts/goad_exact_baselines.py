"""Valores exactos de las columnas de comparación de GOAD (visible óptima, heurísticas, uniforme), atacante exacto.
Uso: python scripts/goad_exact_baselines.py salida.jsonl"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import glob, json, math, sys, time
sys.path.insert(0, REPO)
from periplo import bloodhound, game

out = sys.argv[1]
zips = sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip"))
J = lambda o: o.item() if hasattr(o, "item") else str(o)
for adcs in (False, True):
    G = bloodhound.parse(zips, footholds="regulares", adcs=adcs)
    cands = [v for v in range(G.n) if v not in set(G.starts)]
    for delta in (math.inf, 0.0):
        for k in (1, 2, 3):
            t0 = time.time()
            ev = lambda scen: game.best_response_value(G, scen, 12.0, delta, oracle="exact")
            V0 = ev([(1.0, frozenset())])
            vis = game.visible_interdiction(G, 12.0, delta, k, oracle="exact")
            rec = dict(adcs=adcs, delta=("inf" if math.isinf(delta) else delta), k=k, V0=V0, Vvis=ev([(1.0, vis["B"])]), vis_cert=vis["certified"],
                       vis_B=sorted(G.nodes[v].name.split("@")[0] for v in vis["B"]))
            for nm, B in game.baselines(G, k).items():
                rec[nm] = ev([(1.0, B)])
            rec["uniforme"] = ev(game.uniform_mixture(cands, k, 64, seed=0))
            rec["t"] = time.time() - t0
            with open(out, "a") as fh:
                fh.write(json.dumps(rec, default=J) + "\n")
            print(json.dumps({kk: (round(100 * v / V0, 2) if kk in ("Vvis", "top_valor", "intermediacion", "chokepoint", "uniforme") else v) for kk, v in rec.items()}, default=J), flush=True)
