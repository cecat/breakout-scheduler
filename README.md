# Breakout Scheduler

## Project Overview

This is a Python-based conference scheduling system for TPC breakout sessions. 
These are parallel sessions scheduled in 90-minute blocks.

For TPC26 we have eight breakout rooms and five time slots, so there will be a
total capacity for 40 blocks.

The system schedules:
- **Working Groups (WGs)**: Variable-length sessions (1-5 blocks) that require multiple consecutive time slots
- **BOFs (Birds of a Feather)**: Variable-length sessions (1-2 blocks) that fill remaining empty slots

The scheduler defaults to a 5×8 grid (5 time blocks × 8 rooms) with a
two-phase approach:
1. First, place Working Groups using randomized placement with backtracking
2. Then, fill remaining empty slots with BOFs (which are typically single slots).

Multiple permutations can be generated (see **Command Line Options**), providing alternatives
for cases where certain groups do not want to be scheduled in the same sessions.  The
random placement algorithm minimizes (but does not eliminate) duplication.


## Requirements

- **Python**: 3.6 or higher
- **Dependencies**: None (uses Python standard library only)

## Setup

No installation required. Simply clone the repository and run:

```bash
python scheduler.py --help
```

## Key Files

- **scheduler.py**: Main scheduling engine with two-phase algorithm (WGs + BOFs)
- **config.yaml**: Configuration file specifying CSV column indices (0-based)
- **schedule.csv**: Output 5×8 grid with Room 1-8 headers and Block 1-5 rows

Input CSV files are expected from several Google Forms. Column mappings are configured
in `config.yaml` using 0-based indices.

## Testing

Run the test suite:

```bash
python3 test_scheduler.py

# Or with verbose output
python3 test_scheduler.py -v
```

The test suite includes:
- CSV input validation tests
- Scheduling algorithm tests
- End-to-end integration tests
- Error handling tests

## Configuration

The scheduler uses `config.yaml` to specify which columns to read from your CSV files. All column indices are 0-based (first column = 0).

```yaml
# Working Groups CSV configuration
wg:
  name_column: 8      # Column with group name
  length_column: 10   # Column with session count (1-5, capped at 5)

# Birds of a Feather CSV configuration
bof:
  name_column: 8      # Column with BOF name
  length_column: 11   # Column with session count (1-2, capped at 2)
```

To use a different configuration file, use the `-c/--config` option.

## Command Line Options

### scheduler.py

- `-w, --wgroups FILE`: CSV file containing Working Groups
- `-b, --bofs FILE`: CSV file containing BOFs
- `-s, --schedule FILE`: Schedule CSV file to read (for BOF-only mode) or write
- `-c, --config FILE`: Configuration file with column indices (default: config.yaml)
- `-r, --rooms N`: Number of rooms (default: 8)
- `-p, --permutations N`: Generate N different valid schedules (default: 1). Output files will be numbered (e.g., schedule1.csv, schedule2.csv)
- `--max-tries N`: Maximum random placement attempts for WGs (default: 5000)
- `--verbose`: Show diagnostic information during scheduling

## Common Commands

```bash
# Schedule only Working Groups
python scheduler.py -w WG.csv -s schedule.csv

# Schedule only BOFs (updates existing schedule)
python scheduler.py -b BOF.csv -s schedule.csv

# Schedule both WGs and BOFs
python scheduler.py -w WG.csv -b BOF.csv -s final_schedule.csv

# Generate 5 different valid schedules
python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv -p 5

# Use verbose mode and custom retry limit
python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv --verbose --max-tries 10000

# Use a custom number of rooms
python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv -r 10

# Use a custom configuration file
python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv -c my_config.yaml
```

## Architecture Notes

- **Randomized Placement**: Both schedulers use randomized first-fit algorithms with multiple retry attempts to find valid placements
- **Constraint Handling**: WGs require consecutive time blocks in the same room; BOFs are single-block
- **Input Validation**: Strict validation of CSV formats and session length constraints (1-3 blocks for WGs, 1 block for BOFs)
- **Two-Phase Design**: scheduler.py can operate in three modes: WG-only, BOF-only (updating existing), or combined WG+BOF
- **Rooms**: Default 8 rooms; override with `-r/--rooms N` (affects grid width and capacity)
- **Error Handling**: Comprehensive error reporting for placement failures, capacity overflow, and file I/O issues

## Data Format Requirements

- WG CSV: Column indices specified in config.yaml. Name column must contain group names, length column must contain integers (1-5, automatically capped at 5 if higher)
- BOF CSV: Column indices specified in config.yaml. Name column must contain BOF names, length column must contain integers (1-2, automatically capped at 2 if higher)
- Output CSV: 5×N grid with "Room 1" through "Room N" headers (N determined by `-r` option)

## Test Data Generation

You can generate synthetic test CSV files that match your config.yaml column layout:

```bash
# Generate with defaults (5 WGs, 4 BOFs)
python generate_test_data.py

# Custom counts and output paths
python generate_test_data.py --num-wgs 7 --num-bofs 6 --wg-output my_wg.csv --bof-output my_bof.csv
```
