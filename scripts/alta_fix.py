"""Redundancia alta: si la colocación visible quedó sin certificar porque alguna mejor respuesta exacta tocó el límite de
estados, evaluar con el programa dinámico exacto otros conjuntos candidatos (el óptimo certificado de la corrida
anterior y el argmin del maestro). La cota inferior (enumeración sobre los pools guardados) no cambia; si algún
candidato tiene valor exacto <= LB (+tol), la visible queda certificada con ese conjunto.
Uso: python scripts/alta_fix.py   (escribe results/v2/alta_fix.jsonl)"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, game

V2 = REPO + "/results/v2"
OLD = {r["seed"]: r for r in map(json.loads, open(REPO + "/results/exact_alta.jsonl")) if r["paso"] == "visible"}
for rec in map(json.loads, open(f"{V2}/alta.jsonl")):
    if rec["Vvis_cert"]:
        continue
    seed = rec["seed"]
    G = sharphound.parse(adgen.scaled(60, seed=seed, redundancy="alta"), seed=seed, n_starts=5)
    idx = {nd.name: i for i, nd in enumerate(G.nodes)}
    short = {nd.name.split("@")[0]: i for i, nd in enumerate(G.nodes)}
    types = game.default_types(G)
    pools = [[tuple(idx[x] for x in s) for s in pool] for pool in rec["pools"]]
    LB, Bm = game.visible_lb_enum(G, pools, [p for p, _ in types], list(range(G.n)), rec["k"])
    cands = [("anterior", frozenset(short[x] for x in OLD[seed]["B"])), ("argmin_maestro", Bm)]
    for name, B in cands:
        t0 = time.time()
        i0 = len(game.DP_STATS)
        ub = val = 0.0
        ok = True
        for p, s in types:
            v, _, b, okx = game.exact_br(G.with_start(s), [(1.0, B)], 12.0, 0.0)
            ub += p * b; val += p * v; ok &= okx
        out = dict(task=rec["task"], seed=seed, candidato=name, B=sorted(G.nodes[v].name for v in B), V=val, UB=ub, exact=ok,
                   LB=float(LB), cert=bool(ok and ub <= LB + 1e-4 * max(1, ub)), dp=game.dp_summary(i0), t=time.time() - t0)
        with open(f"{V2}/alta_fix.jsonl", "a") as fh:
            fh.write(json.dumps(out, default=lambda o: o.item()) + "\n")
        print(json.dumps(out, default=lambda o: o.item()), flush=True)
        if out["cert"]:
            break
