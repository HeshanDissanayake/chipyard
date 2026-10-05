// Synthetic register-file kernels.
//
// Each kernel is inline assembly so the instruction mix (and therefore the
// register reads/writes per instruction) is exactly known:
//
//   kernel            body (per loop iteration)                    reads/instr  writes/instr
//   int_ilp           32 x add, 8 independent accumulators         2 int        1 int
//   int_chain         32 x add, one serial dependency chain        2 int        1 int
//   reg_pressure      50 x add, 25 independent accumulators        2 int        1 int
//   fp_ilp            32 x fmadd.d, 8 independent accumulators     3 fp         1 fp
//   fp_chain          32 x fmadd.d, one serial dependency chain    3 fp         1 fp
//   mem_stream        8 x (ld + add) over a 4 KiB buffer           ld: 1 int / add: 2 int, each writes 1 int
//
// plus 2 loop-control instructions (addi + bnez) per iteration.

#ifndef KERNELS_H
#define KERNELS_H

#include <stdint.h>

#define REPT4(x)  x x x x
#define REPT8(x)  REPT4(x) REPT4(x)

// 8 independent integer chains: up to 3 adds/cycle on LargeBoom.
static inline void int_ilp(long n)
{
  asm volatile(
    "li t0, 1\n\t"
    "li a0, 0\n\t li a1, 0\n\t li a2, 0\n\t li a3, 0\n\t"
    "li a4, 0\n\t li a5, 0\n\t li a6, 0\n\t li a7, 0\n\t"
    "1:\n\t"
    REPT4("add a0, a0, t0\n\t add a1, a1, t0\n\t add a2, a2, t0\n\t add a3, a3, t0\n\t"
          "add a4, a4, t0\n\t add a5, a5, t0\n\t add a6, a6, t0\n\t add a7, a7, t0\n\t")
    "addi %0, %0, -1\n\t"
    "bnez %0, 1b\n\t"
    : "+r"(n) :: "t0", "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7");
}

// One serial integer chain: ~1 add/cycle.
static inline void int_chain(long n)
{
  asm volatile(
    "li t0, 1\n\t"
    "li a0, 0\n\t"
    "1:\n\t"
    REPT8("add a0, a0, t0\n\t add a0, a0, t0\n\t add a0, a0, t0\n\t add a0, a0, t0\n\t")
    "addi %0, %0, -1\n\t"
    "bnez %0, 1b\n\t"
    : "+r"(n) :: "t0", "a0");
}

// 25 independent integer chains: as many live architectural registers as
// the ABI lets inline asm clobber.
#define RP_REGS(op) \
  op(s1) op(s2) op(s3) op(s4) op(s5) op(s6) op(s7) op(s8) op(s9) op(s10) op(s11) \
  op(a0) op(a1) op(a2) op(a3) op(a4) op(a5) op(a6) op(a7) \
  op(t1) op(t2) op(t3) op(t4) op(t5) op(t6)
#define RP_ZERO(r) "li " #r ", 0\n\t"
#define RP_ADD(r)  "add " #r ", " #r ", t0\n\t"

static inline void reg_pressure(long n)
{
  asm volatile(
    "li t0, 1\n\t"
    RP_REGS(RP_ZERO)
    "1:\n\t"
    RP_REGS(RP_ADD)
    RP_REGS(RP_ADD)
    "addi %0, %0, -1\n\t"
    "bnez %0, 1b\n\t"
    : "+r"(n) ::
      "t0", "t1", "t2", "t3", "t4", "t5", "t6",
      "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7",
      "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11");
}

// 8 independent FP chains: fills the single FP issue port despite the
// 4-cycle fmadd latency. fa = fa * 1.0 + 0.0 keeps values constant.
static inline void fp_ilp(long n)
{
  asm volatile(
    "li t0, 1\n\t"
    "fcvt.d.l ft0, t0\n\t"
    "fcvt.d.l ft1, zero\n\t"
    "fcvt.d.l fa0, t0\n\t fcvt.d.l fa1, t0\n\t fcvt.d.l fa2, t0\n\t fcvt.d.l fa3, t0\n\t"
    "fcvt.d.l fa4, t0\n\t fcvt.d.l fa5, t0\n\t fcvt.d.l fa6, t0\n\t fcvt.d.l fa7, t0\n\t"
    "1:\n\t"
    REPT4("fmadd.d fa0, fa0, ft0, ft1\n\t fmadd.d fa1, fa1, ft0, ft1\n\t"
          "fmadd.d fa2, fa2, ft0, ft1\n\t fmadd.d fa3, fa3, ft0, ft1\n\t"
          "fmadd.d fa4, fa4, ft0, ft1\n\t fmadd.d fa5, fa5, ft0, ft1\n\t"
          "fmadd.d fa6, fa6, ft0, ft1\n\t fmadd.d fa7, fa7, ft0, ft1\n\t")
    "addi %0, %0, -1\n\t"
    "bnez %0, 1b\n\t"
    : "+r"(n) :: "t0", "ft0", "ft1", "fa0", "fa1", "fa2", "fa3", "fa4", "fa5", "fa6", "fa7");
}

// One serial FP chain: one fmadd every ~4 cycles.
static inline void fp_chain(long n)
{
  asm volatile(
    "li t0, 1\n\t"
    "fcvt.d.l ft0, t0\n\t"
    "fcvt.d.l ft1, zero\n\t"
    "fcvt.d.l fa0, t0\n\t"
    "1:\n\t"
    REPT8("fmadd.d fa0, fa0, ft0, ft1\n\t fmadd.d fa0, fa0, ft0, ft1\n\t"
          "fmadd.d fa0, fa0, ft0, ft1\n\t fmadd.d fa0, fa0, ft0, ft1\n\t")
    "addi %0, %0, -1\n\t"
    "bnez %0, 1b\n\t"
    : "+r"(n) :: "t0", "ft0", "ft1", "fa0");
}

// Load-dominated: sums a 4 KiB buffer (L1-resident after the first pass)
// n times. Exercises the memory issue port and load writebacks.
#define MEM_BUF_LONGS 512
static long mem_buf[MEM_BUF_LONGS] __attribute__((unused));

static inline void mem_stream(long n)
{
  asm volatile(
    "li a1, 0\n\t"
    "2:\n\t"
    "mv a0, %1\n\t"
    "li a2, %2\n\t"
    "add a2, a2, %1\n\t"
    "1:\n\t"
    "ld t1, 0(a0)\n\t  ld t2, 8(a0)\n\t  ld t3, 16(a0)\n\t ld t4, 24(a0)\n\t"
    "ld t5, 32(a0)\n\t ld t6, 40(a0)\n\t ld a3, 48(a0)\n\t ld a4, 56(a0)\n\t"
    "add a1, a1, t1\n\t add a1, a1, t2\n\t add a1, a1, t3\n\t add a1, a1, t4\n\t"
    "add a1, a1, t5\n\t add a1, a1, t6\n\t add a1, a1, a3\n\t add a1, a1, a4\n\t"
    "addi a0, a0, 64\n\t"
    "bne a0, a2, 1b\n\t"
    "addi %0, %0, -1\n\t"
    "bnez %0, 2b\n\t"
    : "+r"(n)
    : "r"(mem_buf), "i"(MEM_BUF_LONGS * 8)
    : "t1", "t2", "t3", "t4", "t5", "t6", "a0", "a1", "a2", "a3", "a4", "memory");
}

#endif
