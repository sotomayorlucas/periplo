"""Estrés del MILP del atacante con mezclas de escenarios y footholds variados contra fuerza bruta."""
import math, random, sys, time
sys.path.insert(0, ".")
from periplo import adgen, sharphound, attacker as A

def main(trials=150):
    rng = random.Random(99)
    bad_val = bad_bound = done = 0; tmax = 0.0
    for trial in range(trials * 2):
        js = adgen.generate(n_ws=rng.randint(4, 8), n_srv=rng.randint(1, 3), n_dc=1, n_helpdesk=rng.randint(1, 2),
                            n_sa=1, n_da=1, n_app_groups=rng.randint(1, 2), n_acl=rng.randint(1, 3),
                            p_hd_admin=0.5, p_reuse=0.1, p_da_tier_violation=1.0, seed=900 + trial)
        G = sharphound.parse(js, seed=trial, n_starts=3)
        if G.n < 6:
            continue
        s = rng.choice(G.starts); Gt = G.with_start(s)
        cands = list(range(G.n))
        scen = []
        for _ in range(rng.randint(2, 4)):
            scen.append((rng.random() + 0.05, frozenset(rng.sample(cands, rng.randint(1, 2)))))
        tot = sum(w for w, _ in scen); scen = [(w / tot, B) for w, B in scen]
        T = rng.choice([6.0, 8.0, 10.0]); delta = rng.choice([0.0, 1.0, 2.5, math.inf])
        try:
            vb, _ = A.brute(Gt, scen, T, delta, max_nodes=2_000_000)
        except RuntimeError:
            continue
        t0 = time.time(); vm, sm, bd, st = A.milp(Gt, scen, T, delta, time_limit=120); tmax = max(tmax, time.time() - t0)
        if abs(vm - vb) > 1e-5 * max(1, vb): bad_val += 1; print("valor", trial, vb, vm, bd, st)
        if bd < vb - 1e-5 * max(1, vb): bad_bound += 1; print("cota", trial, vb, vm, bd, st)
        done += 1
        if done >= trials: break
    print(f"instancias {done}; valor distinto {bad_val}; cota inválida {bad_bound}; t máx {tmax:.1f}s")

if __name__ == "__main__":
    main()
