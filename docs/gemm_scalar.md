# `src/gemm_scalar.c` — guía de uso

Benchmark base del proyecto: multiplicación de matrices densas `C = A × B` en
`float`, escalar y de un solo hilo. Es la referencia contra la que se comparan E2
(superescalar), E3 (SVE) y E4 (multiprocesador), y la plantilla para
`gemm_sve.c` y `gemm_omp.c`.

**Estado:** validado con PASS en nativo (x86), QEMU (AArch64) y gem5
(`ArmTimingSimpleCPU`), con N = 16, 64 y 128.

## Qué hace, en orden

```
leer N (argv[1], por defecto 16, mínimo 2)
reservar A, B, C (n×n floats cada una, en orden por filas)
init(A, B)            ← fuera de la ROI
m5_reset_stats(0, 0)  ← inicio de la ROI: gem5 pone los contadores en 0
gemm(A, B, C)         ← lo único que se mide
m5_dump_stats(0, 0)   ← fin de la ROI: gem5 escribe el bloque 1 de stats.txt
check(A, B, C)        ← fuera de la ROI
imprimir E1_VALIDATION: PASS | FAIL
```

## Contrato de datos (no cambiar)

Todos los benchmarks GEMM del grupo usan **exactamente** estas matrices, para que
los resultados sean comparables entre experimentos:

```
A[i][j] = (i + j) % 8
B[i][j] = (i * j) % 8
```

Elemento `(i, j)` en el arreglo: `i*n + j` (macro `IDX(i, j, n)`).

**Valores de control** (salen de la especificación; sirven para detectar un `init`
o un `gemm` mal escrito):

| N | `C[0][1]` esperado |
|---|---|
| 16 | 280 |
| 64 | 1120 |
| 128 | 2240 |

## Por qué la validación compara con `==` (sin tolerancia)

`check` recalcula cada `C[i][j]` con enteros `long` y compara con igualdad exacta.
Es válido porque:

- A y B solo contienen enteros de 0 a 7, así que cada producto es ≤ 49.
- La suma más grande con N = 128 es 49 × 128 = 6272.
- `float` representa exactamente todos los enteros hasta 2²⁴ ≈ 16,7 millones.

No hay redondeo en ningún paso, así que el resultado es idéntico **con o sin
FMA** y en cualquier orden de suma. Esto importa: AArch64 fusiona `a*b + c` en una
sola instrucción `fmadd` (un redondeo) y x86 por defecto no lo hace (dos redondeos).
Con datos decimales, nativo y ARM darían resultados distintos en los últimos bits.

> Si cambian los datos a valores no enteros, hay que pasar a comparar con
> tolerancia relativa.

## Compilación (3 variantes del mismo fuente)

Desde la raíz del repositorio:

```bash
# 1. Nativo (x86): para iterar rápido
gcc -O2 -fno-tree-vectorize -Wall -Wextra \
  src/gemm_scalar.c -o bin/gemm_scalar_native

# 2. AArch64 para QEMU: sin m5ops
aarch64-linux-gnu-gcc -O2 -fno-tree-vectorize -march=armv8-a -static \
  src/gemm_scalar.c -o bin/gemm_scalar_qemu

# 3. AArch64 para gem5: con m5ops
aarch64-linux-gnu-gcc -O2 -fno-tree-vectorize -march=armv8-a -static -DGEM5 \
  -I$HOME/arqui/gem5/include src/gemm_scalar.c \
  -L$HOME/arqui/gem5/util/m5/build/arm64/out -lm5 -o bin/gemm_scalar
```

| Opción | Para qué |
|---|---|
| `-O2` | Optimización estándar; igual en las tres variantes. |
| `-fno-tree-vectorize` | Apaga la vectorización automática (NEON). Con `-O2` GCC 13 casi no vectoriza, pero con `-O3` sí: la opción lo garantiza siempre. |
| `-march=armv8-a` | ARMv8 base, **sin SVE**. Si se compila con `+sve`, la guarda `#error` del fuente detiene la compilación. |
| `-static` | Obligatorio en modo SE: gem5 no tiene cargador de librerías dinámicas. |
| `-DGEM5` | Activa las m5ops reales. **Sin** esta opción las m5ops son macros vacías. |
| `-I…/include` | Dónde está `gem5/m5ops.h`. |
| `-L…/out -lm5` | Enlaza `libm5.a`. Va **después** del `.c`. |

**No correr la variante 3 en nativo ni en QEMU**: las m5ops son instrucciones que
solo existen en gem5 y el programa muere con `Illegal instruction`.

## Ejecución

```bash
./bin/gemm_scalar_native 16
qemu-aarch64 ./bin/gemm_scalar_qemu 16

cd ~/arqui/gem5
build/ARM_MESI/gem5.opt -d ~/arqui/proyecto-gem5/results/e1/<config> \
  configs/deprecated/example/se.py --cpu-type=ArmTimingSimpleCPU \
  --caches --l2cache -c ~/arqui/proyecto-gem5/bin/gemm_scalar -o 16
```

- `-d` va **antes** de `se.py` (es opción de gem5) y separa la salida de cada corrida.
- `-o 16` es el `argv[1]` del programa.

