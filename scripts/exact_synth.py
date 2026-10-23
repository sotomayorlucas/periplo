"""Reproduce los experimentos sintéticos (delta_f, red_f) con el oráculo EXACTO del atacante (attacker.exact).
Todo valor reportado es exacto: mezcla óptima certificada (double oracle con cota), colocación visible óptima,
heurísticas, uniforme, y la mezcla vieja (optimizada contra el beam) reevaluada exacta.
Uso: python scripts/exact_synth.py {delta_f|red_f} salida.jsonl [deltas...]"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, math, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, game, attacker as A

plan, out = sys.argv[1], sys.argv[2]
rev = "--rev" in sys.argv          # segundo trabajador: recorre el plan desde el final
only = set(a for a in sys.argv[3:] if a != "--rev")
done = set()
try:
    done = {(str(r["delta"]), r["seed"], r["redundancy"]) for r in map(json.loads, open(out))}
except FileNotFoundError:
    pass
J = lambda o: o.item() if hasattr(o, "item") else (sorted(o) if isinstance(o, (set, frozenset)) else str(o))
recs = list(map(json.loads, open(f"{REPO}/results/{plan}.jsonl")))
for r in (reversed(recs) if rev else recs):
    key = (str(r["delta"]), r["seed"], r["redundancy"])
    try:   # releer lo hecho: puede haber otro trabajador
        done = {(str(x["delta"]), x["seed"], x["redundancy"]) for x in map(json.loads, open(out))}
    except FileNotFoundError:
        pass
    if (only and str(r["delta"]) not in only) or key in done:
        continue
    delta = math.inf if r["delta"] == "inf" else float(r["delta"])
    G = sharphound.parse(adgen.scaled(r["scale"], seed=r["seed"], redundancy=r["redundancy"]), seed=r["seed"], n_starts=5)
    idx = {nd.name: i for i, nd in enumerate(G.nodes)}
    T, k = r["T"], r["k"]
    ev = lambda scen: game.best_response_value(G, scen, T, delta, oracle="exact", certify=True)
    t0 = time.time()
    V0, V0_ub = ev([(1.0, frozenset())])
    do = game.double_oracle(G, T, delta, k, oracle="exact")
    vis = game.visible_interdiction(G, T, delta, k, oracle="exact")
    Vvis, Vvis_ub = ev([(1.0, vis["B"])])
    base = {nm: ev([(1.0, B)]) for nm, B in game.baselines(G, k).items()}
    cands = [v for v in range(G.n) if v not in set(G.starts)]
    unif = ev(game.uniform_mixture(cands, k, 64, seed=r["seed"]))
    D_old = [(w, frozenset(idx[x] for x in names)) for w, names in r["mix"]]
    old = ev(D_old)
    # atacante que ignora las trampas: su mejor secuencia sin trampas, evaluada contra la mezcla óptima
    naive = 0.0
    for p, s in game.default_types(G):
        Gt = G.with_start(s)
        _, s0, _, _ = game.exact_br(Gt, [(1.0, frozenset())], T, delta)
        naive += p * A.expected_value(Gt, s0, do["D"])
    rec = dict(plan=plan, delta=r["delta"], redundancy=r["redundancy"], seed=r["seed"], n=G.n, k=k, T=T,
               V0=V0, V0_cerrado=abs(V0_ub - V0) < 1e-9 * max(1, V0),
               Vmix=do["value"], Vmix_LB=do["LB"], Vmix_UB=do["UB"], Vmix_cert=do["certified"], soporte=len(do["D"]),
               it_do=do["iterations"], t_do=do["time"],
               Vvis=Vvis, Vvis_LB=vis["LB"], Vvis_UB=vis["UB"], Vvis_cert=vis["certified"], t_vis=vis["time"],
               base={nm: v[0] for nm, v in base.items()}, uniforme=unif[0], naive=naive,
               Vmix_viejo_exacto=old[0], Vmix_viejo_beam=r["Vmix"],
               mix=[(w, sorted(G.nodes[v].name.split("@")[0] for v in B)) for w, B in do["D"]],
               vis_B=sorted(G.nodes[v].name.split("@")[0] for v in vis["B"]), t=time.time() - t0, alertas=len(A.BOUND_ALERTS))
    with open(out, "a") as fh:
        fh.write(json.dumps(rec, default=J) + "\n")
    print(json.dumps({kk: (round(v / V0, 4) if kk in ("Vmix", "Vvis", "uniforme", "naive", "Vmix_viejo_exacto", "Vmix_viejo_beam") else v)
                      for kk, v in rec.items() if kk not in ("mix", "base")}, default=J), flush=True)
