"""GOADv2 sin trampas sobre los nodos abstractos de dominio ("domain compromised"): todas las estrategias (mezcla,
visible, heurísticas, uniforme) eligen solo entre nodos concretos (usuarios y computadoras). Certificados sin MILP,
guardados como en run_v2.py (con el campo cands para que verify_certs.py enumere sobre el mismo conjunto).
Uso: python -u scripts/goad_nodomain.py"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import glob, json, math, sys, time
sys.path.insert(0, REPO)
from periplo import bloodhound, game

OUT = REPO + "/results/v2/goad_nodomain.jsonl"
GOAD = sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip"))
J = lambda o: o.item() if hasattr(o, "item") else (sorted(o) if isinstance(o, (set, frozenset)) else str(o))
done = set()
try:
    done = {json.loads(l)["task"] for l in open(OUT)}
except FileNotFoundError:
    pass
nm = lambda G, B: sorted(G.nodes[v].name for v in B)
seqn = lambda G, s: [G.nodes[v].name for v in s]
T = 12.0
for adcs in (False, True):
    G = bloodhound.parse(GOAD, footholds="regulares", adcs=adcs)
    cands = [v for v in range(G.n) if G.nodes[v].role != "domain"]
    base_c = [v for v in cands if v not in set(G.starts)]
    for d in ("inf", "0"):
        delta = math.inf if d == "inf" else 0.0
        for k in (1, 2, 3):
            task = f"goadnd:{int(adcs)}:{d}:{k}"
            if task in done:
                continue
            t0, c0 = time.time(), time.process_time()
            V0, _ = game.best_response_value(G, [(1.0, frozenset())], T, delta, oracle="exact", certify=True)
            do = game.double_oracle(G, T, delta, k, cands=cands, oracle="exact")
            vis = game.visible_interdiction(G, T, delta, k, cands=cands, oracle="exact")
            base = {}
            for name, B in game.baselines(G, k, cands=base_c).items():
                v, ub = game.best_response_value(G, [(1.0, B)], T, delta, oracle="exact", certify=True)
                base[name] = dict(v=v, ub=ub, B=nm(G, B))
            uv, _ = game.best_response_value(G, game.uniform_mixture(base_c, k, 64, seed=0), T, delta, oracle="exact", certify=True)
            rec = dict(task=task, adcs=adcs, delta=d, k=k, T=T, n=G.n, V0=V0, cands=[G.nodes[v].name for v in cands],
                       Vmix=do["UB"], Vmix_LB=do["LB"], Vmix_UB=do["UB"], Vmix_cert=do["certified"],
                       D=[(w, nm(G, B)) for w, B in do["D"]],
                       sigma=[[(float(pr), seqn(G, s)) for pr, s in sig if pr > 1e-12] for sig in do["sigma"]],
                       types=[(p, G.nodes[s].name) for p, s in game.default_types(G)],
                       Vvis=vis["UB"], Vvis_LB=vis["LB"], Vvis_UB=vis["UB"], Vvis_cert=vis["certified"], vis_B=nm(G, vis["B"]),
                       pools=[[seqn(G, s) for s in pool] for pool in vis["pools"]], base=base, uniforme=uv,
                       t=time.time() - t0, cpu=time.process_time() - c0)
            with open(OUT, "a") as fh:
                fh.write(json.dumps(rec, default=J) + "\n")
            P = lambda x: round(100 * x / V0, 2)
            print(task, "mix", P(rec["Vmix"]), "vis", P(rec["Vvis"]), rec["Vmix_cert"], rec["Vvis_cert"],
                  {kk: P(b["v"]) for kk, b in base.items()}, rec["vis_B"], flush=True)
