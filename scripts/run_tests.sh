#!/bin/sh
# Suite de pruebas contra fuerza bruta usada por el paper; escribe results/tests_v2.txt (lo lee paper_numbers.py).
cd "$(dirname "$0")/.."
OUT=results/tests_v2.txt
echo "Suite v2, $(date '+%Y-%m-%d %H:%M'), certificación sin MILP" > $OUT
for t in "tests/test_exact.py" "tests/test_enum.py" "tests/test_game.py exact" "tests/test_robust.py" "tests/test_spath.py"; do
  printf '%s\t' "$t" >> $OUT
  python3 $t 2>&1 | tail -2 | tr '\n' ' ' >> $OUT
  echo >> $OUT
done
