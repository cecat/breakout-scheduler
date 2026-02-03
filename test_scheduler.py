#!/usr/bin/env python3
"""
Unit tests for scheduler.py

Run with: python3 -m pytest test_scheduler.py
Or: python3 test_scheduler.py
"""

import unittest
import csv
import os
import tempfile
import sys
from scheduler import (
    read_wgroups, read_bofs, read_schedule, write_schedule,
    greedy_place_wgroups, fill_bofs, NUM_BLOCKS, NUM_ROOMS
)


class TestCSVReaders(unittest.TestCase):
    """Test CSV input parsing functions"""
    
    def setUp(self):
        """Create temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temporary files"""
        for f in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, f))
        os.rmdir(self.test_dir)
    
    def test_read_wgroups_valid(self):
        """Test reading valid WG CSV"""
        wg_path = os.path.join(self.test_dir, "test_wg.csv")
        with open(wg_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Name of Group", "Quantity of Sessions Needed"])
            writer.writerow(["Test WG 1", "2"])
            writer.writerow(["Test WG 2", "1"])
        
        wgroups = read_wgroups(wg_path, name_col=0, length_col=1)
        self.assertEqual(len(wgroups), 2)
        self.assertEqual(wgroups[0], ("Test WG 1", 2))
        self.assertEqual(wgroups[1], ("Test WG 2", 1))
    
    def test_read_wgroups_invalid_length(self):
        """Test that invalid WG length causes exit"""
        wg_path = os.path.join(self.test_dir, "test_wg_bad.csv")
        with open(wg_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Name of Group", "Quantity of Sessions Needed"])
            writer.writerow(["Bad WG", "5"])  # Invalid: must be 1-3
        
        with self.assertRaises(SystemExit):
            read_wgroups(wg_path, name_col=0, length_col=1)
    
    def test_read_bofs_valid(self):
        """Test reading valid BOF CSV with name and length columns"""
        bof_path = os.path.join(self.test_dir, "test_bof.csv")
        with open(bof_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Create header with 12 columns (name=8, length=11)
            header = [f"Col{i}" for i in range(12)]
            header[8] = "BOF Title"
            header[11] = "Session Count"
            writer.writerow(header)
            # Add data rows with BOF names and lengths
            row1 = [""] * 12
            row1[8] = "BOF 1"
            row1[11] = "1"
            writer.writerow(row1)
            row2 = [""] * 12
            row2[8] = "BOF 2"
            row2[11] = "2"
            writer.writerow(row2)
        
        bofs = read_bofs(bof_path, name_col=8, length_col=11)
        self.assertEqual(len(bofs), 2)
        self.assertEqual(bofs[0], ("BOF 1", 1))
        self.assertEqual(bofs[1], ("BOF 2", 2))
    
    def test_read_schedule(self):
        """Test reading existing schedule CSV"""
        sched_path = os.path.join(self.test_dir, "test_sched.csv")
        with open(sched_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Use actual NUM_ROOMS from config
            writer.writerow([f"Room {i+1}" for i in range(NUM_ROOMS)])
            # Create NUM_BLOCKS rows
            for block in range(NUM_BLOCKS):
                row = [""] * NUM_ROOMS
                if block == 0:  # First block only
                    row[0] = "WG A"
                    row[2] = "WG B"
                elif block == 1:  # Second block
                    row[0] = "WG A"
                writer.writerow(row)
        
        grid = read_schedule(sched_path)
        self.assertEqual(len(grid), NUM_BLOCKS)
        self.assertEqual(len(grid[0]), NUM_ROOMS)
        self.assertEqual(grid[0][0], "WG A")
        self.assertEqual(grid[0][2], "WG B")
        self.assertIsNone(grid[0][1])


class TestSchedulingAlgorithms(unittest.TestCase):
    """Test scheduling placement algorithms"""
    
    def test_greedy_place_wgroups_simple(self):
        """Test basic WG placement"""
        wgroups = [("WG 1", 1), ("WG 2", 2), ("WG 3", 1)]
        grid, failed, empty_rows = greedy_place_wgroups(wgroups, max_tries=100, verbose=False)
        
        self.assertIsNone(failed)
        self.assertEqual(len(grid), NUM_BLOCKS)
        # Count total placed blocks
        placed = sum(1 for row in grid for cell in row if cell is not None)
        self.assertEqual(placed, 4)  # 1+2+1 = 4 blocks total
    
    def test_greedy_place_wgroups_capacity_exceeded(self):
        """Test that exceeding capacity causes exit"""
        # Create too many WGs (more than NUM_BLOCKS * NUM_ROOMS capacity)
        capacity = NUM_BLOCKS * NUM_ROOMS
        wgroups = [("WG", 3) for _ in range((capacity // 3) + 5)]  # Exceed capacity
        with self.assertRaises(SystemExit):
            greedy_place_wgroups(wgroups, max_tries=10, verbose=False)
    
    def test_fill_bofs_simple(self):
        """Test BOF filling into empty grid"""
        # Create empty grid using current config
        grid = [[None] * NUM_ROOMS for _ in range(NUM_BLOCKS)]
        bofs = [("BOF 1", 1), ("BOF 2", 2), ("BOF 3", 1)]
        
        new_grid, leftovers = fill_bofs(grid, bofs, verbose=False)
        
        self.assertEqual(len(leftovers), 0)
        # Count BOF slots placed (1+2+1 = 4)
        placed = sum(1 for row in new_grid for cell in row if cell is not None)
        self.assertEqual(placed, 4)
    
    def test_fill_bofs_overflow(self):
        """Test that too many BOFs leaves leftovers"""
        # Create full grid using current config
        grid = [["WG"] * NUM_ROOMS for _ in range(NUM_BLOCKS)]
        bofs = [("BOF 1", 1), ("BOF 2", 1)]
        
        new_grid, leftovers = fill_bofs(grid, bofs, verbose=False)
        
        # All BOFs should be in leftovers since grid is full
        self.assertEqual(len(leftovers), 2)


class TestScheduleIO(unittest.TestCase):
    """Test schedule writing functions"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        for f in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, f))
        os.rmdir(self.test_dir)
    
    def test_write_schedule(self):
        """Test writing schedule to CSV"""
        # Create grid using current config
        grid = [[None] * NUM_ROOMS for _ in range(NUM_BLOCKS)]
        # Add some test data
        grid[0][0] = "WG A"
        grid[0][1] = "WG B"
        if NUM_BLOCKS > 1:
            grid[1][0] = "WG A"
        
        out_path = os.path.join(self.test_dir, "output.csv")
        write_schedule(grid, out_path)
        
        # Verify file was written
        self.assertTrue(os.path.exists(out_path))
        
        # Read back and verify format
        with open(out_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(len(header), NUM_ROOMS)
            self.assertTrue(header[0].startswith("Room"))
            
            rows = list(reader)
            self.assertEqual(len(rows), NUM_BLOCKS)
            self.assertEqual(rows[0][0], "WG A")
            self.assertEqual(rows[0][1], "WG B")
            self.assertEqual(rows[0][2], "")  # Empty cells become ""


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        for f in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, f))
        os.rmdir(self.test_dir)
    
    def test_full_workflow_wg_and_bof(self):
        """Test complete WG + BOF scheduling workflow"""
        # Create WG input
        wg_path = os.path.join(self.test_dir, "wg.csv")
        with open(wg_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Name of Group", "Quantity of Sessions Needed"])
            writer.writerow(["WG Alpha", "2"])
            writer.writerow(["WG Beta", "1"])
        
        # Create BOF input
        bof_path = os.path.join(self.test_dir, "bof.csv")
        with open(bof_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            header = [f"Col{i}" for i in range(12)]
            writer.writerow(header)
            row1 = [""] * 12
            row1[8] = "BOF Gamma"
            row1[11] = "1"
            writer.writerow(row1)
        
        # Run scheduling
        wgroups = read_wgroups(wg_path, name_col=0, length_col=1)
        bofs = read_bofs(bof_path, name_col=8, length_col=11)
        
        grid, failed, empty_rows = greedy_place_wgroups(wgroups, max_tries=100)
        self.assertIsNone(failed)
        
        final_grid, leftovers = fill_bofs(grid, bofs)
        self.assertEqual(len(leftovers), 0)
        
        # Write and verify output
        out_path = os.path.join(self.test_dir, "schedule.csv")
        write_schedule(final_grid, out_path)
        self.assertTrue(os.path.exists(out_path))
        
        # Count total sessions
        total = sum(1 for row in final_grid for cell in row if cell is not None)
        self.assertEqual(total, 4)  # 2+1+1 = 4 sessions
    
    def test_all_sessions_scheduled(self):
        """Test that all requested sessions appear in the schedule"""
        wgroups = [("WG 1", 2), ("WG 2", 1), ("WG 3", 3)]
        bofs = [("BOF 1", 1), ("BOF 2", 1)]
        
        # Schedule WGs
        grid, failed, _ = greedy_place_wgroups(wgroups, max_tries=100)
        self.assertIsNone(failed, "WG placement should succeed")
        
        # Add BOFs
        final_grid, leftovers = fill_bofs(grid, bofs)
        self.assertEqual(len(leftovers), 0, "All BOFs should be placed")
        
        # Verify all sessions appear in grid
        # Count occurrences of each session
        from collections import Counter
        all_cells = [cell for row in final_grid for cell in row if cell is not None]
        counts = Counter(all_cells)
        
        # Verify WG counts (should match requested lengths)
        self.assertEqual(counts["WG 1"], 2)
        self.assertEqual(counts["WG 2"], 1)
        self.assertEqual(counts["WG 3"], 3)
        # Verify BOF counts (always 1)
        self.assertEqual(counts["BOF 1"], 1)
        self.assertEqual(counts["BOF 2"], 1)
    
    def test_output_dimensions(self):
        """Test that output schedule has correct dimensions"""
        wgroups = [("WG Test", 1)]
        grid, failed, _ = greedy_place_wgroups(wgroups, max_tries=100)
        self.assertIsNone(failed)
        
        # Verify grid dimensions
        self.assertEqual(len(grid), NUM_BLOCKS, f"Grid should have {NUM_BLOCKS} time blocks")
        for block_idx, row in enumerate(grid):
            self.assertEqual(len(row), NUM_ROOMS, 
                           f"Block {block_idx} should have {NUM_ROOMS} rooms")
        
        # Write to CSV and verify output format
        out_path = os.path.join(self.test_dir, "test_output.csv")
        write_schedule(grid, out_path)
        
        with open(out_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(len(header), NUM_ROOMS, 
                           f"Header should have {NUM_ROOMS} room columns")
            
            data_rows = list(reader)
            self.assertEqual(len(data_rows), NUM_BLOCKS,
                           f"CSV should have {NUM_BLOCKS} data rows")
    
    def test_wg_sessions_consecutive(self):
        """Test that WG sessions are consecutive in same room"""
        wgroups = [("WG Multi", 3)]
        grid, failed, _ = greedy_place_wgroups(wgroups, max_tries=100)
        self.assertIsNone(failed)
        
        # Find where "WG Multi" is placed
        wg_positions = []
        for block_idx, row in enumerate(grid):
            for room_idx, cell in enumerate(row):
                if cell == "WG Multi":
                    wg_positions.append((block_idx, room_idx))
        
        self.assertEqual(len(wg_positions), 3, "Should have 3 sessions")
        
        # All should be in same room
        rooms = [room for _, room in wg_positions]
        self.assertEqual(len(set(rooms)), 1, "All sessions must be in same room")
        
        # Should be consecutive time blocks
        blocks = sorted([block for block, _ in wg_positions])
        for i in range(len(blocks) - 1):
            self.assertEqual(blocks[i+1], blocks[i] + 1, 
                           "Sessions must be in consecutive time blocks")
    
    def test_no_double_booking(self):
        """Test that no room/time slot has multiple sessions"""
        wgroups = [("WG A", 1), ("WG B", 1), ("WG C", 2)]
        bofs = [("BOF X", 1), ("BOF Y", 1)]
        
        grid, failed, _ = greedy_place_wgroups(wgroups, max_tries=100)
        self.assertIsNone(failed)
        
        final_grid, leftovers = fill_bofs(grid, bofs)
        self.assertEqual(len(leftovers), 0)
        
        # Each cell should have at most one session
        for block_idx, row in enumerate(final_grid):
            for room_idx, cell in enumerate(row):
                # Cell is either None or a single string (not a list)
                self.assertTrue(cell is None or isinstance(cell, str),
                              f"Cell [{block_idx}][{room_idx}] should be None or string")


if __name__ == '__main__':
    unittest.main()