## Salida

```
N=16  C[0][1]=280.0  errores=0
E1_VALIDATION: PASS
```

| Código de salida | Significado |
|---|---|
| 0 | PASS |
| 1 | FAIL, N inválido (N < 2) o sin memoria |

En gem5 un FAIL aparece además como `Simulated exit code not 0! Exit code is 1`.
Los scripts deben revisar el código de salida, no solo el texto.

## Cómo leer `stats.txt`

Cada corrida produce **2 bloques** (`grep -c "Begin Simulation Statistics"` da 2):

| Bloque | Lo escribe | Contiene |
|---|---|---|
| 1 | `m5_dump_stats` | **Solo la ROI (GEMM).** Es el que se usa. |
| 2 | gem5 al terminar | Desde el reset **hasta el final**: ROI + `check` + `printf` + salida. |

`m5_dump_stats` escribe pero **no reinicia** los contadores, por eso el bloque 2
incluye al bloque 1. `scripts/parse_e1.py` toma siempre el **primer** bloque.

## ROI verificada a la instrucción

Contando las instrucciones del desensamblado de `gemm` y de las llamadas en `main`,
el bloque 1 debe tener:

```
simInsts = 6n³ + 9n² + 8n + 20
```

| Término | Origen |
|---|---|
| 6n³ | Bucle `k`: `ldr`, `add`, `ldr`, `fmadd`, `cmp`, `b.ne` |
| 9n² | Bucle `j`: poner en cero el acumulador, preparar punteros y guardar `C[i][j]` |
| 8n | Bucle `i`: avanzar punteros de fila |
| 20 | Entrada y salida de `gemm` (9) + paso de argumentos, llamadas y m5ops en `main` (11) |

| N | `simInsts` predicho | Medido en gem5 |
|---|---|---|
| 16 | 27 028 | **27 028** ✅ |
| 64 | 1 610 260 | — |
| 128 | 12 731 412 | — |

La coincidencia exacta con N = 16 demuestra que la ROI contiene `gemm` y nada más.
El modelo depende del compilador (GCC 13.3 de Ubuntu 24.04, `-O2`): con otra
versión pueden cambiar los términos de orden n² y n, y el de n³ casi nunca.

**Medición de control:** con `gemm` vacía, el bloque 1 tiene `simInsts = 5`
(`ret`, dos `mov`, `bl m5_dump_stats` y la instrucción mágica). GCC elimina por
completo una función `static` que no tiene efectos, aunque tenga `noinline`.

## Valores de aceptación en gem5

gem5 es determinista: con la misma versión de gem5, el mismo compilador y el mismo
fuente, cualquier integrante debe obtener **exactamente** estos números
(`ArmTimingSimpleCPU`, `--caches --l2cache`, N = 16):

| Estadística (bloque 1) | Valor |
|---|---|
| `simInsts` | 27 028 |
| `simTicks` | 36 810 000 |

Si difieren, revisar primero `aarch64-linux-gnu-gcc --version` (debe ser 13.3.0).

> `simInsts` solo depende del código de `gemm` y debe dar 27 028 en cualquier entorno
> con GCC 13.3. `simTicks` también depende de dónde quedan A, B y C en memoria (que
> cambia con la versión de la libc), así que el valor de la tabla corresponde al
> entorno donde se midió. Ver `docs/E1.md`, sección Reproducibilidad.

## Verificaciones antes de usar los resultados

**`gemm` existe como función aparte:**

```bash
aarch64-linux-gnu-nm bin/gemm_scalar | grep -w gemm
```

Debe mostrar una línea `... t gemm`. La `t` minúscula significa "código, local al
archivo" (`static`). Esto lo garantiza `__attribute__((noinline))`.

**Sin vectorización y sin SVE** en el código medido:

```bash
aarch64-linux-gnu-objdump -d --disassemble=gemm bin/gemm_scalar \
  | grep -cE '\.(4s|2d|8h|16b)\b|\bz[0-9]+\.|\b(ld|st)[1-4]\b'
```

Debe dar **0**. El patrón busca operaciones con registros NEON de 128 bits
(`v0.4s`…), registros SVE (`z0.`…) y cargas vectoriales (`ld1`…). Una línea
`movi v0.2s, #0` es normal: es la forma en que GCC pone en cero un registro escalar.

No hay que revisar el binario completo: la libc estática trae cientos de
instrucciones vectoriales propias (`memcpy`, `strlen`…).

## Reutilizar para otros benchmarks

| Archivo | Qué se mantiene | Qué cambia |
|---|---|---|
| `gemm_sve.c` | `init`, `check`, `main`, ROI | `gemm` con SVE; compilar con `-march=armv8-a+sve` y **quitar** la guarda `#error` de SVE |
| `gemm_omp.c` | `init`, `check`, ROI | `gemm` paralelo; `main` recibe además el número de hilos. Las m5ops las llama **un solo hilo**, fuera de la región paralela |

Si los tres archivos terminan repitiendo `init` y `check`, conviene moverlas a
`src/gemm_common.h` para que el contrato de datos viva en un solo lugar.
