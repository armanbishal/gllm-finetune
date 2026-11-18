import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EVENTS = "power/energy-pkg/,power/energy-ram/"
MEASURE_LOCK = threading.Lock()

def have_perf():
    try:
        r = subprocess.run(["perf", "stat", "-e", "power/energy-pkg/", "--",
                            sys.executable, "-c", "pass"],
                           capture_output=True, text=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return "energy-pkg" in r.stderr and "<not supported>" not in r.stderr

def grab(stderr, needle):
    for line in stderr.splitlines():
        if needle in line:
            try:
                return float(line.split(",")[0])
            except (ValueError, IndexError):
                return None
    return None


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def measure(code, reps, timeout):
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(code)

    pkg, ram, rt = [], [], []
    try:
        for _ in range(reps):
            cmd = ["perf", "stat", "-e", EVENTS, "-x", ",", "--", sys.executable, path]
            t0 = time.time()
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "timeout"}
            except FileNotFoundError:
                return {"ok": False, "error": "perf not installed on this node"}
            if r.returncode != 0:
                tail = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "?"
                return {"ok": False, "error": "exit %d: %s" % (r.returncode, tail)}
            p = grab(r.stderr, "energy-pkg")
            if p is None:
                return {"ok": False, "error": "no energy counter"}
            pkg.append(p)
            ram.append(grab(r.stderr, "energy-ram") or 0.0)
            rt.append(time.time() - t0)
            time.sleep(0.5)
    finally:
        os.unlink(path)

    p, m = median(pkg), median(ram)
    return {"ok": True, "pkg_energy_j": round(p, 4), "ram_energy_j": round(m, 4),
            "total_energy_j": round(p + m, 4), "runtime_s": round(median(rt), 4),
            "reps": reps, "pkg_runs": [round(x, 4) for x in pkg]}


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.reply(200, {"ok": True, "perf_available": have_perf(),
                             "python": sys.version.split()[0]})
        else:
            self.reply(404, {"ok": False, "error": "GET /health or POST /measure"})

    def do_POST(self):
        if self.path not in ("/measure", "/measure_batch"):
            self.reply(404, {"ok": False, "error": "unknown endpoint"})
            return
        n = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError as e:
            self.reply(400, {"ok": False, "error": "bad json: %s" % e})
            return

        reps = int(data.get("reps", 5))
        timeout = int(data.get("timeout", 120))

        if self.path == "/measure_batch":
            items = data.get("codes", [])
            results = []
            with MEASURE_LOCK:
                for code in items:
                    if not code or not code.strip():
                        results.append({"ok": False, "error": "empty code"})
                    else:
                        results.append(measure(code, reps, timeout))
            self.reply(200, {"ok": True, "results": results})
            return

        code = data.get("code", "")
        if not code.strip():
            self.reply(400, {"ok": False, "error": "empty code"})
            return
        with MEASURE_LOCK:
            out = measure(code, reps, timeout)
        self.reply(200, out)

    def log_message(self, fmt, *args):
        sys.stderr.write("[server] %s\n" % (fmt % args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    print("[server] perf available:", have_perf())
    print("[server] listening on %s:%d" % (a.host, a.port))
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
