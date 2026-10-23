import json, collections, sys
for f in ("results/solver_cuts.jsonl", "results/solver_stress.jsonl"):
    rows = [json.loads(l) for l in open(f)]
    agg = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0, 0.0])
    fails = collections.defaultdict(list)
    for r in rows:
        for k, v in r.items():
            if isinstance(v, dict):
                a = agg[k]; a[0] += 1; a[1] += (not v["ok_val"]); a[2] += (not v["ok_bound"]); a[3] += v["t"]; a[4] += (v["st"] != "Optimal"); a[5] = max(a[5], v["t"])
                if not (v["ok_val"] and v["ok_bound"]):
                    fails[k].append((r["trial"], r["delta"], v["st"]))
    print(f, len(rows), "instancias")
    for k, a in agg.items():
        print(f"  {k:14s} valor_mal={a[1]:3d} cota_inválida={a[2]:3d} no_opt={a[4]:3d} t_medio={a[3]/max(a[0],1):6.2f}s t_max={a[5]:6.1f}s  {fails[k][:6]}")
