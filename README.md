# PERIPLO

Code, data pointers and certificates for the paper *Certified Randomized Deception against Multi-Target Attackers
in Active Directory Attack Graphs* (`paper/main.tex`).

A defender places at most `k` traps on existing nodes of an Active Directory attack graph. An attacker with an
unknown foothold acquires nodes in sequence under a time budget `T`; every acquisition of node `v` is detected with
probability `q_v`, a trap is detected with certainty, and detection ends the intrusion. Loot `r_v` is collected only
for undetected acquisitions. A pivot-switch cost `delta` interpolates between credential accumulation (`delta = 0`)
and a single route (`delta = inf`). The defender randomizes over trap sets (Bayesian zero-sum game over footholds);
the *visible* variant uses a single trap set known to the attacker.

Every game value reported in the paper comes with a certificate that is checked **without any MILP or LP solver**:
an exact dynamic program for the attacker side and exhaustive enumeration of trap sets for the defender side.

## Layout

| Path | Contents |
| --- | --- |
| `periplo/bloodhound.py` | Parser for BloodHound JSON collections (formats v3–v6, SharpHound or BloodHound.py, one or several domains). Tested on the v5/v6 fixtures of BloodHound CE and on the GOADv2 collection. Arc types: local admin (with group expansion), sessions, abusable ACEs on users and computers, group control, constrained and resource-based delegation, DCSync, DCs and Domain Admins, parent–child trusts and trusts without SID filtering, AD CS (ESC1, ESC3 via enrollment agents, ESC4, ESC6) and coercion towards unconstrained delegation (`adcs=`, `coercion=` flags). |
| `periplo/adgen.py`, `periplo/sharphound.py` | Synthetic SharpHound-like generator with three path-redundancy profiles (`adgen.PROFILES`, `adgen.scaled`) and its parser. |
| `periplo/graph.py` | `AttackGraph`, feasibility, `value(G, seq, traps)` = U(pi, B). |
| `periplo/attacker.py` | Attacker oracles. `exact` is Algorithm 1 (exact best response against a trap mixture); `index_knapsack` is the completion bound of Lemma 1; `beam` is the beam search used for cheap columns and incumbents. Also legacy MILP bounds (`milp`, `set_bound`, `group_bound`) used only for the comparison in Section 5. |
| `periplo/game.py` | `double_oracle(..., oracle="exact")` is Algorithm 2; `exact_br` wraps `attacker.exact`; `defender_br_enum` (defender best response) and `visible_lb_enum` (master of the visible variant) enumerate all k-subsets; `visible_interdiction(..., oracle="exact")` solves the visible variant; `baselines`, `uniform_mixture`. |
| `scripts/run_v2.py` | Runs every experiment of the paper and stores the certificates in `results/v2/`. |
| `scripts/verify_certs.py` | Independent re-verification of the stored certificates. |
| `scripts/ablation.py` | Ablation of the completion bound (Table 2 of the paper). |
| `scripts/goad_nodomain.py` | GOADv2 with traps restricted to concrete nodes (no abstract "domain compromised" nodes). |
| `scripts/alta_fix.py` | Certifies a high-redundancy visible placement whose first candidate set hit the state limit, by evaluating other candidate sets against the same lower bound. |
| `scripts/run_tests.sh` | Runs the brute-force test suite and logs it to `results/tests_v2.txt`. |
| `scripts/paper_numbers.py` | Generates every result-dependent number and table of the paper into `paper/generated/`. |
| `tests/` | Brute-force checks of all oracles and of the game solvers. |
| `results/v2/` | Results and certificates used by the paper. Older files in `results/` are kept for the history described in `NOTAS.md` (Spanish); the paper uses them only for the evaluation-bias lesson (Section 7). |

## Mapping paper → code

