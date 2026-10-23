"""Enumeración de conjuntos de trampas (defensor y maestro visible) contra fuerza bruta directa con value()."""
import itertools, random, sys
sys.path.insert(0, ".")
from periplo import adgen, sharphound, game
from periplo.graph import value
from periplo import attacker as A


def main(trials=60):
    rng = random.Random(11)
    bad = done = 0
    for trial in range(trials):
        js = adgen.generate(n_ws=rng.choice([5, 8, 12]), n_srv=2, n_dc=1, n_helpdesk=1, n_sa=1, n_da=1, n_app_groups=1,
                            n_acl=2, p_hd_admin=0.5, p_reuse=0.2, p_da_tier_violation=1.0, seed=900 + trial)
        G = sharphound.parse(js, seed=trial, n_starts=3)
        types = game.default_types(G)
        k = rng.choice([1, 2, 3])
        cands = list(range(G.n)) if rng.random() < 0.5 else [v for v in range(G.n) if v not in set(G.starts)]
        # secuencias: beam contra trampas aleatorias, para tener prefijos variados
        pools = []
        for _, s in types:
            Gt = G.with_start(s)
            pool = []
            for _ in range(rng.choice([1, 3, 6])):
                B = frozenset(rng.sample(range(G.n), min(G.n, rng.choice([0, 1, 2]))))
                _, seq = A.beam(Gt, [(1.0, B)], 8.0, rng.choice([0.0, 2.0, float("inf")]), width=20)
                if seq and seq not in pool:
                    pool.append(seq)
            pools.append(pool)
        seqs = [q for pool in pools for q in pool]
        if not seqs:
            continue
        ws = [rng.random() for _ in seqs]
        # fuerza bruta del defensor
        allB = [frozenset(c) for c in itertools.combinations(cands, min(k, len(cands)))]
        f = lambda B: sum(w * value(G, q, B) for w, q in zip(ws, seqs))
        best = min(f(B) for B in allB)
        Be, ve = game.defender_br_enum(G, seqs, ws, cands, k)
        if abs(ve - best) > 1e-9 * max(1, best) or abs(f(Be) - ve) > 1e-9:
            bad += 1; print("DEF", trial, ve, best)
        # contra el MILP (SCIP)
        Bm, vm = game.defender_br_milp(G, seqs, ws, cands, k)
        if vm < best - 1e-7:
            bad += 1; print("MILP por debajo del óptimo?", trial, vm, best)
        # maestro visible
        probs = [p for p, _ in types]
        g = lambda B: sum(p * max([value(G, q, B) for q in pool] or [0.0]) for p, pool in zip(probs, pools))
        bestv = min(g(B) for B in allB)
        lb, Bv = game.visible_lb_enum(G, pools, probs, cands, k)
        if abs(lb - bestv) > 1e-9 * max(1, bestv) or abs(g(Bv) - lb) > 1e-9:
            bad += 1; print("VIS", trial, lb, bestv)
        done += 1
    print(f"test_enum: {done} instancias, {bad} fallas")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
