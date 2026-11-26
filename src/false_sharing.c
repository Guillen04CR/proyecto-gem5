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