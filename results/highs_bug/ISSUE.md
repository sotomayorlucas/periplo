> **Status (22 Oct 2026): not posted.** The development branch `latest` (commit 3a0555f, 22 Oct 2026), built from source,
> returns the true optimum on all three models with `presolve=off`. Related issues closed in October 2026 include #3387, #3170,
> #3171 and #3180. Keep this only as a record.

# MIP reports "Optimal" with an objective well below the true optimum (presolve off), highspy 1.15.1

## Summary

On three small maximization MIPs (96–152 integer variables), HiGHS 1.15.1 with `presolve=off` returns model status
`Optimal`, with primal and dual bounds equal, at an objective far below the true optimum:

| Model | True optimum | `presolve=off` | `presolve=off`, `mip_root_presolve_only=true` | default options |
| --- | --- | --- | --- | --- |
| trial13_abcde.mps | 68.6962 | 59.4518 | 0.0 | 68.6962 |
| trial80_abcde.mps | 68.6962 | 0.0 | 68.6962 | 68.6962 |
| game_trial1_deltainf.mps | 59.1888 | 1.8400 | 59.1888 | 59.1888 |

All the wrong results are declared after a single node (`mip_node_count = 1`), with `mip_gap = 0`.

The same wrong values appear with highspy 1.12.0, 1.13.1, 1.14.0 and 1.15.1, so this is not a 1.15 regression. Setting `threads=1` does not change them.

The true optima are confirmed in three independent ways:

1. Exhaustive enumeration of the underlying combinatorial problem.
2. CBC 2.10.3 (the one bundled with PuLP) and SCIP 10.0 (via pyscipopt 6.3.0) both find them.
3. HiGHS itself, with the integer variables fixed to SCIP's optimal values, solves the remaining LP to the same objective. So the better solution is feasible for HiGHS's reading of the model.

Default options return the correct value on these three models. In earlier runs of related models, we had also seen
wrong optima with presolve on. Those instances were not kept, so this report covers only the `presolve=off` cases.

## Environment

- highspy 1.15.1 from PyPI (HiGHS 1.15.1), Python 3.13.16, Linux x86_64.
- Models written by PuLP 2.9.0 with `writeMPS`. PuLP puts the objective sense only in a comment (`*SENSE:Maximize`), so the script sets `kMaximize` after reading.

## Reproduce

```bash
pip install highspy==1.15.1
python repro.py
```

`repro.py` solves each MPS under the three option sets above. It then fixes the integer columns to the values in
`optimal_integer_solutions.json` (SCIP's optimum) and re-solves.

Expected output (abridged):

```
trial13_abcde.mps     {'presolve': 'off'}   Optimal  obj 59.4518  dual bound 59.4518  nodes 1  (true optimum 68.696244288)
trial13_abcde.mps     integers fixed to SCIP's optimum -> Optimal, obj 68.6962
trial80_abcde.mps     {'presolve': 'off'}   Optimal  obj  0.0000  dual bound -0.0000  nodes 1  (true optimum 68.696244288)
game_trial1_deltainf.mps {'presolve': 'off'} Optimal obj  1.8400  dual bound  1.8400  nodes 1  (true optimum 59.1888)
```

## Model class

The models are position-indexed sequencing formulations, all sized as follows:

- 224–320 columns, 606–794 rows and 2.6k–3.9k nonzeros;
- binary assignment variables `z[v,k]` and continuous "owned" variables;
- continuous survival variables chained with big-M rows of the form `S[k] <= c_v * S[k-1] + 1 - z[v,k]`.

The two `trial*` models also carry valid inequalities:

- adjacent-swap dominance (set-packing rows on `z`);
- per-position upper bounds on `S`;
- `S[k] <= 1 - own[v,k]`;
- a chord cut `S[k] <= 1 - c * sum lambda_v own[v,k]`.

`game_trial1_deltainf` has none of those inequalities. The coefficients are well scaled:
- survival factors are 0 for "trap" nodes and between 0.70 and 0.97 otherwise;
- rewards lie between 0.5 and 50;
- the big-M constants equal the largest reward.

## Files

Attached as `highs_bug_repro.zip`:
- `trial13_abcde.mps`, `trial80_abcde.mps`, `game_trial1_deltainf.mps`;
- `optimal_integer_solutions.json`, the integer part of SCIP's optimal solution, by column name;
- `repro.py`.
