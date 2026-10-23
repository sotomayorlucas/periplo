"""Certificación de la comparación aleatorizada vs visible en delta_f (δ = 0 e ∞, ~81-95 nodos, 5 footholds).
UB de V(D): por foothold, min(cota del MILP por posiciones, cota por conjuntos), ambas con SCIP.
LB del óptimo visible: cota del maestro de interdicción visible de scripts/reeval.py (las secuencias del pool son reales,
así que min_B max_pool U <= min_B V(B)); reeval.py la guardó con el signo invertido (bug corregido en game.py).
La aleatorización gana CERTIFICADAMENTE si UB(V(D)) < LB(visible).
Uso: python scripts/certify_synth.py salida.jsonl {0|inf}"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, math, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, game, attacker as A

out, which = sys.argv[1], sys.argv[2]
A.DEFAULT_SOLVER = "scip"
TL = 120
reev = {(r["delta"], r["seed"]): r for r in map(json.loads, open(REPO + "/results/reeval_delta.jsonl"))}
rows = [json.loads(l) for l in open(REPO + "/results/delta_f.jsonl")]
rows = [r for r in rows if str(r["delta"]) == ("inf" if which == "inf" else "0.0")]
for r in rows:
    delta = math.inf if r["delta"] == "inf" else float(r["delta"])
    G = sharphound.parse(adgen.scaled(r["scale"], seed=r["seed"], redundancy=r["redundancy"]), seed=r["seed"], n_starts=5)
    idx = {nd.name: i for i, nd in enumerate(G.nodes)}
    D = [(w, frozenset(idx[x] for x in names)) for w, names in r["mix"]]
    t0 = time.time()
    lo = up = up_m = up_s = 0.0; per = []
    for p, s in game.default_types(G):
        Gt = G.with_start(s)
        lb, _ = A.beam(Gt, D, r["T"], delta, width=1500)
        vm, _, bm, stm = A.milp(Gt, D, r["T"], delta, time_limit=TL)
        lb = max(lb, vm)
        bs, sts, _ = A.set_bound(Gt, D, r["T"], time_limit=TL)
        bm, _ = A.checked_bound(bm, lb, "milp"); bs, _ = A.checked_bound(bs, lb, "set")
        ub = min(bm, bs)
        per.append(dict(lb=lb, ub_milp=bm, st_milp=stm.split(":")[0], ub_set=bs, st_set=sts.split(":")[0]))
        lo += p * lb; up += p * ub; up_m += p * bm; up_s += p * bs
    rv = reev.get((r["delta"], r["seed"]), {})
    lb_vis = -rv["Vvis_LB_strong"] if rv else None
    rec = dict(delta=r["delta"], seed=r["seed"], n=r["n"], V0=r["V0"], escenarios=len(D), LB_D=lo, UB_D=up, UB_milp=up_m,
               UB_conjuntos=up_s, LB_vis=lb_vis, Vvis_beam=rv.get("Vvis_best"), gana_certificado=(lb_vis is not None and up < lb_vis),
               mejor_heuristica_beam=(min(rv["base_nostart"].values()) if rv else None), por_foothold=per, t=time.time() - t0, alertas=len(A.BOUND_ALERTS))
    with open(out, "a") as fh:
        fh.write(json.dumps(rec, default=float) + "\n")
    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items() if k != "por_foothold"}), flush=True)
