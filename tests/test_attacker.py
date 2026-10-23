"""Validación de los oráculos del atacante contra fuerza bruta en instancias chicas."""
import math, random, sys, time
sys.path.insert(0, ".")
import numpy as np
from periplo import adgen, sharphound, attacker
from periplo.graph import is_feasible, expected_value


def small_instance(seed):
    js = adgen.generate(n_ws=4, n_srv=2, n_dc=1, n_helpdesk=1, n_sa=1, n_da=1, n_app_groups=1,
                        n_acl=2, p_hd_admin=0.6, p_reuse=0.15, p_da_tier_violation=1.0, seed=seed)
    return sharphound.parse(js, seed=seed)


def random_scenarios(G, rng):
    cands = [v for v in range(G.n) if v != G.start]
    out = []
    for _ in range(rng.randint(1, 3)):
        k = rng.randint(0, min(2, len(cands)))
        out.append((rng.random() + 0.1, frozenset(rng.sample(cands, k))))
    tot = sum(w for w, _ in out)
    return [(w / tot, B) for w, B in out]


def main(trials=40):
    rng = random.Random(7)
    stats = {"milp_bad": 0, "beam_gap": [], "n": [], "t_milp": [], "t_brute": []}
    for trial in range(trials):
        G = small_instance(trial)
        scen = random_scenarios(G, rng)
        T = rng.choice([5.0, 7.0, 9.0])
        delta = rng.choice([0.0, 1.5, math.inf])
        t0 = time.time(); vb, sb = attacker.brute(G, scen, T, delta); stats["t_brute"].append(time.time() - t0)
        t0 = time.time(); vm, sm, bound, st = attacker.milp(G, scen, T, delta, time_limit=60); stats["t_milp"].append(time.time() - t0)
        vbe, sbe = attacker.beam(G, scen, T, delta, width=50)
        assert is_feasible(G, sb, T, delta) and abs(expected_value(G, sb, scen) - vb) < 1e-9
        assert not sbe or is_feasible(G, sbe, T, delta)
        if abs(vm - vb) > 1e-5 * max(1, vb) or bound < vb - 1e-5:
            stats["milp_bad"] += 1
            print("MILP mismatch", trial, G.n, T, delta, vb, vm, bound, st, sb, sm)
        stats["beam_gap"].append(0.0 if vb == 0 else 1 - vbe / vb)
        stats["n"].append(G.n)
    print(f"instancias: {trials}, nodos: {min(stats['n'])}-{max(stats['n'])}")
    print(f"MILP != fuerza bruta: {stats['milp_bad']}")
    g = np.array(stats["beam_gap"])
    print(f"beam(w=50) gap: medio {100*g.mean():.2f}%, máx {100*g.max():.2f}%, exactos {np.sum(g < 1e-9)}/{trials}")
    print(f"tiempo medio: brute {np.mean(stats['t_brute']):.2f}s, milp {np.mean(stats['t_milp']):.2f}s")


if __name__ == "__main__":
    main()
