# Ejecutar E2

E2 barre el núcleo O3 con ancho {1, 2, 4, 8} × ROB {32, 64, 192} × N {64, 128}:
**24 corridas** (12 configuraciones de hardware por tamaño).

## Qué cambia respecto a E1

`configs/run_e2.py` es una copia de `configs/run_e1.py` con una sola diferencia: el
núcleo es siempre O3 y recibe `--width` y `--rob`.

- **Ancho coherente:** `fetchWidth`, `decodeWidth`, `renameWidth`, `dispatchWidth`,
  `issueWidth`, `wbWidth` y `commitWidth` toman el mismo valor.
- **Fijo, igual que E1:** 2 GHz, L1I y L1D de 32 kB (2 vías), L2 de 256 kB, DDR3,
  IQ de 64 entradas, LQ y SQ de 32, 256 registros físicos por tipo, predictor por
  defecto. E2 aísla el efecto del ancho y del ROB.
- **Mismo binario y misma ruta** (`bin/gemm_scalar`) que E1.
- **`forwardComSize = 64`** (por defecto 5). Es un parámetro del simulador, no del
  hardware: cuántos ciclos hacia adelante puede IEW reservar un puerto de escritura.
  Con ancho 1 o 2, varias cargas que esperaban la misma línea de caché terminan en el
  mismo ciclo y la reserva se pasa de 5 ciclos; gem5 aborta con `TimeBuffer
  out-of-bounds access! ... Increase forwardComSize`. Se aplica a las 24
  configuraciones, y el control contra E1 comprueba que no cambia los resultados.

**Control de calidad:** ancho 8 y ROB 192 son los valores por defecto de O3 en gem5
v26, o sea la corrida O3 de E1. `parse_e2.py` comprueba que den **los mismos
ciclos** que `results/e1/summary.csv` para cada N.

## Uso

Dentro del contenedor (`docker compose run --rm gem5`), desde la raíz del repo:

```bash
JOBS=3 ./scripts/run_e2.sh ~/arqui/gem5/build/ARM_MESI/gem5.opt   # 24 corridas
python3 scripts/parse_e2.py                                         # → results/e2/summary.csv
python3 scripts/plot_e2.py                                          # → results/e2/*.png
```

- `JOBS` = corridas en paralelo (por defecto 1). Con 4 hilos y 15 GB de RAM, 3 es
  un buen valor. Cada corrida guarda la salida de gem5 en su `run.log` y la
  terminal muestra una línea por corrida.
- Igual que `run_e1.sh`, se niega a sobrescribir resultados existentes. Para repetir
  todo, primero borrar `results/e2/` a mano.
- Las pruebas a mano van a `/tmp`, no a `results/`:

  ```bash
  ~/arqui/gem5/build/ARM_MESI/gem5.opt -d /tmp/e2_w4_rob64_N128 \
    configs/run_e2.py --width 4 --rob 64 --size 128
  ```

## Salida

```text
results/e2/w<ANCHO>_rob<ROB>_N<N>/   stats.txt, config.ini, run.log
results/e2/summary.csv                24 filas
results/e2/e2_ipc.png                 IPC vs. ancho, una línea por ROB
results/e2/e2_stalls.png              % de ciclos con rename bloqueado, por causa
```

## Columnas de `summary.csv`

| Columna | Significado |
|---|---|
| `ipc`, `cpi`, `cycles`, `insts` | Igual que E1 (bloque 1 = ROI; `insts` incluye NOP) |
| `speedup_vs_w1_rob32` | Ciclos de (ancho 1, ROB 32) / ciclos de la configuración, mismo N |
| `issued_per_cycle` | Instrucciones emitidas a ejecución por ciclo, promedio |
| `rob_full_frac`, `iq_full_frac`, `lq_full_frac`, `sq_full_frac`, `regs_full_frac` | Fracción de ciclos en que la etapa rename se bloqueó porque ese recurso estaba lleno |
| `l1d_miss_rate` | Fallos / accesos de L1D |
| `load_to_use_cycles` | Ciclos promedio entre emitir una carga y tener su dato |
| `mispredicts`, `mispredicts_pki` | Saltos condicionales mal predichos (total y por mil instrucciones) |
| `same_as_e1_o3` | Solo en ancho 8 / ROB 192: `yes` si los ciclos coinciden con O3 de E1 |

Los contadores `*_full_frac` vienen de `system.cpu.rename.<X>FullEvents`. gem5 suma
uno por cada ciclo en que rename no puede avanzar por ese recurso (como mucho una
causa por ciclo), así que las fracciones se pueden sumar. gem5 no imprime estos
contadores cuando valen 0; el parser los toma como 0.

El mensaje del benchmark sigue siendo `E1_VALIDATION: PASS`: es el mismo programa
que E1, y `run_e2.sh` y `parse_e2.py` exigen ese texto en cada `run.log`.
