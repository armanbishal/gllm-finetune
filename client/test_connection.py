import json

from energy_client import health, measure
from config import DATA, IMPORTS, LIMIT


# read the problem set
def load_problems():
    return json.load(open(DATA))


def main():
    print("health:", health(), "\n")

    problems = load_problems()
    if LIMIT:
        problems = problems[:LIMIT]   # set TEST_LIMIT=0 in .env to run the whole set

    total = 0.0
    for p in problems:
        code = IMPORTS + p["canonical_solution"] + "\n\n" + p["small_test_cases"]
        r = measure(code)
        if r.get("ok"):
            total += r["total_energy_j"]
            print("%-28s %8.3f J  %6.3f s" % (p["task_name"][:28],
                                              r["total_energy_j"], r["runtime_s"]))
        else:
            print("%-28s  FAIL  %s" % (p["task_name"][:28], r.get("error")))

    print("\n%d problems, %.3f J total" % (len(problems), total))


if __name__ == "__main__":
    main()
