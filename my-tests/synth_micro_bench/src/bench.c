// Single-kernel benchmark. Built once per kernel by the Makefile:
//   -DKERNEL=<kernel from kernels.h> -DITERS=<loop iterations>

#include "common.h"
#include "kernels.h"

#define STR_(x) #x
#define STR(x)  STR_(x)

int main(void)
{
  MEASURE(STR(KERNEL), KERNEL(ITERS));
  return 0;
}
