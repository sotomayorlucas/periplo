"""Algoritmo exacto (DP sobre conjuntos con poda por índice) contra fuerza bruta, δ en {0, 1, 2.5, ∞}, con mezclas."""
import math, random, sys, time
sys.path.insert(0, ".")
from periplo import adgen, sharphound, attacker as A


def main(trials=200):
    rng = random.Random(4242); bad = done = 0; t_ex = t_br = 0.0; states = []
    for trial in range(trials * 4):
        js = adgen.generate(n_ws=rng.randint(4, 9), n_srv=rng.randint(1, 3), n_dc=1, n_helpdesk=rng.randint(1, 2),
                            n_sa=1, n_da=1, n_app_groups=rng.randint(1, 2), n_acl=rng.randint(1, 3),
                            p_hd_admin=0.5, p_reuse=0.12, p_da_tier_violation=1.0, seed=8000 + trial)
        G = sharphound.parse(js, seed=trial, n_starts=3)
        if G.n < 6:
            continue
        Gt = G.with_start(rng.choice(G.starts))
        scen = [(rng.random() + 0.05, frozenset(rng.sample(range(G.n), rng.randint(0, 2)))) for _ in range(rng.randint(1, 4))]
        tot = sum(w for w, _ in scen); scen = [(w / tot, B) for w, B in scen]
        T = rng.choice([6.0, 8.0, 10.0]); delta = rng.choice([0.0, 1.0, 2.5, math.inf])
        t0 = time.time()
        try:
            vb, sb = A.brute(Gt, scen, T, delta, max_nodes=2_000_000)
        except RuntimeError:
            continue
        t_br += time.time() - t0; t0 = time.time()
        ve, se, ub, st, info = A.exact(Gt, scen, T, delta)
        t_ex += time.time() - t0; states.append(info["states"])
        ok = st == "Optimal" and abs(ve - vb) <= 1e-9 * max(1, vb) and abs(ub - vb) <= 1e-9 * max(1, vb)
        ok = ok and (not se or (A.is_feasible(Gt, se, T, delta) and abs(A.expected_value(Gt, se, scen) - ve) <= 1e-9 * max(1, ve)))
        if not ok:
            bad += 1; print("FALLA", trial, delta, vb, ve, ub, st, sb, se)
        done += 1
        if done >= trials:
            break
    print(f"instancias {done}; fallas {bad}; tiempo total brute {t_br:.1f}s, exacto {t_ex:.1f}s; estados máx {max(states)}")


if __name__ == "__main__":
    main()
