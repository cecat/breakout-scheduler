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


# ──────────────────────── I/O Helpers ────────────────────────
def read_wgroups(path):
    """
    Read “Working Groups” CSV. Expect exactly these two headers:
      “Name of Group”  and  “Quantity of Sessions Needed”
    Each length must be in {1,2,3}.
    Returns:  [ (name:str, length:int), … ]
    """
    wgs = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            name = row.get("Name of Group", "").strip()
            if not name:
                sys.exit("✖  Found a blank “Name of Group” in WGs file.")
            try:
                length = int(row.get("Quantity of Sessions Needed", "").strip())
            except ValueError:
                sys.exit(f"✖  Unable to parse length for “{name}”. Must be an integer.")
            if length < 1 or length > 3:
                sys.exit(f"✖  WG “{name}” asked for {length} blocks (only 1–3 allowed).")
            wgs.append((name, length))
    return wgs


def read_bofs(path):
    """
    Read “BOFs” CSV. We ignore all columns except column AG (33rd column).
    For each row, take the first line (split on '\\n') of the AG‐cell as the BOF name.
    Returns: [ (bof_name:str, 1), … ]  — all length=1
    """
    bofs = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        if header is None:
            sys.exit("✖  BOFs file is empty or malformed.")
        for row_num, row in enumerate(rdr, start=2):
            if len(row) < 33:
                # Fewer than 33 columns means no AG column
                continue
            raw_cell = row[32].strip()  # zero‐based index 32 = column AG
            if not raw_cell:
                continue  # skip blank AG cells
            name = raw_cell.strip()

            if name:
                bofs.append((name, 1))
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


