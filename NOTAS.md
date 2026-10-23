# PERIPLO — notas internas (español)

El README del artefacto, en inglés, es `README.md`. Este archivo guarda la historia y las advertencias de desarrollo.

Juego de decepción sobre grafos de ataque de Active Directory: el defensor coloca k trampas
(honeytokens o sensores de alta fidelidad) sin saber por qué foothold entra el atacante; cada atacante
adquiere nodos en secuencia bajo un presupuesto de tiempo, con riesgo de detección multiplicativo.

## Modelo

- Grafo efectivo usuarios + computadoras (grupos contraídos): AdminTo, HasSession, ACL abusables.
- Nodo v: valor r, tiempo de adquisición p, probabilidad de detección base q (supuestos por rol, ver `sharphound.DEFAULT_VALUATION`).
- Secuencia factible: cada nodo tiene un in-vecino ya controlado; tiempo = Σ p + δ · (#cambios de pivote) ≤ T.
  - δ = 0: modelo acumulativo (credenciales).
  - δ = ∞: ruta pura sobre aristas (la premisa TSP/orienteering literal).
- Pago: botín cobrado antes de la primera trampa, descontado por supervivencia.
- Juego bayesiano de suma cero sobre footholds; el atacante conoce la política, no la realización.

## Módulos

| Archivo | Qué hace |
| --- | --- |
| `periplo/adgen.py` | AD sintético en formato tipo SharpHound, con perfiles de redundancia |
| `periplo/sharphound.py` | Parser mínimo para el JSON sintético |
| `periplo/bloodhound.py` | Parser de colecciones reales (SharpHound/BloodHound.py v3–v6, varios dominios): ACL, control de grupos, DCSync, trusts, delegaciones, sesiones, ADCS (ESC1, ESC3, ESC4, ESC6) y coerción con delegación no restringida |
| `periplo/graph.py` | Modelo, factibilidad, valor esperado |
| `periplo/attacker.py` | Oráculos: fuerza bruta, beam search, MILP por posiciones con escenarios (cortes opcionales) y algoritmo exacto `exact` (DP sobre conjuntos adquiridos o sobre conjunto y último nodo, con poda por la cota de índice); cotas superiores alternativas: por conjuntos con orden por índice (`set_bound`) y por grupos de escenarios (`group_bound`); alarma de cotas inconsistentes (`checked_bound`) |
| `periplo/game.py` | LP bayesiano, oráculo defensor por enumeración de los conjuntos de k trampas (`defender_br_enum`; MILP solo si hay más de 3M conjuntos), double oracle con [LB, UB] (con `oracle="exact"` guarda la mejor D y el mejor sigma vistos: intervalo certificado aunque se corte por tiempo), interdicción visible con maestro por enumeración (`visible_lb_enum`), líneas base |
| `periplo/experiments.py` | Planes `escala`, `delta`, `redundancia`, `cert` |
| `periplo/analyze.py` | Resumen de resultados |

## Uso

```bash
pip install pulp==2.9.0 highspy pyscipopt numpy scipy networkx
python tests/test_attacker.py        # oráculos vs fuerza bruta
python tests/test_milp_stress.py     # MILP con escenarios vs fuerza bruta
python tests/test_cuts.py            # cortes del MILP (con SCIP) vs fuerza bruta
python tests/test_bounds.py          # cotas por conjuntos y por grupos vs fuerza bruta
python tests/test_exact.py           # algoritmo exacto vs fuerza bruta (δ en {0, 1, 2.5, ∞})
python tests/test_robust.py          # monotonía: la esquina pesimista acota toda la caja de parámetros
python tests/test_game.py exact      # DO y visible con el oráculo exacto (incluye corridas cortadas por tiempo)
python tests/test_enum.py            # enumeración del defensor y del maestro visible vs fuerza bruta
python tests/test_game.py            # DO y caso visible vs juego completo enumerado
python tests/test_bloodhound.py      # parser real: regresión, coerción, fixtures de BloodHound CE
python -m periplo.experiments escala
python -m periplo.analyze
```

Para una colección real: `bloodhound.parse(["dominio1.zip", "dominio2.zip"], footholds="regulares", verbose=True)`.
Ejemplo completo sobre GOADv2: `python scripts/goad.py results/goad_adcs.jsonl adcs scip` y después
`python scripts/goad_cert.py results/goad_adcs.jsonl results/goad_adcs_cert.jsonl` para ajustar las cotas
(datos: github.com/m4lwhere/Bloodhound-CE-Sample-Data, Unlicense).

## Certificados (v2)

Desde la revisión del 22-oct-2026 ningún certificado depende de un MILP ni de un LP: la mejor respuesta del atacante es el
programa dinámico exacto y la del defensor (y el maestro de la visible) es enumeración de todos los conjuntos de k trampas.
`scripts/run_v2.py` corre todo (GOAD, sintéticos, sensibilidad, redundancia alta) con una cola compartida entre
trabajadores, reanudable, y guarda en `results/v2/` cada certificado: (D, sigma) para el juego aleatorizado y (B, pools)
para la visible. `scripts/verify_certs.py [--ub]` los re-verifica sin confiar en la corrida. `scripts/ablation.py` mide
el efecto de excluir nodos ya adquiridos en la cota de completamiento (`results/ablation.jsonl`).

## Paper

`paper/main.tex` (LNCS, inglés), con bibliografía verificada en `paper/refs.bib`. Ningún resultado del texto se tipea a mano
(los parámetros de los experimentos sí): `python scripts/paper_numbers.py` genera `paper/generated/` (macros y tablas)
desde `results/v2/` y, para la lección del beam, desde `results/exact_delta_f.jsonl`. `paper/main_v1.tex` es la versión
anterior a la revisión. Compilar con
`cd paper && pdflatex main && bibtex main && pdflatex main && pdflatex main` (requiere `llncs` y `lmodern`).

## Resultados incluidos

- `results/v2/`: corrida certificada sin solver que usa el paper (ver arriba). Lo que sigue es historia: sus valores de
  ataque son exactos, pero las cotas inferiores de optimalidad dependían de SCIP.

- `results/delta_f.jsonl`, `results/red_f.jsonl`: protocolo justo (DO con beam 400 verificado con 1500; todas las estrategias evaluadas con beam 1500). Reemplazados por los exactos (`exact_*.jsonl`).
- `results/escala.jsonl`, `delta.jsonl`, `redundancia.jsonl`: exploratorios con beam 150; subestiman al atacante 13–15% de media y no sirven para comparar estrategias.
- `results/reeval_delta.jsonl`, `results/reeval_red.jsonl`: posauditoría; colocación visible reoptimizada con beam 1500 y líneas base sin footholds (`scripts/reeval.py`). Los números finales del documento salen de acá combinados con `*_f.jsonl`.
- `results/cert.jsonl`: intentos de certificación exacta a 42 nodos con HiGHS; el campo `certified` es falso positivo (PuLP), y las cotas son de HiGHS (ver advertencias).
- `results/goad_v2_s.jsonl`, `results/goad_adcs_s.jsonl` (δ = 0) y `results/goad_adcs_sinf.jsonl` (δ = ∞): GOADv2 sin y con ADCS, SCIP en todos los MILP, con la estrategia mixta del atacante guardada; `*_cert.jsonl`: cotas ajustadas con la cota por conjuntos. `goad_v2.jsonl` y `goad_adcs.jsonl` usaron SCIP solo para el atacante (mismos valores); `goad.jsonl` es la corrida original con HiGHS: no usar sus cotas.
- `results/bench_cuts.jsonl`, `results/bench_set.jsonl`: cota del MILP por posiciones (con y sin cortes) vs cota por conjuntos, δ = 0, 81–95 nodos.
- `results/cert_synth_inf.jsonl`: intento de certificar aleatorizada < visible en `delta_f` con δ = ∞.
- `results/solver_cuts.jsonl`, `results/solver_stress.jsonl`: HiGHS (dos configuraciones), CBC y SCIP contra fuerza bruta (`scripts/solver_study.py`, reanudable; resumen con `scripts/solver_summary.py`).
- `results/tests_final.txt`: salida de la suite completa con SCIP.
- `results/goad_exact_*.jsonl`: V(D) exacto foothold por foothold en las 12 configuraciones de GOAD (`scripts/goad_exact.py`).
- `results/cert_exact_synth.jsonl`: la mezcla vieja de `delta_f` (optimizada contra el beam) reevaluada con el atacante exacto.
- `results/exact_delta_f.jsonl`, `results/exact_red_f.jsonl`: los experimentos sintéticos rehechos con el oráculo exacto (`scripts/exact_synth.py`); reemplazan a `*_f.jsonl` y `reeval_*.jsonl`.
- `results/sensitivity_k*.jsonl`: sensibilidad a r, p, q y modelo robusto en caja (`scripts/sensitivity.py`).
- `results/exact_alta.jsonl`: redundancia alta (143 nodos), donde el DO exacto no termina en 2 h: valor exacto (o cota) de la mezcla vieja y visible óptima certificada (`scripts/exact_alta.py`).
- `results/goad_exact_baselines.jsonl`: columnas de comparación de GOAD (visible, heurísticas, uniforme) con el atacante exacto.
- `results/highs_bug_repro.zip` y `results/highs_bug/ISSUE.md`: el issue para HiGHS, listo para publicar.
- `results/highs_bug/`: reproductor autónomo de los óptimos falsos de HiGHS 1.15.1 (tres MPS + `repro.py`).

## Advertencias

- `bloodhound.py` se probó con los fixtures oficiales v5/v6 de BloodHound CE y con la colección pública de GOADv2. Cubre ADCS (ESC1, ESC3 por agente de enrolamiento, ESC4, ESC6) y coerción con delegación no restringida dentro del bosque, esta última bajo el supuesto de que hay una primitiva de coerción en los DCs. No cubre GPO, ESC8 ni relay NTLM, que necesitan datos que SharpHound no colecta. Si la colección no es privilegiada (sin admins locales ni sesiones), el modelo concluye "sin caminos" donde sí los hay.
- El parser sintético (`sharphound.py`) solo cubre AdminTo, HasSession y ACL sobre usuarios; para datos reales usar `bloodhound.py`.
- Costos y probabilidades por rol son supuestos, no mediciones.
- HiGHS 1.15.1 devolvió "Optimal" con valores falsos en el MILP del atacante: primero con presolve; después, con presolve apagado, en 2 de las 120 instancias de `test_cuts.py` (con cortes) y en 1 de las 25 de `test_game.py` (sin cortes, δ = ∞, un escenario). CBC 2.10.3 y SCIP 10.0 dan el óptimo correcto en esos tres casos y en las 99 instancias del estudio de solvers. Reproductor en `results/highs_bug/` (con presolve apagado falla en los tres modelos; con `mip_root_presolve_only` en uno; por defecto en ninguno de estos tres, pero con presolve ya había fallado en otras instancias). Política: el paquete usa SCIP por defecto en todos los MILP (`attacker.DEFAULT_SOLVER`), y cualquier cota por debajo del valor de una secuencia factible conocida se descarta y queda en `attacker.BOUND_ALERTS`.
- `visible_interdiction` devolvía la cota inferior del maestro con el signo invertido (corregido). En `results/reeval_*.jsonl`, `Vvis_LB_strong` está guardado con ese signo.
- Los resultados sintéticos con beam (`*_f.jsonl`, `reeval_*.jsonl`) son cotas inferiores sesgadas: reevaluada con el atacante exacto, la mezcla optimizada contra el beam vale hasta 2 veces más de lo que el beam decía (δ = 0, semilla 3), y en ese caso queda peor que la colocación visible. Los resultados que valen son los exactos (`exact_*.jsonl`, `goad_exact_*.jsonl`).
- Auditoría (21-oct-2026), corregido: desalineación de pesos en el oráculo defensor del DO; `visible_interdiction(certify=True)` elegía B por la cota y no por el incumbente; gap MIP por defecto en defensor y maestro visible; footholds como candidatos en líneas base.

## 23-oct-2026: línea base de camino más corto (Ngo et al.)

- `periplo/spath.py`: colocación óptima contra el "simple attacker" de Ngo et al. (INFOCOM 2024): camino más corto
  en saltos, elegido al azar, hacia tier 0 fusionado; exacta para k <= 3 (conteo de caminos + inclusión-exclusión),
  empates rotos hacia la captura más temprana. Probada contra enumeración explícita (`tests/test_spath.py`).
- `scripts/spopt.py` la evalúa con nuestro atacante (`results/v2/spopt.jsonl`). Candidatos: los mismos que la mezcla y
  la visible (todos los nodos), más favorable a la línea base que el "solo computadoras" de Ngo et al.
- Resultado: en los sintéticos atrapa al 100% de los atacantes de camino más corto pero deja 1,1–4,7 veces el botín de
  la visible óptima; en GOAD coincide con la visible óptima en 10 de 24 configuraciones (máx 1,6 veces).
- Verificador: si una mejor respuesta tocó un límite (solo en las corridas de alta redundancia con tope de 1 h), se
  acepta una cota recalculada menor o igual que la registrada (antes se exigía igualdad; altado:3 dio 25,07 vs 25,66).
