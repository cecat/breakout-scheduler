#!/usr/bin/env python3
"""
Generate synthetic test CSV files based on config.yaml settings.

Usage:
    python generate_test_data.py [--config config.yaml] [--wg-output test_wg.csv] [--bof-output test_bof.csv]
"""

import csv
import argparse
import sys
import os

# Import config loader from scheduler
from scheduler import load_config


def generate_wg_csv(output_path, name_col, length_col, num_wgs=5):
    """
    Generate synthetic WG CSV with specified column indices.
    
    Args:
        output_path: Path to write CSV
        name_col: 0-based index for name column
        length_col: 0-based index for length column
        num_wgs: Number of working groups to generate
    """
    max_col = max(name_col, length_col)
    num_cols = max_col + 3  # Add some buffer columns
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Create header
        header = [f"Column_{i}" for i in range(num_cols)]
        header[name_col] = "Name of Group"
        header[length_col] = "Quantity of Sessions Needed"
        writer.writerow(header)
        
        # Generate test WGs
        wg_names = [
            "WG: Data Science",
            "WG: Machine Learning",
            "WG: High Performance Computing",
            "WG: Climate Modeling",
            "WG: Quantum Computing",
            "WG: Cybersecurity",
            "WG: Edge Computing"
        ]
        
        lengths = [2, 3, 1, 5, 1, 4, 2]  # Mix of 1-5 sessions
        
        for i in range(min(num_wgs, len(wg_names))):
            row = [""] * num_cols
            row[name_col] = wg_names[i]
            row[length_col] = str(lengths[i])
            writer.writerow(row)
    
    print(f"✓ Generated WG test data: {output_path}")
    print(f"  - {num_wgs} working groups")
    print(f"  - Name column: {name_col}")
    print(f"  - Length column: {length_col}")


def generate_bof_csv(output_path, name_col, length_col, num_bofs=4):
    """
    Generate synthetic BOF CSV with specified column indices.
    
    Args:
        output_path: Path to write CSV
        name_col: 0-based index for name column
        length_col: 0-based index for length column
        num_bofs: Number of BOFs to generate
    """
    max_col = max(name_col, length_col)
    num_cols = max_col + 3  # Add some buffer columns
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Create header
        header = [f"Column_{i}" for i in range(num_cols)]
        header[name_col] = "BOF Title"
        header[length_col] = "Session Count"
        writer.writerow(header)
        
        # Generate test BOFs
        bof_names = [
            "BOF: Future of AI",
            "BOF: Open Source Tools",
            "BOF: Career Development",
            "BOF: Diversity in Tech",
            "BOF: Networking Session",
            "BOF: Industry Trends"
        ]
        
        lengths = [1, 2, 1, 1, 2, 1]  # Mix of 1-2 sessions (BOF limit)
        
        for i in range(min(num_bofs, len(bof_names))):
            row = [""] * num_cols
            row[name_col] = bof_names[i]
            row[length_col] = str(lengths[i])
            writer.writerow(row)
    
    print(f"✓ Generated BOF test data: {output_path}")
    print(f"  - {num_bofs} BOFs")
    print(f"  - Name column: {name_col}")
    print(f"  - Length column: {length_col}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic test CSV files based on config.yaml"
    )
    parser.add_argument("-c", "--config", default="config.yaml",
                       help="Path to config file (default: config.yaml)")
    parser.add_argument("--wg-output", default="test_wg.csv",
                       help="Output path for WG CSV (default: test_wg.csv)")
    parser.add_argument("--bof-output", default="test_bof.csv",
                       help="Output path for BOF CSV (default: test_bof.csv)")
    parser.add_argument("--num-wgs", type=int, default=5,
                       help="Number of WGs to generate (default: 5)")
    parser.add_argument("--num-bofs", type=int, default=4,
                       help="Number of BOFs to generate (default: 4)")
    
    args = parser.parse_args()
    
    # Load config
    if not os.path.isfile(args.config):
        sys.exit(f"✖  Config file not found: {args.config}")
    
    cfg = load_config(args.config)
    
    print(f"📋 Using configuration from: {args.config}")
    print()
    
    # Generate WG CSV
    generate_wg_csv(
        args.wg_output,
        cfg['wg']['name_column'],
        cfg['wg']['length_column'],
        args.num_wgs
    )
    print()
    
    # Generate BOF CSV
    generate_bof_csv(
        args.bof_output,
        cfg['bof']['name_column'],
        cfg['bof']['length_column'],
        args.num_bofs
    )
    print()
    print("✓ Test data generation complete!")
