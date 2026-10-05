// All kernels back to back, ~16k cycles each, so every phase spans several
// monitor windows and shows up as a distinct band on the waterfalls.

#include "common.h"
#include "kernels.h"

int main(void)
{
  MEASURE("int_ilp",      int_ilp(1500));
  MEASURE("mem_stream",   mem_stream(32));
  MEASURE("fp_ilp",       fp_ilp(500));
  MEASURE("int_chain",    int_chain(500));
  MEASURE("fp_chain",     fp_chain(130));
  MEASURE("reg_pressure", reg_pressure(1000));
  return 0;
}
