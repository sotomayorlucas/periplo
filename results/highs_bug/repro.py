"""Reproducer: HiGHS 1.15.1 (highspy) reports "Optimal" for MIPs whose true optimum is higher (maximization).

Models were written by PuLP 2.9.0; the objective sense is only in a comment ("*SENSE:Maximize"), so it is set here.
True optima: 68.696244288 (trial13_abcde, trial80_abcde) and 59.1888 (game_trial1_deltainf), confirmed by
exhaustive enumeration of the underlying combinatorial problem, CBC 2.10.3 and SCIP 10.0.
Second check: fixing the integer variables to SCIP's optimal values (optimal_integer_solutions.json) and solving
the remaining LP with HiGHS itself gives the higher objective, so that solution is feasible for HiGHS too."""
import glob, json, os
import highspy

here = os.path.dirname(os.path.abspath(__file__))
OPT = {"trial13_abcde.mps": 68.696244288, "trial80_abcde.mps": 68.696244288, "game_trial1_deltainf.mps": 59.1888}
SOLS = json.load(open(os.path.join(here, "optimal_integer_solutions.json")))
CONFIGS = [dict(), dict(presolve="off"), dict(presolve="off", mip_root_presolve_only=True)]


def load(path, opts):
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    for k, v in opts.items():
        h.setOptionValue(k, v)
    h.readModel(path)
    h.changeObjectiveSense(highspy.ObjSense.kMaximize)
    return h


print("highspy", highspy.Highs().version() if hasattr(highspy.Highs(), "version") else "")
for f in sorted(glob.glob(os.path.join(here, "*.mps"))):
    name = os.path.basename(f)
    for opts in CONFIGS:
        h = load(f, opts)
        h.run()
        info = h.getInfo()
        print(f"{name:28s} {str(opts or 'default'):55s} {h.modelStatusToString(h.getModelStatus()):8s} "
              f"obj {info.objective_function_value:10.4f}  dual bound {info.mip_dual_bound:10.4f}  nodes {info.mip_node_count}  "
              f"(true optimum {OPT[name]})")
    # fijar las enteras a la solución de SCIP y resolver el LP restante con HiGHS
    h = load(f, dict(presolve="off"))
    lp = h.getLp()
    names = [h.getColName(j)[1] for j in range(lp.num_col_)]
    sol = SOLS[name]
    for j, nm in enumerate(names):
        if nm in sol:
            val = round(sol[nm])
            h.changeColBounds(j, val, val)
    h.run()
    print(f"{name:28s} integers fixed to SCIP's optimum -> {h.modelStatusToString(h.getModelStatus())}, "
          f"obj {h.getInfo().objective_function_value:.4f}")
