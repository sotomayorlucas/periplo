"""Redundancia alta (143 nodos): el double oracle exacto no termina en 2 h. Evaluación más barata y certificada:
V(D_viejo) exacto (la mezcla del beam: cualquier mezcla acota por arriba el valor del juego) y la colocación visible
óptima con el oráculo exacto. Si V(D_viejo) < V_vis*, aleatorizar le gana a toda colocación visible, certificado.
Escribe cada paso apenas termina. Uso: python scripts/exact_alta.py semilla salida.jsonl"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, math, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, game, attacker as A

seed, out = int(sys.argv[1]), sys.argv[2]
r = [x for x in map(json.loads, open(REPO + "/results/red_f.jsonl")) if x["redundancy"] == "alta" and x["seed"] == seed][0]
delta = math.inf if r["delta"] == "inf" else float(r["delta"])
G = sharphound.parse(adgen.scaled(r["scale"], seed=r["seed"], redundancy=r["redundancy"]), seed=r["seed"], n_starts=5)
idx = {nd.name: i for i, nd in enumerate(G.nodes)}
T, k = r["T"], r["k"]
J = lambda o: o.item() if hasattr(o, "item") else str(o)


def emit(**kw):
    kw.update(seed=seed, n=G.n, redundancy="alta", delta=r["delta"])
    with open(out, "a") as fh:
        fh.write(json.dumps(kw, default=J) + "\n")
    print(json.dumps(kw, default=J), flush=True)


t0 = time.time()
V0, V0_ub = game.best_response_value(G, [(1.0, frozenset())], T, delta, oracle="exact", certify=True)
emit(paso="V0", V0=V0, V0_ub=V0_ub, t=time.time() - t0)
D_old = [(w, frozenset(idx[x] for x in names)) for w, names in r["mix"]]
lo = up = 0.0; ok = True
for p, s in game.default_types(G):
    v, _, ub, okx = game.exact_br(G.with_start(s), D_old, T, delta, time_limit=1800)
    lo += p * v; up += p * ub; ok &= okx
emit(paso="D_viejo", V_inf=lo, V_sup=up, exacto=ok, beam=r["Vmix"], escenarios=len(D_old), t=time.time() - t0)
vis = game.visible_interdiction(G, T, delta, k, oracle="exact")
emit(paso="visible", Vvis=vis["value"], LB=vis["LB"], UB=vis["UB"], cert=vis["certified"],
     B=sorted(G.nodes[v].name.split("@")[0] for v in vis["B"]), t=time.time() - t0)
base = {nm: game.best_response_value(G, [(1.0, B)], T, delta, oracle="exact") for nm, B in game.baselines(G, k).items()}
emit(paso="heuristicas", base=base, gana_a_visible_certificado=up < vis["LB"], t=time.time() - t0)
