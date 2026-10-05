# synth_micro_bench: synthetic register-file micro-benchmarks

Bare-metal kernels with a known instruction mix, for checking and exploring
the BOOM register-file monitor (`boom.monitors.RegFileMonitor`).

| Benchmark | What it does | Expected register-file behaviour |
|---|---|---|
| `int_ilp` | 8 independent `add` chains | ~3 int adds/cycle, ~6 int reads/cycle |
| `int_chain` | 1 serial `add` chain | ~1 add/cycle, ~2 int reads/cycle |
| `reg_pressure` | 25 independent `add` chains | like `int_ilp`, but 25 live architectural registers |
| `fp_ilp` | 8 independent `fmadd.d` chains | ~1 fmadd/cycle, ~3 FP reads/cycle |
| `fp_chain` | 1 serial `fmadd.d` chain | ~1 fmadd per 4 cycles |
| `mem_stream` | load + add over a 4 KiB buffer | load-port bound, int writes from load writebacks |
| `phases` | all of the above back to back, ~16k cycles each | distinct bands on the waterfalls |

Kernels are inline assembly in `include/kernels.h`; each program prints the cycle
range (`rdcycle`, counted from reset like the monitor windows) and IPC of its kernel.

```
synth_micro_bench/
├── Makefile
├── include/   common.h (timing/report), kernels.h (the kernels)
├── src/       bench.c (one kernel, built per benchmark), phases.c (all kernels)
└── build/     *.riscv, *.dump  (generated; `make clean` removes it)
```

To add a benchmark: add a kernel to `include/kernels.h`, then add its name to
`KERNELS` and an `ITERS_<name>` line in the `Makefile` (or write a new
`src/<name>.c` with its own rule, like `phases`).

```bash
source ../../env.sh         # or: source <conda>/etc/profile.d/conda.sh && source ../../env.sh
make                        # build *.riscv and *.dump
make run -j                 # run all on the LargeBoomRegMonConfig Verilator simulator
make run-fp_ilp             # run one
CONFIG=OtherConfig make run # use another monitor-enabled simulator
```

Logs go to `sims/verilator/output/chipyard.harness.TestHarness.<CONFIG>/`:
`<bench>.log` (program output), `<bench>_int_hart0.bin` / `<bench>_fp_hart0.bin`
(register-file counts). View them with
`python ../../scripts/regmon_web.py --dir ../../sims/verilator/output`.

Iteration counts are set per benchmark in the `Makefile` (`ITERS_<bench>`).
