import sys, json

if __name__ == "__main__":
    with open(sys.argv[1], 'r') as f:
        data = json.load(f)
    
    # North + South + East + West
    total = sum(data.values())
    expected = 52428800.0
    if abs(total - expected) > 1.0:
        print(f"AUDIT FAILED: Expected sum {expected}, got {total} (Delta: {total - expected})")
        sys.exit(1)
    else:
        print("AUDIT PASSED")
