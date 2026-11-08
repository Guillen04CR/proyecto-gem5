#!/usr/bin/env bash
# Ejecuta las seis configuraciones de la línea base E1.
# Uso: ./scripts/run_e1.sh /ruta/a/gem5/build/<VARIANTE>/gem5.opt

set -euo pipefail

usage() {
    printf '%s\n' "Uso: $0 /ruta/a/gem5/build/<VARIANTE>/gem5.opt" >&2
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GEM5_ROOT="$(cd "$(dirname "$GEM5_BIN")/../.." && pwd)"

SOURCE="$REPO_ROOT/src/gemm_scalar.c"
CONFIG="$REPO_ROOT/configs/run_e1.py"
BENCHMARK="$REPO_ROOT/bin/gemm_scalar"
M5_INCLUDE="$GEM5_ROOT/include/gem5/m5ops.h"
LIBM5="$GEM5_ROOT/util/m5/build/arm64/out/libm5.a"
OUTPUT_ROOT="$REPO_ROOT/results/e1"
CC="${AARCH64_CC:-aarch64-linux-gnu-gcc}"

command -v "$CC" >/dev/null 2>&1 || fail "no se encontró el compilador cruzado: $CC"
[[ -f "$SOURCE" ]] || fail "no existe el benchmark: $SOURCE"
[[ -f "$CONFIG" ]] || fail "no existe la configuración: $CONFIG"
[[ -f "$M5_INCLUDE" ]] || fail "no se encontró gem5/m5ops.h bajo: $GEM5_ROOT"
[[ -f "$LIBM5" ]] || fail "no se encontró libm5.a para AArch64 bajo: $GEM5_ROOT"

CPUS=(timing minor o3)
SIZES=(64 128)

# Se revisan todos los destinos antes de compilar o ejecutar: nunca se sobrescribe
# una corrida existente ni se elimina evidencia automáticamente.
for cpu in "${CPUS[@]}"; do
    for size in "${SIZES[@]}"; do
        output="$OUTPUT_ROOT/${cpu}_N${size}"
        [[ ! -e "$output" ]] || fail "ya existe una salida: $output"
    done
done

mkdir -p "$REPO_ROOT/bin" "$OUTPUT_ROOT"

printf '%s\n' "Compilando GEMM escalar para AArch64..."
"$CC" -O2 -fno-tree-vectorize -march=armv8-a -static -DGEM5 \
    -I"$GEM5_ROOT/include" \
    "$SOURCE" \
    -L"$GEM5_ROOT/util/m5/build/arm64/out" -lm5 \
    -o "$BENCHMARK"

for cpu in "${CPUS[@]}"; do
    for size in "${SIZES[@]}"; do
        output="$OUTPUT_ROOT/${cpu}_N${size}"

        printf '%s\n' "Ejecutando CPU=$cpu, N=$size..."
        "$GEM5_BIN" -d "$output" "$CONFIG" --cpu "$cpu" --size "$size"

        [[ -f "$output/stats.txt" ]] || fail "la corrida no produjo stats.txt: $output"
        [[ -f "$output/config.ini" ]] || fail "la corrida no produjo config.ini: $output"
    done
done

printf '%s\n' "E1 completado: seis corridas generadas en $OUTPUT_ROOT"
