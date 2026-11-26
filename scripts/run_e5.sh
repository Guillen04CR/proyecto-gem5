#!/usr/bin/env bash
# Ejecuta las doce corridas de coherencia de E5.
# Uso:
#   ./scripts/run_e5.sh /ruta/a/ARM_MESI/gem5.opt /ruta/a/ARM_MOESI/gem5.opt

set -euo pipefail

THREADS=(2 4 8)
ITERATIONS=100000
LAYOUTS=(unpadded padded)

usage() {
    printf '%s\n' "Uso: $0 /ruta/a/ARM_MESI/gem5.opt /ruta/a/ARM_MOESI/gem5.opt" >&2
}

fail() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

gem5_root_from_binary() {
    local binary="$1"
    cd "$(dirname "$binary")/../.." && pwd
}

if [[ $# -ne 2 ]]; then
    usage
    exit 2
fi

MESI_BIN="$1"
MOESI_BIN="$2"

[[ -x "$MESI_BIN" ]] || fail "gem5 MESI no existe o no es ejecutable: $MESI_BIN"
[[ -x "$MOESI_BIN" ]] || fail "gem5 MOESI no existe o no es ejecutable: $MOESI_BIN"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MESI_ROOT="$(gem5_root_from_binary "$MESI_BIN")"
MOESI_ROOT="$(gem5_root_from_binary "$MOESI_BIN")"

MESI_COMMIT="$(git -C "$MESI_ROOT" rev-parse HEAD 2>/dev/null)" \
    || fail "no se pudo leer el commit de gem5 MESI: $MESI_ROOT"
MOESI_COMMIT="$(git -C "$MOESI_ROOT" rev-parse HEAD 2>/dev/null)" \
    || fail "no se pudo leer el commit de gem5 MOESI: $MOESI_ROOT"
[[ "$MESI_COMMIT" == "$MOESI_COMMIT" ]] \
    || fail "MESI y MOESI no se compilaron desde el mismo commit de gem5"

SOURCE="$REPO_ROOT/src/false_sharing.c"
CONFIG="$REPO_ROOT/configs/run_e5.py"
BENCHMARK="$REPO_ROOT/bin/false_sharing"
M5_INCLUDE="$MESI_ROOT/include/gem5/m5ops.h"
LIBM5="$MESI_ROOT/util/m5/build/arm64/out/libm5.a"
CC="${AARCH64_CC:-aarch64-linux-gnu-gcc}"

command -v "$CC" >/dev/null 2>&1 || fail "no se encontro el compilador cruzado: $CC"
[[ -f "$SOURCE" ]] || fail "no existe el benchmark: $SOURCE"
[[ -f "$CONFIG" ]] || fail "no existe la configuracion Ruby: $CONFIG"
[[ -d "$MESI_ROOT/configs" ]] || fail "no existe <gem5>/configs bajo: $MESI_ROOT"
[[ -d "$MOESI_ROOT/configs" ]] || fail "no existe <gem5>/configs bajo: $MOESI_ROOT"
[[ -f "$M5_INCLUDE" ]] || fail "no se encontro gem5/m5ops.h bajo: $MESI_ROOT"
[[ -f "$LIBM5" ]] || fail "no se encontro libm5.a para AArch64 bajo: $MESI_ROOT"

# Revisar todos los destinos antes de cambiar el binario o iniciar una corrida.
# La evidencia nunca se borra ni se sobrescribe automaticamente.
for protocol in mesi moesi; do
    for threads in "${THREADS[@]}"; do
        for layout in "${LAYOUTS[@]}"; do
            output="$OUTPUT_ROOT/${protocol}_t${threads}_${layout}"
            [[ ! -e "$output" ]] || fail "ya existe una salida: $output"
        done
    done
done

mkdir -p "$REPO_ROOT/bin" "$OUTPUT_ROOT"

printf '%s\n' "Compilando false_sharing para AArch64..."
"$CC" -std=c11 -O2 -Wall -Wextra -Werror -static -pthread \
    -DGEM5 -march=armv8-a \
    -I"$MESI_ROOT/include" \
    "$SOURCE" \
    -L"$MESI_ROOT/util/m5/build/arm64/out" -lm5 \
    -o "$BENCHMARK"

run_one() {
    local label="$1"
    local expected_protocol="$2"
    local gem5_bin="$3"
    local gem5_root="$4"
    local threads="$5"
    local layout="$6"
    local output="$OUTPUT_ROOT/${label}_t${threads}_${layout}"

    printf '%s\n' "Ejecutando protocolo=$expected_protocol layout=$layout hilos=$threads..."
    mkdir -p "$output"

    # GEM5_CONFIGS permite a configs/run_e5.py importar Ruby y Options desde el
    # clon externo de gem5 sin codificar rutas del anfitrion en el repositorio.
    GEM5_CONFIGS="$gem5_root/configs" \
        "$gem5_bin" -d "$output" "$CONFIG" \
        --threads "$threads" \
        --layout "$layout" \
        --iterations "$ITERATIONS" \
        --binary "$BENCHMARK" 2>&1 | tee "$output/run.log"

    [[ -f "$output/stats.txt" ]] || fail "la corrida no produjo stats.txt: $output"
    [[ -f "$output/config.ini" ]] || fail "la corrida no produjo config.ini: $output"
    grep -q 'E5_VALIDATION: PASS' "$output/run.log" \
        || fail "la validacion no dio PASS: $output/run.log"
    grep -q "Protocolo: $expected_protocol" "$output/run.log" \
        || fail "el binario no confirma el protocolo esperado ($expected_protocol): $output/run.log"
}

for threads in "${THREADS[@]}"; do
    for layout in "${LAYOUTS[@]}"; do
        run_one mesi MESI_Two_Level "$MESI_BIN" "$MESI_ROOT" "$threads" "$layout"
    done
done

for threads in "${THREADS[@]}"; do
    for layout in "${LAYOUTS[@]}"; do
        run_one moesi MOESI_CMP_directory "$MOESI_BIN" "$MOESI_ROOT" "$threads" "$layout"
    done
done

printf '%s\n' "E5 completado: doce corridas generadas en $OUTPUT_ROOT"
