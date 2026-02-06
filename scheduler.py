#!/usr/bin/env python3
"""
schedule_conf_v3.py – 5×8 conference scheduler with two‐phase filling.

  - “Working Groups” (length 1–3 blocks) go first.
  - Then “BOFs” (all length = 1) fill any leftover empty cells.

USAGE EXAMPLES
--------------
  # 1) Only working groups
  python schedule_conf_v3.py -w wgroups.csv -s my_schedule.csv

  # 2) Only BOFs (updates an existing schedule file in place)
  python schedule_conf_v3.py -b bofs.csv -s my_schedule.csv

  # 3) Both: schedule WGs first, then fill in BOFs
  python schedule_conf_v3.py -w wgroups.csv -b bofs.csv -s final_schedule.csv


COMMAND‐LINE OPTIONS
--------------------
  -w, --wgroups FILE   CSV with columns:
                         Name of Group, Quantity of Sessions Needed (1, 2 or 3)
  -b, --bofs    FILE   CSV with many columns; we only read column AG (33rd col).
                       Each BOF is length 1, name = first‐line of column AG cell.
  -s, --schedule FILE  Path to the 5×8 schedule CSV. If “only ‐b” is used, we
                       read & overwrite this file. If “‐w” is used, this is the
                       output filename (default = “schedule.csv”).
  --max-tries N        How many randomised attempts to try when placing WGs
                       (default = 5000).
  -r, --rooms N        Number of rooms (default = 8).
  --verbose            Print helpful progress/​diagnostic messages.

OUTPUT
------
  A 5×N CSV with header “Room 1,…,Room N” and five rows for “Block 1,…,Block 5”.
  Empty cells are blank strings.

ERRORS & WARNINGS
-----------------
  • If total requested WG‐blocks > 40 ⇒ fatal error with counts.
  • If a specific WG cannot be placed after max tries ⇒ fatal error naming it.
  • If too many BOFs to fit into the leftover empty cells ⇒ fatal error listing
    how many BOFs could not be placed.
  • If some rows end up completely empty after everything ⇒ prints a warning (not
    fatal).
"""

import csv
import random
import argparse
import sys
import os

NUM_BLOCKS = 5
NUM_ROOMS = 8
CAPACITY = NUM_BLOCKS * NUM_ROOMS
DEFAULT_MAX_TRIES = 5_000


# ──────────────────────── Configuration ────────────────────────

