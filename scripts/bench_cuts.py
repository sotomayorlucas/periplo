"""Benchmark: MILP base vs con cortes, en instancias delta_f con δ = 0 (V0 y mezcla del DO)."""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, math, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, attacker as A

TL = float(sys.argv[1]) if len(sys.argv) > 1 else 120
rows = [json.loads(l) for l in open(REPO + "/results/delta_f.jsonl")]
rows = [r for r in rows if r["delta"] == 0.0][:3]
for r in rows:
    G = sharphound.parse(adgen.scaled(r["scale"], seed=r["seed"], redundancy=r["redundancy"]), seed=r["seed"], n_starts=5)
    idx = {nd.name: i for i, nd in enumerate(G.nodes)}
    D = [(w, frozenset(idx[x] for x in names)) for w, names in r["mix"]]
    for label, scen in (("V0", [(1.0, frozenset())]), ("mezcla", D)):
        for s in G.starts[:2]:
            Gt = G.with_start(s)
            out = {"seed": r["seed"], "n": G.n, "caso": label, "escenarios": len(scen), "foothold": G.nodes[s].name.split("@")[0]}
            for cuts in (False, True):
                t0 = time.time()
                v, seq, bd, st = A.milp(Gt, scen, r["T"], 0.0, time_limit=TL, cuts=cuts)
                out["cortes" if cuts else "base"] = dict(v=round(v, 4), bound=round(bd, 4), gap=round((bd - v) / max(v, 1e-9), 4),
                                                         t=round(time.time() - t0, 1), st=st.split(":")[0])
            print(json.dumps(out), flush=True)
