import os


# load key=value lines from .env
def load_env():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(os.path.dirname(here), ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


load_env()

SERVER = os.environ.get("ENERGY_SERVER", "http://127.0.0.1:8000")
MODEL = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-Coder-0.5B")
REPS = int(os.environ.get("ENERGY_REPS", "5"))
TIMEOUT = int(os.environ.get("ENERGY_TIMEOUT", "180"))
LIMIT = int(os.environ.get("TEST_LIMIT", "10"))

_here = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(_here), "dataset", "problems.jsonl")

IMPORTS = ("from typing import *\n"
           "from collections import *\n"
           "from itertools import *\n"
           "import math, heapq, re, bisect\n\n")
