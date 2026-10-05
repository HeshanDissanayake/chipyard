// Timing helpers for the synthetic benchmarks.
//
// mcycle counts core cycles from reset, like the register-file monitor's
// windows, so the printed start/end cycles locate a kernel on the waterfall.

#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>
#include <stdint.h>

static inline uint64_t rdcycle(void)   { uint64_t x; asm volatile("rdcycle %0"   : "=r"(x)); return x; }
static inline uint64_t rdinstret(void) { uint64_t x; asm volatile("rdinstret %0" : "=r"(x)); return x; }

// Run `call` and report its cycle span and IPC.
#define MEASURE(name, call) do {                                              \
    uint64_t c0 = rdcycle(), i0 = rdinstret();                                \
    call;                                                                     \
    uint64_t c1 = rdcycle(), i1 = rdinstret();                                \
    uint64_t dc = c1 - c0, di = i1 - i0;                                      \
    printf("%-13s cycles %8lu .. %8lu  (%7lu)  instret %8lu  IPC %lu.%02lu\n", \
           name, c0, c1, dc, di, di / dc, (di * 100 / dc) % 100);             \
  } while (0)

#endif
