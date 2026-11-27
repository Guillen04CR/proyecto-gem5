
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#define MAX_CONFIGS 32
#define MAX_PATH 512
#define MAX_LINE 1024

typedef struct {
    int cores;
    char path[MAX_PATH];
    unsigned long long ticks;
    double time_seconds;
    double speedup;
    double efficiency;
    double serial_fraction;
} Result;

int read_ticks(const char *path, unsigned long long *ticks) {
    FILE *file = fopen(path, "r");

    if (file == NULL) {
        perror(path);
        return 0;
    }

    char line[MAX_LINE];
    int found = 0;

    while (fgets(line, sizeof(line), file)) {
        if (sscanf(line, "simTicks %llu", ticks) == 1) {
            found = 1;
            break;
        }
    }

    fclose(file);
    return found;
}

int main(int argc, char *argv[]) {

    if (argc < 5) {
        printf("Uso:\n");
        printf("./analizar_gemm N frecuencia_hz "
               "cores:stats.txt [cores:stats.txt ...]\n\n");

        printf("Ejemplo:\n");
        printf("./analizar_gemm 128 1e12 "
               "1:m5out/gemm_1/stats.txt "
               "2:m5out/gemm_2/stats.txt "
               "4:m5out/gemm_4/stats.txt "
               "8:m5out/gemm_8/stats.txt\n");

        return 1;
    }

    int N = atoi(argv[1]);
    double frequency = atof(argv[2]);

    if (N <= 0 || frequency <= 0 || argc - 3 > MAX_CONFIGS) {
        printf("Error: parametros invalidos.\n");
        return 1;
    }

    int count = argc - 3;
    Result results[MAX_CONFIGS];

    int baseline_index = -1;

    // Leer configuraciones y extraer simTicks
    for (int i = 0; i < count; i++) {

        char argument[MAX_PATH + 32];
        strncpy(argument, argv[i + 3], sizeof(argument) - 1);
        argument[sizeof(argument) - 1] = '\0';

        char *separator = strchr(argument, ':');

        if (separator == NULL) {
            printf("Error: formato incorrecto: %s\n", argument);
            return 1;
        }

        *separator = '\0';

        char *endptr;
        long cores = strtol(argument, &endptr, 10);

        if (*argument == '\0' || *endptr != '\0' ||
            cores <= 0 || cores > 100000) {
            printf("Error: cantidad de nucleos invalida.\n");
            return 1;
        }

        results[i].cores = (int)cores;

        if (strlen(separator + 1) >= MAX_PATH) {
            printf("Error: ruta demasiado larga.\n");
            return 1;
        }

        strcpy(results[i].path, separator + 1);

        if (!read_ticks(results[i].path, &results[i].ticks)) {
            printf("Error: no se encontro simTicks en %s\n",
                   results[i].path);
            return 1;
        }

        if (results[i].cores == 1) {
            if (baseline_index != -1) {
                printf("Error: hay mas de una configuracion de 1 nucleo.\n");
                return 1;
            }
            baseline_index = i;
        }

        // Tiempo en segundos
        results[i].time_seconds =
            (double)results[i].ticks / frequency;
    }

    if (baseline_index == -1) {
        printf("Error: se necesita una configuracion de 1 nucleo.\n");
        return 1;
    }

    double baseline_time = results[baseline_index].time_seconds;

    // Calcular indicadores
    for (int i = 0; i < count; i++) {

        results[i].speedup =
            baseline_time / results[i].time_seconds;

        results[i].efficiency =
            results[i].speedup / results[i].cores * 100.0;

        if (results[i].cores == 1) {
            results[i].serial_fraction = -1.0;
        } else {
            double P = results[i].cores;
            double S = results[i].speedup;

            results[i].serial_fraction =
                (1.0 / S - 1.0 / P) / (1.0 - 1.0 / P);
        }
    }

    // Mostrar resultados
    printf("\n============================================================\n");
    printf("       ANALISIS DE RENDIMIENTO GEMM - GEM5\n");
    printf("============================================================\n");

    printf("Dimension de matriz: %d x %d\n", N, N);
    printf("Frecuencia de simulacion: %.3e Hz\n", frequency);
    printf("Configuraciones analizadas: %d\n", count);

    printf("------------------------------------------------------------\n");

    printf("%-7s %-16s %-14s %-10s %-12s %-12s\n",
           "Cores", "Ticks", "Tiempo(ms)",
           "Speedup", "Eficiencia", "Serial(%)");

    printf("------------------------------------------------------------\n");

    for (int i = 0; i < count; i++) {

        printf("%-7d %-16llu %-14.6f %-10.4f %-11.2f%% ",
               results[i].cores,
               results[i].ticks,
               results[i].time_seconds * 1000.0,
               results[i].speedup,
               results[i].efficiency);

        if (results[i].serial_fraction < 0) {
            printf("%-12s\n", "N/A");
        } else {
            printf("%-11.2f%%\n",
                   results[i].serial_fraction * 100.0);
        }
    }

    printf("============================================================\n");

    printf("\nFraccion serial: estimacion efectiva mediante Amdahl.\n");
    printf("Referencia de speedup: configuracion de 1 nucleo.\n\n");

    return 0;
}
