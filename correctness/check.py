import argparse
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

from test_helpers import PREAMBLE, resolve_model

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TESTS = ROOT / "dataset" / "tests"


def load_tests():
    table = {}
    for shard in sorted(TESTS.glob("tests_*.jsonl.gz")):
        with gzip.open(str(shard), "rt") as g:
            for line in g:
                r = json.loads(line)
                table[r["problem_id"]] = r.get("large_test_cases", []) + r.get("small_test_cases", [])
    return table


def extract_code(text):
    if "```python" in text:
        text = text.split("```python", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]
        return text.strip()
    m = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def run(code, tests):
    body = PREAMBLE + "\n" + code + "\n\n" + "\n".join(tests) + "\n"
    try:
        r = subprocess.run([sys.executable, "-I", "-c", body],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return "TimeOutError", "execution timed out"
    except Exception as e:
        return "UnknownError", str(e)
    if r.returncode == 0:
        return None, ""
    if "AssertionError" in r.stderr:
        return "AssertionError", r.stderr.strip().splitlines()[-1]
    return "ExecutionError", r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "nonzero exit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--model", required=True)
    ap.add_argument("-r", "--run", type=int, required=True)
    a = ap.parse_args()

    model_name = resolve_model(a.model)
    model_id = model_name.split("/")[-1]
    run_dir = HERE / "results" / model_id / f"{model_id}_{a.run}"
    dataset = json.load(open(run_dir / f"{model_id}_{a.run}.json"))
    tests = load_tests()

    passed = 0
    errors = []
    for entry in dataset:
        completion = entry.get("completion", "")
        if "```python" not in completion:
            errors.append({"problem_idx": entry["problem_id"], "error_type": "FormatError",
                           "error_message": "no python block"})
            print("%-6s %-34s FAIL no-code" % (entry["problem_id"], entry["title"][:34]))
            continue
        code = extract_code(completion)
        etype, emsg = run(code, tests.get(entry["problem_id"], []))
        if etype is None:
            passed += 1
            print("%-6s %-34s PASS" % (entry["problem_id"], entry["title"][:34]))
        else:
            errors.append({"problem_idx": entry["problem_id"], "error_type": etype,
                           "error_message": emsg.replace("^", "")})
            print("%-6s %-34s FAIL %s" % (entry["problem_id"], entry["title"][:34], etype))

    total = len(dataset)
    pct = round(100 * passed / total, 2) if total else 0.0
    print("\n%d / %d correct  (%.2f%%)" % (passed, total, pct))

    with open(run_dir / f"{model_id}_{a.run}_errors.json", "w") as f:
        json.dump(errors, f, indent=4)
    with open(run_dir / f"{model_id}_{a.run}_correctness.json", "w") as f:
        json.dump({"model": model_name, "run": a.run, "passed": passed,
                   "total": total, "pct": pct}, f, indent=4)
    print("saved", run_dir / f"{model_id}_{a.run}_correctness.json")


if __name__ == "__main__":
    main()
