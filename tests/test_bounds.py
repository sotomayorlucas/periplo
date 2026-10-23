"""Cotas superiores alternativas contra fuerza bruta: por conjuntos (orden por índice, todo δ) y por grupos de escenarios."""
import math, random, statistics, sys
sys.path.insert(0, ".")
from periplo import adgen, sharphound, attacker as A


def instances(seed, n, deltas):
    rng = random.Random(seed); done = 0
    for trial in range(n * 4):
        js = adgen.generate(n_ws=rng.randint(4, 8), n_srv=rng.randint(1, 3), n_dc=1, n_helpdesk=rng.randint(1, 2), n_sa=1, n_da=1,
                            n_app_groups=rng.randint(1, 2), n_acl=rng.randint(1, 3), p_hd_admin=0.5, p_reuse=0.12,
                            p_da_tier_violation=1.0, seed=seed * 10 + trial)
        G = sharphound.parse(js, seed=trial, n_starts=3)
        if G.n < 6:
            continue
        Gt = G.with_start(rng.choice(G.starts))
        scen = [(rng.random() + 0.05, frozenset(rng.sample(range(G.n), rng.randint(0, 2)))) for _ in range(rng.randint(1, 4))]
        tot = sum(w for w, _ in scen); scen = [(w / tot, B) for w, B in scen]
        T = rng.choice([6.0, 8.0, 10.0]); delta = rng.choice(deltas)
        try:
            vb, _ = A.brute(Gt, scen, T, delta, max_nodes=1_000_000)
        except RuntimeError:
            continue
        yield Gt, scen, T, delta, vb
        done += 1
        if done >= n:
            return


def main():
    bad = 0; ratios = []
    for Gt, scen, T, delta, vb in instances(701, 60, [0.0, 0.0, 1.0, math.inf]):
        ub, st, _ = A.set_bound(Gt, scen, T, solver_name="scip")
        if ub < vb - 1e-6 * max(1, vb) or not st.startswith("Optimal"):
            bad += 1; print("conjuntos FALLA", delta, vb, ub, st)
        if delta == 0.0:
            ratios.append(ub / max(vb, 1e-9))
    print(f"conjuntos: 60 instancias, fallas {bad}; δ=0 cota/óptimo mediana {statistics.median(ratios):.3f}, máx {max(ratios):.3f}")
    bad = 0
    for Gt, scen, T, delta, vb in instances(503, 25, [0.0]):
        for g in (1, 2, len(scen)):
            r = A.group_bound(Gt, scen, T, 0.0, group_size=g, time_limit=60, beam_width=100)
            if r["LB"] > vb + 1e-6 or r["UB"] < vb - 1e-6:
                bad += 1; print("grupos FALLA", g, r["LB"], vb, r["UB"])
    print(f"grupos: 25 instancias x 3 niveles, fallas {bad}; alertas de cota {len(A.BOUND_ALERTS)}")


if __name__ == "__main__":
    main()