| Paper | Code |
| --- | --- |
| Proposition 1 (index rule) | ordering by `r_v c_v / (1 - c_v)` in `attacker.index_knapsack` |
| Lemma 1 (completion bound) | `attacker.index_knapsack` (knapsack in reverse index order, Horner step `c_v (r_v + x)`, Pareto list of (time, value) pairs so times may be real) and `rem_bound` inside `attacker.exact`, which excludes the owned nodes among the `n_big = 12` reachable nodes with the largest loot and memoizes by that subset |
| Proposition 2 (set sufficiency) | state keys in `attacker.exact`: acquired set (`delta = 0`), (set, last node) (`delta = inf`), (set, last node) with Pareto (time, value) labels (finite `delta > 0`) |
| Algorithm 1 | `attacker.exact(G, scenarios, T, delta, incumbent, max_states, time_limit, n_big)`; on a state or time limit it returns a valid upper bound |
| Algorithm 2 | `game.double_oracle(G, T, delta, k, oracle="exact", time_limit=None)`; returns the mixture `D` that achieved the best upper bound, the attacker strategy `sigma` that achieved the best lower bound, `LB`, `UB` and `certified` |
| Visible variant | `game.visible_interdiction(G, T, delta, k, oracle="exact")`; returns `B`, `LB`, `UB` and the attacker pools |
| Defender best response | `game.defender_br_enum` (used whenever C(n, k) <= `game.ENUM_MAX_SETS` = 3,000,000; otherwise a MILP fallback that the paper never uses) |

## Certificates

For the randomized game, a certificate is a pair (`D`, `sigma`):

* **upper bound**: `UB = sum_t mu_t max_pi E_{B~D} U(pi, B)`, the attacker's best response to `D` over *all*
  sequences, computed with `attacker.exact`;
* **lower bound**: `LB = min_{|B| = k} sum_t mu_t E_{pi~sigma_t} U(pi, B)`, the defender's best response to `sigma`
  over *all* trap sets, computed by enumeration.

When a best response reached a state or time limit (only in the time-capped high-redundancy runs), its upper bound
depends on where the search stopped; the verifier then accepts a recomputed bound that is at most the recorded one,
since V* <= recomputed <= recorded. The upper-bound side of the verification re-runs `attacker.exact`, so it relies on that function being correct; it is
checked against brute force in `tests/test_exact.py`. Any `D` gives a valid upper bound and any `sigma` a valid lower
bound on the game value, so the certificate does not
depend on the linear program solved inside the double oracle (HiGHS through SciPy), which only proposes strategies.
For the visible variant the certificate is (`B`, attacker pools): `UB` is the exact value of `B`, and
`LB = min_B sum_t mu_t max_{pi in pool_t} U(pi, B)` by enumeration. Sets of size exactly `k` suffice because `U` is
non-increasing in `B`.

Each record in `results/v2/{goad,synth,sens_k1,sens_k2}.jsonl` stores, besides the values:

| Field | Meaning |
| --- | --- |
| `D` | list of `[weight, [node names]]` (the defender mixture behind `Vmix_UB`) |
| `sigma` | per type, list of `[probability, [node names in order]]` (the attacker strategy behind `Vmix_LB`) |
| `types` | list of `[prior, foothold name]` |
| `vis_B`, `pools` | the visible placement and, per type, the attacker sequences of the master problem |
| `Vmix_LB`, `Vmix_UB`, `Vmix_cert`, `Vvis_LB`, `Vvis_UB`, `Vvis_cert` | bounds and flags |
| `dp_do`, `dp_vis` | dynamic-program statistics: calls, states (sum, max), CPU seconds, limits reached |
| `cpu_do`, `cpu_vis`, `t_do`, `t_vis` | CPU and wall-clock seconds |

`results/v2/alta.jsonl` and `results/v2/altado.jsonl` hold the high-redundancy runs (visible placement certified;
double oracle capped at one hour, so the mixture has a certified interval rather than a zero gap).

## Reproducing

Requirements: Python 3.10 or later with `numpy`, `scipy`, `networkx` (tested with Python 3.13, NumPy 2.5.3,
SciPy 1.18.1, NetworkX 3.7). `pulp` and `pyscipopt` are needed only for the legacy MILP code and its tests.

