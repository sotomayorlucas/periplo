"""Corrida v2 de todos los experimentos con certificación SIN MILP:
- mejor respuesta del atacante: programa dinámico exacto (attacker.exact);
- mejor respuesta del defensor y maestro de la colocación visible: enumeración exhaustiva de los conjuntos de k trampas.
Cada certificado queda guardado (D, sigma por tipo; B y pools de la visible) para que scripts/verify_certs.py lo
re-verifique sin confiar en esta corrida. Cola de tareas compartida entre trabajadores (reclamos con O_EXCL),
reanudable, con presupuesto de tiempo por trabajador.
Uso: python -u scripts/run_v2.py presupuesto_min [filtro_prefijo]"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import copy, glob, json, math, os, random, resource, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, bloodhound, game, attacker as A

ROOT = REPO + "/results/v2"
os.makedirs(f"{ROOT}/claims", exist_ok=True)
budget = float(sys.argv[1]) * 60
prefix = sys.argv[2] if len(sys.argv) > 2 else ""
T0 = time.time()
J = lambda o: o.item() if hasattr(o, "item") else (sorted(o) if isinstance(o, (set, frozenset)) else str(o))
GOAD = sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip"))

# ------------------------------------------------------------------ tareas (orden = prioridad) y estimaciones (s)
TASKS = []
for adcs in (False, True):
    for d in ("inf", "0"):
        for k in (1, 2, 3):
            TASKS.append((f"goad:{int(adcs)}:{d}:{k}", 400))
OLD = {}
for f in ("delta_f", "red_f"):
    for r in map(json.loads, open(f"{REPO}/results/exact_{f}.jsonl")):
        OLD[(r["redundancy"], 40 if f == "delta_f" else 60, r["seed"], str(r["delta"]))] = r["t"]
est = lambda red, sc, s, d, dflt: 1.15 * OLD.get((red, sc, s, d), dflt)
for s in range(1, 9):
    TASKS.append((f"synth:media:40:{s}:0.0", est("media", 40, s, "0.0", 1500)))
for s in (1, 2, 3):
    TASKS.append((f"synth:media:60:{s}:0.0", est("media", 60, s, "0.0", 3000)))
for s in (1, 2, 3):
    TASKS.append((f"synth:baja:60:{s}:0.0", est("baja", 60, s, "0.0", 300)))
TASKS += [("sens:1", 2400), ("sens:2", 2400)]
for d in ("inf", "3.0", "1.0"):
    for s in range(1, 5):
        TASKS.append((f"synth:media:40:{s}:{d}", est("media", 40, s, d, 1000)))
for s in (1, 2, 3):
    TASKS.append((f"alta:{s}", 4500))
for s in (1, 2, 3):
    TASKS.append((f"altado:{s}", 4200))
TASKS = [(t, e) for t, e in TASKS if t.startswith(prefix)]


def outfile(task):
    return f"{ROOT}/{task.split(':')[0]}.jsonl"


def done(task):
    try:
        return any(json.loads(l).get("task") == task for l in open(outfile(task)))
    except FileNotFoundError:
        return False


def claim(task):
    path = f"{ROOT}/claims/{task.replace(':', '_')}"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            pid = int(open(path).read().strip() or 0)
            os.kill(pid, 0)
            return None                       # otro trabajador vivo la tiene
        except (ProcessLookupError, ValueError):
            os.remove(path)                   # reclamo huérfano (trabajador muerto)
            return claim(task)
        except PermissionError:
            return None
    os.write(fd, str(os.getpid()).encode()); os.close(fd)
    return path


def emit(task, rec):
    rec["task"] = task
    rec["rss_max_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    with open(outfile(task), "a") as fh:
        fh.write(json.dumps(rec, default=J) + "\n")


nm = lambda G, B: sorted(G.nodes[v].name for v in B)
seqn = lambda G, s: [G.nodes[v].name for v in s]


def ev(G, scen, T, delta):
    """Valor exacto sum_t p_t max_pi E_scen U; devuelve (valor, cota, exacto)."""
    i0 = len(game.DP_STATS)
    lo, hi = game.best_response_value(G, scen, T, delta, oracle="exact", certify=True)
    ok = all(x[2] == "Optimal" for x in game.DP_STATS[i0:])
    return lo, hi, ok


def per_type_V0(G, T, delta):
    out = []
    for p, s in game.default_types(G):
        v, _, ub, ok = game.exact_br(G.with_start(s), [(1.0, frozenset())], T, delta)
        out.append(dict(start=G.nodes[s].name, p=p, V0=v, exact=ok))
    return out


def solve_game(G, T, delta, k):
    """Mezcla óptima certificada + colocación visible certificada, con certificados guardables."""
    i0, c0, w0 = len(game.DP_STATS), time.process_time(), time.time()
    do = game.double_oracle(G, T, delta, k, oracle="exact")
    do_cpu, do_wall, do_dp = time.process_time() - c0, time.time() - w0, game.dp_summary(i0)
    i1, c1, w1 = len(game.DP_STATS), time.process_time(), time.time()
    vis = game.visible_interdiction(G, T, delta, k, oracle="exact")
    vis_cpu, vis_wall, vis_dp = time.process_time() - c1, time.time() - w1, game.dp_summary(i1)
    types = game.default_types(G)
    rec = dict(
        Vmix=do["UB"], Vmix_LP=do["value"], Vmix_LB=do["LB"], Vmix_UB=do["UB"], Vmix_cert=do["certified"],
        do_enum=do["enum"], it_do=do["iterations"], t_do=do_wall, cpu_do=do_cpu, dp_do=do_dp, soporte=len(do["D"]),
        soporte_att=do["support_att"],
        D=[(w, nm(G, B)) for w, B in do["D"]],
        sigma=[[(float(pr), seqn(G, s)) for pr, s in sig if pr > 1e-12] for sig in do["sigma"]],
        types=[(p, G.nodes[s].name) for p, s in types],
        Vvis=vis["UB"], Vvis_LB=vis["LB"], Vvis_UB=vis["UB"], Vvis_cert=vis["certified"], vis_enum=vis["enum"],
        it_vis=vis["iterations"], t_vis=vis_wall, cpu_vis=vis_cpu, dp_vis=vis_dp,
        vis_B=nm(G, vis["B"]), pools=[[seqn(G, s) for s in pool] for pool in vis["pools"]])
    return rec, do, vis


def run_synth(task):
    _, red, sc, seed, d = task.split(":")
    sc, seed = int(sc), int(seed)
    delta = math.inf if d == "inf" else float(d)
    T, k = 12.0, 3
    G = sharphound.parse(adgen.scaled(sc, seed=seed, redundancy=red), seed=seed, n_starts=5)
    t0, c0 = time.time(), time.process_time()
    V0, V0_ub, V0_ok = ev(G, [(1.0, frozenset())], T, delta)
    rec, do, vis = solve_game(G, T, delta, k)
    base = {}
    for name, B in game.baselines(G, k).items():
        v, ub, ok = ev(G, [(1.0, B)], T, delta)
        base[name] = dict(v=v, ub=ub, exact=ok, B=nm(G, B))
    cands = [v for v in range(G.n) if v not in set(G.starts)]
    uv, uub, uok = ev(G, game.uniform_mixture(cands, k, 64, seed=seed), T, delta)
    naive = 0.0
    for p, s in game.default_types(G):
        Gt = G.with_start(s)
        _, s0, _, _ = game.exact_br(Gt, [(1.0, frozenset())], T, delta)
        naive += p * A.expected_value(Gt, s0, do["D"])
    rec.update(redundancy=red, scale=sc, seed=seed, delta=d, n=G.n, m=sum(len(G.out[v]) for v in range(G.n)), k=k, T=T,
               V0=V0, V0_ub=V0_ub, V0_exact=V0_ok, base=base, uniforme=dict(v=uv, ub=uub, exact=uok), naive=naive,
               t=time.time() - t0, cpu=time.process_time() - c0)
    emit(task, rec)


def run_goad(task):
    _, adcs, d, k = task.split(":")
    adcs, k = bool(int(adcs)), int(k)
    delta = math.inf if d == "inf" else float(d)
    T = 12.0
    G = bloodhound.parse(GOAD, footholds="regulares", adcs=adcs)
    t0, c0 = time.time(), time.process_time()
    V0, V0_ub, V0_ok = ev(G, [(1.0, frozenset())], T, delta)
    rec, do, vis = solve_game(G, T, delta, k)
    base = {}
    for name, B in game.baselines(G, k).items():
        v, ub, ok = ev(G, [(1.0, B)], T, delta)
        base[name] = dict(v=v, ub=ub, exact=ok, B=nm(G, B))
    cands = [v for v in range(G.n) if v not in set(G.starts)]
    uv, uub, uok = ev(G, game.uniform_mixture(cands, k, 64, seed=0), T, delta)
    rec.update(adcs=adcs, delta=d, k=k, T=T, n=G.n, m=sum(len(G.out[v]) for v in range(G.n)), V0=V0, V0_ub=V0_ub,
               V0_exact=V0_ok, V0_types=per_type_V0(G, T, delta), base=base, uniforme=dict(v=uv, ub=uub, exact=uok),
               t=time.time() - t0, cpu=time.process_time() - c0)
    emit(task, rec)


def run_alta(task):
    """Redundancia alta: el double oracle exacto no termina en 2 h (corridas anteriores). Se certifica la colocación
    visible óptima (sin MILP) y se compara con el valor exacto (o cota) de la mezcla vieja, ya calculado en
    results/exact_alta.jsonl (evaluación exacta de una mezcla fija: no depende de ningún solver)."""
    seed = int(task.split(":")[1])
    T, k, delta = 12.0, 3, 0.0
    G = sharphound.parse(adgen.scaled(60, seed=seed, redundancy="alta"), seed=seed, n_starts=5)
    t0, c0 = time.time(), time.process_time()
    V0, V0_ub, V0_ok = ev(G, [(1.0, frozenset())], T, delta)
    i1 = len(game.DP_STATS)
    vis = game.visible_interdiction(G, T, delta, k, oracle="exact")
    old = [r for r in map(json.loads, open(REPO + "/results/exact_alta.jsonl"))
           if r["seed"] == seed and r["paso"] == "D_viejo"][0]
    base = {}
    for name, B in game.baselines(G, k).items():
        v, ub, ok = ev(G, [(1.0, B)], T, delta)
        base[name] = dict(v=v, ub=ub, exact=ok, B=nm(G, B))
    emit(task, dict(redundancy="alta", scale=60, seed=seed, delta="0.0", n=G.n, k=k, T=T, V0=V0, V0_ub=V0_ub, V0_exact=V0_ok,
                    Vvis=vis["UB"], Vvis_LB=vis["LB"], Vvis_UB=vis["UB"], Vvis_cert=vis["certified"], vis_enum=vis["enum"],
                    it_vis=vis["iterations"], t_vis=vis["time"], dp_vis=game.dp_summary(i1), vis_B=nm(G, vis["B"]),
                    pools=[[seqn(G, s) for s in pool] for pool in vis["pools"]],
                    Dold_inf=old["V_inf"], Dold_sup=old["V_sup"], Dold_exact=old["exacto"],
                    gana_cert=old["V_sup"] < vis["LB"], base=base, t=time.time() - t0, cpu=time.process_time() - c0))


def run_sens(task):
    k = int(task.split(":")[1])
    T, delta = 12.0, math.inf
    out = f"{ROOT}/sens_k{k}.jsonl"
    G0 = bloodhound.parse(GOAD, footholds="regulares", adcs=True)
    have = {}
    try:
        have = {r["etiqueta"]: r for r in map(json.loads, open(out))}
    except FileNotFoundError:
        pass

    def perturb(fr, fp, fq):
        G = copy.deepcopy(G0)
        for v, nd in enumerate(G.nodes):
            nd.r *= fr(v); nd.p *= fp(v); nd.q = min(0.95, max(1e-4, nd.q * fq(v)))
        return G

    idx = {nd.name: i for i, nd in enumerate(G0.nodes)}
    toD = lambda D: [(w, frozenset(idx[x] for x in names)) for w, names in D]

    def tv(D1, D2):
        a = {frozenset(n): w for w, n in D1}; b = {frozenset(n): w for w, n in D2}
        return 0.5 * sum(abs(a.get(B, 0.0) - b.get(B, 0.0)) for B in set(a) | set(b))

    def record(label, kind, G, nom):
        if label in have:
            return have[label]
        if time.time() - T0 > budget - 120:
            raise TimeoutError
        t0 = time.time()
        V0, _, _ = ev(G, [(1.0, frozenset())], T, delta)
        rec, do, vis = solve_game(G, T, delta, k)
        rec.update(k=k, tipo=kind, etiqueta=label, V0=V0)
        if nom is not None:
            V_Dnom, _, ok1 = ev(G, toD(nom["D"]), T, delta)
            V_Bnom, _, ok2 = ev(G, [(1.0, frozenset(idx[x] for x in nom["vis_B"]))], T, delta)
            rec.update(V_Dnom=V_Dnom, V_Bvisnom=V_Bnom, nom_eval_exact=ok1 and ok2,
                       regret_D=V_Dnom - rec["Vmix"], regret_Bvis=V_Bnom - rec["Vvis"], tv_D=tv(rec["D"], nom["D"]),
                       vis_cambia=sorted(rec["vis_B"]) != sorted(nom["vis_B"]))
        rec["t"] = time.time() - t0
        with open(out, "a") as fh:
            fh.write(json.dumps(rec, default=J) + "\n")
        have[label] = json.loads(json.dumps(rec, default=J))
        return have[label]

    one = lambda v: 1.0
    nom = record("nominal", "nominal", G0, None)
    roles = sorted({nd.role for nd in G0.nodes})
    for role in roles:
        for par in ("r", "p", "q"):
            for f in (0.5, 1.5):
                fx = lambda v, role=role, f=f: f if G0.nodes[v].role == role else 1.0
                G = perturb(fx if par == "r" else one, fx if par == "p" else one, fx if par == "q" else one)
                record(f"{role}.{par}x{f}", "un_parametro", G, nom)
    rng = random.Random(7)
    for i in range(20):
        fac = {(v, par): rng.uniform(0.5, 1.5) for v in range(G0.n) for par in "rpq"}
        G = perturb(lambda v: fac[(v, "r")], lambda v: fac[(v, "p")], lambda v: fac[(v, "q")])
        record(f"ruido{i}", "ruido_nodo", G, nom)
    corner = perturb(lambda v: 1.5, lambda v: 0.5, lambda v: 0.5)
    rob = record("esquina_pesimista", "robusto", corner, nom)
    V_rob_nom, _, ok = ev(G0, toD(rob["D"]), T, delta)
    emit(task, dict(k=k, V_Drob_en_nominal=V_rob_nom, exact=ok, Vmix_nominal=nom["Vmix"], V0_nominal=nom["V0"],
                    Vmix_esquina=rob["Vmix"], V0_esquina=rob["V0"], V_Dnom_en_esquina=rob["V_Dnom"]))


def run_altado(task):
    """Redundancia alta: double oracle exacto con tope de 1 h. Toda D vista da una cota superior y todo sigma una
    inferior (por enumeración), así que aunque no converja queda un intervalo certificado del valor del juego."""
    seed = int(task.split(":")[1])
    T, k, delta = 12.0, 3, 0.0
    G = sharphound.parse(adgen.scaled(60, seed=seed, redundancy="alta"), seed=seed, n_starts=5)
    i0, c0, t0 = len(game.DP_STATS), time.process_time(), time.time()
    do = game.double_oracle(G, T, delta, k, oracle="exact", time_limit=3600)
    emit(task, dict(redundancy="alta", scale=60, seed=seed, delta="0.0", n=G.n, k=k, T=T,
                    Vmix_LB=do["LB"], Vmix_UB=do["UB"], Vmix_cert=do["certified"], timed_out=do.get("timed_out"),
                    it_do=do["iterations"], t_do=time.time() - t0, cpu_do=time.process_time() - c0, dp_do=game.dp_summary(i0),
                    D=[(w, nm(G, B)) for w, B in do["D"]],
                    sigma=[[(float(pr), seqn(G, s)) for pr, s in sig if pr > 1e-12] for sig in (do["sigma"] or [])],
                    types=[(p, G.nodes[s].name) for p, s in game.default_types(G)]))


RUN = dict(goad=run_goad, synth=run_synth, alta=run_alta, sens=run_sens, altado=run_altado)
progress = True
while progress:
    progress = False
    for task, e in TASKS:
        if done(task):
            continue
        left = budget - (time.time() - T0)
        if e > left and not task.startswith("sens"):
            continue
        c = claim(task)
        if not c:
            continue
        try:
            if done(task):
                continue
            print(f"[{time.strftime('%H:%M:%S')}] {task} (est {e:.0f}s, quedan {left:.0f}s)", flush=True)
            t = time.time()
            RUN[task.split(":")[0]](task)
            print(f"[{time.strftime('%H:%M:%S')}] {task} listo en {time.time() - t:.0f}s", flush=True)
            progress = True
        except TimeoutError:
            print(f"{task}: presupuesto agotado, se retoma en la próxima corrida", flush=True)
        finally:
            os.remove(c)
print("trabajador terminó; pendientes:", [t for t, _ in TASKS if not done(t)], flush=True)
