"""V(D) exacto en GOAD con el algoritmo de DP sobre conjuntos (attacker.exact), foothold por foothold.
Uso: python scripts/goad_exact.py resultados.jsonl salida.jsonl [k]"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import glob, json, math, sys, time
sys.path.insert(0, REPO)
from periplo import bloodhound, game, attacker as A

src, out = sys.argv[1], sys.argv[2]
only_k = int(sys.argv[3]) if len(sys.argv) > 3 else None
recs = [json.loads(l) for l in open(src)]
G = bloodhound.parse(sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip")), footholds="regulares",
                     adcs=recs[0].get("adcs", True))
types = game.default_types(G)
for r in recs:
    if only_k is not None and r["k"] != only_k:
        continue
    delta = math.inf if r["delta"] == "inf" else float(r["delta"])
    D = [(w, frozenset(B)) for w, B in r["mix_ids"]]
    t0 = time.time(); lo = up = 0.0; per = []
    for p, s in types:
        Gt = G.with_start(s)
        vb, sb = A.beam(Gt, D, r["T"], delta, width=1500)
        v, seq, ub, st, info = A.exact(Gt, D, r["T"], delta, incumbent=(vb, sb), max_states=5_000_000, time_limit=900)
        lo += p * v; up += p * ub
        per.append(dict(foothold=G.nodes[s].name.split("@")[0], beam=vb, exacto=v, cota=ub, estado=st, estados=info["states"], t=round(info.get("time", 0), 1)))
    rec = dict(delta=r["delta"], k=r["k"], adcs=r.get("adcs"), V0=r["V0"], LB_juego=r["LB"], V_D_inf=lo, V_D_sup=up,
               brecha_juego_pctV0=100 * (up - r["LB"]) / r["V0"], cerrado=all(x["estado"] == "Optimal" for x in per),
               t=time.time() - t0, por_foothold=per)
    with open(out, "a") as fh:
        fh.write(json.dumps(rec, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")
    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items() if k != "por_foothold"}, default=lambda o: o.item() if hasattr(o, "item") else str(o)), flush=True)
