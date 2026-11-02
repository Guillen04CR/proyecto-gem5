# Montaje del entorno (reproducible)

Guía para que cualquier integrante (o el profesor) monte desde cero el mismo
entorno con el que se generaron los resultados. Tiempo total: ~2–3 h, la mayor
parte es la compilación de gem5 (desatendida).

## Requisitos

| Requisito | Valor usado | Mínimo recomendado |
|---|---|---|
| Sistema operativo | Ubuntu 24.04.5 LTS (x86-64) | Ubuntu 24.04 nativo o en WSL2 |
| RAM | 15 GB | 8 GB (compilar con `-j2`) |
| Disco libre | 73 GB | 25 GB |
| Hilos de CPU | 4 | 2 |

> Otros sistemas (Ubuntu 22.04, Mac, otras distros) pueden funcionar pero **no
> están verificados**; los nombres de paquetes y versiones del compilador cambian,
> y con ellos el conteo exacto de instrucciones simuladas.

## Estructura de carpetas asumida

```
~/arqui/
├─ gem5/            ← simulador (NO va dentro del repo)
└─ proyecto-gem5/   ← este repositorio
```

## 1. Dependencias

```bash
sudo apt update
sudo apt install -y build-essential scons python3-dev python3-pydot git m4 \
  zlib1g zlib1g-dev libprotobuf-dev protobuf-compiler libprotoc-dev \
  libgoogle-perftools-dev libboost-all-dev libhdf5-dev libpng-dev \
  libelf-dev libcapstone-dev pkg-config \
  gcc-aarch64-linux-gnu g++-aarch64-linux-gnu qemu-user
```

## 2. Descargar gem5 y este repositorio

```bash
mkdir -p ~/arqui && cd ~/arqui
git clone https://github.com/gem5/gem5.git
git -C gem5 checkout v26.0.0.0
git clone https://github.com/Guillen04CR/proyecto-gem5.git
```

El aviso de *detached HEAD* tras el `checkout` es normal: estamos fijados a una
versión, no a una rama.

## 3. Compilar gem5

```bash
cd ~/arqui/gem5
scons defconfig build/ARM_MESI ~/arqui/proyecto-gem5/configs/build_opts/ARM_MESI_Two_Level
systemd-inhibit --what=sleep:idle:handle-lid-switch \
  scons build/ARM_MESI/gem5.opt -j3 --ignore-style
```

- La primera vez gem5 pregunta si instalar *pre-commit hooks*: `Enter` y luego
  `y`. Los hooks solo aplican a quien contribuye a gem5; no afectan este proyecto.
- `-j3`: trabajos de compilación en paralelo. Con ≤ 8 GB de RAM usar `-j2`; si
  aparece `Killed`, bajar a `-j1` y relanzar (SCons retoma donde quedó).
- `systemd-inhibit` evita que la laptop se suspenda durante la compilación.
- **Solo el líder de E5** compila además la versión MOESI:
  ```bash
  scons defconfig build/ARM_MOESI ~/arqui/proyecto-gem5/configs/build_opts/ARM_MOESI_CMP_directory
  scons build/ARM_MOESI/gem5.opt -j3 --ignore-style
  ```

## 4. Compilar libm5 para ARM

```bash
cd ~/arqui/gem5/util/m5
scons arm64.CROSS_COMPILE=aarch64-linux-gnu- build/arm64/out/m5
```

Produce `~/arqui/gem5/util/m5/build/arm64/out/libm5.a`.
Encabezados: `~/arqui/gem5/include/gem5/m5ops.h`.

## 5. Prueba de aceptación

```bash
cd ~/arqui/proyecto-gem5
mkdir -p bin
aarch64-linux-gnu-gcc -O2 -static src/hola.c -o bin/hola
qemu-aarch64 ./bin/hola
cd ~/arqui/gem5
build/ARM_MESI/gem5.opt configs/deprecated/example/se.py -c ~/arqui/proyecto-gem5/bin/hola
```

El entorno está correcto si se cumple **todo** lo siguiente:

| Comprobación | Resultado esperado |
|---|---|
| `qemu-aarch64 ./bin/hola` | `Hola desde ARM en gem5` |
| Salida de gem5 | `gem5 version 26.0.0.0` |
| Salida de gem5 | `Hola desde ARM en gem5` |
| Última línea de gem5 | `Exiting @ tick 46502000 because exiting with last active thread context` |
| `ls ~/arqui/gem5/m5out/` | contiene `stats.txt`, `config.ini` y `config.dot.pdf` |

gem5 es determinista: con la misma versión de gem5 y el mismo binario, el número
de tick es idéntico en cualquier máquina. **Si el tick difiere**, casi siempre es
porque el compilador cruzado o la libc son de otra versión (comparar
`aarch64-linux-gnu-gcc --version` con la tabla de abajo).

## Avisos esperados (no son errores)

| Aviso | Motivo |
|---|---|
| `The se.py script is deprecated` | gem5 recomienda su librería nueva; `se.py` funciona en v26. |
| `DRAM device capacity ... does not match` | Módulo DRAM de 8 GB con 512 MB asignados; los benchmarks usan < 1 MB. |
| `ignoring syscall set_robust_list / mprotect` | Llamadas de arranque de la libc que el modo SE omite. |
| `instruction 'bti' unimplemented` | Protección de saltos de ARMv8.5; gem5 la ejecuta como NOP. |
| `remote_gdb: Listening ... port 7000` | Puerto para depurar con GDB; corridas en paralelo toman 7001, 7002… |

## Versiones verificadas

| Componente | Versión |
|---|---|
| Ubuntu | 24.04.5 LTS |
| gem5 | v26.0.0.0 (commit fed0e07e93) |
| SCons | 4.5.2 |
| aarch64-linux-gnu-gcc | 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) |
| qemu-aarch64 | 8.2.2 |

CPU usadas (`--list-cpu-types`): `ArmTimingSimpleCPU`, `ArmMinorCPU`, `ArmO3CPU`.
