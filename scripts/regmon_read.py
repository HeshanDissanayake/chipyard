#!/usr/bin/env python3

# Reader for the binary logs written by boom.monitors.RegFileMonitor
# (generators/boom/src/main/resources/csrc/regfile_monitor.cc).
#
# As a library:
#   from regmon_read import load
#   hdr, counts = load("regmon_int_hart0.bin")
#   counts.shape == (num_windows, 2, num_regs)   # [:, 0] reads, [:, 1] writes
#
# From the command line:
#   regmon_read.py FILE [FILE ...]          summary
#   regmon_read.py --records FILE           one line per (window, preg)

import argparse
import os
import struct
import sys

import numpy as np

HEADER = struct.Struct("<IHBBIIQII")
MAGIC = 0x4E4D4752  # "RGMN"
UNKNOWN = 0xFFFFFFFF
RF_NAMES = {0: "int", 1: "fp"}


def load(path):
    """Return (header dict, counts array of shape (windows, 2, num_regs))."""
    with open(path, "rb") as f:
        raw = f.read(HEADER.size)
    if len(raw) < HEADER.size:
        raise ValueError(f"{path}: too short for a header")
    (magic, version, cbytes, rf_type, num_regs, hart_id,
     window_cycles, num_windows, last_cycles) = HEADER.unpack(raw)
    if magic != MAGIC:
        raise ValueError(f"{path}: bad magic 0x{magic:08x}")
    if version != 1:
        raise ValueError(f"{path}: unsupported version {version}")

    dtype = {1: np.uint8, 2: np.uint16, 4: np.uint32}[cbytes]
    rec_items = 2 * num_regs
    data = np.fromfile(path, dtype=np.dtype(dtype).newbyteorder("<"), offset=HEADER.size)

    clean = num_windows != UNKNOWN
    if not clean:
        # not closed cleanly: keep only complete records
        num_windows = data.size // rec_items
        last_cycles = window_cycles
    data = data[:num_windows * rec_items].reshape(num_windows, 2, num_regs)

    hdr = dict(rf_type=RF_NAMES.get(rf_type, str(rf_type)), num_regs=num_regs,
               hart_id=hart_id, window_cycles=window_cycles, num_windows=num_windows,
               last_window_cycles=last_cycles, counter_bytes=cbytes, closed_cleanly=clean)
    return hdr, data


def summary(path):
    hdr, c = load(path)
    reads, writes = c[:, 0, :].astype(np.uint64), c[:, 1, :].astype(np.uint64)
    print(f"{path}")
    print(f"  {hdr['rf_type']} regfile, hart {hdr['hart_id']}, {hdr['num_regs']} pregs, "
          f"{hdr['counter_bytes']}-byte counters, window {hdr['window_cycles']} cycles")
    partial = hdr["last_window_cycles"] != hdr["window_cycles"]
    print(f"  {hdr['num_windows']} windows"
          + (f" (last is partial: {hdr['last_window_cycles']} cycles)" if partial else "")
          + ("" if hdr["closed_cleanly"] else "  [file not closed cleanly]"))
    print(f"  total reads {int(reads.sum())}, writes {int(writes.sum())}")
    if hdr["num_windows"] == 0:
        return
    per_win = reads.sum(axis=1)
    print(f"  reads/window: min {int(per_win.min())}, max {int(per_win.max())}, "
          f"mean {per_win.mean():.1f}")
    tot = reads.sum(axis=0) + writes.sum(axis=0)
    top = np.argsort(tot)[::-1][:5]
    print("  busiest pregs: " + ", ".join(f"p{p} ({int(reads[:, p].sum())}r/{int(writes[:, p].sum())}w)"
                                          for p in top if tot[p] > 0))
    print(f"  pregs never touched: {int((tot == 0).sum())}")


def records(path):
    hdr, c = load(path)
    name = hdr["rf_type"]
    for w in range(hdr["num_windows"]):
        for p in range(hdr["num_regs"]):
            print(f"[regmon-{name}] window={w} preg={p} reads={c[w, 0, p]} writes={c[w, 1, p]}")


def main():
    ap = argparse.ArgumentParser(description="Read RegFileMonitor binary logs")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--records", action="store_true", help="print every (window, preg) record")
    args = ap.parse_args()
    for path in args.files:
        if not os.path.exists(path):
            sys.exit(f"{path}: not found")
        if args.records:
            records(path)
        else:
            summary(path)


if __name__ == "__main__":
    main()
