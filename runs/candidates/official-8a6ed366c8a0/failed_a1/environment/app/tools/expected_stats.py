import csv
import ipaddress
import sys
import json
from collections import defaultdict

LOG_PATH = "/app/data/access.log"
GEOIP_PATH = "/app/data/geoip.csv"


def load_geoip(path):
    entries = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            net = ipaddress.ip_network(row["cidr"], strict=False)
            entries.append((net, row["country"]))
    return entries


def lookup_country(ip_str, entries):
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return "UNKNOWN"
    # 10.42.x.x
    if ip in ipaddress.ip_network("10.42.0.0/16"):
        return "INTERNAL"
    # 172.16.0.0/12 - binary treats as empty, we normalise to INTERNAL
    if ip in ipaddress.ip_network("172.16.0.0/12"):
        return "INTERNAL"
    # Other RFC1918
    if ip in ipaddress.ip_network("10.0.0.0/8"):
        return "INTERNAL"
    if ip in ipaddress.ip_network("192.168.0.0/16"):
        return "INTERNAL"
    for net, country in entries:
        if ip in net:
            return country
    return "UNKNOWN"


def compute_stats(log_path, geoip_path):
    entries = load_geoip(geoip_path)
    country_counts = defaultdict(int)
    path_counts = defaultdict(int)
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            ip, method, path, status = parts[0], parts[1], parts[2], parts[3]
            country = lookup_country(ip, entries)
            country_counts[country] += 1
            path_counts[path] += 1
    return dict(country_counts), dict(path_counts)


if __name__ == "__main__":
    country_counts, path_counts = compute_stats(LOG_PATH, GEOIP_PATH)
    print(json.dumps({"country_counts": country_counts, "path_counts": path_counts}, indent=2))
