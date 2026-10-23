"""Confiabilidad de solvers MILP sobre el modelo del atacante: cada configuración contra fuerza bruta.
Uso: python scripts/solver_study.py {cuts|stress} salida.jsonl"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, math, random, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, attacker as A

fam, out = sys.argv[1], sys.argv[2]
CONFIGS = [(sn, c) for sn in ("highs", "highs_root", "cbc", "scip") for c in (False, True)]


def instances():
    if fam == "cuts":     # mismas instancias que tests/test_cuts.py (δ = 0)
        rng, base, n_tr, pr, smin = random.Random(2026), 3000, 120, 0.12, 0
    else:                 # mismas que tests/test_milp_stress.py (δ variado)
        rng, base, n_tr, pr, smin = random.Random(99), 900, 150, 0.1, 1
    done = 0
    for trial in range(n_tr * 2):
        js = adgen.generate(n_ws=rng.randint(4, 8), n_srv=rng.randint(1, 3), n_dc=1, n_helpdesk=rng.randint(1, 2),
                            n_sa=1, n_da=1, n_app_groups=rng.randint(1, 2), n_acl=rng.randint(1, 3),
                            p_hd_admin=0.5, p_reuse=pr, p_da_tier_violation=1.0, seed=base + trial)
        G = sharphound.parse(js, seed=trial, n_starts=3)
        if G.n < 6:
            continue
        Gt = G.with_start(rng.choice(G.starts))
        scen = []
        if fam == "cuts":
            for _ in range(rng.randint(1, 4)):
                scen.append((rng.random() + 0.05, frozenset(rng.sample(range(G.n), rng.randint(0, 2)))))
        else:
            for _ in range(rng.randint(2, 4)):
                scen.append((rng.random() + 0.05, frozenset(rng.sample(list(range(G.n)), rng.randint(1, 2)))))
        tot = sum(w for w, _ in scen); scen = [(w / tot, B) for w, B in scen]
        T = rng.choice([6.0, 8.0, 10.0])
        delta = 0.0 if fam == "cuts" else rng.choice([0.0, 1.0, 2.5, math.inf])
        try:
            vb, _ = A.brute(Gt, scen, T, delta, max_nodes=2_000_000)
        except RuntimeError:
            continue
        yield trial, Gt, scen, T, delta, vb
        done += 1
        if done >= n_tr:
            return


import os
done_trials = {json.loads(l)["trial"] for l in open(out)} if os.path.exists(out) else set()
for trial, Gt, scen, T, delta, vb in instances():
    if trial in done_trials:
        continue
    rec = dict(fam=fam, trial=trial, n=Gt.n, delta=("inf" if math.isinf(delta) else delta), opt=vb)
    for sn, c in CONFIGS:
        t0 = time.time()
        v, s, bd, st = A.milp(Gt, scen, T, delta, time_limit=120, solver_name=sn, cuts=c)
        tol = 1e-5 * max(1.0, vb)
        rec[f"{sn}{'+c' if c else ''}"] = dict(ok_val=abs(v - vb) <= tol, ok_bound=bd >= vb - tol,
                                                 st=st.split(":")[0], t=round(time.time() - t0, 2))
    with open(out, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
