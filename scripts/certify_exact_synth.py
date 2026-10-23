"""Certificación exacta de la comparación aleatorizada vs visible en delta_f con el algoritmo de DP (attacker.exact).
V(D) exacto foothold por foothold; LB del visible = cota del maestro con SCIP (results/reeval_delta_scip.jsonl).
Uso: python scripts/certify_exact_synth.py salida.jsonl [delta ...]"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, math, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, game, attacker as A

out = sys.argv[1]
which = set(sys.argv[2:]) or {"0.0", "inf"}
reev = {(str(r["delta"]), r["seed"]): r for r in map(json.loads, open(REPO + "/results/reeval_delta_scip.jsonl"))}
for r in map(json.loads, open(REPO + "/results/delta_f.jsonl")):
    if str(r["delta"]) not in which:
        continue
    delta = math.inf if r["delta"] == "inf" else float(r["delta"])
    G = sharphound.parse(adgen.scaled(r["scale"], seed=r["seed"], redundancy=r["redundancy"]), seed=r["seed"], n_starts=5)
    idx = {nd.name: i for i, nd in enumerate(G.nodes)}
    D = [(w, frozenset(idx[x] for x in names)) for w, names in r["mix"]]
    t0 = time.time(); lo = up = 0.0; per = []
    for p, s in game.default_types(G):
        Gt = G.with_start(s)
        vb, sb = A.beam(Gt, D, r["T"], delta, width=1500)
        v, seq, ub, st, info = A.exact(Gt, D, r["T"], delta, incumbent=(vb, sb), max_states=4_000_000, time_limit=600)
        lo += p * v; up += p * ub
        per.append(dict(beam=vb, exacto=v, cota=ub, estado=st, estados=info["states"], t=round(info.get("time", 0), 1)))
    rv = reev[(str(r["delta"]), r["seed"])]
    lb_vis = rv["Vvis_LB_strong"]          # con SCIP y el signo corregido
    rec = dict(delta=r["delta"], seed=r["seed"], n=r["n"], escenarios=len(D), V0=r["V0"], Vmix_beam=r["Vmix"], V_D_inf=lo, V_D_sup=up,
               LB_vis=lb_vis, Vvis_beam=rv["Vvis_best"], mejor_heuristica_beam=min(rv["base_nostart"].values()),
               gana_a_visible_certificado=up < lb_vis, gana_a_heuristica_certificado=up < min(rv["base_nostart"].values()),
               cerrado=all(x["estado"] == "Optimal" for x in per), t=time.time() - t0, por_foothold=per)
    with open(out, "a") as fh:
        fh.write(json.dumps(rec, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")
    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items() if k != "por_foothold"}, default=lambda o: o.item() if hasattr(o, "item") else str(o)), flush=True)
