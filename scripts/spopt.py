"""Línea base: la colocación óptima contra el atacante de camino más corto de Ngo et al. (periplo/spath.py), evaluada
con el atacante de este paper (programa dinámico exacto). Mismos candidatos que la mezcla y la colocación visible
óptimas (todos los nodos; en la variante de GOAD sin nodos de dominio, todos menos esos), para no ponerla en
desventaja frente a ellas. Reanudable. Uso: python -u scripts/spopt.py [goad|synth|alta ...]"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import glob, json, math, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, bloodhound, game, spath

OUT = REPO + "/results/v2/spopt.jsonl"
groups = sys.argv[1:] or ["goad", "synth", "alta"]
done = set()
try:
    done = {json.loads(l)["task"] for l in open(OUT)}
except FileNotFoundError:
    pass


def evaluate(task, G, k, delta, cands, extra):
    if task in done:
        return
    t0 = time.time()
    B, obj, nreach = spath.sp_optimal(G, k, cands)
    if B is None:                     # ningún foothold alcanza tier 0: el modelo de camino más corto no da guía
        rec = dict(task=task, k=k, delta=("inf" if math.isinf(delta) else str(delta)), B=None, sp_hit=0.0,
                   footholds_reach=0, V=None, V_ub=None, exact=None, t=time.time() - t0, **extra)
        with open(OUT, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(task, "sin footholds que alcancen tier 0", flush=True)
        return
    i0 = len(game.DP_STATS)
    lo, hi = game.best_response_value(G, [(1.0, B)], 12.0, delta, oracle="exact", certify=True)
    exact = all(x[2] == "Optimal" for x in game.DP_STATS[i0:])
    rec = dict(task=task, k=k, delta=("inf" if math.isinf(delta) else str(delta)), B=sorted(G.nodes[v].name for v in B),
               sp_hit=obj, footholds_reach=nreach, V=lo, V_ub=hi, exact=exact, t=time.time() - t0, **extra)
    with open(OUT, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(json.dumps({kk: v for kk, v in rec.items() if kk != "B"}), rec["B"], flush=True)


if "goad" in groups:
    Z = sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip"))
    for adcs in (False, True):
        G = bloodhound.parse(Z, footholds="regulares", adcs=adcs)
        base = list(range(G.n))
        nodom = [v for v in base if G.nodes[v].role != "domain"]
        for d in ("inf", "0"):
            delta = math.inf if d == "inf" else 0.0
            for k in (1, 2, 3):
                evaluate(f"goad:{int(adcs)}:{d}:{k}", G, k, delta, base, dict(adcs=adcs))
                evaluate(f"goadnd:{int(adcs)}:{d}:{k}", G, k, delta, nodom, dict(adcs=adcs))
if "synth" in groups:
    for r in map(json.loads, open(REPO + "/results/v2/synth.jsonl")):
        G = sharphound.parse(adgen.scaled(r["scale"], seed=r["seed"], redundancy=r["redundancy"]), seed=r["seed"], n_starts=5)
        delta = math.inf if r["delta"] == "inf" else float(r["delta"])
        evaluate(r["task"], G, r["k"], delta, list(range(G.n)), {})
if "alta" in groups:
    for r in map(json.loads, open(REPO + "/results/v2/alta.jsonl")):
        G = sharphound.parse(adgen.scaled(60, seed=r["seed"], redundancy="alta"), seed=r["seed"], n_starts=5)
        evaluate(r["task"], G, r["k"], 0.0, list(range(G.n)), {})
