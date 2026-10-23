"""Ablación de la cota de completamiento del programa dinámico exacto: cuántos nodos de alto botín ya adquiridos se
excluyen de la cota de índice (0 = cota simple, 4, 8, 12 = valor usado, todos). Mejores respuestas del atacante
contra las mezclas óptimas certificadas de results/v2 (todas las de GOAD y una muestra de sintéticos).
Mismo incumbente inicial (beam de ancho 50) para todas las variantes. Límites: 3M estados, 300 s.
Uso: python -u scripts/ablation.py salida.jsonl"""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import glob, json, math, sys, time
sys.path.insert(0, REPO)
from periplo import adgen, sharphound, bloodhound, game, attacker as A

out = sys.argv[1]
GOAD = sorted(glob.glob(GOAD_DIR + "/*BloodHound-2.3.3.zip"))
SETTINGS = [0, 4, 8, 12, "all"]
done = set()
try:
    done = {(r["inst"], r["start"], str(r["n_big"])) for r in map(json.loads, open(out))}
except FileNotFoundError:
    pass


def run(inst, G, rec, delta):
    idx = {nd.name: i for i, nd in enumerate(G.nodes)}
    D = [(w, frozenset(idx[x] for x in names)) for w, names in rec["D"]]
    for _, sname in rec["types"]:
        s = idx[sname]
        Gt = G.with_start(s)
        inc = A.beam(Gt, D, 12.0, delta, width=50)
        for nb in SETTINGS:
            if (inst, sname, str(nb)) in done:
                continue
            n_big = G.n if nb == "all" else nb
            t0, c0 = time.time(), time.process_time()
            v, seq, ub, st, stats = A.exact(Gt, D, 12.0, delta, incumbent=inc, n_big=n_big, max_states=3_000_000, time_limit=300.0)
            r = dict(inst=inst, start=sname, n_big=nb, value=v, ub=ub, status=st, states=stats.get("states", 0),
                     t=time.time() - t0, cpu=time.process_time() - c0, n=G.n, scen=len(D))
            with open(out, "a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(json.dumps(r), flush=True)


Gs = {a: bloodhound.parse(GOAD, footholds="regulares", adcs=a) for a in (False, True)}
for rec in map(json.loads, open(REPO + "/results/v2/goad.jsonl")):
    d = math.inf if rec["delta"] == "inf" else float(rec["delta"])
    run(rec["task"], Gs[rec["adcs"]], rec, d)
sample = {"synth:media:40:1:0.0", "synth:media:40:2:0.0", "synth:media:40:1:inf", "synth:media:40:2:inf"}
for rec in map(json.loads, open(REPO + "/results/v2/synth.jsonl")):
    if rec["task"] in sample:
        G = sharphound.parse(adgen.scaled(rec["scale"], seed=rec["seed"], redundancy=rec["redundancy"]), seed=rec["seed"], n_starts=5)
        d = math.inf if rec["delta"] == "inf" else float(rec["delta"])
        run(rec["task"], G, rec, d)
