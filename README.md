# Breakout Scheduler

## Project Overview

This is a Python-based conference scheduling system for TPC breakout sessions. 
These are parallel sessions scheduled in 90-minute blocks.

For TPC26 we have eight breakout rooms and five time slots, so there will be a
total capacity for 40 blocks.

The system schedules:
- **Working Groups (WGs)**: Variable-length sessions (1-3 blocks) that require multiple consecutive time slots
- **BOFs (Birds of a Feather)**: Single-block sessions that fill remaining empty slots

The scheduler defaults to a 5×8 grid (5 time blocks × 8 rooms) with a
two-phase approach:
1. First, place Working Groups using randomized placement with backtracking
2. Then, fill remaining empty cells with BOFs (which are typically single slots).

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
- **stage1.py**: Simplified single-phase scheduler (WGs only)
- **WG.csv**: Working Groups input data with columns "Name of Group" and "Quantity of Sessions Needed"
- **BOF.csv**: BOFs input data (reads from column AG/33rd column)
- **schedule.csv**: Output 5×8 grid with Room 1-8 headers and Block 1-5 rows

## Common Commands

```bash
# Schedule only Working Groups
python scheduler.py -w WG.csv -s schedule.csv

# Schedule only BOFs (updates existing schedule)
python scheduler.py -b BOF.csv -s schedule.csv

# Schedule both WGs and BOFs
python scheduler.py -w WG.csv -b BOF.csv -s final_schedule.csv

# Use verbose mode and custom retry limit
python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv --verbose --max-tries 10000

# Use a custom number of rooms (default is 8; this sets 8 rooms)
python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv -r 8

# Alternative single-phase scheduler
python stage1.py WG.csv -o schedule.csv --verbose
```

## Architecture Notes

- **Randomized Placement**: Both schedulers use randomized first-fit algorithms with multiple retry attempts to find valid placements
- **Constraint Handling**: WGs require consecutive time blocks in the same room; BOFs are single-block
- **Input Validation**: Strict validation of CSV formats and session length constraints (1-3 blocks for WGs, 1 block for BOFs)
- **Two-Phase Design**: scheduler.py can operate in three modes: WG-only, BOF-only (updating existing), or combined WG+BOF
- **Rooms**: Default 8 rooms; override with `-r/--rooms N` (affects grid width and capacity)
- **Error Handling**: Comprehensive error reporting for placement failures, capacity overflow, and file I/O issues

## Data Format Requirements

- WG CSV: Must have headers "Name of Group" and "Quantity of Sessions Needed"
- BOF CSV: Complex format where BOF names are extracted from column AG (33rd column, 0-indexed as 32)
- Output CSV: 5×8 grid with "Room 1" through "Room 8" headers
