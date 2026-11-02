# proyecto-gem5

Segundo proyecto del curso EL4314 Arquitectura de Computadoras (TEC, II Semestre 2026):
**arquitecturas paralelas para la multiplicación de matrices (GEMM) en gem5**.

Evaluamos núcleos superescalares, extensiones vectoriales SVE, multiprocesadores y
protocolos de coherencia sobre ARMv8 en gem5 (modo SE), para responder:

> Con un presupuesto de 32 unidades de costo, ¿qué combinación de núcleos, ancho
> superescalar, longitud vectorial y protocolo de coherencia minimiza el tiempo de
> ejecución de GEMM?
>
> `Costo = N_núcleos × (W_issue / 2 + VL / 128)`

## Equipo y experimentos

| Experimento | Tema | Líder | Estado |
|---|---|---|---|
| E1 | Línea base: TimingSimple, Minor, O3 | Andrés Guillén | En curso |
| E2 | Superescalar: ancho 1/2/4/8 × ROB 32/64/192 | Andrés Guillén | Pendiente |
| E3 | Vectorial: escalar vs. SVE, VL 128–1024 | _(nombre)_ | Pendiente |
| E4 | Multiprocesador: 1, 2, 4, 8 núcleos | _(nombre)_ | Pendiente |
| E5 | Coherencia: MESI_Two_Level vs. MOESI_CMP_directory | _(nombre)_ | Pendiente |
| E6 | Exploración bajo presupuesto (≥ 6 configuraciones) | Todos | Pendiente |

## Estructura del repositorio

```
proyecto-gem5/
├─ src/              # Benchmarks en C: gemm_scalar.c, gemm_sve.c, gemm_omp.c, false_sharing.c
├─ bin/              # Binarios AArch64 compilados (ignorados por git, se regeneran)
├─ configs/
│  └─ build_opts/    # Opciones de compilación de gem5 (ISA + protocolo Ruby)
├─ scripts/          # run_e1.sh … run_e6.sh, parse_stats.py
├─ results/          # Una carpeta por corrida (stats.txt, config.ini) + CSV por experimento
├─ report/           # Informe IEEE
└─ docs/
   └─ SETUP.md       # Guía de montaje del entorno
```

## Entorno

Para montar el entorno desde cero, seguir **[docs/SETUP.md](docs/SETUP.md)**.
Incluye una prueba de aceptación: si `hola.c` termina en `tick 46502000`, el entorno
es equivalente al usado para generar los resultados.

| Componente | Versión |
|---|---|
| Ubuntu | 24.04.5 LTS |
| gem5 | v26.0.0.0 (commit fed0e07e93) |
| SCons | 4.5.2 |
| aarch64-linux-gnu-gcc | 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) |
| qemu-aarch64 | 8.2.2 |

| Binario de gem5 | Protocolo Ruby | Usado en |
|---|---|---|
| `build/ARM_MESI/gem5.opt` | MESI_Two_Level | E1–E6 |
| `build/ARM_MOESI/gem5.opt` | MOESI_CMP_directory | E5 |

CPU usadas (`--list-cpu-types`): `ArmTimingSimpleCPU`, `ArmMinorCPU`, `ArmO3CPU`.

Tamaños de matriz: N = 64 y N = 128. Todas las métricas se toman solo de la región
de interés, delimitada con `m5_reset_stats()` y `m5_dump_stats()`.

## Reproducir los experimentos

Cada experimento se regenera con un solo comando desde la raíz del repositorio:

```bash
./scripts/run_e1.sh    # (pendiente)
```

## Convenciones de trabajo

- **Ramas:** nadie trabaja directo en `main`. Cada tarea va en una rama
  `nombre/tema` (p. ej. `andres/e1-linea-base`) y entra a `main` por pull request
  revisado por otro integrante.
- **Binarios:** se compilan en `bin/`, nunca se suben al repositorio.
- **Resultados:** cada corrida de gem5 usa `-d results/eX/<configuración>` para no
  sobrescribir otras corridas.
- **Uso de IA generativa:** permitido según el enunciado; todo resultado obtenido con
  su ayuda se verifica con una simulación propia y se declara en la bitácora.
