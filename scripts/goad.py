"""PERIPLO sobre la colección real de GOADv2 (SharpHound 2.3.3, repo m4lwhere/Bloodhound-CE-Sample-Data).
Uso: python scripts/goad.py salida.jsonl [adcs|noadcs] [scip|highs|cbc] [0|inf] [1,2,3]
Las cotas que certifican salen del solver elegido (SCIP por defecto; ver results/highs_bug)."""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import glob, json, math, sys, time
sys.path.insert(0, REPO)
from periplo import bloodhound, game, attacker as A

out = sys.argv[1]
adcs = not (len(sys.argv) > 2 and sys.argv[2] == "noadcs")
A.DEFAULT_SOLVER = sys.argv[3] if len(sys.argv) > 3 else "scip"
zips = sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip"))
G = bloodhound.parse(zips, footholds="regulares", adcs=adcs)
T = 12.0
name = lambda B: sorted(G.nodes[v].name.split("@")[0] for v in B)
types = game.default_types(G)
DELTAS = {"0": [0.0], "inf": [math.inf]}.get(sys.argv[4] if len(sys.argv) > 4 else "", [0.0, math.inf])
KS = [int(x) for x in sys.argv[5].split(",")] if len(sys.argv) > 5 else [1, 2, 3]
for delta in DELTAS:
    for k in KS:
        t0 = time.time()
        rec = dict(delta=("inf" if math.isinf(delta) else delta), k=k, T=T, n=G.n, footholds=len(G.starts),
                   adcs=adcs, solver=A.DEFAULT_SOLVER)
        rec["V0"] = game.best_response_value(G, [(1.0, frozenset())], T, delta, beam_width=1500)
        r = game.double_oracle(G, T, delta, k, beam_width=400, verify_width=1500, certify=True, milp_time=60)
        D = r["D"]
        rec.update(Vmix=game.best_response_value(G, D, T, delta, beam_width=1500), Vmix_do=r["value"],
                   LB=r["LB"], UB=r["UB"], certified=r["certified"], t_do=r["time"],
                   mix=[(round(w, 4), name(B)) for w, B in D], mix_ids=[(w, sorted(B)) for w, B in D])
        rec["cert_types"] = r["cert_types"]
        # estrategia mixta del atacante (para poder reverificar la cota inferior del juego)
        rec["sigma"] = [[(float(w), list(map(int, seq))) for w, seq in st if w > 1e-9] for st in r["sigma"]]
        rv = game.visible_interdiction(G, T, delta, k, beam_width=1500, certify=False)
        rec.update(Vvis=game.best_response_value(G, [(1.0, rv["B"])], T, delta, beam_width=1500), vis_B=name(rv["B"]))
        for nm, B in game.baselines(G, k).items():
            rec[nm] = game.best_response_value(G, [(1.0, B)], T, delta, beam_width=1500)
            rec[nm + "_B"] = name(B)
        cands = [v for v in range(G.n) if v not in set(G.starts)]
        rec["uniforme"] = game.best_response_value(G, game.uniform_mixture(cands, k, 64, seed=0), T, delta, beam_width=1500)
        rec["naive_vs_mix"] = game.naive_value(G, D, T, delta, beam_width=1500)
        rec["t_total"] = time.time() - t0
        rec["bound_alerts"] = len(A.BOUND_ALERTS)
        with open(out, "a") as fh:
            fh.write(json.dumps(rec, default=float) + "\n")
        rel = ("Vmix", "Vvis", "LB", "UB", "top_valor", "intermediacion", "chokepoint", "uniforme", "naive_vs_mix")
        print(json.dumps({kk: (round(v / rec["V0"], 4) if kk in rel and v is not None else v)
                          for kk, v in rec.items() if kk not in ("mix", "mix_ids", "cert_types")}, default=float), flush=True)
