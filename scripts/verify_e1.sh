#!/usr/bin/env bash
# verify_e1.sh — Comprueba que los resultados de E1 están completos y son defendibles.
#
# Uso (desde cualquier carpeta):
#   ./scripts/verify_e1.sh            # revisa results/e1
#   ./scripts/verify_e1.sh DIR        # revisa otra carpeta con la misma estructura
#
# No modifica nada. Revisa todo y al final informa: código 0 si todo pasa, 1 si algo falla.
#
# Comprobaciones:
#   1. Las 6 carpetas <cpu>_N<n> existen.
#   2. Cada una tiene stats.txt, config.ini y run.log.
#   3. Cada stats.txt tiene exactamente 2 bloques (1 = ROI, 2 = dump final).
#   4. Cada run.log contiene "E1_VALIDATION: PASS" y ningún FAIL.
#   5. config.ini: un solo núcleo con un hilo, el CPU que dice la carpeta, el N que dice
#      la carpeta, reloj de 2 GHz y la misma jerarquía L1I/L1D/L2 en las 6 corridas.
#   6. summary.csv: 6 filas, sin métricas vacías, y coincide con lo que produce
#      parse_e1.py a partir de los stats.txt actuales (no está desactualizado).
#   7. Instrucciones de la ROI = 6n³ + 9n² + 8n + 20 (la ROI contiene solo gemm).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS="${1:-$REPO_ROOT/results/e1}"
CSV="$RESULTS/summary.csv"

CPUS=(timing minor o3)
SIZES=(64 128)

# Configuración fija de E1 (configs/run_e1.py). clock en ticks: 500 ps = 2 GHz.
EXPECTED_CLOCK=500
EXPECTED_L1I=32768
EXPECTED_L1D=32768
EXPECTED_L2=262144
declare -A CPU_TYPE=([timing]=TimingSimpleCPU [minor]=MinorCPU [o3]=O3CPU)

failures=0
pass() { printf '  [OK]    %s\n' "$1"; }
fail() { printf '  [FALLA] %s\n' "$1"; failures=$((failures + 1)); }

