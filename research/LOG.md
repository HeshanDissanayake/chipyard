# Research Log

## 2026-10-05 — Regfile monitor + benchmark folder

- Added `RegFileMonitor` to BOOM: per-register read/write counts over N-cycle windows (int + FP), logged to binary files in RTL sim. Config: `LargeBoomRegMonConfig`.
- Started `my-tests/synth_micro_bench/`: synthetic kernels with known register read/write mixes.
- Measured rates matched predictions within 0.01/cycle.
- **Next:** monitor output for FireSim/FPGA (no DPI there).
