"""Certificación posterior de V(D) en GOAD: para cada registro, reconstruye la mezcla D y, por foothold,
toma min(cota del MILP por posiciones del DO, cota por conjuntos). Uso: python scripts/goad_cert.py resultados.jsonl salida.jsonl"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import glob, json, math, sys, time
sys.path.insert(0, REPO)
from periplo import bloodhound, game, attacker as A

src, out = sys.argv[1], sys.argv[2]
recs = [json.loads(l) for l in open(src)]
adcs = recs[0].get("adcs", True)
zips = sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip"))
G = bloodhound.parse(zips, footholds="regulares", adcs=adcs)
types = game.default_types(G)
only = sys.argv[3] if len(sys.argv) > 3 else None
for r in recs:
    if only is not None and str(r["delta"]) != only:
        continue
    delta = math.inf if r["delta"] == "inf" else float(r["delta"])
    D = [(w, frozenset(B)) for w, B in r["mix_ids"]]
    ct = r.get("cert_types") or [None] * len(types)
    lo = up = up_milp = up_set = 0.0
    n_closed = 0; t0 = time.time()
    for t, (p, s) in enumerate(types):
        Gt = G.with_start(s)
        lb_t = ct[t]["v"] if ct[t] else 0.0
        ub_m = ct[t]["bound"] if ct[t] else math.inf
        if ub_m - lb_t <= 1e-4 * max(1.0, ub_m):          # ya cerrado por el MILP del DO
            ub_s = ub_m
        else:
            lb_b, _ = A.beam(Gt, D, r["T"], delta, width=1500)
            lb_t = max(lb_t, lb_b)
            ub_s, st, _ = A.set_bound(Gt, D, r["T"], time_limit=120, solver_name="scip")
            ub_s, ok = A.checked_bound(ub_s, lb_t, "set")
        ub_t = min(ub_m, ub_s)
        n_closed += int(ub_t - lb_t <= 1e-4 * max(1.0, ub_t))
        lo += p * lb_t; up += p * ub_t; up_milp += p * ub_m; up_set += p * ub_s
    rec = dict(delta=r["delta"], k=r["k"], adcs=adcs, V0=r["V0"], LB_D=lo, UB_D=up, UB_milp=up_milp, UB_conjuntos=up_set,
               LB_juego=r["LB"], footholds_cerrados=n_closed, n_footholds=len(types), t=time.time() - t0,
               brecha_D_pctV0=100 * (up - lo) / r["V0"], brecha_juego_pctV0=100 * (up - r["LB"]) / r["V0"])
    with open(out, "a") as fh:
        fh.write(json.dumps(rec, default=float) + "\n")
    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()}), flush=True)
