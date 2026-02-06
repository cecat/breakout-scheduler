# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Python-based conference scheduling system for TPC breakout sessions. Schedules two types of sessions onto a 5×8 grid (5 time blocks × 8 rooms):
- **Working Groups (WGs)**: Variable-length sessions (1-3 consecutive blocks in same room)
- **BOFs (Birds of a Feather)**: Single-block sessions that fill remaining slots

Uses a two-phase randomized placement algorithm with backtracking: WGs first, then BOFs.

## Requirements

- Python 3.6+ (no external dependencies, standard library only)

## Configuration

CSV column mappings are specified in `config.yaml` using 0-based indices:

```yaml
grid:
  num_sessions: 5     # Number of time sessions (default: 5)
  num_rooms: 8        # Number of parallel rooms (default: 8)

wg:
  name_column: 8      # Working group name column
  length_column: 10   # Session count column
  max_length: 5       # Max sessions (cannot exceed num_sessions)

bof:
  name_column: 8      # BOF name column
  length_column: 11   # Session count column
  max_length: 2       # Max sessions (cannot exceed num_sessions)
```

Use `-c/--config` to specify an alternate configuration file.

## Common Commands

```bash
# Schedule Working Groups only
python scheduler.py -w WG.csv -s schedule.csv

# Schedule BOFs only (updates existing schedule in place)
python scheduler.py -b BOF.csv -s schedule.csv

# Schedule both WGs and BOFs together
python scheduler.py -w WG.csv -b BOF.csv -s final_schedule.csv

# Verbose mode with custom retry limit
python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv --verbose --max-tries 10000

# Custom number of rooms (default is 8)
python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv -r 10

# Use custom configuration file
python scheduler.py -w WG.csv -b BOF.csv -s schedule.csv -c my_config.yaml
```

## Architecture

### Core Algorithm
- **Two-phase scheduling**: `scheduler.py` has three operating modes:
  1. WG-only: Schedule working groups into empty grid
  2. BOF-only: Fill remaining empty cells in existing schedule
  3. Combined: Schedule WGs first, then fill with BOFs

- **Placement strategy**: Randomized first-fit with backtracking
  - For WGs: Shuffle order, sort by descending length, try up to `max_tries` random placements
  - For BOFs: Randomly shuffle empty cell positions, fill sequentially

- **Constraint handling**:
  - WGs require consecutive blocks in same room (vertical placement in grid)
  - BOFs are single-block (any empty cell)
  - Strict capacity checking: total WG blocks must not exceed grid capacity (5 × NUM_ROOMS)

### Data Structures
- Grid representation: `grid[block_index][room_index]` where each cell is a session name or None
- Constants: `NUM_BLOCKS = 5`, `NUM_ROOMS = 8` (default, overridable via `-r`)

### Key Functions
- `greedy_place_wgroups()`: Randomized WG placement with retry logic, returns grid and empty row warnings
- `fill_bofs()`: Fills BOFs into empty cells of existing grid
- `read_wgroups()`, `read_bofs()`: CSV parsers with strict validation
- `write_schedule()`: Outputs 5×N grid with "Room 1"..."Room N" headers

## Input File Formats

### WG.csv (Working Groups)
- Column indices specified in `config.yaml`
- Name column: contains working group names
- Length column: integers (automatically capped at max_length if higher, defaults to 1 if ≤ 0)
- Default indices: name=8, length=10
- Default max_length: 5

### BOF.csv (Birds of a Feather)
- Column indices specified in `config.yaml`
- Name column: contains BOF names (takes first line if multi-line cell)
- Length column: integers (automatically capped at max_length if higher, defaults to 1 if ≤ 0)
- Default indices: name=8, length=11
- Default max_length: 2

### schedule.csv (Output)
- Header row: "Room 1", "Room 2", ..., "Room N"
- 5 data rows (one per time block)
- Empty cells are blank strings

## Error Handling

- Fatal errors cause immediate `sys.exit()` with ✖ prefix:
  - Total WG blocks exceed capacity
  - WG cannot be placed after max_tries attempts
  - Too many BOFs for available empty cells
  - Missing/malformed input files
  
- Warnings printed with ⚠ prefix (non-fatal):
  - Empty time blocks after scheduling

## Testing

```bash
# Run test suite
python3 test_scheduler.py -v
```

Test coverage includes:
- CSV parsing (WG.csv, BOF.csv, schedule.csv)
- WG placement algorithm with capacity checks
- BOF filling with overflow handling
- End-to-end workflows
- Error conditions (invalid lengths, capacity exceeded)

## Development Notes

- CSV encoding: UTF-8 with BOM support (`encoding="utf-8-sig"`)
- All placement uses Python's `random` module for non-deterministic behavior
- Exit codes: 0 for success, 1 for errors
- CI/CD: GitHub Actions runs tests on Python 3.8-3.12 on every push
