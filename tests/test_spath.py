"""Atacante de camino más corto: probabilidades de captura y colocación óptima contra enumeración explícita de caminos."""
import itertools, random, sys
from collections import deque
sys.path.insert(0, ".")
from periplo import adgen, sharphound, spath


def all_shortest_paths(G, s, targets):
    tset = set(targets)
    # BFS por capas desde s hasta el primer nivel que toca el objetivo
    dist = {s: 0}; dq = deque([s])
    while dq:
        u = dq.popleft()
        for w in G.out[u]:
            if w not in dist:
                dist[w] = dist[u] + 1; dq.append(w)
    reach = [dist[t] for t in tset if t in dist and t != s]
    if not reach:
        return []
    d = min(reach)
    out = []
    def rec(path):
        u = path[-1]
        if len(path) - 1 == d:
            if u in tset:
                out.append(tuple(path))
            return
        if u in tset and len(path) > 1:
            return
        for w in G.out[u]:
            if w not in path:
                rec(path + [w])
    rec([s])
    return out


def main(trials=40):
    rng = random.Random(5)
    bad = done = 0
    for trial in range(trials):
        js = adgen.generate(n_ws=rng.choice([5, 8, 12]), n_srv=2, n_dc=1, n_helpdesk=rng.choice([1, 2]), n_sa=1, n_da=1,
                            n_app_groups=1, n_acl=rng.choice([1, 3]), p_hd_admin=0.6, p_reuse=0.25,
                            p_da_tier_violation=1.0, seed=1300 + trial)
        G = sharphound.parse(js, seed=trial, n_starts=3)
        targets = [v for v in range(G.n) if G.nodes[v].tier == 0]
        cands = [v for v in range(G.n) if v not in set(G.starts)]
        k = rng.choice([1, 2, 3])
        types = [(1.0 / len(G.starts), s) for s in G.starts]
        paths = {s: all_shortest_paths(G, s, targets) for _, s in types}
        if not any(paths.values()):
            continue
        def obj(B):
            num = den = 0.0
            for p, s in types:
                P = paths[s]
                if P:
                    num += p * sum(1 for q in P if any(v in B for v in q[1:])) / len(P); den += p
            return num / den
        def steps(B):
            num = den = 0.0
            for p, s in types:
                P = paths[s]
                if P:
                    tot = 0
                    for q in P:
                        f = next((i for i, v in enumerate(q[1:], 1) if v in B), len(q) - 1)
                        tot += f
                    num += p * tot / len(P); den += p
            return num / den
        allB = [set(c) for c in itertools.combinations(cands, min(k, len(cands)))]
        best = max(obj(B) for B in allB)
        best_steps = min(steps(B) for B in allB if obj(B) >= best - 1e-12)
        B, val, nreach = spath.sp_optimal(G, k, cands, targets, types)
        if B is not None and abs(steps(set(B)) - best_steps) > 1e-9:
            bad += 1; print("desempate", trial, steps(set(B)), best_steps)
        # el conteo del DAG tiene que coincidir con la enumeración
        for p, s in types:
            r = spath.sp_counts(G, s, targets)
            if (r is None) != (not paths[s]) or (r is not None and abs(r[0] - len(paths[s])) > 1e-9):
                bad += 1; print("conteo", trial, s, None if r is None else r[0], len(paths[s]))
        if abs(val - best) > 1e-9 or abs(obj(B) - val) > 1e-9:
            bad += 1; print("FALLA", trial, k, val, best, obj(B))
        done += 1
    print(f"test_spath: {done} instancias, {bad} fallas")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
