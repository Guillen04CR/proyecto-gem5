# Ejecutar E1

`scripts/run_e1.sh` reproduce la matriz completa de E1: una GEMM escalar para
un núcleo, los modelos TimingSimple, Minor y O3, y los tamaños `N=64` y
`N=128`.

## Prerrequisitos

- Un binario `gem5.opt` de ARM ya compilado.
- `aarch64-linux-gnu-gcc` disponible en `PATH`.
- `libm5.a` para AArch64 compilada dentro del mismo clon de gem5.
- El `src/gemm_scalar.c` y la configuración `configs/run_e1.py`.

## Uso

Desde la raíz del repositorio:

```bash
./scripts/run_e1.sh ~/arqui/gem5/build/ARM_MESI/gem5.opt
```

La ruta se proporciona al ejecutar y no se guarda en el repositorio. El equipo
debe usar el binario gem5 que haya acordado para las corridas oficiales.

## Corridas generadas

| CPU | Tamaños |
|---|---|
| `timing` | 64, 128 |
| `minor` | 64, 128 |
| `o3` | 64, 128 |

Cada combinación se ejecuta de forma secuencial y queda aislada en:

```text
results/e1/timing_N64/
results/e1/timing_N128/
results/e1/minor_N64/
results/e1/minor_N128/
results/e1/o3_N64/
results/e1/o3_N128/
```

Cada carpeta contiene `stats.txt` y `config.ini` (los genera gem5) y `run.log`
(la salida de gem5 y del programa, con `E1_VALIDATION: PASS`). gem5 también puede
generar `config.dot*`, `config.json` y `citations.bib`; son redundantes y el
`.gitignore` los excluye.

El script se detiene si alguna carpeta de salida ya existe (no elimina ni
sobrescribe una corrida anterior) o si alguna corrida no da `E1_VALIDATION: PASS`.

## Alcance

Este script compila el binario AArch64 de E1 y ejecuta las seis configuraciones.
No extrae métricas, no selecciona el bloque ROI y no genera CSV ni gráficas.
Esas tareas corresponden a `scripts/parse_e1.py`, `scripts/plot_e1.py` y
`scripts/verify_e1.sh` (ver `docs/E1.md`).

Después de revisar las seis corridas oficiales, `stats.txt` y `config.ini` de
cada configuración quedan disponibles como entrada para el parser y como
evidencia que el equipo decida versionar.