# Valor de una clave dentro de una sección [nombre] de config.ini.
ini_get() {  # archivo sección clave
    awk -v sec="[$2]" -v key="$3" '
        $0 == sec { inside = 1; next }
        /^\[/     { inside = 0 }
        inside && index($0, key "=") == 1 { print substr($0, length(key) + 2); exit }
    ' "$1"
}

printf 'Verificando E1 en %s\n\n' "$RESULTS"

# ---------------------------------------------------------------- 1 a 5: por corrida
runs_ok=0
for cpu in "${CPUS[@]}"; do
    for n in "${SIZES[@]}"; do
        run="${cpu}_N${n}"
        dir="$RESULTS/$run"
        printf '%s\n' "$run"

        if [[ ! -d "$dir" ]]; then
            fail "no existe la carpeta $dir"
            continue
        fi

        missing=0
        for f in stats.txt config.ini run.log; do
            [[ -f "$dir/$f" ]] || { fail "falta $f"; missing=1; }
        done

        if [[ -f "$dir/stats.txt" ]]; then
            blocks=$(grep -c 'Begin Simulation Statistics' "$dir/stats.txt")
            if [[ "$blocks" -eq 2 ]]; then
                pass "stats.txt con 2 bloques (ROI + final)"
            else
                fail "stats.txt tiene $blocks bloques; se esperaban 2"
            fi
        fi

        if [[ -f "$dir/run.log" ]]; then
            if grep -q 'E1_VALIDATION: FAIL' "$dir/run.log"; then
                fail "run.log contiene E1_VALIDATION: FAIL"
            elif [[ $(grep -c 'E1_VALIDATION: PASS' "$dir/run.log") -eq 1 ]]; then
                pass "run.log con E1_VALIDATION: PASS"
            else
                fail "run.log no contiene E1_VALIDATION: PASS"
            fi
            if grep -q 'Simulated exit code not 0' "$dir/run.log"; then
                fail "el programa simulado terminó con código distinto de 0"
            fi
        fi

        ini="$dir/config.ini"
        if [[ -f "$ini" ]]; then
            ncpu=$(grep -cE '^\[system\.cpu[0-9]*\]$' "$ini")
            threads=$(ini_get "$ini" system.cpu numThreads)
            if [[ "$ncpu" -eq 1 && "$threads" == "1" ]]; then
                pass "un núcleo, un hilo"
            else
                fail "se esperaba 1 núcleo con 1 hilo (núcleos=$ncpu, hilos=$threads)"
            fi

            type=$(ini_get "$ini" system.cpu type)
            if [[ "$type" == *"${CPU_TYPE[$cpu]}" ]]; then
                pass "CPU $type"
            else
                fail "CPU $type no corresponde a '$cpu' (${CPU_TYPE[$cpu]})"
            fi

            cmd=$(ini_get "$ini" system.cpu.workload cmd)
            if [[ "$cmd" == *gemm_scalar\ "$n" ]]; then
                pass "binario gemm_scalar con N=$n"
            else
                fail "cmd no corresponde a N=$n: '$cmd'"
            fi

            clock=$(ini_get "$ini" system.clk_domain clock)
            l1i=$(ini_get "$ini" system.cpu.icache size)
            l1d=$(ini_get "$ini" system.cpu.dcache size)
            l2=$(ini_get "$ini" system.l2cache size)
            if [[ "$clock" == "$EXPECTED_CLOCK" && "$l1i" == "$EXPECTED_L1I" \
                  && "$l1d" == "$EXPECTED_L1D" && "$l2" == "$EXPECTED_L2" ]]; then
                pass "2 GHz, L1I 32 kB, L1D 32 kB, L2 256 kB"
            else
                fail "configuración distinta: clock=$clock L1I=$l1i L1D=$l1d L2=$l2"
            fi
        fi

        [[ $missing -eq 0 ]] && runs_ok=$((runs_ok + 1))
    done
done

printf '\nCorridas completas (stats.txt + config.ini + run.log): %d de 6\n\n' "$runs_ok"

# ---------------------------------------------------------------- 6 y 7: summary.csv
printf 'summary.csv\n'
if [[ ! -f "$CSV" ]]; then
    fail "no existe $CSV (correr scripts/parse_e1.py)"
else
    rows=$(($(wc -l < "$CSV") - 1))
    if [[ "$rows" -eq 6 ]]; then
        pass "6 filas"
    else
        fail "tiene $rows filas; se esperaban 6"
    fi

    empty=$(awk -F, 'NR > 1 { for (i = 1; i <= NF; i++) if ($i == "") c++ } END { print c + 0 }' "$CSV")
    if [[ "$empty" -eq 0 ]]; then
        pass "sin métricas vacías"
    else
        fail "$empty campos vacíos"
    fi

    tmp="$(mktemp)"
    if python3 "$SCRIPT_DIR/parse_e1.py" --results "$RESULTS" --out "$tmp" >/dev/null 2>&1; then
        if cmp -s "$tmp" "$CSV"; then
            pass "coincide con los stats.txt actuales"
        else
            fail "no coincide con los stats.txt actuales (volver a correr parse_e1.py)"
        fi
    else
        fail "parse_e1.py no pudo leer los stats.txt"
    fi
    rm -f "$tmp"

    col=$(head -n1 "$CSV" | tr ',' '\n' | grep -nx 'insts_match_model' | cut -d: -f1)
    if [[ -z "$col" ]]; then
        fail "el CSV no tiene la columna insts_match_model"
    else
        bad=$(awk -F, -v c="$col" 'NR > 1 && $c != "yes" { printf "%s_N%s ", $1, $2 }' "$CSV")
        if [[ -z "$bad" ]]; then
            pass "instrucciones de la ROI = 6n³ + 9n² + 8n + 20 en las 6 corridas"
        else
            fail "instrucciones distintas del modelo en: $bad"
        fi
    fi
fi

printf '\n'
if [[ $failures -eq 0 ]]; then
    printf 'E1 VERIFICADO: todo pasa.\n'
    exit 0
fi
printf 'E1 NO VERIFICADO: %d comprobaciones fallaron.\n' "$failures"
exit 1