# ────────────────────── Placement Algorithms ──────────────────────
def greedy_place_wgroups(wgroups, max_tries, verbose=False):
    """
    Try up to max_tries to place all working groups (length 1–3) into an empty 5×8 grid.
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
        # Shuffle order of WGs, then sort by descending length
        a_list = random.sample(wgroups, len(wgroups))
        a_list.sort(key=lambda x: -x[1])

        # Initialize empty grid
        grid = [[None] * NUM_ROOMS for _ in range(NUM_BLOCKS)]
        failed_name = None

        # Place each WG in “randomised first‐fit” fashion
        for (name, length) in a_list:
            # Build all candidate (start_block, room) pairs
            candidates = [
                (start, room)
                for start in range(0, NUM_BLOCKS - length + 1)
                for room in range(NUM_ROOMS)
            ]
            random.shuffle(candidates)
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


def fill_bofs(grid, bofs, verbose=False):
    """
    Given a partially filled 5×8 grid (with None in empty cells) and a list of BOFs
    [(name,1),…], attempt to fill each BOF into a single free cell.
    Returns (new_grid, leftover_bofs_list).  
      If leftover_bofs_list is non‐empty, there weren’t enough empty cells.
    """
    # Collect all empty coordinates
    empties = [(r, c) for r in range(NUM_BLOCKS) for c in range(NUM_ROOMS) if grid[r][c] is None]
    if verbose:
        print(f"    → {len(empties)} empty cell(s) available for BOFs.")
    random.shuffle(empties)

    new_grid = [row[:] for row in grid]
    leftovers = []

    for idx, (name, _) in enumerate(bofs):
        if idx < len(empties):
            r, c = empties[idx]
            new_grid[r][c] = name
        else:
            leftovers.append(name)

    return new_grid, leftovers


# ───────────────────────── CLI & Dispatcher ─────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Schedule Working Groups (1–3 blocks) and BOFs (1 block) "
                    "into a 5×8 grid."
    )
    parser.add_argument("-w", "--wgroups", help="CSV of Working Groups (Name, Quantity)")
    parser.add_argument("-b", "--bofs", help="CSV of BOFs (we read column AG).")
    parser.add_argument("-s", "--schedule", help="Schedule CSV to read (for BOFs) or write.")
    parser.add_argument("--max-tries", type=int, default=DEFAULT_MAX_TRIES,
                        help=f"Max random attempts for placing WGs (default {DEFAULT_MAX_TRIES})")
    parser.add_argument("-r", "--rooms", type=int, default=NUM_ROOMS,
                        help=f"Number of rooms (default {NUM_ROOMS})")
    parser.add_argument("--verbose", action="store_true",
                        help="Show diagnostic info (attempt counts, empty rows, etc.)")
    args = parser.parse_args()
    
    # Update NUM_ROOMS based on command line argument
    NUM_ROOMS = args.rooms
    CAPACITY = NUM_BLOCKS * NUM_ROOMS

    has_w = bool(args.wgroups)
    has_b = bool(args.bofs)
    has_s = bool(args.schedule)

    # “Only -b” is not allowed
    if has_b and not (has_s or has_w):
        sys.exit("✖  Error: “-b/--bofs” requires either “-s/--schedule” (existing file) "
                 "or “-w/--wgroups” (to schedule both phases).")

    # Load Working Groups if requested
    wgroups = []
    if has_w:
        if not os.path.isfile(args.wgroups):
            sys.exit(f"✖  WG file not found: {args.wgroups!r}")
        wgroups = read_wgroups(args.wgroups)
        if args.verbose:
            print(f"→ Loaded {len(wgroups)} Working Groups.")

    # Load BOFs if requested
    bofs = []
    if has_b:
        if not os.path.isfile(args.bofs):
            sys.exit(f"✖  BOFs file not found: {args.bofs!r}")
        bofs = read_bofs(args.bofs)
        if args.verbose:
            print(f"→ Loaded {len(bofs)} BOF request(s) (each length=1).")

    # 1) Only WGs  → schedule WGs → write & exit
    if has_w and not has_b:
        out_path = args.schedule or "schedule.csv"
        grid, failed, empty_rows = greedy_place_wgroups(wgroups,
                                                        args.max_tries,
                                                        args.verbose)
        if empty_rows:
            print("⚠  Warning: The following block(s) have no Working Group assigned:",
                  ", ".join(f"Block {r+1}" for r in empty_rows))
        # Stats
        filled = sum(1 for row in grid for cell in row if cell)
        empty_slots = CAPACITY - filled
        tries = getattr(greedy_place_wgroups, 'last_attempts', None) or 1
        print(f"ℹ  Stats: WG requests={len(wgroups)}, BOF requests=0, slots filled={filled}/{CAPACITY}, empty slots={empty_slots}, tries={tries}")
        write_schedule(grid, out_path)
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
        new_grid, leftovers = fill_bofs(base_grid, bofs, args.verbose)

        if leftovers:
            sys.exit(f"✖  {len(leftovers)} BOF(s) could not be placed (no empty slots). "
                     f"Example leftover: “{leftovers[0]}”.")
        empty_after = [i for i, row in enumerate(new_grid) if not any(row)]
        if empty_after:
            print("⚠  Warning: These block(s) remain empty after filling BOFs:",
                  ", ".join(f"Block {r+1}" for r in empty_after))
        # Stats
        filled = sum(1 for row in new_grid for cell in row if cell)
        empty_slots = CAPACITY - filled
        print(f"ℹ  Stats: WG requests=-, BOF requests={len(bofs)}, slots filled={filled}/{CAPACITY}, empty slots={empty_slots}, tries=-")
        write_schedule(new_grid, sched_path)
        print(f"✓  Updated schedule with BOFs written back to {sched_path!r}.")
        sys.exit(0)

    # 3) Both WGs and BOFs  → schedule WGs first, then BOFs
    if has_w and has_b:
        out_path = args.schedule or "schedule.csv"

        # Place Working Groups
        grid_wg, failed, empty_rows = greedy_place_wgroups(wgroups,
                                                           args.max_tries,
                                                           args.verbose)
        if failed:
            # (This sys.exit is redundant since greedy_place_wgroups() already sys.exit on failure)
            sys.exit(f"✖  Unexpected: Could not place WG “{failed}”.")

        if args.verbose and empty_rows:
            print("⚠  After placing WGs, these block(s) are still empty:",
                  ", ".join(f"Block {r+1}" for r in empty_rows))

        # Fill BOFs into any remaining empty cells
        new_grid, leftovers = fill_bofs(grid_wg, bofs, args.verbose)
        if leftovers:
            sys.exit(f"✖  {len(leftovers)} BOF(s) could not be placed (no empty slots). "
                     f"Example leftover: “{leftovers[0]}”.")
        empty_after = [i for i, row in enumerate(new_grid) if not any(row)]
        if empty_after:
            print("⚠  Warning: After placing BOFs, these block(s) remain empty:",
                  ", ".join(f"Block {r+1}" for r in empty_after))

        # Stats
        filled = sum(1 for row in new_grid for cell in row if cell)
        empty_slots = CAPACITY - filled
        tries = getattr(greedy_place_wgroups, 'last_attempts', None) or 1
        print(f"ℹ  Stats: WG requests={len(wgroups)}, BOF requests={len(bofs)}, slots filled={filled}/{CAPACITY}, empty slots={empty_slots}, tries={tries}")
        write_schedule(new_grid, out_path)
        print(f"✓  Final schedule (WG + BOF) written to {out_path!r}.")
        sys.exit(0)

    # If no valid combination of arguments, print help
    parser.print_help()
    sys.exit(1)

