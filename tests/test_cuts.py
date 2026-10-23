"""Los cortes de dominancia y las cotas por posición no cambian el óptimo (δ = 0, con escenarios)."""
import math, random, sys
sys.path.insert(0, ".")
from periplo import adgen, sharphound, attacker as A

def main(trials=120):
    rng = random.Random(2026); bad = done = 0
    for trial in range(trials * 2):
        js = adgen.generate(n_ws=rng.randint(4, 8), n_srv=rng.randint(1, 3), n_dc=1, n_helpdesk=rng.randint(1, 2),
                            n_sa=1, n_da=1, n_app_groups=rng.randint(1, 2), n_acl=rng.randint(1, 3),
                            p_hd_admin=0.5, p_reuse=0.12, p_da_tier_violation=1.0, seed=3000 + trial)
        G = sharphound.parse(js, seed=trial, n_starts=3)
        if G.n < 6: continue
        Gt = G.with_start(rng.choice(G.starts))
        scen = []
        for _ in range(rng.randint(1, 4)):
            scen.append((rng.random() + 0.05, frozenset(rng.sample(range(G.n), rng.randint(0, 2)))))
        tot = sum(w for w, _ in scen); scen = [(w / tot, B) for w, B in scen]
        T = rng.choice([6.0, 8.0, 10.0])
        try:
            vb, _ = A.brute(Gt, scen, T, 0.0, max_nodes=2_000_000)
        except RuntimeError:
            continue
        vm, sm, bd, st = A.milp(Gt, scen, T, 0.0, time_limit=120, cuts=True, solver_name="scip")  # HiGHS 1.15.1 falla acá: ver results/highs_bug
        if abs(vm - vb) > 1e-5 * max(1, vb) or bd < vb - 1e-5 * max(1, vb):
            bad += 1; print("falla", trial, vb, vm, bd, st)
        done += 1
        if done >= trials: break
    print(f"instancias {done}; fallas con cortes: {bad}")

if __name__ == "__main__":
    main()
