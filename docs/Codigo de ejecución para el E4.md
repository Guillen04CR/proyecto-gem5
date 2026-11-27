
# Experimento E4 (GEM5) Comandos y datos importantes a tener en cuenta para probar el experimento

## 1. Ubicación del proyecto

Todos los comandos deben ejecutarse desde:

```bash
cd ~/proyectos/proyecto-gem5
```

## 2. Configuraciones para el experimento

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

## 4. Compilar "analizar_gem"

```bash
gcc -O2 -Wall -Wextra src/analizar_gemm.c -o bin/analizar_gemm
```

## 5. Ejecutar "ejectutar_gemm" para correr el ejecutable

```bash
python3 scripts/ejecutar_gemm.py
```

## 6. Verificar los archivos generados

```bash
ls -lh results/gemm_1_check/
ls -lh results/gemm_2_check/
ls -lh results/gemm_4_check/
ls -lh results/gemm_8_check/
```

Cada uno de estos archivos generados contienen la info de cada prueba con 1,2,4 y 8 nucleos

## 7. Revisar los resultados "cortos"

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

## 8. Revisar los resultados "completos"

```bash
cat results/gemm_1_check/console.txt
cat results/gemm_2_check/console.txt
cat results/gemm_4_check/console.txt
cat results/gemm_8_check/console.txt
```

## 9. Para analizar el rendimiento (importante si las compilaciones tardan mucho)(frecuencia de 1e12 Hz)

```bash
./bin/analizar_gemm 128 1e12 \
  1:results/gemm_1_check/stats.txt \
  2:results/gemm_2_check/stats.txt \
  4:results/gemm_4_check/stats.txt \
  8:results/gemm_8_check/stats.txt
```
