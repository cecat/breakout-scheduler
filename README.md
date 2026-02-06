# Breakout Scheduler

## Project Overview

This is a Python-based conference scheduling system for TPC breakout sessions. 
These are parallel sessions scheduled in 90-minute blocks.

For TPC26 we have eight breakout rooms and five time slots, so there will be a
total capacity for 40 blocks.

The system schedules:
- **Working Groups (WGs)**: Variable-length sessions that require multiple consecutive time slots (max configurable in config.yaml, default 5)
- **BOFs (Birds of a Feather)**: Variable-length sessions that fill remaining empty slots (max configurable in config.yaml, default 2)

The scheduler defaults to a 5×8 grid (5 time blocks × 8 rooms) with a
two-phase approach:
1. First, place Working Groups using randomized placement with backtracking.
2. Then, fill remaining empty slots with BOFs (which are typically single slots).

Multiple permutations can be generated (see **Command Line Options**), providing alternatives
for cases where certain groups do not want to be scheduled in the same sessions.  The
random placement algorithm with multiple permutations will hopefully yield schedule options
that avoid undesired collisions, but does not eliminate the possibility.


## Requirements

- **Python**: 3.6 or higher
- **Dependencies**: None (uses Python standard library only)

## Setup 

### Run in your Local Environment

1. Clone the repository.

```bash
git clone git@github.com:cecat/breakout-scheduler.git
cd breakout-scheduler
```

2. Import the CSV files for WG and BOF requests.  The settings in config.yaml for column assignments (name, number of slots) should match these.

3. Run the scheduler.

```bash
python scheduler.py --help
```

4. Run the schedule summary script for an index of groups and slots.

```bash
python schedule_summary.py
```

### Run in Google Colab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](
https://colab.research.google.com/github/cecat/breakout-scheduler/blob/main/colab/TPC_Breakout_Scheduler.ipynb)


## Key Files

- **scheduler.py**: Main scheduling engine with two-phase algorithm (WGs + BOFs)
- **schedule_summary.py**: Generate human-readable reports from schedule CSV files
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
# Grid dimensions
grid:
  num_sessions: 5     # Number of time sessions/blocks (rows)
  num_rooms: 8        # Number of parallel rooms (columns)

# Algorithm parameters
algorithm:
  max_tries: 5000              # Maximum placement attempts before failure
  sort_strategy: largest_first # How to order items: largest_first, smallest_first, as_is
  random_seed: null            # Integer for reproducible results, null for random

# Working Groups CSV configuration
wg:
  name_column: 8      # Column with group name
  length_column: 10   # Column with session count
  max_length: 5       # Max consecutive sessions (cannot exceed num_sessions)

# Birds of a Feather CSV configuration
bof:
  name_column: 8      # Column with BOF name
  length_column: 11   # Column with session count
  max_length: 2       # Max consecutive sessions (cannot exceed num_sessions)
```

### Algorithm Parameters

- **max_tries**: Controls how many randomized placement attempts to try before giving up (higher = more likely to find solution, but slower)
- **sort_strategy**: 
  - `largest_first` (default): Process largest items first, reduces fragmentation
  - `smallest_first`: Process smallest items first, may help with tight constraints
  - `as_is`: No sorting, use random shuffle order only
- **random_seed**: Set to an integer (e.g., 42) for reproducible schedules, or `null` for different results each run

The scheduler validates that `max_length` values don't exceed `num_sessions` to prevent configuration errors.

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

### schedule_summary.py

Generates human-readable reports from schedule CSV files showing slot utilization and group details.

**Usage**: `python schedule_summary.py <schedule.csv> [<schedule2.csv> ...]`

**Output format**:
```
Schedule: schedule.csv
39/40 slots filled (97.5%)

Security WG: 3 slots
Privacy WG: 2 slots
IoT BOF: 1 slot
...
```

Groups are listed alphabetically. When multiple schedule files are provided, reports are separated by dividers.

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

# Generate a summary report of a schedule
python schedule_summary.py schedule.csv

# Generate reports for multiple schedules
python schedule_summary.py schedule1.csv schedule2.csv schedule3.csv
```

## Architecture Notes

