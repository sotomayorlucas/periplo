"""
Experimentos de PERIPLO. Cada corrida agrega una línea JSON por instancia.

  escala       escalera de tamaños (delta = 0, redundancia media)
  delta        barrido del costo de cambio: 0 (acumulativo) ... inf (ruta tipo TSP)
  redundancia  baja / media / alta
  cert         certificación exacta con MILP en instancias chicas

Todos los valores son cotas inferiores del botín del atacante (beam search). OJO: el sesgo NO es neutro:
la mezcla y la colocación visible se optimizan contra el beam y pueden quedar en puntos donde el beam
subestima; las líneas base no. Por eso los planes *_f evalúan todo con el mismo atacante de ancho 1500
(y la auditoría recomienda además cotas MILP donde se pueda).
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
from . import adgen, sharphound, game


def run_instance(scale, seed, redundancy="media", delta=0.0, k=3, T=12.0, n_starts=5, certify=False,
                 milp_time=120.0, beam_width=150, eval_width=None, exp=""):
    """eval_width: todas las estrategias se evalúan con el mismo atacante (beam de ese ancho)."""
    ew = eval_width or beam_width
    G = sharphound.parse(adgen.scaled(scale, seed=seed, redundancy=redundancy), seed=seed, n_starts=n_starts)
    rec = dict(exp=exp, scale=scale, seed=seed, redundancy=redundancy, delta=("inf" if math.isinf(delta) else delta),
               k=k, T=T, n=G.n, m=sum(len(s) for s in G.out), footholds=len(G.starts))
    t0 = time.time()
    rec["V0"] = game.best_response_value(G, [(1.0, frozenset())], T, delta, beam_width=ew)
    r = game.double_oracle(G, T, delta, k, beam_width=beam_width, certify=certify, milp_time=milp_time,
                           verify_width=eval_width)
    rec["Vmix_do"] = r["value"]
    rec.update(Vmix=game.best_response_value(G, r["D"], T, delta, beam_width=ew), Vmix_LB=r["LB"], Vmix_UB=r["UB"], certified=r["certified"], it_do=r["iterations"],
               t_do=r["time"], n_milp=r["n_milp"], supp_def=r["support_def"], supp_att=r["support_att"])
    rec["mix"] = [(w, sorted(G.nodes[v].name for v in B)) for w, B in r["D"]]
    rec["naive_vs_mix"] = game.naive_value(G, r["D"], T, delta, beam_width=ew)
    tv = time.time()
    rv = game.visible_interdiction(G, T, delta, k, beam_width=beam_width, certify=False)
    rec.update(Vvis=game.best_response_value(G, [(1.0, rv["B"])], T, delta, beam_width=ew), Vvis_opt=rv["value"],
               Vvis_LB=rv["LB"], t_vis=time.time() - tv,
               vis_B=sorted(G.nodes[v].name for v in rv["B"]))
    for name, B in game.baselines(G, k).items():
        rec[name] = game.best_response_value(G, [(1.0, B)], T, delta, beam_width=ew)
    unif = game.uniform_mixture([v for v in range(G.n) if v not in set(G.starts)], k, n_samples=64, seed=seed)
    rec["uniforme"] = game.best_response_value(G, unif, T, delta, beam_width=ew)
    rec["t_total"] = time.time() - t0
    return rec


PLANS = {
    "escala": [dict(scale=s, seed=sd) for s in (20, 40, 80, 160, 320) for sd in ((1, 2, 3) if s <= 80 else (1, 2))],
    "delta": [dict(scale=40, seed=sd, delta=d) for d in (0.0, 1.0, 3.0, math.inf) for sd in (1, 2, 3)],
    "redundancia": [dict(scale=60, seed=sd, redundancy=rd) for rd in ("baja", "media", "alta") for sd in (1, 2, 3)],
    "cert": [dict(scale=s, seed=sd, certify=True) for s in (15, 20) for sd in (1, 2, 3)],
    # protocolo justo: DO con beam 400 + verificación 1500; todas las estrategias evaluadas con beam 1500
    "delta_f": [dict(scale=40, seed=sd, delta=d, beam_width=400, eval_width=1500)
                for d in (0.0, 1.0, 3.0, math.inf) for sd in (1, 2, 3, 4)],
    "red_f": [dict(scale=60, seed=sd, redundancy=rd, beam_width=400, eval_width=1500)
              for rd, seeds in (("baja", (1, 2)), ("media", (1, 2, 3)), ("alta", (1, 2, 3))) for sd in seeds],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", choices=list(PLANS))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or f"results/{a.plan}.jsonl"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    for cfg in PLANS[a.plan]:
        try:
            rec = run_instance(exp=a.plan, **cfg)
        except Exception as e:  # registrar y seguir
            rec = dict(exp=a.plan, error=repr(e), **{k: (str(v) if isinstance(v, float) and math.isinf(v) else v)
                                                       for k, v in cfg.items()})
        with open(out, "a") as fh:
            fh.write(json.dumps(rec, default=float) + "\n")
        print(json.dumps({k: rec.get(k) for k in ("exp", "scale", "seed", "redundancy", "delta", "n", "V0", "Vmix",
                                                    "Vvis", "t_total", "error")}, default=float), flush=True)


if __name__ == "__main__":
    main()
