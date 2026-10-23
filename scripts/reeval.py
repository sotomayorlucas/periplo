"""Reevaluación post-auditoría: colocación visible optimizada con beam 1500 y líneas base sin footholds."""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, math, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, game

src, out = sys.argv[1], sys.argv[2]
for line in open(src):
    r = json.loads(line)
    if "error" in r:
        continue
    d = math.inf if r["delta"] == "inf" else float(r["delta"])
    G = sharphound.parse(adgen.scaled(r["scale"], seed=r["seed"], redundancy=r["redundancy"]), seed=r["seed"], n_starts=5)
    t0 = time.time()
    rv = game.visible_interdiction(G, r["T"], d, r["k"], beam_width=1500, certify=False)
    vis_s = game.best_response_value(G, [(1.0, rv["B"])], r["T"], d, beam_width=1500)
    base = {name: game.best_response_value(G, [(1.0, B)], r["T"], d, beam_width=1500)
            for name, B in game.baselines(G, r["k"]).items()}
    cands = [v for v in range(G.n) if v not in set(G.starts)]
    unif = game.best_response_value(G, game.uniform_mixture(cands, r["k"], 64, seed=r["seed"]), r["T"], d, beam_width=1500)
    rec = dict(exp=r["exp"], delta=r["delta"], redundancy=r["redundancy"], seed=r["seed"], n=r["n"], V0=r["V0"],
               Vmix=r["Vmix"], Vvis_old=r["Vvis"], Vvis_LB_old=r["Vvis_LB"], Vvis_strong=vis_s, Vvis_LB_strong=rv["LB"],
               Vvis_best=min(r["Vvis"], vis_s), base_nostart=base, unif_nostart=unif, t=time.time() - t0)
    with open(out, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(json.dumps({k: (round(v / r["V0"], 4) if k.startswith("V") and k != "V0" else v) for k, v in rec.items() if k not in ("base_nostart",)}), flush=True)
