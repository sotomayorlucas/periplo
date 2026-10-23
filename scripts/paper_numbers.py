"""Genera las tablas y macros del paper a partir de los resultados v2 (certificados sin MILP). Ningún resultado del
paper se tipea a mano; los parámetros de los experimentos (T, k, límites) sí. Con --parcial tolera datos faltantes.
Salida: paper/generated/*.tex"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import json, math, os, statistics as st, sys
R = REPO + "/results"
V2 = f"{R}/v2"
OUT = REPO + "/paper/generated"
os.makedirs(OUT, exist_ok=True)
partial = "--parcial" in sys.argv


def write_tab(name, lines, ncols):
    """Escribe una tabla generada; en modo parcial, una fila de marcador si todavía no hay datos."""
    if not lines:
        lines = [" & ".join([TODO] + [""] * (ncols - 1)) + " \\\\"]
    open(os.path.join(OUT, name), "w").write("\n".join(lines) + "\n\\bottomrule\n")


def load(path):
    try:
        return [json.loads(l) for l in open(path)]
    except FileNotFoundError:
        if not partial:
            raise
        return []


f1 = lambda x: f"{x:.1f}"
f2 = lambda x: f"{x:.2f}"
pct = lambda r, x: 100.0 * x / r["V0"]
macros = {}
TODO = "\\textbf{??}"

# ------------------------------------------------------------------ sintéticos
S = load(f"{V2}/synth.jsonl")
for r in S:
    assert r["V0_exact"], r["task"]
    if not partial:
        assert r["Vmix_cert"] and r["Vvis_cert"], r["task"]
best_heur = lambda r: min(b["v"] for b in r["base"].values())
# línea base: colocación óptima contra el atacante de camino más corto (Ngo et al.), scripts/spopt.py
SPR = {r["task"]: r for r in load(f"{V2}/spopt.jsonl")}
def sp_pct(r, task=None):
    x = SPR.get(task or r["task"])
    if x is None or x["V"] is None:
        return None
    if not partial:
        assert x["exact"], x["task"]
    return pct(r, x["V"])
main = sorted([r for r in S if r["redundancy"] == "media" and r["delta"] == "0.0"], key=lambda r: (r["scale"], r["seed"]))
ratio = lambda r: r["Vmix"] / r["Vvis"]
if main:
    rs = [ratio(r) for r in main]
    macros.update(NMain=len(main), NodesMinMain=min(r["n"] for r in main), NodesMaxMain=max(r["n"] for r in main),
                  MixMean=f1(st.mean(pct(r, r["Vmix"]) for r in main)), VisMean=f1(st.mean(pct(r, r["Vvis"]) for r in main)),
                  HeurMean=f1(st.mean(pct(r, best_heur(r)) for r in main)),
                  UnifMean=f1(st.mean(pct(r, r["uniforme"]["v"]) for r in main)),
                  NaiveMean=f1(st.mean(pct(r, r["naive"]) for r in main)),
                  RatioMean=f2(st.mean(rs)), RatioMin=f2(min(rs)), RatioMax=f2(max(rs)),
                  RedPct=f"{100 * (1 - st.mean(rs)):.0f}", RedMin=f"{100 * (1 - max(rs)):.0f}", RedMax=f"{100 * (1 - min(rs)):.0f}",
                  HeurOverMixMin=f1(min(best_heur(r) / r["Vmix"] for r in main)),
                  HeurOverMixMax=f1(max(best_heur(r) / r["Vmix"] for r in main)),
                  SuppMin=min(r["soporte"] for r in main), SuppMax=max(r["soporte"] for r in main),
                  NRatioOne=sum(x > 0.99 for x in rs))
    spm = [(sp_pct(r), r) for r in main if sp_pct(r) is not None]
    if spm:
        assert all(SPR[r["task"]]["sp_hit"] > 1 - 1e-9 for _, r in spm)   # el texto dice que atrapa a todo atacante de camino más corto
        macros.update(SpMean=f1(st.mean(x for x, _ in spm)), SpNoGuide=len(main) - len(spm), SpGuided=len(spm),
                      SpOverVisMin=f1(min(x / pct(r, r["Vvis"]) for x, r in spm)), SpOverVisMax=f1(max(x / pct(r, r["Vvis"]) for x, r in spm)),
                      SpOverMixMin=f1(min(x / pct(r, r["Vmix"]) for x, r in spm)), SpOverMixMax=f1(max(x / pct(r, r["Vmix"]) for x, r in spm)))
    small = [r for r in main if r["scale"] == 40]; big = [r for r in main if r["scale"] == 60]
    gcpu = lambda r: (r["cpu_do"] + r["cpu_vis"]) / 60
    fm = lambda x: f"{x:.1f}" if x < 10 else f"{x:.0f}"
    if small:
        macros.update(TcpuMainMin=fm(min(map(gcpu, small))), TcpuMainMax=fm(max(map(gcpu, small))))
    if big:
        macros.update(TcpuBigMin=fm(min(map(gcpu, big))), TcpuBigMax=fm(max(map(gcpu, big))))

# tabla por perfil (δ = 0)
alta = {r["seed"]: r for r in load(f"{V2}/alta.jsonl")}
altado = {r["seed"]: r for r in load(f"{V2}/altado.jsonl")}
lines = []
for lab, sel in (("medium", lambda r: r["redundancy"] == "media" and r["scale"] == 40),
                 ("medium", lambda r: r["redundancy"] == "media" and r["scale"] == 60),
                 ("low", lambda r: r["redundancy"] == "baja")):
    xs = [r for r in S if r["delta"] == "0.0" and sel(r)]
    if not xs:
        continue
    nmin, nmax = min(r["n"] for r in xs), max(r["n"] for r in xs)
    nodes = f"{nmin}" if nmin == nmax else f"{nmin}--{nmax}"
    rr = [ratio(r) for r in xs]
    sps = [sp_pct(r) for r in xs if sp_pct(r) is not None]
    spc = (f1(st.mean(sps)) + ("$^\\ddagger$" if len(sps) < len(xs) else "")) if sps else "--"
    lines.append(f"{lab} & {len(xs)} & {nodes} & {f1(st.mean(pct(r, r['Vmix']) for r in xs))} & {f1(st.mean(pct(r, r['Vvis']) for r in xs))} & "
                 f"{f2(st.mean(rr))} ({f2(min(rr))}--{f2(max(rr))}) & {f1(st.mean(pct(r, best_heur(r)) for r in xs))} & "
                 f"{spc} & {st.median(r['cpu_do'] for r in xs):.0f} \\\\")
    if lab == "low":
        macros.update(LowRatioMin=f2(min(rr)), LowRatioMax=f2(max(rr)))
fix = {r["seed"]: r for r in load(f"{V2}/alta_fix.jsonl") if r["cert"]}
for s_, a in alta.items():                 # visible certificada por el candidato de alta_fix.py
    if not a["Vvis_cert"] and s_ in fix:
        a.update(Vvis=fix[s_]["UB"], Vvis_UB=fix[s_]["UB"], Vvis_cert=True, vis_B=fix[s_]["B"])
both = sorted(s for s in alta if s in altado)
if both:
    if not partial:
        assert all(alta[s]["Vvis_cert"] for s in both)
    # cota superior certificada de V*: la mejor D del double oracle cortado (guardada y re-verificada)
    UBmix = {s: altado[s]["Vmix_UB"] for s in both}
    ub = [pct(alta[s], UBmix[s]) for s in both]
    lb = [pct(alta[s], altado[s]["Vmix_LB"]) for s in both]
    vis = [pct(alta[s], alta[s]["Vvis"]) for s in both]
    hb = [pct(alta[s], best_heur(alta[s])) for s in both]
    rr = [u / v for u, v in zip(ub, vis)]
    spa = [sp_pct(alta[s], f"alta:{s}") for s in both]
    spa = [x for x in spa if x is not None]
    lines.append(rf"high$^\dagger$ & {len(both)} & {alta[both[0]]['n']} & $\le$ {f1(st.mean(ub))} & {f1(st.mean(vis))} & "
                 rf"$\le$ {f2(st.mean(rr))} & {f1(st.mean(hb))} & {f1(st.mean(spa)) if spa else '--'} & -- \\")
    nw = sum(UBmix[s] < alta[s]["Vvis_LB"] for s in both)
    macros.update(AltaWinsText=("all three" if nw == 3 == len(both) else f"{nw} of {len(both)}"),
                  AltaWins=nw,
                  AltaTmin=f"{min(altado[s]['t_do'] for s in both) / 60:.0f}", AltaTmax=f"{max(altado[s]['t_do'] for s in both) / 60:.0f}",
                  AltaGapMax=f1(max(u - l for u, l in zip(ub, lb))))
macros.update(NAltaTot=3)
write_tab("tab_synth.tex", lines, 9)

# figura
fig = []
for name, fn in (("Uniform at random", lambda r: pct(r, r["uniforme"]["v"])), ("Shortest-path optimal", sp_pct),
                 ("Best heuristic (ex post)", lambda r: pct(r, best_heur(r))),
                 ("Optimal visible placement", lambda r: pct(r, r["Vvis"])), ("Randomized deception", lambda r: pct(r, r["Vmix"]))):
    xs = [x for x in (fn(r) for r in main) if x is not None] or [0.0]
    fig.append(f"{name} & {st.mean(xs):.2f} & {min(xs):.2f} & {max(xs):.2f}")
open(os.path.join(OUT, "fig_strategies.dat"), "w").write("name & mean & lo & hi\n" + "\n".join(fig) + "\n")

# barrido de δ
dl, dr, tdo = [], [], {}
for d, lab in (("0.0", "0"), ("1.0", "1"), ("3.0", "3"), ("inf", r"$\infty$")):
    xs = [r for r in S if r["redundancy"] == "media" and r["scale"] == 40 and r["seed"] <= 4 and r["delta"] == d]
    if not xs:
        continue
    rr = [ratio(r) for r in xs]
    dr.append(st.mean(rr))
    tdo[d] = st.median(r["cpu_do"] for r in xs)
    smax = max(max(r["dp_do"]["states_max"], r["dp_vis"]["states_max"]) for r in xs)
    dl.append(f"{lab} & {f1(st.mean(pct(r, r['Vmix']) for r in xs))} & {f1(st.mean(pct(r, r['Vvis']) for r in xs))} & "
              f"{f2(st.mean(rr))} ({f2(min(rr))}--{f2(max(rr))}) & {tdo[d]:.0f} & {smax:,}".replace(",", "\\,") + " \\\\")
write_tab("tab_delta.tex", dl, 6)
if dr:
    macros.update(DeltaRatioMin=f2(min(dr)), DeltaRatioMax=f2(max(dr)))
if "0.0" in tdo and "inf" in tdo:
    macros.update(TdoRatio=f"{tdo['0.0'] / tdo['inf']:.1f}")

# ------------------------------------------------------------------ GOAD
G = {(r["adcs"], r["delta"], r["k"]): r for r in load(f"{V2}/goad.jsonl")}
for r in G.values():
    assert r["Vmix_cert"] and r["Vvis_cert"] and r["V0_exact"], r["task"]
P = lambda r, x: (f"{pct(r, x):.2f}" if pct(r, x) < 10 else f"{pct(r, x):.1f}")
gl = []
for adcs, lab in ((False, "no AD~CS"), (True, "AD~CS")):
    for d, dlab in (("inf", r"$\infty$"), ("0", "0")):
        for k in (1, 2, 3):
            r = G.get((adcs, d, k))
            if r is None:
                continue
            b = r["base"]
            first = k == 1
            gl.append(f"{lab if first and d == 'inf' else ''} & {dlab if first else ''} & {f1(r['V0']) if first else ''} & {k} & "
                      f"{P(r, r['Vmix'])} & {P(r, r['Vvis'])} & {P(r, b['chokepoint']['v'])} & {P(r, b['top_valor']['v'])} & "
                      f"{P(r, b['intermediacion']['v'])} & {P(r, SPR[r['task']]['V']) if r['task'] in SPR else '--'} \\\\")
        if adcs is False and d == "0":
            gl.append("\\midrule")
# GOAD con trampas solo en nodos concretos (sin nodos abstractos de dominio)
ND = {(r["adcs"], r["delta"], r["k"]): r for r in load(f"{V2}/goad_nodomain.jsonl")}
for r in ND.values():
    if not partial:
        assert r["Vmix_cert"] and r["Vvis_cert"], r["task"]
if all((True, "inf", k) in ND for k in (1, 2, 3)):
    gl.append("\\midrule")
    for k in (1, 2, 3):
        r = ND[(True, "inf", k)]; b = r["base"]
        gl.append(f"{'AD~CS$^\\ast$' if k == 1 else ''} & {'$\\infty$' if k == 1 else ''} & {f1(r['V0']) if k == 1 else ''} & {k} & "
                  f"{P(r, r['Vmix'])} & {P(r, r['Vvis'])} & {P(r, b['chokepoint']['v'])} & {P(r, b['top_valor']['v'])} & "
                  f"{P(r, b['intermediacion']['v'])} & {P(r, SPR[r['task']]['V']) if r['task'] in SPR else '--'} \\\\")
    n1, n2 = ND[(True, "inf", 1)], ND[(True, "inf", 2)]
    macros.update(GoadNdMixOne=f1(pct(n1, n1["Vmix"])), GoadNdVisOne=f1(pct(n1, n1["Vvis"])),
                  GoadNdMixTwo=f1(pct(n2, n2["Vmix"])), GoadNdVisTwo=f1(pct(n2, n2["Vvis"])),
                  GoadNdHeurTwo=f"{min(pct(n2, b['v']) for b in n2['base'].values()):.0f}",
                  GoadNdSameNo=int(all(abs(ND[(False, d, k)]["Vmix"] - G[(False, d, k)]["Vmix"]) < 1e-9
                                       for d in ("inf", "0") for k in (1, 2, 3) if (False, d, k) in ND)))
    if all((True, "0", k) in ND for k in (1, 2, 3)):
        z1, z2 = ND[(True, "0", 1)], ND[(True, "0", 2)]
        macros.update(GoadNdZeroMixOne=f1(pct(z1, z1["Vmix"])), GoadNdZeroVisOne=f1(pct(z1, z1["Vvis"])),
                      GoadNdZeroMixTwo=f1(pct(z2, z2["Vmix"])), GoadNdZeroVisTwo=f1(pct(z2, z2["Vvis"])))
gsp = [(r, SPR[r["task"]]["V"]) for r in list(G.values()) + list(ND.values()) if r["task"] in SPR and SPR[r["task"]]["V"] is not None]
if gsp:
    macros.update(GoadSpTot=len(gsp), GoadSpEqVis=sum(abs(v - r["Vvis"]) <= 1e-6 * max(1, r["Vvis"]) for r, v in gsp),
                  GoadSpMaxOverVis=f1(max(v / r["Vvis"] for r, v in gsp if r["Vvis"] > 0)))
    if (True, "inf", 1) in ND and ND[(True, "inf", 1)]["task"] in SPR:
        r = ND[(True, "inf", 1)]; macros.update(GoadNdSpOne=f1(pct(r, SPR[r["task"]]["V"])))
write_tab("tab_goad.tex", gl, 10)
if len(G) == 12:
    a1, a2, n1 = G[(True, "inf", 1)], G[(True, "inf", 2)], G[(False, "inf", 1)]
    macros.update(GoadMixAdcsOne=f1(pct(a1, a1["Vmix"])), GoadVisAdcsOne=f1(pct(a1, a1["Vvis"])),
                  GoadMixAdcsTwo=f2(pct(a2, a2["Vmix"])), GoadChokeAdcsTwo=f1(pct(a2, a2["base"]["chokepoint"]["v"])),
                  GoadChokeOverMixTwo=f"{a2['base']['chokepoint']['v'] / a2['Vmix']:.0f}",
                  GoadVisNoOne=f1(pct(n1, n1["Vvis"])),
                  GoadZeroNo=sum(x["V0"] < 1e-12 for x in n1["V0_types"]), GoadZeroAdcs=sum(x["V0"] < 1e-12 for x in a1["V0_types"]),
                  GoadCpuMax=f"{max(r['cpu_do'] + r['cpu_vis'] for r in G.values()):.0f}")
    assert a2["base"]["chokepoint"]["B"] != a2["vis_B"]

# ------------------------------------------------------------------ sensibilidad
sl = []
SENS = {}
for k in (1, 2):
    rows = load(f"{V2}/sens_k{k}.jsonl")
    SENS[k] = rows
    for tipo, lab in (("un_parametro", r"one role parameter $\times\{0.5, 1.5\}$"), ("ruido_nodo", r"per-node noise $\times U[0.5, 1.5]$")):
        xs = [r for r in rows if r.get("tipo") == tipo]
        if not xs:
            continue
        if not partial:
            assert all(r["Vmix_cert"] and r["Vvis_cert"] and r["nom_eval_exact"] for r in xs)
        adv = [pct(r, r["Vvis"] - r["Vmix"]) for r in xs]; reg = [pct(r, r["regret_D"]) for r in xs]
        wins = sum(r["Vmix"] < r["Vvis"] - 1e-4 * r["V0"] for r in xs)
        sl.append(f"{k} & {lab} & {len(xs)} & {wins} / {len(xs) - wins} & {min(adv):.2f}--{max(adv):.2f} & {st.median(reg):.2f} / {max(reg):.2f} \\\\")
write_tab("tab_sens.tex", sl, 6)
summ = {r["k"]: r for r in load(f"{V2}/sens.jsonl")}
if 1 in summ and SENS.get(1):
    s1 = SENS[1]; sm = summ[1]
    nom = [r for r in s1 if r["tipo"] == "nominal"][0]
    pert = [r for r in s1 if r.get("tipo") in ("un_parametro", "ruido_nodo")]
    macros.update(SensRegretMaxOne=f2(max(pct(r, r["regret_D"]) for r in pert)),
                  SensRegretMaxRoleOne=f2(max(pct(r, r["regret_D"]) for r in pert if r["tipo"] == "un_parametro")),
                  SensRoleTop=", ".join(sorted({r["etiqueta"].split(".")[0] for r in sorted(
                      [r for r in pert if r["tipo"] == "un_parametro"], key=lambda r: -r["regret_D"] / r["V0"])[:4]})),
                  SensVisChange=sum(1 for r in s1 if r.get("tipo") == "ruido_nodo" and r["vis_cambia"]),
                  CornerVzeroOne=f1(sm["V0_esquina"] / sm["V0_nominal"]),
                  PriceRobAbsOne=f1(sm["V_Drob_en_nominal"] - sm["Vmix_nominal"]),
                  PriceRobPctOne=f1(100 * (sm["V_Drob_en_nominal"] - sm["Vmix_nominal"]) / sm["V0_nominal"]),
                  RegretCornerAbsOne=f1(sm["V_Dnom_en_esquina"] - sm["Vmix_esquina"]),
                  RegretCornerPctOne=f1(100 * (sm["V_Dnom_en_esquina"] - sm["Vmix_esquina"]) / sm["V0_nominal"]))
macros.update(SensCount=sum(1 for k in (1, 2) for r in SENS.get(k, []) if r.get("tipo") in ("un_parametro", "ruido_nodo")))

# ------------------------------------------------------------------ certificados
NC = 2 * len(G) + 2 * len(S) + 2 * sum(1 for k in (1, 2) for r in SENS.get(k, []) if r.get("tipo") != "nominal") + len(alta)
NI = len(altado)                                   # intervalos (double oracle cortado)
import glob
ver = [json.loads(l) for f in sorted(glob.glob(f"{V2}/verify_ub_*.jsonl")) for l in open(f)]
nver = sum(("mix_ok" in v) + ("vis_ok" in v) for v in ver if not v["label"].startswith(("altado", "goadnd")))
macros.update(NCert=NC, NInterval=NI)
if not partial:
    dup = 4                                        # sens nominal k=1,2 (mezcla y visible) == goad:1:inf:{1,2}
    assert nver - dup == NC, (nver, NC)
    assert all(v.get("mix_ok", True) and v.get("vis_ok", True) for v in ver), "re-verificación con fallas"
    assert sum(1 for v in ver if v["label"].startswith("altado")) == NI
gaps = [(r["Vmix_UB"] - r["Vmix_LB"]) / max(1, r["Vmix_UB"]) for r in list(G.values()) + S + [x for k in (1, 2) for x in SENS.get(k, [])]]
gaps += [(r["Vvis_UB"] - r["Vvis_LB"]) / max(1, r["Vvis_UB"]) for r in list(G.values()) + S + [x for k in (1, 2) for x in SENS.get(k, [])]]
gm = max(gaps)
e = math.floor(math.log10(gm)) if gm > 0 else -16
macros.update(GapMaxConv=f"10^{{{e + 1}}}")
nmax = max([r["n"] for r in S if r.get("Vmix_cert")] + [46])
macros.update(NodesMaxCert=nmax, EnumSetsMax=f"{math.comb(143, 3):,}".replace(",", "\\,"))

# ------------------------------------------------------------------ ablación
AB = load(f"{R}/ablation.jsonl")
al = []
if AB:
    for grp, lab, sel in (("goad", "GOADv2", lambda x: x["inst"].startswith("goad")), ("syn", "synthetic", lambda x: x["inst"].startswith("synth"))):
        xs = [x for x in AB if sel(x)]
        keys = sorted({(x["inst"], x["start"]) for x in xs})
        macros["AblGoadN" if grp == "goad" else "AblSynN"] = len(keys)
        solved_all = [kk for kk in keys if all(x["status"] == "Optimal" for x in xs if (x["inst"], x["start"]) == kk)
                      and sum(1 for x in xs if (x["inst"], x["start"]) == kk) == 5]
        for nb in ("0", "4", "8", "12", "all"):
            ys = [x for x in xs if str(x["n_big"]) == nb]
            ok = [x for x in ys if x["status"] == "Optimal"]
            nonzero = {(x["inst"], x["start"]) for x in xs if str(x["n_big"]) == "0" and x["states"] > 0}
            com = [x["states"] for x in ok if (x["inst"], x["start"]) in nonzero]
            al.append(f"{lab if nb == '0' else ''} & {nb} & {len(ok)} / {len(ys)} & "
                      f"{(f'{st.median(com):,.0f} / {max(com):,}' if com else '--').replace(',', '{,}')} & {max(x['cpu'] for x in ys):.1f} \\\\")
        al.append("\\midrule")
    g = [x for x in AB if x["inst"].startswith("goad")]
    fail = [x for x in g if str(x["n_big"]) == "0" and x["status"] != "Optimal"]
    w12 = {(x["inst"], x["start"]): x for x in g if str(x["n_big"]) == "12"}
    macros.update(AblPlainFail=len(fail),
                  AblPlainFailStates=f"{min(x['states'] for x in fail) / 1e6:.1f}" if fail else "0",
                  AblFailWithExcl=max(w12[(x["inst"], x["start"])]["states"] for x in fail) if fail else 0)
    sy = [x for x in AB if x["inst"].startswith("synth")]
    by = {}
    for x in sy:
        by.setdefault((x["inst"], x["start"]), {})[str(x["n_big"])] = x["states"]
    macros.update(AblSynSame=sum(1 for v in by.values() if len({v.get(n) for n in ("0", "4", "8", "12")}) == 1),
                  AblSynTotalDiff=f"{100 * (sum(v['0'] for v in by.values()) / sum(v['12'] for v in by.values()) - 1):.1f}",
                  AblSynMaxAbsDiff=max(v["0"] - v["12"] for v in by.values()))
if al and al[-1] == "\\midrule":
    al.pop()
write_tab("tab_ablation.tex", al, 5)

# ------------------------------------------------------------------ lecciones (datos de la primera ronda, beam)
OLD = load(f"{R}/exact_delta_f.jsonl")
if OLD:
    bias = [(r["Vmix_viejo_exacto"] / r["Vmix_viejo_beam"], str(r["delta"])) for r in OLD]
    vis_v2 = {(r["seed"], r["delta"]): r["Vvis"] for r in S if r["scale"] == 40 and r["redundancy"] == "media"}
    worse = sum(1 for r in OLD if r["Vmix_viejo_exacto"] > vis_v2.get((r["seed"], str(r["delta"])), r["Vvis"]) + 1e-9)
    macros.update(BeamAvgReported=f1(st.mean(pct(r, r["Vmix_viejo_beam"]) for r in OLD)),
                  BeamAvgExact=f1(st.mean(pct(r, r["Vmix_viejo_exacto"]) for r in OLD)))
    macros.update(BeamBiasMax=f2(max(b for b, _ in bias)), BeamBiasOverFive=sum(b > 1.05 for b, _ in bias),
                  BeamExactOther=sum(abs(b - 1) <= 1e-6 for b, d in bias if d != "0.0"), BeamWorseCount=worse)
    assert all(d == "0.0" for b, d in bias if b > 1.05)
BS = [x for x in load(f"{R}/bench_set.jsonl") if x["caso"] == "mezcla" and x["st"] == "timelimit"]
if BS:
    macros.update(SetBoundMin=f1(min(x["UB_conjuntos"] / x["LB"] for x in BS)), SetBoundMax=f1(max(x["UB_conjuntos"] / x["LB"] for x in BS)))
cert = {}
for f in ("goad_adcs_s_cert.jsonl", "goad_adcs_sinf_cert.jsonl", "goad_v2_s_cert.jsonl"):
    for c in load(f"{R}/{f}"):
        cert[(str(c["delta"]), c["k"], c["adcs"])] = c["brecha_juego_pctV0"]
if cert:
    macros.update(MilpGapMax=f"{max(cert.values()):.0f}")

# suite contra fuerza bruta (results/tests_v2.txt, scripts/run_tests.sh)
import re as _re
try:
    tl = {l.split("\t")[0]: l for l in open(f"{R}/tests_v2.txt") if "\t" in l}
    m = _re.search(r"instancias (\d+); fallas (\d+)", tl["tests/test_exact.py"])
    assert m and m.group(2) == "0"
    g = _re.search(r"instancias (\d+); DO != LP completo: (\d+); visible != fuerza bruta: (\d+)", tl["tests/test_game.py exact"])
    assert g and g.group(2) == "0" and g.group(3) == "0"
    e = _re.search(r"test_enum: (\d+) instancias, (\d+) fallas", tl["tests/test_enum.py"])
    assert e and e.group(2) == "0"
    macros.update(NTestExact=m.group(1), NTestGame=g.group(1), NTestEnum=e.group(1))
except (FileNotFoundError, KeyError, AssertionError):
    if not partial:
        raise
with open(os.path.join(OUT, "numbers.tex"), "w") as fh:
    for k, v in macros.items():
        fh.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")
# macros que faltan (modo parcial): marcarlas en el PDF
need = set()
import re
for m in re.findall(r"\\([A-Z][A-Za-z]+)", open(REPO + "/paper/main.tex").read()):
    need.add(m)
known = set(macros) | {"Cref", "DeclareMathOperator", "Exp", "R", "Bigl", "Bigr", "Comment", "EndFor", "EndIf", "EndWhile",
                       "For", "If", "Lambda", "Pi", "Repeat", "Require", "Return", "State", "Until", "While"}
missing = sorted(need - known)
with open(os.path.join(OUT, "numbers.tex"), "a") as fh:
    for m in missing:
        fh.write(f"\\newcommand{{\\{m}}}{{{TODO}}}\n")
print(json.dumps(macros, default=str))
print("FALTAN:", missing)
