import json
import math
import os
import re
import subprocess
import sys
import urllib.request

SERVER = os.environ.get("ENERGY_SERVER", "http://127.0.0.1:8000")
REPS = int(os.environ.get("ENERGY_REPS", "5"))
HTTP_TIMEOUT = int(os.environ.get("ENERGY_HTTP_TIMEOUT", "120"))

FAILURE_BASE = -1.0
FAILURE_SLOPE = 0.5
TANH_K = 3.0
RATIO_LO, RATIO_HI = 0.25, 4.0

W_PKG = float(os.environ.get("W_PKG", "0.55"))
W_RAM = float(os.environ.get("W_RAM", "0.15"))
W_T = float(os.environ.get("W_T", "0.25"))
W_M = float(os.environ.get("W_M", "0.05"))

IMPORT_HEADER = (
    "from typing import List, Optional, Dict, Tuple, Set\n"
    "from functools import cache, lru_cache, reduce\n"
    "from collections import defaultdict, Counter, deque, OrderedDict\n"
    "from bisect import bisect_left, bisect_right, insort\n"
    "import heapq, math, itertools, re, sys\n"
    "from math import inf\n\n"
)


def extract_code(text):
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def pass_fraction(code, tests, timeout=10):
    if not tests:
        return 1.0
    passed = 0
    for t in tests:
        body = IMPORT_HEADER + code + "\n" + t + "\n"
        try:
            r = subprocess.run([sys.executable, "-I", "-c", body],
                               capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0:
                passed += 1
        except (subprocess.TimeoutExpired, OSError):
            pass
    return passed / len(tests)


def measure_remote(code, tests, reps=REPS, timeout=HTTP_TIMEOUT):
    payload = json.dumps({"code": IMPORT_HEADER + code + "\n\n" + "\n".join(tests),
                          "tests": [], "reps": reps, "timeout": timeout}).encode()
    req = urllib.request.Request(SERVER.rstrip("/") + "/measure", data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout + 30) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def measure_batch(codes, tests_list, reps=REPS, timeout=HTTP_TIMEOUT):
    bodies = [IMPORT_HEADER + c + "\n\n" + "\n".join(t) for c, t in zip(codes, tests_list)]
    payload = json.dumps({"codes": bodies, "reps": reps, "timeout": timeout}).encode()
    req = urllib.request.Request(SERVER.rstrip("/") + "/measure_batch", data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout * len(codes) + 60) as resp:
            return json.loads(resp.read()).get("results", [])
    except Exception:
        return [None] * len(codes)


def health_check(server=SERVER, timeout=15):
    try:
        with urllib.request.urlopen(server.rstrip("/") + "/health", timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def composite_reward(meas, ref):
    def ratio(key):
        m, r = meas.get(key), ref.get(key)
        if not m or not r or r <= 0:
            return 1.0
        return _clip(m / r, RATIO_LO, RATIO_HI)

    c_y = (W_PKG * ratio("pkg_energy_j") + W_RAM * ratio("ram_energy_j")
           + W_T * ratio("runtime_s") + W_M * ratio("peak_mem_kb"))
    c_ref = W_PKG + W_RAM + W_T + W_M
    g = (c_ref - c_y) / c_ref
    return 0.5 + 0.5 * math.tanh(TANH_K * g), g


def reward_for_candidate(completion, tests, ref_meas):
    code = extract_code(completion)
    if not code or ("def " not in code and "class Solution" not in code):
        return FAILURE_BASE, {"status": "no_code"}

    f = pass_fraction(code, tests)
    if f < 1.0:
        return FAILURE_BASE + FAILURE_SLOPE * f, {"status": "incorrect", "pass_frac": round(f, 3)}

    meas = measure_remote(code, tests)
    if not meas or not meas.get("ok"):
        return 0.5, {"status": "correct_no_energy"}
    if ref_meas is None or not ref_meas.get("ok"):
        return 0.5, {"status": "correct_no_reference"}

    reward, g = composite_reward(meas, ref_meas)
    return reward, {"status": "correct", "g": round(g, 3),
                    "energy_j": meas.get("total_energy_j")}
