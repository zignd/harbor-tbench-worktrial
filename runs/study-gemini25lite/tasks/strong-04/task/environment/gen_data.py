import sys, os, csv

def gen_csv(path, num_records, regions):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['region', 'value'])
        for i in range(num_records):
            region = regions[i % len(regions)]
            writer.writerow([region, 5.0])

if __name__ == "__main__":
    out_dir = sys.argv[1]
    num_files = int(sys.argv[2])
    records_per_file = int(sys.argv[3])
    os.makedirs(out_dir, exist_ok=True)
    regions = ['North', 'South', 'East', 'West']
    for i in range(num_files):
        gen_csv(os.path.join(out_dir, f'data_{i}.csv'), records_per_file, regions)
