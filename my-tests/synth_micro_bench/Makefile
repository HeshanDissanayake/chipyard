#################################
# Synthetic register-file benchmarks
#
#   make                 build all benchmarks (+ disassembly)
#   make run -j          run all on the monitor simulator in parallel
#   make run-<bench>     run one, e.g. make run-fp_ilp
#   make clean
#
# Requires the Chipyard environment (source env.sh) and a built simulator
# for $(CONFIG). Register-file logs are written next to the simulator's
# outputs, where scripts/regmon_web.py finds them.
#################################

TARGET  = riscv64-unknown-elf
GCC     = $(TARGET)-gcc
OBJDUMP = $(TARGET)-objdump

CFLAGS  = -std=gnu99 -O2 -march=rv64imafdc -mabi=lp64d -fno-common -fno-builtin-printf -Wall -Iinclude
LDFLAGS = -static -specs=htif_nano.specs

# Loop iterations per single-kernel benchmark (~50k cycles each on LargeBoom)
ITERS_int_ilp      = 4500
ITERS_int_chain    = 1500
ITERS_reg_pressure = 3000
ITERS_fp_ilp       = 1500
ITERS_fp_chain     = 400
ITERS_mem_stream   = 100

KERNELS = int_ilp int_chain reg_pressure fp_ilp fp_chain mem_stream
BENCHES = $(KERNELS) phases

CONFIG   ?= LargeBoomRegMonConfig
SIM_DIR  := $(abspath ../../sims/verilator)
OUT_DIR  := $(SIM_DIR)/output/chipyard.harness.TestHarness.$(CONFIG)

.PHONY: all run clean $(addprefix run-,$(BENCHES))
.DEFAULT_GOAL := all

BUILD   := build
HEADERS := $(wildcard include/*.h)

all: $(BENCHES:%=$(BUILD)/%.riscv) $(BENCHES:%=$(BUILD)/%.dump)

$(BUILD):
	mkdir -p $@

$(KERNELS:%=$(BUILD)/%.riscv): $(BUILD)/%.riscv: src/bench.c $(HEADERS) | $(BUILD)
	$(GCC) $(CFLAGS) -DKERNEL=$* -DITERS=$(ITERS_$*) $(LDFLAGS) $< -o $@

$(BUILD)/phases.riscv: src/phases.c $(HEADERS) | $(BUILD)
	$(GCC) $(CFLAGS) $(LDFLAGS) $< -o $@

$(BUILD)/%.dump: $(BUILD)/%.riscv
	$(OBJDUMP) -d $< > $@

run: $(addprefix run-,$(BENCHES))

$(addprefix run-,$(BENCHES)): run-%: $(BUILD)/%.riscv
	$(MAKE) -s -C $(SIM_DIR) CONFIG=$(CONFIG) run-binary BINARY=$(abspath $<) LOADMEM=1 \
		BREAK_SIM_PREREQ=1 EXTRA_SIM_FLAGS=+regmon_prefix=$(OUT_DIR)/$* > /dev/null
	@printf '%s: ' $*; grep -h 'IPC' $(OUT_DIR)/$*.log | tr -s ' ' | paste -sd ';'

clean:
	rm -rf $(BUILD)