- **Randomized Placement**: Both schedulers use randomized first-fit algorithms with multiple retry attempts to find valid placements
- **Constraint Handling**: WGs require consecutive time blocks in the same room; BOFs are single-block
- **Input Validation**: Strict validation of CSV formats and session length constraints (1-3 blocks for WGs, 1 block for BOFs)
- **Two-Phase Design**: scheduler.py can operate in three modes: WG-only, BOF-only (updating existing), or combined WG+BOF
- **Rooms**: Default 8 rooms; override with `-r/--rooms N` (affects grid width and capacity)
- **Error Handling**: Comprehensive error reporting for placement failures, capacity overflow, and file I/O issues

## Data Format Requirements

- WG CSV: Column indices specified in config.yaml. Name column must contain group names, length column must contain integers (automatically capped at max_length from config if higher, defaults to 1 if 0 or negative)
- BOF CSV: Column indices specified in config.yaml. Name column must contain BOF names, length column must contain integers (automatically capped at max_length from config if higher, defaults to 1 if 0 or negative)
- Output CSV: 5×N grid with "Room 1" through "Room N" headers (N determined by `-r` option)

## Test Data Generation

You can generate synthetic test CSV files that match your config.yaml column layout:

```bash
# Generate with defaults (5 WGs, 4 BOFs)
python generate_test_data.py

# Custom counts and output paths
python generate_test_data.py --num-wgs 7 --num-bofs 6 --wg-output my_wg.csv --bof-output my_bof.csv
```

## Handling Over-Subscription

If the total requested slots exceed capacity (num_sessions × num_rooms), the scheduler will detect this and report an error. You can resolve over-subscription by iteratively reducing the `max_length` values in `config.yaml`.

**Strategy**: Squeeze groups requesting more slots first (they have more flexibility), while protecting groups requesting fewer slots.

### Resolution Steps

1. **Attempt scheduling** and check for over-subscription error:
   ```bash
   python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv
   # ⚠ Over-subscription: 52 slots requested, 40 capacity
   #    Overflow: 12 slots
   ```

2. **Reduce BOF max_length**: Edit `config.yaml` and decrement `bof.max_length` (e.g., `2` → `1`). Re-run scheduler. If still over-subscribed, proceed to step 3.

3. **Decrement WG max_length**: Edit `config.yaml` and decrement `wg.max_length`. Re-run scheduler.

**Important**: Reducing `wg.max_length` below 3 should be carefully considered, as it involves a trade-off between allowing existing working groups to make progress versus introducing new groups. If further reduction is needed, the program committee should evaluate whether to:
- Reduce WG allocations for specific WGs (limiting established group progress), or
- Decline BOFs with the lowest promise and likely success at creating momentum.

If these are not feasible, it is worth discussing with the logistics team whether more space could be opened up, or suggesting that BOFs share a slot (e.g., somewhat related BOFs each taking 45 minutes of a slot).

## Scheduling Algorithm

The scheduler implements a **Randomized First-Fit Decreasing (FFD) with Backtracking** algorithm for the bin packing problem:

### Problem Formulation

- **Items**: Working groups and BOFs (each requiring 1-5 consecutive time slots)
- **Bins**: Room columns (each with capacity = `num_sessions`)
- **Constraint**: Items must occupy consecutive slots within a single room
- **Objective**: Fit all items into available rooms

### Algorithm Steps

1. **Randomization**: Shuffle item order for diversity across multiple runs
2. **Decreasing Sort**: Process largest items first (reduces fragmentation)
3. **First-Fit Placement**: 
   - Try time sessions sequentially (1, 2, 3...)
   - Randomize room order within each session
   - Place in first available position
4. **Backtracking**: If any item fails to place, restart entire attempt
5. **Retry**: Repeat up to `max_tries` attempts

### Problem Class

This is a variant of **2D Bin Packing with Contiguity Constraints** (also known as Strip Packing), which is NP-hard. The randomized approach provides:
- Good solutions in practice
- Diverse alternatives (useful for avoiding schedule conflicts)
- Reasonable runtime for typical conference sizes

### References

- Coffman Jr, Edward G., Michael R. Garey, and David S. Johnson. "Approximation algorithms for bin-packing—an updated survey." In Algorithm design for computer system design, pp. 49-106. Vienna: Springer Vienna, 1984.
- Lodi, Andrea, Silvano Martello, and Daniele Vigo. "Recent advances on two-dimensional bin packing problems." Discrete Applied Mathematics 123, no. 1-3 (2002): 379-396.
