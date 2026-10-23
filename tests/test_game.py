"""Double oracle y caso visible contra el juego completo enumerado (instancias chicas)."""
import itertools, math, random, sys
sys.path.insert(0, ".")
import numpy as np
from periplo import adgen, sharphound, game
from periplo.graph import step_cost, value


def all_seqs(G, T, delta):
    out = [()]
    def rec(seq, owned, frontier, prev, t):
        for v in frontier:
            c = step_cost(G, prev, v, delta)
            if t + c > T + 1e-9:
                continue
            s = seq + (v,)
            out.append(s)
            rec(s, owned | {v}, (frontier | G.out[v]) - owned - {v}, v, t + c)
    rec((), {G.start}, set(G.out[G.start]) - {G.start}, G.start, 0.0)
    return out


ORACLE = sys.argv[1] if len(sys.argv) > 1 else "beam"   # "beam" (con MILP) o "exact"


def main(trials=25):
    rng = random.Random(3)
    bad_do = bad_vis = done = 0
    ratios = []
    for trial in range(trials * 3):
        js = adgen.generate(n_ws=6, n_srv=2, n_dc=1, n_helpdesk=1, n_sa=1, n_da=1, n_app_groups=1, n_acl=2,
                            p_hd_admin=0.5, p_reuse=0.1, p_da_tier_violation=1.0, seed=500 + trial)
        G = sharphound.parse(js, seed=trial, n_starts=3)
        if G.n < 8:
            continue
        T = rng.choice([6.0, 8.0]); delta = rng.choice([0.0, 1.5, math.inf]); k = rng.choice([1, 2])
        types = game.default_types(G)
        seqs = [all_seqs(G.with_start(s), T, delta) for _, s in types]
        if sum(map(len, seqs)) > 6000:
            continue
        cands = list(range(G.n))
        Bs = [frozenset(c) for c in itertools.combinations(cands, k)]
        Ms = [np.array([[value(G, s, B) for s in sq] for B in Bs]) for sq in seqs]
        probs = np.array([p for p, _ in types])
        Vstar, _, _, _ = game.solve_bayes(Ms, probs)
        Vvis = min(sum(p * M[i].max() for p, M in zip(probs, Ms)) for i in range(len(Bs)))
        V0 = sum(p * max(value(G, s) for s in sq) for p, sq in zip(probs, seqs))
        r = game.double_oracle(G, T, delta, k, beam_width=60, milp_time=60, oracle=ORACLE)
        if not (abs(r["value"] - Vstar) <= 1e-5 * max(1, V0) and r["LB"] <= Vstar + 1e-6 and r["UB"] >= Vstar - 1e-6
                and (ORACLE != "exact" or r["certified"])):
            bad_do += 1; print("DO", trial, G.n, Vstar, r["value"], r["LB"], r["UB"])
        if ORACLE == "exact":   # corrida cortada por tiempo: el intervalo [LB, UB] tiene que contener V*
            r2 = game.double_oracle(G, T, delta, k, beam_width=60, oracle=ORACLE, time_limit=0.05)
            if not (r2["LB"] <= Vstar + 1e-6 and r2["UB"] >= Vstar - 1e-6):
                bad_do += 1; print("DO cortado", trial, Vstar, r2["LB"], r2["UB"])
        rv = game.visible_interdiction(G, T, delta, k, beam_width=60, oracle=ORACLE)
        if ORACLE == "exact" and not (rv["certified"] and rv["LB"] <= Vvis + 1e-6):
            bad_vis += 1; print("VIS cert", trial, Vvis, rv["LB"], rv["UB"])
        if abs(rv["value"] - Vvis) > 1e-5 * max(1, V0):
            bad_vis += 1; print("VIS", trial, G.n, Vvis, rv["value"], rv["LB"])
        if V0 > 0:
            ratios.append((Vstar / V0, Vvis / V0))
        done += 1
        if done >= trials:
            break
    a = np.array(ratios)
    print(f"instancias {done}; DO != LP completo: {bad_do}; visible != fuerza bruta: {bad_vis}")
    print(f"V_mix/V0 medio {a[:,0].mean():.3f}; V_vis/V0 medio {a[:,1].mean():.3f}")


if __name__ == "__main__":
    main()
