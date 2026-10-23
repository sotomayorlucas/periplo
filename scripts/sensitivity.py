"""Sensibilidad de la decisión a los supuestos r, p, q (GOAD con ADCS, δ = ∞, oráculo exacto).
- de a un parámetro por rol, factores 0,5 y 1,5;
- ruido por nodo: cada r, p, q multiplicado por un factor uniforme en [0,5; 1,5], independiente;
- esquina pesimista de la caja (r x1,5, q x0,5, p x0,5): por monotonía es el peor caso para TODA estrategia
  del defensor, así que el problema robusto en caja es el nominal en esa esquina.
Para cada perturbación: óptimo re-resuelto (mezcla y visible, exactos) y valor de las estrategias nominales.
Uso: python scripts/sensitivity.py salida.jsonl k [n_aleatorias]"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import copy, glob, json, math, random, sys, time
sys.path.insert(0, REPO)
from periplo import bloodhound, game, attacker as A

out, k = sys.argv[1], int(sys.argv[2])
n_rand = int(sys.argv[3]) if len(sys.argv) > 3 else 20
T, delta = 12.0, math.inf
G0 = bloodhound.parse(sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip")), footholds="regulares", adcs=True)
J = lambda o: o.item() if hasattr(o, "item") else (sorted(o) if isinstance(o, (set, frozenset)) else str(o))
name = lambda G, B: sorted(G.nodes[v].name.split("@")[0] for v in B)


def perturb(fr, fp, fq):
    G = copy.deepcopy(G0)
    for v, nd in enumerate(G.nodes):
        nd.r *= fr(v); nd.p *= fp(v); nd.q = min(0.95, max(1e-4, nd.q * fq(v)))
    return G


def ev(G, scen):
    return game.best_response_value(G, scen, T, delta, oracle="exact")


def solve(G):
    do = game.double_oracle(G, T, delta, k, oracle="exact")
    vis = game.visible_interdiction(G, T, delta, k, oracle="exact")
    return dict(V0=ev(G, [(1.0, frozenset())]), Vmix=do["value"], cert=do["certified"], gap=(do["UB"] - do["LB"]),
                D=do["D"], Vvis=ev(G, [(1.0, vis["B"])]), Bvis=vis["B"], vis_cert=vis["certified"])


def tv(D1, D2):
    a, b = {B: w for w, B in D1}, {B: w for w, B in D2}
    return 0.5 * sum(abs(a.get(B, 0.0) - b.get(B, 0.0)) for B in set(a) | set(b))


def record(label, kind, G, nom):
    t0 = time.time()
    res = solve(G)
    V_Dnom = ev(G, nom["D"]); V_Bnom = ev(G, [(1.0, nom["Bvis"])])
    rec = dict(k=k, tipo=kind, etiqueta=label, V0=res["V0"], Vmix=res["Vmix"], cert=res["cert"], brecha=res["gap"],
               Vvis=res["Vvis"], vis_cert=res["vis_cert"], V_Dnom=V_Dnom, V_Bvisnom=V_Bnom,
               regret_D_pctV0=100 * (V_Dnom - res["Vmix"]) / res["V0"], regret_Bvis_pctV0=100 * (V_Bnom - res["Vvis"]) / res["V0"],
               tv_D=tv(res["D"], nom["D"]), aleatorizar_gana=res["Vmix"] < res["Vvis"] - 1e-9,
               mix=[(w, name(G, B)) for w, B in res["D"]], vis_B=name(G, res["Bvis"]), t=time.time() - t0)
    with open(out, "a") as fh:
        fh.write(json.dumps(rec, default=J) + "\n")
    print(json.dumps({kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in rec.items() if kk != "mix"}, default=J), flush=True)
    return res


one = lambda v: 1.0
nom = solve(G0)
record("nominal", "nominal", G0, nom)
roles = sorted({nd.role for nd in G0.nodes})
for role in roles:
    for par in ("r", "p", "q"):
        for f in (0.5, 1.5):
            fx = lambda v, role=role, f=f: f if G0.nodes[v].role == role else 1.0
            G = perturb(fx if par == "r" else one, fx if par == "p" else one, fx if par == "q" else one)
            record(f"{role}.{par}x{f}", "un_parametro", G, nom)
rng = random.Random(7)
for i in range(n_rand):
    fac = {(v, par): rng.uniform(0.5, 1.5) for v in range(G0.n) for par in "rpq"}
    G = perturb(lambda v: fac[(v, "r")], lambda v: fac[(v, "p")], lambda v: fac[(v, "q")])
    record(f"ruido{i}", "ruido_nodo", G, nom)
corner = perturb(lambda v: 1.5, lambda v: 0.5, lambda v: 0.5)
rob = record("esquina_pesimista", "robusto", corner, nom)
# precio de la robustez: la mezcla robusta jugada en el escenario nominal
V_rob_nom = ev(G0, rob["D"])
with open(out, "a") as fh:
    fh.write(json.dumps(dict(k=k, tipo="precio_robustez", V_Drob_en_nominal=V_rob_nom, Vmix_nominal=nom["Vmix"],
                             V0_nominal=nom["V0"], precio_pctV0=100 * (V_rob_nom - nom["Vmix"]) / nom["V0"]), default=J) + "\n")
print("precio de la robustez (pct V0):", round(100 * (V_rob_nom - nom["Vmix"]) / nom["V0"], 4), flush=True)
