
#include <stdio.h>
#include <stdlib.h>
#include <omp.h>

int main(int argc, char *argv[]) {

    int N = 128;
    int num_threads = 1;

    if (argc >= 2)
        N = atoi(argv[1]);

    if (argc >= 3)
        num_threads = atoi(argv[2]);

    if (N <= 0 || num_threads <= 0) {
        printf("Dimensiones o hilos invalidos.\n");
        return 1;
    }

    omp_set_dynamic(0);
    omp_set_num_threads(num_threads);

    double *A = malloc(N * N * sizeof(double));
    double *B = malloc(N * N * sizeof(double));
    double *C = malloc(N * N * sizeof(double));

    if (A == NULL || B == NULL || C == NULL) {
        printf("Error al reservar memoria.\n");
        free(A);
        free(B);
        free(C);
        return 1;
    }

    // Inicializar matrices
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            A[i * N + j] = (i + j) % 10;
            B[i * N + j] = (i - j + 10) % 10;
        }
    }

    // Comprobar cantidad real de hilos
    int actual_threads = 0;

    #pragma omp parallel
    {
        #pragma omp single
        actual_threads = omp_get_num_threads();
    }

    // Multiplicacion de matrices paralelizada por filas
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {

            double sum = 0.0;

            for (int k = 0; k < N; k++) {
                sum += A[i * N + k] * B[k * N + j];
            }

            C[i * N + j] = sum;
        }
    }

    // Calcular checksum para verificar el resultado
    double checksum = 0.0;

    for (int i = 0; i < N * N; i++) {
        checksum += C[i];
    }

    printf("GEMM completado correctamente.\n");
    printf("Dimension: %d x %d\n", N, N);
    printf("Hilos solicitados: %d\n", num_threads);
    printf("Hilos utilizados: %d\n", actual_threads);
    printf("Checksum: %.2f\n", checksum);

    free(A);
    free(B);
    free(C);

    return 0;
}
