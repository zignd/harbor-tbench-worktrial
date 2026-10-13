import sys, json
with open(sys.argv[1]) as f:
    data = json.load(f)
expected = 52428800.0
actual = sum(data.values())
if abs(actual - expected) > 0.1:
    print(f"AUDIT FAILED: Expected sum {expected}, got {actual} (Delta: {actual - expected})")
    sys.exit(1)
print("AUDIT PASSED")
