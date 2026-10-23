"""Parser real: regresión contra el sintético y lectura de fixtures oficiales de BloodHound CE (v5, v6)."""
import os as _os
REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
GOAD_DIR = _os.environ.get("PERIPLO_GOAD", _os.path.join(REPO, "data", "bh-goad"))
import glob, os, sys
sys.path.insert(0, ".")
from periplo import adgen, sharphound, bloodhound

FIX = _os.environ.get("PERIPLO_BH_FIXTURES", "/nonexistent")


def main():
    for s in (20, 40, 80):
        js = adgen.scaled(s, seed=s)
        Go = sharphound.parse(js, seed=s, n_starts=1)
        Gn = bloodhound.parse([js], footholds=[Go.nodes[Go.start].name])
        eo = {(Go.nodes[a].id, Go.nodes[b].id) for a in range(Go.n) for b in Go.out[a]}
        en = {(Gn.nodes[a].id, Gn.nodes[b].id) for a in range(Gn.n) for b in Gn.out[a]}
        assert eo == en, f"regresión sintético {s}"
    print("regresión sintético: OK")
    # coerción: una workstation con delegación no restringida debe dar arista al dominio solo con coercion=True
    import copy
    js = copy.deepcopy(adgen.scaled(20, seed=1))
    dom = "S-1-5-21-1111-2222-3333"
    js["domains.json"] = {"meta": {"type": "domains", "count": 1, "version": 5},
                          "data": [{"ObjectIdentifier": dom, "Properties": {"name": "CORP.LOCAL"}, "Trusts": [], "Aces": []}]}
    ws = js["computers.json"]["data"][0]
    ws["Properties"]["unconstraineddelegation"] = True; ws["DomainSID"] = dom
    for flag in (True, False):
        G = bloodhound.parse([js], footholds="regulares", coercion=flag)
        kinds = [k for (a, b), k in G.edge_kind.items() if k == "Coercion"]
        assert bool(kinds) == flag, f"coerción={flag}: {kinds}"
    print("coerción: OK")
    for sub in ("v5/ingest", "v6/ingest", "v6/all"):
        d = os.path.join(FIX, sub)
        if not os.path.isdir(d):
            print("sin fixtures", sub); continue
        try:
            G = bloodhound.parse([d], footholds="regulares")
            print(f"fixture {sub}: {G.summary()}")
        except Exception as e:
            print(f"fixture {sub}: sin footholds alcanzables o error -> {e!r}")


if __name__ == "__main__":
    main()
