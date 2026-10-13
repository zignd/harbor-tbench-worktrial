import csv, os, sys, random
def generate(path, num_files, rows_per_file):
    os.makedirs(path, exist_ok=True)
    regions = ['North', 'South', 'East', 'West']
    for i in range(num_files):
        with open(os.path.join(path, f'data_{i}.csv'), 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'region', 'value'])
            for j in range(rows_per_file):
                writer.writerow([i * rows_per_file + j, random.choice(regions), 10.0])
if __name__ == '__main__':
    generate(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
