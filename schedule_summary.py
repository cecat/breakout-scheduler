#!/usr/bin/env python3
"""
schedule_summary.py – Generate a human-readable report from a schedule CSV.

Reads a schedule CSV (5×N grid) and outputs:
- Schedule filename
- Total slots filled / capacity
- List of all groups with their slot counts

USAGE
-----
  python schedule_summary.py schedule.csv
  python schedule_summary.py schedule1.csv schedule2.csv schedule3.csv

OUTPUT
------
  Schedule: schedule.csv
  39/40 slots filled (97.5%)
  
  Security WG: 3 slots
  Privacy WG: 2 slots
  IoT BOF: 1 slot
  Crypto BOF: 2 slots
  ...
"""

import csv
import sys
import os
from collections import Counter


def read_schedule(path):
    """
    Read a schedule CSV and return:
    - num_blocks (rows)
    - num_rooms (columns)
    - grid[block][room] = group_name or None
    """
    grid = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        if header is None:
            sys.exit(f"✖  Schedule file {path!r} has no header row.")
        num_rooms = len(header)
        
        for row in rdr:
            cells = []
            for i in range(num_rooms):
                val = row[i].strip() if i < len(row) else ""
                cells.append(val if val else None)
            grid.append(cells)
    
    num_blocks = len(grid)
    return num_blocks, num_rooms, grid


def generate_report(path):
    """
    Generate a report for a single schedule file.
    Returns the report as a string.
    """
    if not os.path.isfile(path):
        return f"✖  File not found: {path!r}\n"
    
    try:
        num_blocks, num_rooms, grid = read_schedule(path)
    except Exception as e:
        return f"✖  Error reading {path!r}: {e}\n"
    
    capacity = num_blocks * num_rooms
    
    # Count occurrences of each group
    group_counts = Counter()
    filled = 0
    
    for row in grid:
        for cell in row:
            if cell:
                group_counts[cell] += 1
                filled += 1
    
    # Build report
    lines = []
    lines.append(f"Schedule: {path}")
    percentage = (filled / capacity * 100) if capacity > 0 else 0
    lines.append(f"{filled}/{capacity} slots filled ({percentage:.1f}%)")
    lines.append("")
    
    # Sort groups alphabetically
    for group in sorted(group_counts.keys()):
        count = group_counts[group]
        slot_word = "slot" if count == 1 else "slots"
        lines.append(f"{group}: {count} {slot_word}")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python schedule_summary.py <schedule.csv> [<schedule2.csv> ...]")
        print("\nGenerates a human-readable report showing slot utilization and group details.")
        sys.exit(1)
    
    schedule_files = sys.argv[1:]
    
    for i, path in enumerate(schedule_files):
        if i > 0:
            print("\n" + "="*60 + "\n")
        report = generate_report(path)
        print(report)


if __name__ == "__main__":
    main()
