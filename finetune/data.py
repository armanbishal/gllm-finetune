import gzip
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROBLEMS = os.path.join(ROOT, "dataset", "problems.jsonl")
REFERENCES = os.path.join(ROOT, "dataset", "references.jsonl")
TESTS_DIR = os.path.join(ROOT, "dataset", "tests")


def load_tests():
    table = {}
    for name in sorted(os.listdir(TESTS_DIR)):
        if not name.endswith(".jsonl.gz"):
            continue
        with gzip.open(os.path.join(TESTS_DIR, name), "rt") as g:
            for line in g:
                r = json.loads(line)
                table[r["problem_id"]] = r.get("large_test_cases", []) + r.get("small_test_cases", [])
    return table


def load_references():
    table = {}
    with open(REFERENCES) as f:
        for line in f:
            r = json.loads(line)
            table[r["problem_id"]] = r["reference"]
    return table


def load_problems(limit=0):
    rows = []
    with open(PROBLEMS) as f:
        for line in f:
            rows.append(json.loads(line))
    if limit:
        rows = rows[:limit]
    return rows


def build_prompt(entry):
    return ("Implement the class Solution method for this task.\n\n"
            + "# Task description:\n" + entry["problem_description"] + "\n\n"
            + "# Starter code:\n" + entry["starter_code"])
