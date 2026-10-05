#!/usr/bin/env python3

# Web UI for RegFileMonitor binary logs (see regmon_read.py).
#
#   regmon_web.py [--dir DIR] [--port 8050] [--host 127.0.0.1]
#
# Scans DIR recursively for *.bin logs and serves an interactive page with
# register-file activity over time, a register x time heatmap and
# per-register totals. Long runs are binned server-side so a response never
# has more columns than the browser asked for.

import argparse
import errno
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regmon_read import load  # noqa: E402

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regmon_web.html")


class LogIndex:
    """Known log files, addressed by index so clients never send paths."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.files = []
        self._cache = {}

    def scan(self):
        found = []
        for dirpath, _, names in os.walk(self.root):
            for n in sorted(names):
                if not n.endswith(".bin"):
                    continue
                path = os.path.join(dirpath, n)
                try:
                    hdr, _ = self._load(path)
                except (ValueError, OSError):
                    continue  # not a regmon log
                found.append((path, hdr))
        found.sort(key=lambda x: x[0])
        self.files = found
        return [dict(id=i, name=os.path.relpath(p, self.root), **h) for i, (p, h) in enumerate(found)]

    def _load(self, path):
        mtime = os.path.getmtime(path)
        hit = self._cache.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
        res = load(path)
        self._cache[path] = (mtime, res)
        return res

    def get(self, idx):
        path, _ = self.files[idx]
        return self._load(path)


def binned(hdr, counts, start, end, max_cols):
    """Sum windows [start, end) into at most max_cols bins."""
    n = hdr["num_windows"]
    start = max(0, min(start, n))
    end = max(start, min(end, n))
    sel = counts[start:end].astype(np.int64)  # (w, 2, regs)
    w = sel.shape[0]

    cycles = np.full(n, hdr["window_cycles"], dtype=np.int64)
    if n:
        cycles[-1] = hdr["last_window_cycles"]
    cycles = cycles[start:end]

    per_bin = max(1, -(-w // max(1, max_cols)))  # ceil
    cols = -(-w // per_bin) if w else 0
    edges = np.arange(0, cols * per_bin, per_bin)
    if w:
        sums = np.add.reduceat(sel, edges, axis=0)          # (cols, 2, regs)
        bin_cycles = np.add.reduceat(cycles, edges)
    else:
        sums = np.zeros((0, 2, hdr["num_regs"]), dtype=np.int64)
        bin_cycles = np.zeros(0, dtype=np.int64)

    return dict(
        start=start, end=end, per_bin=int(per_bin),
        bin_start=(edges + start).tolist(),
        bin_cycles=bin_cycles.tolist(),
        reads=sums[:, 0, :].tolist(),       # [col][preg]
        writes=sums[:, 1, :].tolist(),
        reg_reads=sel[:, 0, :].sum(axis=0).tolist(),
        reg_writes=sel[:, 1, :].sum(axis=0).tolist(),
        total_cycles=int(cycles.sum()),
    )


def make_handler(index):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, separators=(",", ":")), "application/json")

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            try:
                if url.path == "/":
                    with open(PAGE, "rb") as f:
                        self._send(200, f.read(), "text/html; charset=utf-8")
                elif url.path == "/api/files":
                    self._json(dict(root=index.root, files=index.scan()))
                elif url.path == "/api/data":
                    idx = int(q["file"][0])
                    if not 0 <= idx < len(index.files):
                        return self._json(dict(error="unknown file"), 404)
                    hdr, counts = index.get(idx)
                    start = int(q.get("start", ["0"])[0])
                    end = int(q.get("end", [str(hdr["num_windows"])])[0])
                    cols = min(4000, max(1, int(q.get("cols", ["800"])[0])))
                    self._json(dict(header=hdr, **binned(hdr, counts, start, end, cols)))
                else:
                    self._json(dict(error="not found"), 404)
            except (KeyError, ValueError) as e:
                self._json(dict(error=f"bad request: {e}"), 400)

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    ap = argparse.ArgumentParser(description="Web UI for RegFileMonitor logs")
    ap.add_argument("--dir", default=".", help="directory to scan for *.bin logs (recursive)")
    ap.add_argument("--port", type=int, default=8050)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    index = LogIndex(args.dir)
    n = len(index.scan())
    srv = None
    for port in range(args.port, args.port + 20):
        try:
            srv = ThreadingHTTPServer((args.host, port), make_handler(index))
            break
        except OSError as e:
            if e.errno != errno.EADDRINUSE:
                raise
            print(f"port {port} is in use, trying {port + 1}", flush=True)
    if srv is None:
        sys.exit(f"no free port in {args.port}-{args.port + 19}; pass --port")
    args.port = srv.server_address[1]
    print(f"regmon web UI: http://{args.host}:{args.port}/  ({n} logs under {index.root})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
