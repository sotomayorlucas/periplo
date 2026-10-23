"""Atacante de camino más corto (el "simple attacker" de Ngo et al., INFOCOM 2024): desde su foothold elige al azar,
uniforme, uno de los caminos más cortos (en saltos) hacia el objetivo, con todos los nodos de tier 0 fusionados en un
único objetivo; no ve las trampas. El defensor elige un conjunto fijo B (|B| <= k) que maximiza la probabilidad de que
el camino elegido pase por una trampa, promediada sobre los footholds que alcanzan el objetivo (equivale a minimizar
la fracción de caminos limpios, el objetivo de Ngo et al.).

Cálculo exacto para k <= 3: conteo de caminos en el DAG de caminos más cortos e inclusión-exclusión, evaluado
vectorialmente sobre todos los conjuntos de tamaño k (los de menor tamaño están dominados). Muchos conjuntos empatan
en probabilidad de captura (por ejemplo, con probabilidad 1); los empates se rompen a favor de atrapar antes:
mínimo número esperado de pasos del atacante hasta la detección (todos los pasos del camino si no hay captura)."""
from __future__ import annotations
import itertools
from collections import deque
import numpy as np


def sp_counts(G, s, targets):
    """Para el foothold s: (N, a, b, C, nodes) con N = cantidad de caminos más cortos s -> objetivo,
    a[v] = caminos s -> v y b[v] = caminos v -> objetivo dentro del DAG, C[u, v] = caminos u -> v en el DAG
    (C[u, u] = 1). Índices sobre `nodes` (los nodos del DAG). None si s no alcanza el objetivo."""
    dist = {t: 0 for t in targets}
    dq = deque(targets)
    while dq:
        v = dq.popleft()
        for u in G.inn[v]:
            if u not in dist:
                dist[u] = dist[v] + 1
                dq.append(u)
    if s not in dist or dist[s] == 0:
        return None
    # nodos alcanzables desde s por aristas que bajan la distancia en 1
    succ = lambda u: [w for w in G.out[u] if dist.get(w, -1) == dist[u] - 1]
    seen, order, dq = {s}, [s], deque([s])
    while dq:
        u = dq.popleft()
        if dist[u] == 0:
            continue
        for w in succ(u):
            if w not in seen:
                seen.add(w); order.append(w); dq.append(w)
    nodes = sorted(seen, key=lambda v: -dist[v])          # orden topológico (distancia decreciente)
    ix = {v: i for i, v in enumerate(nodes)}
    n = len(nodes)
    b = np.zeros(n)
    for v in reversed(nodes):                              # distancia creciente
        b[ix[v]] = 1.0 if dist[v] == 0 else sum(b[ix[w]] for w in succ(v) if w in ix)
    a = np.zeros(n)
    a[ix[s]] = 1.0
    for v in nodes:
        if dist[v] == 0:
            continue
        for w in succ(v):
            if w in ix:
                a[ix[w]] += a[ix[v]]
    C = np.zeros((n, n))
    for v in reversed(nodes):
        i = ix[v]
        C[i, i] = 1.0
        if dist[v] > 0:
            for w in succ(v):
                if w in ix:
                    C[i] += C[ix[w]]
    return b[ix[s]], a, b, C, nodes, {v: dist[s] - dist[v] for v in nodes}


def hit_probabilities(G, s, targets, cands, k):
    """Vector, sobre todos los conjuntos de tamaño k de cands (orden de itertools.combinations), de la probabilidad de
    que el camino más corto elegido al azar por el atacante desde s pase por alguna trampa. None si s no alcanza."""
    res = sp_counts(G, s, targets)
    if res is None:
        return None
    N, a, b, C, nodes, layer = res
    ix = {v: i for i, v in enumerate(nodes)}
    depth = max(layer.values())
    m = len(cands)
    # extender a los candidatos: los que no están en el DAG no cortan ningún camino
    pos = np.array([ix.get(v, -1) for v in cands])
    inD = pos >= 0
    n = len(nodes)
    A = np.zeros(m); Bv = np.zeros(m); CC = np.zeros((m, m))
    A[inD] = a[pos[inD]]; Bv[inD] = b[pos[inD]]
    if inD.any():
        sel = np.where(inD)[0]
        CC[np.ix_(sel, sel)] = C[np.ix_(pos[sel], pos[sel])]
    # el foothold nunca se adquiere: una trampa en s no corta nada
    if s in cands:
        j = cands.index(s)
        A[j] = Bv[j] = 0.0; CC[j, :] = 0.0; CC[:, j] = 0.0
    combos = np.array(list(itertools.combinations(range(m), k)), dtype=np.int64).reshape(-1, k)
    if k > 3:
        raise ValueError("k <= 3")
    lay = np.array([layer.get(v, 10 ** 6) for v in cands])
    S1 = A * Bv
    def pair(x, y):                                        # caminos por x y por y (en cualquier orden)
        return A[x] * CC[x, y] * Bv[y] + A[y] * CC[y, x] * Bv[x]
    cols = [combos[:, i] for i in range(k)]
    P2 = {(i, j): pair(cols[i], cols[j]) for i in range(k) for j in range(i + 1, k)}
    tri = None
    if k == 3:
        tri = np.zeros(len(combos))
        for p, q, r in itertools.permutations(cols):
            tri += A[p] * CC[p, q] * CC[q, r] * Bv[r]

    def hit_upto(c):
        """Probabilidad de que la primera trampa esté en las capas 1..c del camino (inclusión-exclusión restringida)."""
        msk = [lay[col] <= c for col in cols]
        h = sum(S1[col] * mk for col, mk in zip(cols, msk))
        for (i, j), v in P2.items():
            h = h - v * (msk[i] & msk[j])
        if tri is not None:
            h = h + tri * (msk[0] & msk[1] & msk[2])
        return h / N
    hits = hit_upto(10 ** 6)
    # pasos esperados hasta la detección: sum_{c=0}^{d-1} P(sin trampa en las capas 1..c)
    steps = np.full(len(combos), float(depth))
    for c in range(1, depth):
        steps -= hit_upto(c)
    return hits, combos, steps


def sp_optimal(G, k, cands, targets=None, types=None):
    """Colocación que maximiza la probabilidad media de atrapar al atacante de camino más corto. Devuelve
    (B, objetivo, footholds que alcanzan el objetivo)."""
    targets = targets if targets is not None else [v for v in range(G.n) if G.nodes[v].tier == 0]
    types = types or [(1.0 / len(G.starts), s) for s in G.starts]
    cands = list(cands)
    kk = min(k, len(cands))
    tot, stp, wsum, combos, nreach = None, None, 0.0, None, 0
    for p, s in types:
        r = hit_probabilities(G, s, targets, cands, kk)
        if r is None:
            continue
        h, combos, st = r
        tot = h * p if tot is None else tot + h * p
        stp = st * p if stp is None else stp + st * p
        wsum += p; nreach += 1
    if tot is None:
        return None, 0.0, 0                                 # ningún foothold alcanza el objetivo: el modelo no guía
    best = tot.max()
    tie = np.where(tot >= best - 1e-12 * max(1.0, best))[0]
    i = int(tie[np.argmin(stp[tie])])
    return frozenset(cands[j] for j in combos[i]), float(tot[i] / wsum), nreach
