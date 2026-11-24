#!/usr/bin/env bash
# Ejecuta las 24 corridas de E2: ancho {1,2,4,8} x ROB {32,64,192} x N {64,128}.
# Uso: ./scripts/run_e2.sh /ruta/a/gem5/build/<VARIANTE>/gem5.opt
# Paralelismo: JOBS=3 ./scripts/run_e2.sh ...   (por defecto 1, en serie)

set -euo pipefail

usage() {
    printf '%s\n' "Uso: [JOBS=n] $0 /ruta/a/gem5/build/<VARIANTE>/gem5.opt" >&2
}

fail() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi

GEM5_BIN="$1"
[[ -x "$GEM5_BIN" ]] || fail "gem5.opt no existe o no es ejecutable: $GEM5_BIN"

JOBS="${JOBS:-1}"
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || fail "JOBS debe ser un entero positivo: $JOBS"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GEM5_ROOT="$(cd "$(dirname "$GEM5_BIN")/../.." && pwd)"

SOURCE="$REPO_ROOT/src/gemm_scalar.c"
CONFIG="$REPO_ROOT/configs/run_e2.py"
BENCHMARK="$REPO_ROOT/bin/gemm_scalar"
M5_INCLUDE="$GEM5_ROOT/include/gem5/m5ops.h"
LIBM5="$GEM5_ROOT/util/m5/build/arm64/out/libm5.a"
OUTPUT_ROOT="$REPO_ROOT/results/e2"
CC="${AARCH64_CC:-aarch64-linux-gnu-gcc}"

command -v "$CC" >/dev/null 2>&1 || fail "no se encontró el compilador cruzado: $CC"
[[ -f "$SOURCE" ]] || fail "no existe el benchmark: $SOURCE"
[[ -f "$CONFIG" ]] || fail "no existe la configuración: $CONFIG"
[[ -f "$M5_INCLUDE" ]] || fail "no se encontró gem5/m5ops.h bajo: $GEM5_ROOT"
[[ -f "$LIBM5" ]] || fail "no se encontró libm5.a para AArch64 bajo: $GEM5_ROOT"

# N=128 primero: son las corridas largas, así el paralelismo se aprovecha mejor.
SIZES=(128 64)
WIDTHS=(1 2 4 8)
ROBS=(32 64 192)

# Igual que E1: se revisan todos los destinos antes de empezar. Nunca se
# sobrescribe una corrida existente ni se borra evidencia automáticamente.
for size in "${SIZES[@]}"; do
    for width in "${WIDTHS[@]}"; do
        for rob in "${ROBS[@]}"; do
            output="$OUTPUT_ROOT/w${width}_rob${rob}_N${size}"
            [[ ! -e "$output" ]] || fail "ya existe una salida: $output"
        done
    done
done

mkdir -p "$REPO_ROOT/bin" "$OUTPUT_ROOT"

# Mismo comando de compilación que run_e1.sh: el binario de E2 es idéntico al de E1.
printf '%s\n' "Compilando GEMM escalar para AArch64..."
"$CC" -O2 -fno-tree-vectorize -march=armv8-a -static -DGEM5 \
    -I"$GEM5_ROOT/include" \
    "$SOURCE" \
    -L"$GEM5_ROOT/util/m5/build/arm64/out" -lm5 \
    -o "$BENCHMARK"

# Cada corrida que falla anota su nombre aquí. Así no se pierde ningún fallo,
# aunque la corrida termine mientras el script está esperando a otra.
FAILLOG="$(mktemp)"
trap 'rm -f "$FAILLOG"' EXIT

# Una corrida. Con JOBS > 1 varias se ejecutan a la vez, así que la salida de
# gem5 va SOLO a run.log (en la terminal se mezclaría) y aquí se imprime una línea.
run_one() {
    local width="$1" rob="$2" size="$3"
    local output="$OUTPUT_ROOT/w${width}_rob${rob}_N${size}"
    local tag="ancho=$width ROB=$rob N=$size"
    local start=$SECONDS

    mkdir -p "$output"
    if ! "$GEM5_BIN" -d "$output" "$CONFIG" \
            --width "$width" --rob "$rob" --size "$size" > "$output/run.log" 2>&1; then
        printf 'FALLÓ  %-24s gem5 terminó con error (ver %s/run.log)\n' "$tag" "$output" >&2
        printf '%s\n' "$tag" >> "$FAILLOG"
        return 1
    fi
    [[ -f "$output/stats.txt" && -f "$output/config.ini" ]] || {
        printf 'FALLÓ  %-24s faltan stats.txt o config.ini\n' "$tag" >&2
        printf '%s\n' "$tag" >> "$FAILLOG"
        return 1
    }
    grep -q 'E1_VALIDATION: PASS' "$output/run.log" || {
        printf 'FALLÓ  %-24s la validación no dio PASS\n' "$tag" >&2
        printf '%s\n' "$tag" >> "$FAILLOG"
        return 1
    }
    printf 'OK     %-24s %4d s\n' "$tag" $((SECONDS - start))
}

printf 'Ejecutando 24 corridas con JOBS=%s...\n' "$JOBS"
for size in "${SIZES[@]}"; do
    for width in "${WIDTHS[@]}"; do
        for rob in "${ROBS[@]}"; do
            run_one "$width" "$rob" "$size" &
            # Si ya hay JOBS corridas activas, esperar a que termine alguna.
            while (( $(jobs -rp | wc -l) >= JOBS )); do
                wait -n || true
            done
        done
    done
done
# Esperar las que quedan.
wait

if [[ -s "$FAILLOG" ]]; then
    printf 'Corridas fallidas:\n' >&2
    sed 's/^/  - /' "$FAILLOG" >&2
    fail "$(wc -l < "$FAILLOG") corrida(s) fallaron; las demás quedaron en $OUTPUT_ROOT"
fi
printf '%s\n' "E2 completado: 24 corridas generadas en $OUTPUT_ROOT"
