# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Chipyard (v1.11.0 base, branch `v1.11.0-heshds`) is a Chisel/Scala framework for generating RISC-V SoCs. Upstream docs: https://chipyard.readthedocs.io/. This fork is used mainly for **FireSim FPGA-accelerated simulation on a Xilinx VCU118** board, with custom target configs added in `generators/firechip`.

## Environment

Always source the environment first (activates the conda env in `.conda-env`, sets `RISCV`, adds FireMarshal to `PATH`):

```bash
source env.sh
# for FireSim work, additionally:
cd sims/firesim && source sourceme-manager.sh
```

In a non-interactive shell (e.g. Claude's Bash tool), `conda activate` inside `env.sh` fails with "Run 'conda init'", leaving a stale `RISCV` from the user's profile and no `riscv64-unknown-elf-gcc`/`verilator` on PATH. Source conda first:

```bash
source /home/heshds/miniforge3/etc/profile.d/conda.sh && source env.sh
```

Setup (already done in this checkout) is `./build-setup.sh`; submodules are initialized by `scripts/init-submodules-no-riscv-tools.sh`.

## Build / simulate (RTL software simulation)

All RTL sim flows run from a simulator directory (`sims/verilator`, `sims/vcs`, `sims/xcelium`) and are driven by `common.mk` + `variables.mk`. The key variable is `CONFIG` (a Scala `Config` class, default `RocketConfig`).

```bash
cd sims/verilator
make CONFIG=RocketConfig -j$(nproc)                  # build simulator
make CONFIG=RocketConfig verilog                      # only elaborate + emit Verilog
make CONFIG=RocketConfig run-binary BINARY=../../tests/hello.riscv
make CONFIG=RocketConfig run-binary BINARY=... LOADMEM=1   # preload DRAM (much faster)
make CONFIG=RocketConfig run-asm-tests-fast           # riscv-tests ISA suite
make CONFIG=RocketConfig run-bmark-tests-fast         # riscv-tests benchmarks
make CONFIG=RocketConfig debug run-binary-debug BINARY=...  # waveform-dumping sim
make help                                             # list all variables/targets
make find-config-fragments                            # list available config fragments
make launch-sbt                                       # interactive sbt shell
```

- `SUB_PROJECT` (in `variables.mk`) switches the default MODEL/TOP/CONFIG_PACKAGE for unit-test flows (`rocketchip`, `testchipip`, `icenet`, `constellation`, `hwacha`).
- Build outputs go to `sims/<sim>/generated-src/<long_name>/`; `gen-collateral/` holds the emitted Verilog.
- Bare-metal test programs: `make -C tests` (C sources in `tests/`, built with `riscv64-unknown-elf-gcc` via `libgloss.mk`).
- CI test matrix lives in `.github/scripts/run-tests.sh` and `defaults.sh` (maps job names to CONFIGs) — a good reference for which configs/tests go together.

## Elaboration pipeline (what `make` actually does)

1. **sbt** compiles the Scala projects defined in the root `build.sbt` and runs `chipyard.Generator` to elaborate `$(MODEL)` (TestHarness) with `$(CONFIG)` → CHIRRTL `.fir` + annotations.
2. **barstools `GenerateModelStageMain`** (SFC) optionally lowers to LowFIRRTL (only when `Fixed` types are present or `ENABLE_CUSTOM_FIRRTL_PASS` is set).
3. **firtool** (MFC/CIRCT) emits split Verilog and a seq-mem conf.
4. `scripts/uniquify-module-names.py` / `split-mems-conf.py` separate DUT (`ChipTop`) from harness modules; **barstools MacroCompiler** maps SRAMs (synflops for sim).

## Architecture

- `build.sbt` defines every generator as an sbt subproject; `chipyard` depends on nearly all of them. `firechip` depends on `chipyard` plus FireSim's `midas`/`firesimLib` (pulled in via `ProjectRef` into `sims/firesim`).
- **Configs are composed with the CDE `Config` mixin pattern** (`tools/cde`): `new FragmentA ++ new FragmentB ++ new BaseConfig`. Leftmost fragment wins. Top-level configs are in `generators/chipyard/src/main/scala/config/*Configs.scala`, all built on `AbstractConfig.scala`; reusable fragments are in `config/fragments/`.
- Hierarchy: `TestHarness` (harness/) → `ChipTop` (ChipTop.scala, IO cells/clocking) → `DigitalTop` (DigitalTop.scala, mixes in peripheral traits) → `ChipyardSystem`/`Subsystem` (tiles, buses). **IOBinders** (iobinders/) punch ports out of the system to ChipTop; **HarnessBinders** (harness/) connect ChipTop ports to sim models in the harness. New peripherals usually need a trait on DigitalTop, an IOBinder, and a HarnessBinder.
- Examples of adding MMIO/RoCC/accelerator blocks: `generators/chipyard/src/main/scala/example/`.
- `generators/*` are git submodules (rocket-chip, boom, testchipip, gemmini, …). `generators/rocket-chip` and `sims/firesim` have local modifications — check `git -C <submodule> status` before editing and remember changes there are committed in the submodule, not the top repo.
- `fpga/` is the non-FireSim FPGA prototyping flow (fpga-shells; `make -C fpga SUB_PROJECT=vcu118 bitstream`).
- `vlsi/` is the Hammer VLSI flow; `software/firemarshal` builds Linux/bare-metal workloads.

## FireSim on VCU118 (this fork's main use)

- FireSim is at `sims/firesim` (used as a library by Chipyard's sbt build). Target designs/configs are in `generators/firechip/src/main/scala/TargetConfigs.scala` (custom additions include `FireSimLargeBoomConfigVCU1184GB`, `FireSimQuadRocket4GiBDRAMConfig`). Platform configs (e.g. `BaseXilinxVCU118Config`, `WithPrintfSynthesis_`) are in `sims/firesim/sim/firesim-lib/src/main/scala/configs/CompilerConfigs.scala`.
- Build recipes: `sims/firesim/deploy/config_build_recipes.yaml` (search `xilinx_vcu118_`); select which to build in `config_build.yaml` `builds_to_run`, then `firesim buildbitstream`. Build farm is `localhost` with `default_build_dir` = this repo root.
- Consequently, the untracked top-level `platforms/xilinx_vcu118/garnet-firesim/` is **FireSim bitstream build output**: a copy of the Garnet shell (`sims/firesim/platforms/xilinx_vcu118/garnet-firesim`) with one `cl_xilinx_vcu118-firesim-<DESIGN>-<TARGET_CONFIG>-<PLATFORM_CONFIG>/` directory per build (contains `build/*.bit`, `*.dcp`). Edit the source under `sims/firesim/platforms/`, not these copies. Garnet uses partial reconfiguration (`xvsecctl` loads `*_pblock_partition_partial.bit`) and requires Vivado 2023.1.
- Metasimulation / driver builds run from `sims/firesim/sim`. Defaults there are F1 (`PLATFORM=f1`, `PLATFORM_CONFIG=BaseF1Config`, `TARGET_CONFIG=FireSimRocketConfig`, set in `src/main/makefrag/firesim/config.mk`), so always override them for this board:
  ```bash
  cd sims/firesim/sim
  make PLATFORM=xilinx_vcu118 TARGET_CONFIG=FireSimRocket4GiBDRAMConfig PLATFORM_CONFIG=BaseXilinxVCU118Config verilator   # build metasim
  make PLATFORM=xilinx_vcu118 ... run-verilator SIM_BINARY=<elf>    # run metasim (also run-vcs, run-xcelium, run-xsim)
  make PLATFORM=xilinx_vcu118 ... driver                            # host driver for the FPGA
  ```
- In `TARGET_CONFIG`/`PLATFORM_CONFIG`, `_` separates config classes that are chained together (e.g. `WithPrintfSynthesis_BaseXilinxVCU118Config`). Each piece is prefixed with its package (`make/config.mk`). Outputs are named `<PLATFORM>-<TARGET_PROJECT>-<DESIGN>-<TARGET_CONFIG>-<PLATFORM_CONFIG>`.

## Hardware monitors (local additions)

Monitors are standalone observers that never modify the monitored design; they live in `generators/boom/src/main/scala/monitors/` and are hooked in by a few lines in the parent module, gated by an off-by-default `BoomCoreParams` field.

- `RegFileMonitor` (`regfile-monitor.scala`): per-physical-register read/write counts over N-cycle windows for the int and FP register files. Enabled with `boom.monitors.WithRegFileMonitor(windowCycles = N)`; test config `LargeBoomRegMonConfig`.
- RTL sim output is a binary file per register file via DPI-C (`src/main/resources/csrc/regfile_monitor.cc`, format documented at its top), including the trailing partial window. Plusargs: `EXTRA_SIM_FLAGS="+regmon_prefix=<path>"` (files `<path>_{int,fp}_hart<N>.bin`, default prefix `regmon` in the run dir), `+regmon_off`.
- Read logs with `scripts/regmon_read.py FILE...` (summary) or `--records`; as a library `load(path)` returns `(header, counts[window, read/write, preg])`.
- Web UI: `scripts/regmon_web.py --dir sims/verilator/output` (stdlib server + numpy, page in `scripts/regmon_web.html`, no external JS) pairs each run's `_int_`/`_fp_` logs and shows two waterfalls (register × cycle) on a shared cycle axis at http://127.0.0.1:8050; `?log=<substring>` preselects a run.
- `my-tests/` holds the user's own tests. `my-tests/synth_micro_bench/`: synthetic inline-asm kernels with known register read/write mixes (`include/kernels.h`, drivers in `src/`, binaries in `build/`); `make && make run -j` builds and runs them on `LargeBoomRegMonConfig`, logs land in `sims/verilator/output/...`. Measured monitor rates matched the instruction-mix predictions to within 0.01/cycle — use them as a regression check after monitor changes.
- The DPI sink is sim-only: FireSim/FPGA builds need `dpiLog = false`.
- Research progress is logged in `research/LOG.md` (short dated entries, newest on top).

## Contribution notes

Upstream `main` is the pre-release branch; releases are tags. Submodule `master/main` should match what's pinned in Chipyard `main` (see `CONTRIBUTING.md`).