def load_config(config_path="config.yaml"):
    """
    Load simple YAML-like configuration with column indices (0-based).
    Supports keys:
      grid: { num_sessions: int, num_rooms: int }
      algorithm: { max_tries: int, sort_strategy: str, random_seed: int|null }
      wg: { name_column: int, length_column: int, max_length: int }
      bof: { name_column: int, length_column: int, max_length: int }
    """
    if not os.path.isfile(config_path):
        sys.exit(f"✖  Config file not found: {config_path!r}")

    # Minimal parser for our simple YAML structure (no external dependencies)
    cfg = {"grid": {}, "algorithm": {}, "wg": {}, "bof": {}}
    section = None
    with open(config_path, "r", encoding="utf-8") as f:
        for raw in f:
            # Strip comments and trailing whitespace
            line = raw.split('#', 1)[0].rstrip()
            if not line:
                continue
            # Section headers (e.g., grid:, algorithm:, wg:, bof:)
            if not line.startswith(' ') and line.endswith(':'):
                key = line[:-1].strip()
                section = key if key in ("grid", "algorithm", "wg", "bof") else None
                continue
            # Key: value within a section (2-space indent)
            if section and line.startswith('  ') and ':' in line:
                k, v = line.strip().split(':', 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                # Handle special cases
                if v.lower() == 'null':
                    cfg[section][k] = None
                elif k == 'sort_strategy':
                    cfg[section][k] = v
                else:
                    try:
                        cfg[section][k] = int(v)
                    except ValueError:
                        sys.exit(f"✖  Config value for {section}.{k} must be an integer (got {v!r}).")

    # Validate required keys
    if 'num_sessions' not in cfg['grid'] or 'num_rooms' not in cfg['grid']:
        sys.exit("✖  Config 'grid' section must have 'num_sessions' and 'num_rooms'.")
    if 'max_tries' not in cfg['algorithm']:
        sys.exit("✖  Config 'algorithm' section must have 'max_tries'.")
    if 'sort_strategy' not in cfg['algorithm']:
        sys.exit("✖  Config 'algorithm' section must have 'sort_strategy'.")
    if 'random_seed' not in cfg['algorithm']:
        sys.exit("✖  Config 'algorithm' section must have 'random_seed'.")
    if 'name_column' not in cfg['wg'] or 'length_column' not in cfg['wg']:
        sys.exit("✖  Config 'wg' section must have 'name_column' and 'length_column'.")
    if 'max_length' not in cfg['wg']:
        sys.exit("✖  Config 'wg' section must have 'max_length'.")
    if 'name_column' not in cfg['bof'] or 'length_column' not in cfg['bof']:
        sys.exit("✖  Config 'bof' section must have 'name_column' and 'length_column'.")
    if 'max_length' not in cfg['bof']:
        sys.exit("✖  Config 'bof' section must have 'max_length'.")

    # Validate algorithm parameters
    valid_strategies = ['largest_first', 'smallest_first', 'as_is']
    if cfg['algorithm']['sort_strategy'] not in valid_strategies:
        sys.exit(f"✖  Config error: algorithm.sort_strategy must be one of {valid_strategies} (got {cfg['algorithm']['sort_strategy']!r}).")
    if cfg['algorithm']['max_tries'] < 1:
        sys.exit(f"✖  Config error: algorithm.max_tries must be >= 1 (got {cfg['algorithm']['max_tries']}).")
    if cfg['algorithm']['random_seed'] is not None and cfg['algorithm']['random_seed'] < 0:
        sys.exit(f"✖  Config error: algorithm.random_seed must be >= 0 or null (got {cfg['algorithm']['random_seed']}).")
    
    # Validate that max_length values don't exceed num_sessions
    num_sessions = cfg['grid']['num_sessions']
    if cfg['wg']['max_length'] > num_sessions:
        sys.exit(f"✖  Config error: wg.max_length ({cfg['wg']['max_length']}) cannot exceed grid.num_sessions ({num_sessions}).")
    if cfg['bof']['max_length'] > num_sessions:
        sys.exit(f"✖  Config error: bof.max_length ({cfg['bof']['max_length']}) cannot exceed grid.num_sessions ({num_sessions}).")

    return cfg

# ──────────────────────── I/O Helpers ────────────────────────
def read_wgroups(path, name_col, length_col, max_length):
    """
    Read “Working Groups” CSV using column indices.
    Length is capped at max_length.
    Returns:  [ (name:str, length:int), … ]
    """
    wgs = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        if header is None:
            sys.exit("✖  WGs file is empty or malformed.")
        max_col = max(name_col, length_col)
        if len(header) <= max_col:
            sys.exit(f"✖  WGs file has {len(header)} columns, but config requires column {max_col}.")
        for row_num, row in enumerate(rdr, start=2):
            if len(row) <= max_col:
                continue  # Skip rows with insufficient columns
            name = row[name_col].strip()
            if not name:
                continue  # Skip blank names
            try:
                length = int(row[length_col].strip())
            except ValueError:
                sys.exit(f"✖  Unable to parse length for “{name}” (row {row_num}). Must be an integer.")
            if length < 1:
                print(f"⚠  WG “{name}” requested {length} slots, defaulting to 1.")
                length = 1
            if length > max_length:
                print(f"⚠  WG “{name}” requested {length} slots, capping at {max_length}.")
                length = max_length
            wgs.append((name, length))
    return wgs


def read_bofs(path, name_col, length_col, max_length):
    """
    Read "BOFs" CSV using the configured name and length column indices.
    For each row, take the first line of the target cell as the BOF name.
    Length is capped at max_length.
    Returns: [ (bof_name:str, length:int), … ]
    """
    bofs = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        if header is None:
            sys.exit("✖  BOFs file is empty or malformed.")
        max_col = max(name_col, length_col)
        if len(header) <= max_col:
            sys.exit(f"✖  BOFs file has {len(header)} columns, but config requires column {max_col}.")
        for row_num, row in enumerate(rdr, start=2):
            if len(row) <= max_col:
                continue
            raw_cell = row[name_col].strip()
            if not raw_cell:
                continue  # skip blank cells
            name = raw_cell.split('\n', 1)[0].strip()
            if not name:
                continue
            try:
                length = int(row[length_col].strip())
            except ValueError:
                sys.exit(f"✖  Unable to parse length for '{name}' (row {row_num}). Must be an integer.")
            if length < 1:
                print(f"⚠  BOF '{name}' requested {length} slots, defaulting to 1.")
                length = 1
            if length > max_length:
                print(f"⚠  BOF '{name}' requested {length} slots, capping at {max_length}.")
                length = max_length
            bofs.append((name, length))
    return bofs


def read_schedule(path):
    """
    Read an existing 5×8 schedule CSV (header + 5 rows).
    Returns a 5×8 list of lists:  grid[block][room] = group_name or None.
    """
    grid = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        if header is None or len(header) < NUM_ROOMS:
            sys.exit(f"✖  Schedule file {path!r} is missing a valid header.")
        for row_num in range(NUM_BLOCKS):
            row = next(rdr, None)
            if row is None:
                sys.exit(f"✖  Schedule file {path!r} has fewer than {NUM_BLOCKS} rows.")
            # Take exactly NUM_ROOMS columns; treat blank or whitespace as None
            cells = []
            for c in row[:NUM_ROOMS]:
                val = c.strip()
                cells.append(val if val else None)
            grid.append(cells)
    return grid


def write_schedule(grid, path):
    """
    Write a 5×N grid to CSV. First row = “Room 1,…,Room N”. Then 5 rows of data.
    Empty cells are output as "".
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"Room {i+1}" for i in range(NUM_ROOMS)])
        for block_row in grid:
            w.writerow([cell or "" for cell in block_row])


# ──────────────────── Placement Algorithms ──────────────────────
def greedy_place_wgroups(wgroups, max_tries, sort_strategy='largest_first', verbose=False):
    """
    Try up to max_tries to place all working groups (length 1–5) into an empty 5×8 grid.
    Returns (grid, failed_name or None, empty_rows_list).
      • grid: 5×8 list-of-lists if successful (each cell = group_name or None).
      • failed_name: if a particular WG couldn’t be placed in any attempt, returns its name.
      • empty_rows_list: after final placement, which rows have zero sessions.
    """
    total_blocks = sum(length for _, length in wgroups)
    if total_blocks > CAPACITY:
        sys.exit(f"✖  Total requested WG blocks = {total_blocks}, capacity = {CAPACITY}.")

    greedy_place_wgroups.last_attempts = 0
    for attempt in range(1, max_tries + 1):
        # Shuffle order of WGs, then sort according to strategy
        a_list = random.sample(wgroups, len(wgroups))
        if sort_strategy == 'largest_first':
            a_list.sort(key=lambda x: -x[1])  # Descending
        elif sort_strategy == 'smallest_first':
            a_list.sort(key=lambda x: x[1])   # Ascending
        # else: 'as_is' - no sorting, keep shuffled order

        # Initialize empty grid
        grid = [[None] * NUM_ROOMS for _ in range(NUM_BLOCKS)]
        failed_name = None

        # Place each WG in "randomised first‐fit" fashion
        for (name, length) in a_list:
            # Build all candidate (start_block, room) pairs
            # Prefer earlier sessions, but randomize room order
            candidates = []
            for start in range(0, NUM_BLOCKS - length + 1):
                rooms = list(range(NUM_ROOMS))
                random.shuffle(rooms)  # Randomize room order within each session
                for room in rooms:
                    candidates.append((start, room))
            placed = False
            for (blk, rms) in candidates:
                # Check if [blk..blk+length-1] in column=room is free
                if all(grid[blk + offset][rms] is None for offset in range(length)):
                    for offset in range(length):
                        grid[blk + offset][rms] = name
                    placed = True
                    break
            if not placed:
                failed_name = name
                break

        if failed_name:
            if verbose:
                print(f"↻  Attempt {attempt}: could not place “{failed_name}”.")
            continue

        # Now see which rows (blocks) remain completely empty
        empty_rows = [idx for idx, row in enumerate(grid) if not any(row)]
        greedy_place_wgroups.last_attempts = attempt
        return grid, None, empty_rows  # success!

    # If we reach here ⇒ no placement found after max_tries
    sys.exit(f"✖  Could not place WG “{failed_name}” after {max_tries} attempts.")


def fill_bofs(grid, bofs, sort_strategy='largest_first', verbose=False):
    """
    Given a partially filled grid and a list of BOFs [(name, length), …],
    attempt to place each BOF (which can now be 1-3 sessions) using same
    algorithm as WGs.
    Returns (new_grid, leftover_bofs_list).
      If leftover_bofs_list is non‐empty, some BOFs couldn't be placed.
    """
    # Copy the grid
    new_grid = [row[:] for row in grid]
    leftovers = []
    
    # Shuffle BOFs and sort according to strategy (same as WGs)
    bof_list = random.sample(bofs, len(bofs))
    if sort_strategy == 'largest_first':
        bof_list.sort(key=lambda x: -x[1])  # Descending
    elif sort_strategy == 'smallest_first':
        bof_list.sort(key=lambda x: x[1])   # Ascending
    # else: 'as_is' - no sorting, keep shuffled order
    
    for (name, length) in bof_list:
        # Build all candidate (start_block, room) pairs
        # Prefer earlier sessions, randomize room order
        candidates = []
        for start in range(0, NUM_BLOCKS - length + 1):
            rooms = list(range(NUM_ROOMS))
            random.shuffle(rooms)  # Randomize room order within each session
            for room in rooms:
                candidates.append((start, room))
        
        placed = False
        for (blk, rms) in candidates:
            # Check if [blk..blk+length-1] in column=room is free
            if all(new_grid[blk + offset][rms] is None for offset in range(length)):
                for offset in range(length):
                    new_grid[blk + offset][rms] = name
                placed = True
                break
        
        if not placed:
            leftovers.append(name)
    
    return new_grid, leftovers


# ─────────────────────────── CLI & Dispatcher ─────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Schedule Working Groups (1–5 blocks) and BOFs (1–2 blocks) "
                    "into a 5×8 grid."
    )
    parser.add_argument("-w", "--wgroups", help="CSV of Working Groups (Name, Quantity)")
    parser.add_argument("-b", "--bofs", help="CSV of BOFs (name column index from config).")
    parser.add_argument("-s", "--schedule", help="Schedule CSV to read (for BOFs) or write.")
    parser.add_argument("--max-tries", type=int, default=DEFAULT_MAX_TRIES,
                        help=f"Max random attempts for placing WGs (default {DEFAULT_MAX_TRIES})")
    parser.add_argument("-c", "--config", default="config.yaml",
                        help="Path to configuration YAML with column indices (default: config.yaml)")
    parser.add_argument("-r", "--rooms", type=int, default=8,
                        help="Number of rooms (default: from config.yaml, or 8 if not specified)")
    parser.add_argument("-p", "--permutations", type=int, default=1,
                        help="Generate multiple valid schedules (default 1)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show diagnostic info (attempt counts, empty rows, etc.)")
    args = parser.parse_args()
    
    # Validate permutations
    if args.permutations < 1:
        sys.exit("✖  Permutations must be >= 1")

    has_w = bool(args.wgroups)
    has_b = bool(args.bofs)
    has_s = bool(args.schedule)

    # Load configuration
    cfg = load_config(args.config)
    
    # Set random seed if specified (for reproducibility)
    if cfg['algorithm']['random_seed'] is not None:
        random.seed(cfg['algorithm']['random_seed'])
        if args.verbose:
            print(f"→ Using random seed: {cfg['algorithm']['random_seed']}")
    
    # Use grid dimensions from config, but allow -r to override num_rooms
    NUM_BLOCKS = cfg['grid']['num_sessions']
    NUM_ROOMS = args.rooms if args.rooms != 8 else cfg['grid']['num_rooms']  # Override if -r specified
    CAPACITY = NUM_BLOCKS * NUM_ROOMS
    
    # Get algorithm parameters (allow --max-tries to override config)
    max_tries = args.max_tries if args.max_tries != DEFAULT_MAX_TRIES else cfg['algorithm']['max_tries']
    sort_strategy = cfg['algorithm']['sort_strategy']

    # “Only -b” is not allowed
    if has_b and not (has_s or has_w):
        sys.exit("✖  Error: “-b/--bofs” requires either “-s/--schedule” (existing file) "
                 "or “-w/--wgroups” (to schedule both phases).")

    # Load Working Groups if requested
    wgroups = []
    if has_w:
        if not os.path.isfile(args.wgroups):
            sys.exit(f"✖  WG file not found: {args.wgroups!r}")
        wgroups = read_wgroups(args.wgroups, cfg['wg']['name_column'], cfg['wg']['length_column'], cfg['wg']['max_length'])
        if args.verbose:
            print(f"→ Loaded {len(wgroups)} Working Groups.")

    # Load BOFs if requested
    bofs = []
    if has_b:
        if not os.path.isfile(args.bofs):
            sys.exit(f"✖  BOFs file not found: {args.bofs!r}")
        bofs = read_bofs(args.bofs, cfg['bof']['name_column'], cfg['bof']['length_column'], cfg['bof']['max_length'])
        if args.verbose:
            print(f"→ Loaded {len(bofs)} BOF request(s).")

    # Pre-flight capacity check (only for WG+BOF mode)
    if has_w and has_b:
        total_wg_slots = sum(length for _, length in wgroups)
        total_bof_slots = sum(length for _, length in bofs)
        total_requested = total_wg_slots + total_bof_slots
        if total_requested > CAPACITY:
            overflow = total_requested - CAPACITY
            print(f"")
            print(f"ℹ️  Over-subscription detected:")
            print(f"   Total requested: {total_requested} slots ({total_wg_slots} WG + {total_bof_slots} BOF)")
            print(f"   Capacity: {CAPACITY} slots ({NUM_BLOCKS} sessions × {NUM_ROOMS} rooms)")
            print(f"   Overflow: {overflow} slots")
            print(f"")
            print(f"   To resolve, edit {args.config}:")
            print(f"   1. Reduce bof.max_length (currently {cfg['bof']['max_length']})")
            print(f"   2. If still over-subscribed, reduce wg.max_length to 3 (currently {cfg['wg']['max_length']})")
            print(f"")
            print(f"   See README.md 'Handling Over-Subscription' for details.")
            print(f"")
            print(f"   No schedule files written.")
            sys.stdout.flush()
            sys.stderr.flush()

            sys.exit(0)

    # 1) Only WGs  → schedule WGs → write & exit
    if has_w and not has_b:
        base_path = args.schedule or "schedule.csv"
        wg_blocks = sum(length for _, length in wgroups)
        if args.permutations > 1:
            print(f"* Scheduling {len(wgroups)} WGs ({wg_blocks} slots), 0 BOFs")
        # Generate requested number of permutations
        for perm in range(1, args.permutations + 1):
            if args.permutations > 1:
                # Multi-permutation: use schedule1.csv, schedule2.csv, etc.
                out_path = base_path.replace(".csv", f"{perm}.csv")
                if not out_path.endswith(".csv"):
                    out_path = f"{base_path}{perm}.csv"
            else:
                out_path = base_path
            
            grid, failed, empty_rows = greedy_place_wgroups(wgroups,
                                                            max_tries,
                                                            sort_strategy,
                                                            args.verbose)
            # Don't print verbose warning - will be shown inline
            # Stats
            filled = sum(1 for row in grid for slot in row if slot)
            tries = getattr(greedy_place_wgroups, 'last_attempts', None) or 1
            # Check if any session (time period across all rooms) is completely empty
            empty_sessions = [i+1 for i, row in enumerate(grid) if not any(row)]
            session_info = f" (session{'s' if len(empty_sessions) != 1 else ''} {','.join(map(str, empty_sessions))} unused)" if empty_sessions else ""
            write_schedule(grid, out_path)
            if args.permutations > 1:
                print(f"  {out_path}: {filled}/{CAPACITY} slots filled{session_info}")
            else:
                print(f"ℹ  {len(wgroups)} WGs ({wg_blocks} slots), 0 BOFs, {filled}/{CAPACITY} slots filled, evaluated {tries} schedule{'s' if tries != 1 else ''}{session_info}")
                print(f"✓  WG‐only schedule written to {out_path!r}.")
        sys.exit(0)

    # 2) Only BOFs (+ existing schedule) → read → fill BOFs → write back
    if has_b and not has_w:
        sched_path = args.schedule
        if not sched_path:
            sys.exit("✖  Please specify an existing schedule (–s SCHEDULE.csv) to update with BOFs.")
        if not os.path.isfile(sched_path):
            sys.exit(f"✖  Cannot find schedule file: {sched_path!r}")

        base_grid = read_schedule(sched_path)
        new_grid, leftovers = fill_bofs(base_grid, bofs, sort_strategy, args.verbose)

        if leftovers:
            sys.exit(f"✖  {len(leftovers)} BOF(s) could not be placed (no empty slots). "
                     f"Example leftover: “{leftovers[0]}”.")
        empty_after = [i for i, row in enumerate(new_grid) if not any(row)]
        # Don't print verbose warning - will be shown inline
        # Stats
        filled = sum(1 for row in new_grid for slot in row if slot)
        empty_sessions = [i+1 for i, row in enumerate(new_grid) if not any(row)]
        session_info = f" (session{'s' if len(empty_sessions) != 1 else ''} {','.join(map(str, empty_sessions))} unused)" if empty_sessions else ""
        print(f"ℹ  {len(bofs)} BOFs added, {filled}/{CAPACITY} slots filled{session_info}")
        write_schedule(new_grid, sched_path)
        print(f"✓  Updated schedule with BOFs written back to {sched_path!r}.")
        sys.exit(0)

    # 3) Both WGs and BOFs  → schedule WGs first, then BOFs
    if has_w and has_b:
        base_path = args.schedule or "schedule.csv"
        wg_blocks = sum(length for _, length in wgroups)
        if args.permutations > 1:
            print(f"* Scheduling {len(wgroups)} WGs ({wg_blocks} slots), {len(bofs)} BOFs")
        # Generate requested number of permutations
        for perm in range(1, args.permutations + 1):
            if args.permutations > 1:
                # Multi-permutation: use schedule1.csv, schedule2.csv, etc.
                out_path = base_path.replace(".csv", f"{perm}.csv")
                if not out_path.endswith(".csv"):
                    out_path = f"{base_path}{perm}.csv"
            else:
                out_path = base_path

            # Place Working Groups
            grid_wg, failed, empty_rows = greedy_place_wgroups(wgroups,
                                                               max_tries,
                                                               sort_strategy,
                                                               args.verbose)
            if failed:
                # (This sys.exit is redundant since greedy_place_wgroups() already sys.exit on failure)
                sys.exit(f"✖  Unexpected: Could not place WG “{failed}”.")

            # Don't print verbose warning - will be shown inline

            # Fill BOFs into any remaining empty cells
            new_grid, leftovers = fill_bofs(grid_wg, bofs, sort_strategy, args.verbose)
            if leftovers:
                sys.exit(f"✖  {len(leftovers)} BOF(s) could not be placed (no empty slots). "
                         f"Example leftover: “{leftovers[0]}”.")
            empty_after = [i for i, row in enumerate(new_grid) if not any(row)]
            # Stats
            filled = sum(1 for row in new_grid for slot in row if slot)
            tries = getattr(greedy_place_wgroups, 'last_attempts', None) or 1
            # Check if any session (time period across all rooms) is completely empty
            empty_sessions = [i+1 for i, row in enumerate(new_grid) if not any(row)]
            session_info = f" (session{'s' if len(empty_sessions) != 1 else ''} {','.join(map(str, empty_sessions))} unused)" if empty_sessions else ""
            write_schedule(new_grid, out_path)
            if args.permutations > 1:
                print(f"  {out_path}: {filled}/{CAPACITY} slots filled{session_info}")
            else:
                print(f"ℹ  {len(wgroups)} WGs ({wg_blocks} slots), {len(bofs)} BOFs, {filled}/{CAPACITY} slots filled, evaluated {tries} schedule{'s' if tries != 1 else ''}{session_info}")
                print(f"✓  Final schedule (WG + BOF) written to {out_path!r}.")
        sys.exit(0)

    # If no valid combination of arguments, print help
    parser.print_help()
    sys.exit(1)

