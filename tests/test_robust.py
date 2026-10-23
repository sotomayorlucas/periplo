"""Monotonía: para toda mezcla D, el botín del atacante en la esquina (r x1,5, q x0,5, p x0,5) acota el de cualquier
punto de la caja. Contra fuerza bruta en instancias chicas."""
import copy, math, random, sys
sys.path.insert(0, ".")
from periplo import adgen, sharphound, attacker as A


def perturb(G, fr, fp, fq):
    H = copy.deepcopy(G)
    for v, nd in enumerate(H.nodes):
        nd.r *= fr(v); nd.p *= fp(v); nd.q = min(0.95, max(1e-4, nd.q * fq(v)))
    return H


def main(trials=40, samples=5):
    rng = random.Random(77); bad = done = 0
    for trial in range(trials * 4):
        js = adgen.generate(n_ws=rng.randint(4, 7), n_srv=rng.randint(1, 2), n_dc=1, n_helpdesk=1, n_sa=1, n_da=1,
                            n_app_groups=1, n_acl=rng.randint(1, 2), p_hd_admin=0.5, p_reuse=0.12, p_da_tier_violation=1.0,
                            seed=9100 + trial)
        G = sharphound.parse(js, seed=trial, n_starts=2)
        if G.n < 6:
            continue
        G = G.with_start(rng.choice(G.starts))
        D = [(rng.random() + 0.05, frozenset(rng.sample(range(G.n), rng.randint(0, 2)))) for _ in range(rng.randint(1, 3))]
        tot = sum(w for w, _ in D); D = [(w / tot, B) for w, B in D]
        T = rng.choice([6.0, 8.0]); delta = rng.choice([0.0, 1.0, math.inf])
        try:
            vc, _ = A.brute(perturb(G, lambda v: 1.5, lambda v: 0.5, lambda v: 0.5), D, T, delta, max_nodes=3_000_000)
            for _ in range(samples):
                f = {(v, x): rng.uniform(0.5, 1.5) for v in range(G.n) for x in "rpq"}
                Gs = perturb(G, lambda v: f[(v, "r")], lambda v: f[(v, "p")], lambda v: f[(v, "q")])
                vs, _ = A.brute(Gs, D, T, delta, max_nodes=3_000_000)
                if vs > vc + 1e-9 * max(1, vc):
                    bad += 1; print("FALLA", trial, delta, vs, vc)
        except RuntimeError:
            continue
        done += 1
        if done >= trials:
            break
    print(f"instancias {done} x {samples} puntos de la caja; violaciones de la cota de la esquina: {bad}")


if __name__ == "__main__":
    main()
