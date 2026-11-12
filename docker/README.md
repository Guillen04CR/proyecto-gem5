E1 — Correr una configuración a mano

Para las seis corridas oficiales usar scripts/run_e1.sh (ver docs/run_e1.md).
Esta guía es para probar una sola configuración de configs/run_e1.py.

Todo se ejecuta DENTRO del contenedor (docker compose run --rm gem5) y desde la
raíz del repositorio:
    ~/arqui/proyecto-gem5

1. Verificar que existan el simulador y el binario AArch64

    ls -lh ~/arqui/gem5/build/ARM_MESI/gem5.opt
    ls -lh bin/gemm_scalar

   Si falta bin/gemm_scalar, compilarlo (lo mismo que hace run_e1.sh):

    aarch64-linux-gnu-gcc -O2 -fno-tree-vectorize -march=armv8-a -static -DGEM5 \
      -I$HOME/arqui/gem5/include src/gemm_scalar.c \
      -L$HOME/arqui/gem5/util/m5/build/arm64/out -lm5 -o bin/gemm_scalar

2. Ejecutar una configuración

    ~/arqui/gem5/build/ARM_MESI/gem5.opt \
      -d /tmp/e1_<CPU>_N<N> \
      configs/run_e1.py \
      --cpu <CPU> \
      --size <N>

   Opciones permitidas:
       CPU: timing | minor | o3
       N:   64 | 128

   Ejemplo:
    ~/arqui/gem5/build/ARM_MESI/gem5.opt -d /tmp/e1_timing_N64 configs/run_e1.py --cpu timing --size 64

   Las pruebas a mano van a /tmp, NO a results/: results/e1/ solo contiene las
   corridas oficiales que genera run_e1.sh.

3. Revisar la salida

    ls -lh /tmp/e1_timing_N64/
    grep -E 'type=|size=|clock=' /tmp/e1_timing_N64/config.ini | head -n 40
    grep -c 'Begin Simulation Statistics' /tmp/e1_timing_N64/stats.txt   # debe dar 2

   config.ini  Configuración utilizada en la simulación.
   stats.txt   Estadísticas. Bloque 1 = ROI (el que se usa), bloque 2 = acumulado.

4. A tener en cuenta

- No cambiar a mano los parámetros fijos de run_e1.py: un núcleo, 2 GHz,
  L1I de 32 kB, L1D de 32 kB, L2 de 256 kB y modo SE.
- run_e1.py recibe únicamente --cpu y --size.
