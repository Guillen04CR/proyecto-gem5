/*
 * gemm_scalar.c — GEMM escalar para E1 (línea base)
 *
 * Multiplica C = A × B (matrices n×n de float), de forma escalar y en un solo hilo.
 * La región de interés (ROI) contiene solo la multiplicación.
 *
 * Uso:    ./gemm_scalar [N]        (N por defecto = 16, mínimo 2)
 * Salida: E1_VALIDATION: PASS  o  E1_VALIDATION: FAIL
 * Guía:   docs/gemm_scalar.md
 */

#include <stdio.h>    /* printf, fprintf */
#include <stdlib.h>   /* atoi, malloc, free, EXIT_SUCCESS/EXIT_FAILURE */

/*
 * Marcas de la región de interés (ROI).
 * - Compilado con -DGEM5: se usan las funciones reales de libm5. Dentro de gem5 son
 *   instrucciones "mágicas" que reinician y vuelcan las estadísticas.
 * - Compilado sin -DGEM5 (nativo o QEMU): esas instrucciones no existen en un
 *   procesador real y el programa moriría con "Illegal instruction". Por eso las
 *   reemplazamos por macros que no hacen nada. (void)0 es una expresión vacía válida.
 */
#ifdef GEM5
#include <gem5/m5ops.h>
#else
#define m5_reset_stats(delay, period) ((void)0)
#define m5_dump_stats(delay, period)  ((void)0)
#endif

/*
 * Guarda contra SVE: este archivo es la línea base escalar. Si alguien lo compila
 * con -march=...+sve, el compilador define __ARM_FEATURE_SVE y la compilación se
 * detiene aquí con un mensaje claro, en vez de producir un binario equivocado.
 */
#if defined(__ARM_FEATURE_SVE)
#error "gemm_scalar.c es la línea base escalar: compilar sin +sve"
#endif

/*
 * Las matrices se guardan en un arreglo de una dimensión, fila por fila
 * ("row-major", el orden natural de C). El elemento (fila i, columna j)
 * de una matriz n×n está en la posición i*n + j.
 */
#define IDX(i, j, n) ((i) * (n) + (j))

/* ---------------------------------------------------------------------------
 * Inicialización determinista (contrato de datos del grupo, no cambiar):
 *     A[i][j] = (i + j) % 8
 *     B[i][j] = (i * j) % 8
 * Solo enteros de 0 a 7: así la validación puede ser exacta (ver check).
 * ------------------------------------------------------------------------- */
static void init(float *A, float *B, int n)
{
    for (int i = 0; i < n; i++) {                         /* cada fila */
        for (int j = 0; j < n; j++) {                     /* cada columna de esa fila */
            /* Primero el % con enteros, después la conversión a float.
             * Al revés, (float)(i + j) % 8, no compila: % no existe para float. */
            A[IDX(i, j, n)] = (float)((i + j) % 8);
            B[IDX(i, j, n)] = (float)((i * j) % 8);
        }
    }
}

/* ---------------------------------------------------------------------------
 * GEMM escalar:  C[i][j] = suma, para k de 0 a n-1, de A[i][k] * B[k][j]
 *
 * - Orden de bucles i-j-k (el "de libro"), con un acumulador local.
 * - noinline: obliga a GCC a dejar gemm como función aparte, para poder
 *   revisarla sola en el desensamblado (objdump --disassemble=gemm).
 * - Sin hilos ni intrínsecos; la vectorización automática se apaga al
 *   compilar con -fno-tree-vectorize.
 * ------------------------------------------------------------------------- */
__attribute__((noinline)) static void gemm(const float *A, const float *B, float *C, int n)
{
    for (int i = 0; i < n; i++) {                         /* fila de C (y de A) */
        for (int j = 0; j < n; j++) {                     /* columna de C (y de B) */
            float suma = 0.0f;                            /* se reinicia para cada C[i][j] */
            for (int k = 0; k < n; k++) {                 /* recorre la fila i de A y la columna j de B */
                suma += A[IDX(i, k, n)] * B[IDX(k, j, n)];
            }
            C[IDX(i, j, n)] = suma;                       /* una sola escritura a memoria por elemento */
        }
    }
}

/* ---------------------------------------------------------------------------
 * Validación contra una referencia independiente.
 * Devuelve cuántos elementos de C están mal (0 = todo correcto).
 *
 * Recalcula cada C[i][j] con enteros (long), no con float. Como A y B solo
 * tienen enteros de 0 a 7, el resultado exacto es un entero: la suma máxima con
 * N = 128 es 49 × 128 = 6272, muy por debajo de 2^24, el mayor entero que float
 * representa sin redondeo. Por eso la comparación puede ser exacta (==), con o
 * sin FMA y en cualquier arquitectura.
 * ------------------------------------------------------------------------- */
static long check(const float *A, const float *B, const float *C, int n)
{
    long errores = 0;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            long ref = 0;                                 /* referencia en aritmética entera */
            for (int k = 0; k < n; k++) {
                ref += (long)A[IDX(i, k, n)] * (long)B[IDX(k, j, n)];
            }
            if (C[IDX(i, j, n)] != (float)ref) {          /* comparación exacta */
                errores++;
            }
        }
    }
    return errores;
}

int main(int argc, char **argv)
{
    /* Tamaño de la matriz: primer argumento, o 16 si no se pasa ninguno.
     * En gem5 se pasa con:  se.py ... -c bin/gemm_scalar -o 128            */
    int n = (argc > 1) ? atoi(argv[1]) : 16;
    if (n < 2) {   /* con n = 1 no existe C[0][1], que imprimimos al final */
        fprintf(stderr, "N debe ser al menos 2\n");
        return EXIT_FAILURE;
    }

    /* Reservar memoria para las tres matrices (n*n floats cada una). */
    size_t bytes = sizeof(float) * (size_t)n * (size_t)n;
    float *A = malloc(bytes);
    float *B = malloc(bytes);
    float *C = malloc(bytes);
    if (!A || !B || !C) {
        fprintf(stderr, "Sin memoria\n");
        return EXIT_FAILURE;
    }

    /* 1. Inicializar — FUERA de la ROI: no queremos medir esto. */
    init(A, B, n);

    /* 2. Inicio de la ROI: gem5 pone en cero todos los contadores aquí.
     *    (0, 0) = sin retardo y sin repetición periódica.                     */
    m5_reset_stats(0, 0);

    /* 3. Lo único que medimos. */
    gemm(A, B, C, n);

    /* 4. Fin de la ROI: gem5 escribe en stats.txt el bloque 1, con lo medido
     *    desde el reset. No reinicia: el bloque 2 (al terminar) es acumulado.  */
    m5_dump_stats(0, 0);

    /* 5. Validar — FUERA de la ROI. */
    long errores = check(A, B, C, n);

    printf("N=%d  C[0][1]=%.1f  errores=%ld\n", n, C[IDX(0, 1, n)], errores);
    printf("E1_VALIDATION: %s\n", (errores == 0) ? "PASS" : "FAIL");

    free(A);
    free(B);
    free(C);

    /* Código de salida 0 si PASS: así un script puede detectar fallos sin leer el texto. */
    return (errores == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
