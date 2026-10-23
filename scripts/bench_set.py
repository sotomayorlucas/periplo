"""Cota por conjuntos (orden por índice) vs cota del MILP por posiciones, instancias delta_f con δ = 0 (~81-95 nodos).
Uso: python scripts/bench_set.py salida.jsonl"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, attacker as A

out = sys.argv[1]
milp_log = {}
for l in open(REPO + "/results/bench_cuts.jsonl"):
    if l.strip():
        r = json.loads(l); milp_log[(r["seed"], r["caso"], r["foothold"])] = r["base"]
rows = [json.loads(l) for l in open(REPO + "/results/delta_f.jsonl")]
rows = [r for r in rows if r["delta"] == 0.0][:3]
for r in rows:
    G = sharphound.parse(adgen.scaled(r["scale"], seed=r["seed"], redundancy=r["redundancy"]), seed=r["seed"], n_starts=5)
    idx = {nd.name: i for i, nd in enumerate(G.nodes)}
    D = [(w, frozenset(idx[x] for x in names)) for w, names in r["mix"]]
    for label, scen in (("V0", [(1.0, frozenset())]), ("mezcla", D)):
        for s in G.starts[:2]:
            Gt = G.with_start(s)
            fh = G.nodes[s].name.split("@")[0]
            lb, _ = A.beam(Gt, scen, r["T"], 0.0, width=1500)
            mb = milp_log.get((r["seed"], label, fh), {})
            lb = max(lb, mb.get("v", 0.0))
            t0 = time.time()
            ub, st, S = A.set_bound(Gt, scen, r["T"], time_limit=300, solver_name="scip")
            rec = dict(seed=r["seed"], n=G.n, caso=label, escenarios=len(scen), foothold=fh, LB=round(lb, 4),
                       UB_conjuntos=round(ub, 4), st=st.split(":")[0], t=round(time.time() - t0, 1),
                       UB_milp_pos=mb.get("bound"), brecha_conj=round((ub - lb) / max(lb, 1e-9), 4),
                       brecha_milp=(round((mb["bound"] - lb) / max(lb, 1e-9), 4) if mb else None))
            with open(out, "a") as fh_:
                fh_.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)
