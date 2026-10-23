"""Re-verificación independiente de los certificados guardados por scripts/run_v2.py, sin MILP ni LP:
- juego aleatorizado: LB = min_B sum_t p_t E_{sigma_t} U(pi, B) por enumeración de todos los conjuntos de k trampas
  (cualquier sigma da una cota inferior válida de V*); UB = sum_t p_t max_pi E_D U(pi, B) con el programa dinámico
  exacto (valor de la D guardada).
- colocación visible: LB = min_B sum_t p_t max_{pi en pool_t} U(pi, B) por enumeración; UB = valor exacto de B*.
Uso: python scripts/verify_certs.py [--ub] [goad|synth|sens ...]   (sin --ub solo recalcula las cotas inferiores)"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import copy, glob, json, math, random, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, bloodhound, game

ROOT = REPO + "/results/v2"
do_ub = "--ub" in sys.argv
groups = [a for a in sys.argv[1:] if not a.startswith("--")] or ["goad", "synth", "sens", "alta", "altado"]
GOAD = sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip"))
TOL = 1e-6


def check(G, rec, T, delta, k, label):
    idx = {nd.name: i for i, nd in enumerate(G.nodes)}
    types = [(p, idx[s]) for p, s in rec["types"]] if "types" in rec else game.default_types(G)
    probs = [p for p, _ in types]
    cands = [idx[x] for x in rec["cands"]] if "cands" in rec else list(range(G.n))
    out = dict(label=label)
    # juego aleatorizado
    if "sigma" in rec:
        seqs, ws = [], []
        for p, sig in zip(probs, rec["sigma"]):
            tot = sum(pr for pr, _ in sig)
            for pr, s in sig:
                seqs.append(tuple(idx[x] for x in s)); ws.append(p * pr / tot)
        _, lb = game.defender_br_enum(G, seqs, ws, cands, k)
        out.update(LB=lb, LB_rec=rec["Vmix_LB"], UB_rec=rec["Vmix_UB"])
        ok = lb >= rec["Vmix_UB"] - TOL * max(1, rec["Vmix_UB"])
        if do_ub:
            D = [(w, frozenset(idx[x] for x in names)) for w, names in rec["D"]]
            ub = 0.0
            for p, s in types:
                v, _, b, okx = game.exact_br(G.with_start(s), D, T, delta)
                ub += p * b; ok &= okx
            out["UB"] = ub
            # si alguna mejor respuesta tocó un límite, la cota depende de dónde se cortó: basta que la recalculada
            # no sea mayor que la registrada (V* <= ub <= registrada)
            ok &= ub <= rec["Vmix_UB"] + TOL * max(1, ub) and lb >= ub - TOL * max(1, ub)
        out["mix_ok"] = bool(ok)
    # visible
    if "pools" in rec:
        pools = [[tuple(idx[x] for x in s) for s in pool] for pool in rec["pools"]]
        lbv, _ = game.visible_lb_enum(G, pools, probs, cands, k)
        out.update(LBvis=lbv, UBvis_rec=rec["Vvis_UB"])
        okv = lbv >= rec["Vvis_UB"] - 1e-4 * max(1, rec["Vvis_UB"])
        if do_ub:
            B = frozenset(idx[x] for x in rec["vis_B"])
            ub = 0.0
            for p, s in types:
                v, _, b, okx = game.exact_br(G.with_start(s), [(1.0, B)], T, delta)
                ub += p * b; okv &= okx
            out["UBvis"] = ub
            okv &= ub <= rec["Vvis_UB"] + TOL * max(1, ub)
        out["vis_ok"] = bool(okv)
    return out


def sens_cases(G0):
    """Mismo orden y mismo generador aleatorio que scripts/run_v2.py:run_sens."""
    def perturb(fr, fp, fq):
        G = copy.deepcopy(G0)
        for v, nd in enumerate(G.nodes):
            nd.r *= fr(v); nd.p *= fp(v); nd.q = min(0.95, max(1e-4, nd.q * fq(v)))
        return G
    one = lambda v: 1.0
    yield "nominal", G0
    for role in sorted({nd.role for nd in G0.nodes}):
        for par in ("r", "p", "q"):
            for f in (0.5, 1.5):
                fx = lambda v, role=role, f=f: f if G0.nodes[v].role == role else 1.0
                yield f"{role}.{par}x{f}", perturb(fx if par == "r" else one, fx if par == "p" else one, fx if par == "q" else one)
    rng = random.Random(7)
    for i in range(20):
        fac = {(v, par): rng.uniform(0.5, 1.5) for v in range(G0.n) for par in "rpq"}
        yield f"ruido{i}", perturb(lambda v: fac[(v, "r")], lambda v: fac[(v, "p")], lambda v: fac[(v, "q")])
    yield "esquina_pesimista", perturb(lambda v: 1.5, lambda v: 0.5, lambda v: 0.5)


results = []
t0 = time.time()
if "goad" in groups:
    Gs = {a: bloodhound.parse(GOAD, footholds="regulares", adcs=a) for a in (False, True)}
    for rec in map(json.loads, open(f"{ROOT}/goad.jsonl")):
        d = math.inf if rec["delta"] == "inf" else float(rec["delta"])
        results.append(check(Gs[rec["adcs"]], rec, rec["T"], d, rec["k"], rec["task"]))
if "synth" in groups:
    try:
        recs = list(map(json.loads, open(f"{ROOT}/synth.jsonl")))
    except FileNotFoundError:
        recs = []
    for rec in recs:
        G = sharphound.parse(adgen.scaled(rec["scale"], seed=rec["seed"], redundancy=rec["redundancy"]), seed=rec["seed"], n_starts=5)
        d = math.inf if rec["delta"] == "inf" else float(rec["delta"])
        results.append(check(G, rec, rec["T"], d, rec["k"], rec["task"]))
if "sens" in groups:
    G0 = bloodhound.parse(GOAD, footholds="regulares", adcs=True)
    for k in (1, 2):
        try:
            recs = {r["etiqueta"]: r for r in map(json.loads, open(f"{ROOT}/sens_k{k}.jsonl"))}
        except FileNotFoundError:
            continue
        for label, G in sens_cases(G0):
            if label in recs:
                results.append(check(G, recs[label], 12.0, math.inf, k, f"sens:{k}:{label}"))
if "goadnd" in groups:
    Gs = {a: bloodhound.parse(GOAD, footholds="regulares", adcs=a) for a in (False, True)}
    for rec in map(json.loads, open(f"{ROOT}/goad_nodomain.jsonl")):
        d = math.inf if rec["delta"] == "inf" else float(rec["delta"])
        results.append(check(Gs[rec["adcs"]], rec, rec["T"], d, rec["k"], rec["task"]))
if "alta" in groups:
    fix = {}
    try:
        fix = {r["task"]: r for r in map(json.loads, open(f"{ROOT}/alta_fix.jsonl")) if r["cert"]}
    except FileNotFoundError:
        pass
    for rec in map(json.loads, open(f"{ROOT}/alta.jsonl")):
        G = sharphound.parse(adgen.scaled(60, seed=rec["seed"], redundancy="alta"), seed=rec["seed"], n_starts=5)
        rec = dict(rec)
        if not rec["Vvis_cert"] and rec["task"] in fix:      # visible certificada con el candidato de alta_fix.py
            rec["vis_B"], rec["Vvis_UB"] = fix[rec["task"]]["B"], fix[rec["task"]]["UB"]
        results.append(check(G, rec, 12.0, 0.0, rec["k"], rec["task"]))
if "altado" in groups:
    for rec in map(json.loads, open(f"{ROOT}/altado.jsonl")):
        G = sharphound.parse(adgen.scaled(60, seed=rec["seed"], redundancy="alta"), seed=rec["seed"], n_starts=5)
        out = check(G, rec, 12.0, 0.0, rec["k"], rec["task"])
        # sin convergencia: no se exige LB = UB, solo que el intervalo guardado sea válido
        out["mix_ok"] = bool(out["LB"] >= rec["Vmix_LB"] - 1e-9 * max(1, rec["Vmix_LB"]) and
                             (not do_ub or out["UB"] <= rec["Vmix_UB"] + 1e-6 * max(1, out["UB"])))
        results.append(out)
bad = [r for r in results if not r.get("mix_ok", True) or not r.get("vis_ok", True)]
with open(f"{ROOT}/verify{'_ub' if do_ub else ''}_{'_'.join(groups)}.jsonl", "w") as fh:
    for r in results:
        fh.write(json.dumps(r) + "\n")
print(f"{len(results)} certificados re-verificados ({'LB y UB' if do_ub else 'solo LB'}), {len(bad)} fallas, {time.time() - t0:.0f}s")
for r in bad:
    print("FALLA", r)
