
# Guía de ejecución - Experimento E4 (GEM5)

## 1. Ubicación del proyecto

Todos los comandos deben ejecutarse desde:

```bash
cd ~/proyectos/proyecto-gem5
```

## 2. Configuración del experimento

- Arquitectura: X86-64.
- Procesador: O3CPU (fuera de orden).
- Núcleos: 1, 2, 4 y 8.
- Dimensión de matrices: 128 x 128.
- Paralelización: OpenMP.
- Cachés: L1 y L2 habilitadas.
- fetchWidth: 2.
- decodeWidth: 2.
- renameWidth: 2.
- dispatchWidth: 2.
- issueWidth: 2.
- wbWidth: 2.
- commitWidth: 2.
- forwardComSize: 10.

## 3. Compilar el programa GEMM

```bash
gcc -O2 -fopenmp src/gemm.c -o bin/gemm
```

## 4. Compilar el analizador de resultados

```bash
gcc -O2 -Wall -Wextra src/analizar_gemm.c -o bin/analizar_gemm
```

## 5. Ejecutar las cuatro simulaciones

```bash
python3 scripts/ejecutar_gemm.py
```

El script utiliza el simulador externo ubicado en:

~/proyectos/gem5/build/X86/gem5.opt

Los resultados se almacenan en:

- results/gemm_1_check/
- results/gemm_2_check/
- results/gemm_4_check/
- results/gemm_8_check/

IMPORTANTE: ejecutar nuevamente el script puede sobrescribir
los resultados existentes.

## 6. Verificar los archivos generados

```bash
ls -lh results/gemm_1_check/
ls -lh results/gemm_2_check/
ls -lh results/gemm_4_check/
ls -lh results/gemm_8_check/
```

## 7. Consultar los resultados resumidos

### 1 núcleo

```bash
grep -E "GEMM completado|Hilos solicitados|Hilos utilizados|Checksum|Exiting" results/gemm_1_check/console.txt

grep -E "simTicks|simInsts|numCycles" results/gemm_1_check/stats.txt
```

### 2 núcleos

```bash
grep -E "GEMM completado|Hilos solicitados|Hilos utilizados|Checksum|Exiting" results/gemm_2_check/console.txt

grep -E "simTicks|simInsts|numCycles" results/gemm_2_check/stats.txt
```

### 4 núcleos

```bash
grep -E "GEMM completado|Hilos solicitados|Hilos utilizados|Checksum|Exiting" results/gemm_4_check/console.txt

grep -E "simTicks|simInsts|numCycles" results/gemm_4_check/stats.txt
```

### 8 núcleos

```bash
grep -E "GEMM completado|Hilos solicitados|Hilos utilizados|Checksum|Exiting" results/gemm_8_check/console.txt

grep -E "simTicks|simInsts|numCycles" results/gemm_8_check/stats.txt
```

## 8. Consultar los registros completos

```bash
cat results/gemm_1_check/console.txt
cat results/gemm_2_check/console.txt
cat results/gemm_4_check/console.txt
cat results/gemm_8_check/console.txt
```

## 9. Ejecutar el analizador de rendimiento

```bash
./bin/analizar_gemm 128 1e12 \
  1:results/gemm_1_check/stats.txt \
  2:results/gemm_2_check/stats.txt \
  4:results/gemm_4_check/stats.txt \
  8:results/gemm_8_check/stats.txt
```

El analizador calcula:

- Ticks de simulación.
- Tiempo de ejecución en milisegundos.
- Speedup.
- Eficiencia de paralelización.
- Fracción serial efectiva mediante la ley de Amdahl.

La frecuencia de 1e12 Hz corresponde a la frecuencia
global de ticks de gem5, no a la frecuencia del procesador.

## 10. Consideraciones

- No es necesario recompilar el simulador gem5.
- Los ejecutables del E4 utilizan arquitectura X86-64.
- Los archivos del E1 no deben modificarse.
- Los archivos console.txt son generados por la nueva
  versión de ejecutar_gemm.py.
- Las simulaciones antiguas trasladadas podrían no
  contener dichos archivos.
