from energy_client import health, measure

SLOW = """
def f(n):
    total = 0
    for i in range(1, n + 1):
        if i % 2 == 0:
            total += i
    return total
print(f(2000000))
"""

FAST = """
def f(n):
    k = n // 2
    return k * (k + 1)
print(f(2000000))
"""


def main():
    print("health:", health(), "\n")
    slow = measure(SLOW)
    fast = measure(FAST)
    print("loop   : %s J, %s s" % (slow["total_energy_j"], slow["runtime_s"]))
    print("formula: %s J, %s s" % (fast["total_energy_j"], fast["runtime_s"]))
    gap = (slow["total_energy_j"] - fast["total_energy_j"]) / slow["total_energy_j"]
    print("\nformula uses %.0f%% less energy" % (gap * 100))


if __name__ == "__main__":
    main()
