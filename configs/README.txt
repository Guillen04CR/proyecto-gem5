E1

Ubicación del proyecto:
    ~/proyectos/proyecto-gem5

1. Abrir la carpeta del proyecto

cd ~/proyectos/proyecto-gem5

2. Verificar que existan el simulador y el binario AArch64

	ls -lh ~/proyectos/gem5/build/ARM/gem5.opt
	ls -lh bin/gemm_scalar

3. Cómo ejecutar un experimento

~/proyectos/gem5/build/ARM/gem5.opt \
  -d results/e1_<CPU>_N<N> \
  configs/run_e1.py \
  --cpu <CPU> \
  --size <N>

Opciones permitidas:
    CPU: timing | minor | o3
    N:   64 | 128

4. Comandos para cada una de las configuraciones

# CPU TimingSimpleCPU, N=64
mkdir -p results
~/proyectos/gem5/build/ARM/gem5.opt -d results/e1_timing_N64 configs/run_e1.py --cpu timing --size 64

# CPU TimingSimpleCPU, N=128
~/proyectos/gem5/build/ARM/gem5.opt -d results/e1_timing_N128 configs/run_e1.py --cpu timing --size 128

# CPU MinorCPU, N=64
~/proyectos/gem5/build/ARM/gem5.opt -d results/e1_minor_N64 configs/run_e1.py --cpu minor --size 64

# CPU MinorCPU, N=128
~/proyectos/gem5/build/ARM/gem5.opt -d results/e1_minor_N128 configs/run_e1.py --cpu minor --size 128

# CPU O3CPU, N=64
~/proyectos/gem5/build/ARM/gem5.opt -d results/e1_o3_N64 configs/run_e1.py --cpu o3 --size 64

# CPU O3CPU, N=128
~/proyectos/gem5/build/ARM/gem5.opt -d results/e1_o3_N128 configs/run_e1.py --cpu o3 --size 128

5. Archivos generados

Cada ejecucion guarda sus resultados en la carpeta indicada por -d.
Como minimo, revisar:

    config.ini   Configuracion utilizada en la simulacion.
    stats.txt    Estadisticas de la simulacion.

Ejemplo para revisar la primera ejecucion:

    ls -lh results/e1_timing_N64/
    grep -E 'type=|size=|clock=' results/e1_timing_N64/config.ini | head -n 40
    head -n 25 results/e1_timing_N64/stats.txt

6. A tener en cuenta 

- Ejecutar los comandos desde la carpeta raiz del proyecto:
  ~/proyectos/proyecto-gem5
- Usar un nombre de carpeta distinto para cada combinacion de CPU y N.
  Asi se evita sobrescribir o mezclar resultados de experimentos.
- No cambiar manualmente los parametros fijos del experimento en run_e1.py:
  un nucleo, frecuencia de 2 GHz, L1I de 32 kB, L1D de 32 kB,
  L2 de 256 kB y modo SE.
- El script recibe unicamente --cpu y --size como parametros del experimento.
