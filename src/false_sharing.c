#define _XOPEN_SOURCE 700

#include <inttypes.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef GEM5
#include <gem5/m5ops.h>
#else
#define m5_reset_stats(delay, period) ((void)0)
#define m5_dump_stats(delay, period)  ((void)0)
#endif

#define CACHELINE_BYTES 64U
#define MAX_THREADS 8
#define DEFAULT_ITERATIONS 100000UL

/* Contadores consecutivos: contador[0] esta en byte 0, contador[1] en byte 8,
 * etc. La alineacion hace que los primeros ocho contadores compartan una linea
 * de 64 B de manera deliberada. */
struct UnpaddedCounter {
    volatile uint64_t value;
};

/* Un contador por linea de cache. La alineacion evita que dos estructuras
 * consecutivas compartan una misma linea. */
struct PaddedCounter {
    volatile uint64_t value;
    unsigned char padding[CACHELINE_BYTES - sizeof(uint64_t)];
} __attribute__((aligned(CACHELINE_BYTES)));

_Static_assert(sizeof(struct PaddedCounter) == CACHELINE_BYTES,
               "PaddedCounter debe ocupar exactamente una linea de cache");

static struct UnpaddedCounter unpadded[MAX_THREADS]
    __attribute__((aligned(CACHELINE_BYTES)));
static struct PaddedCounter padded[MAX_THREADS];

struct WorkerArgs {
    int id;
    unsigned long iterations;
    int use_padding;
    pthread_barrier_t *ready;
    pthread_barrier_t *start;
};

static void increment_assigned_counter(const struct WorkerArgs *args)
{
    if (args->use_padding) {
        volatile uint64_t *counter = &padded[args->id].value;
        for (unsigned long i = 0; i < args->iterations; ++i) {
            ++*counter;
        }
    } else {
        volatile uint64_t *counter = &unpadded[args->id].value;
        for (unsigned long i = 0; i < args->iterations; ++i) {
            ++*counter;
        }
    }
}

static void *increment_counter(void *opaque)
{
    struct WorkerArgs *args = opaque;

    /* Todos los hilos existen antes de que main reinicie estadisticas. */
    (void)pthread_barrier_wait(args->ready);

    /* main libera esta barrera inmediatamente despues de m5_reset_stats(). */
    (void)pthread_barrier_wait(args->start);

    increment_assigned_counter(args);

    return NULL;
}

static void usage(const char *program)
{
    fprintf(stderr,
            "Uso: %s <hilos: 2|4|8> <unpadded|padded> [iteraciones]\n",
            program);
}

static int parse_threads(const char *text, int *threads)
{
    char *end = NULL;
    long value = strtol(text, &end, 10);

    if (*text == '\0' || *end != '\0' ||
        (value != 2 && value != 4 && value != 8)) {
        return 0;
    }

    *threads = (int)value;
    return 1;
}

static int parse_iterations(const char *text, unsigned long *iterations)
{
    char *end = NULL;
    unsigned long value = strtoul(text, &end, 10);

    if (*text == '\0' || *end != '\0' || value == 0) {
        return 0;
    }

    *iterations = value;
    return 1;
}