```bash
pip install numpy scipy networkx                 # core
pip install pulp==2.9.0 pyscipopt                # only for legacy MILP code and tests

python tests/test_exact.py        # attacker.exact vs brute force (delta in {0, 1, 2.5, inf}, mixtures)
python tests/test_enum.py         # defender and visible-master enumeration vs brute force
python tests/test_game.py exact   # double oracle (also time-capped) and visible variant vs the fully enumerated game
python tests/test_robust.py       # box robustness (Proposition 3)
python tests/test_bloodhound.py   # parser (needs the BloodHound CE fixtures; skipped if absent)
```

The GOADv2 collection is the public sample data at <https://github.com/m4lwhere/Bloodhound-CE-Sample-Data>
(SharpHound v2.3.3, released into the public domain under the Unlicense). The three `*_BloodHound-2.3.3.zip` files,
with their README and LICENSE, are copied in `data/bh-goad/`; set `PERIPLO_GOAD` to use another directory. The
parser test reads the BloodHound CE fixtures from `PERIPLO_BH_FIXTURES` and is skipped without them. Run every
command from the repository root.

```bash
python -u scripts/run_v2.py 115          # one worker, 115-minute budget; start several to share the queue
python -u scripts/goad_nodomain.py
python scripts/alta_fix.py
python scripts/verify_certs.py --ub goad synth sens alta altado goadnd   # LB by enumeration, UB by the DP
sh scripts/run_tests.sh
python -u scripts/ablation.py results/ablation.jsonl
python scripts/paper_numbers.py          # writes paper/generated/
cd paper && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

`run_v2.py` keeps a shared task queue in `results/v2/claims/` and is resumable: a task is skipped once its record
exists, and a worker starts a task only if its time estimate fits the remaining budget.

## Parameters used in the paper

| Parameter | Value |
| --- | --- |
| Time budget `T` | 12 |
| Traps `k` | 3 (synthetic); 1, 2, 3 (GOADv2) |
| Footholds | 5 random workstations (synthetic); 22 non-privileged users (GOADv2); uniform prior |
| Best-response limits | 3,000,000 states, 600 s (`game.EXACT_MAX_STATES`, `game.exact_br`) |
| Beam seed width | 50 |
| Double-oracle tolerance | 1e-6; visible variant: 1e-4 relative |
| Uniform baseline | 64 random k-sets of non-foothold nodes |
| Heuristics | most valuable nodes, betweenness, chokepoints of shortest paths to tier 0 (non-foothold nodes) |
| High-redundancy double oracle | one-hour cap |

Node parameters by role are in Table 1 of the paper and in `periplo/bloodhound.py` (`VALUATION`). They are
assumptions, not measurements.

## Hardware and timing

All runs used a cloud machine with 2 vCPUs and 7 GB of memory, with two single-threaded jobs at a time. The paper
reports CPU time (`cpu_*` fields); wall-clock times (`t_*`) are affected by the concurrent job.

## Dual use

`attacker.exact` computes an optimal attack order on BloodHound data against a given trap mixture, so it is also an
attack planner. The marginal risk is low (BloodHound already computes attack paths, and an offensive operator does not
need certified optimality), but users should know it.

## Limitations

* The parser does not cover GPO abuse, ESC8 or NTLM relay. An unprivileged collection (no local administrators,
  few sessions) hides paths that exist.
* Certification by enumeration is practical for small `k` (here `k <= 3`).
* `attacker.exact` is exponential in the worst case; see the paper for the sizes where it was certified.

## License

MIT (see `LICENSE`). The files in `data/bh-goad/` keep their own license (Unlicense).

## Citation

If you use this code, please cite the paper (citation to be updated after review):

> L. Sotomayor. *Certified Randomized Deception against Multi-Target Attackers in Active Directory Attack Graphs.*
> Manuscript, 2026.
