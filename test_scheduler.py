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
    greedy_place_wgroups, fill_bofs, NUM_BLOCKS
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
        
        wgroups = read_wgroups(wg_path)
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
            read_wgroups(wg_path)
    
    def test_read_bofs_valid(self):
        """Test reading valid BOF CSV with column AG"""
        bof_path = os.path.join(self.test_dir, "test_bof.csv")
        with open(bof_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Create header with 33 columns
            header = [f"Col{i}" for i in range(33)]
            header[32] = "BOF Title"
            writer.writerow(header)
            # Add data rows with BOF names in column 33 (index 32)
            row1 = [""] * 33
            row1[32] = "BOF 1"
            writer.writerow(row1)
            row2 = [""] * 33
            row2[32] = "BOF 2"
            writer.writerow(row2)
        
        bofs = read_bofs(bof_path)
        self.assertEqual(len(bofs), 2)
        self.assertEqual(bofs[0], ("BOF 1", 1))
        self.assertEqual(bofs[1], ("BOF 2", 1))
    
    def test_read_schedule(self):
        """Test reading existing schedule CSV"""
        sched_path = os.path.join(self.test_dir, "test_sched.csv")
        with open(sched_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Room 1", "Room 2", "Room 3", "Room 4", "Room 5", "Room 6", "Room 7", "Room 8"])
            writer.writerow(["WG A", "", "WG B", "", "", "", "", ""])
            writer.writerow(["WG A", "", "", "", "", "", "", ""])
            writer.writerow(["", "", "", "", "", "", "", ""])
            writer.writerow(["", "", "", "", "", "", "", ""])
            writer.writerow(["", "", "", "", "", "", "", ""])
        
        grid = read_schedule(sched_path)
        self.assertEqual(len(grid), 5)  # 5 blocks
        self.assertEqual(len(grid[0]), 8)  # 8 rooms
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
        # Create too many WGs (more than 5*8=40 blocks)
        wgroups = [("WG", 3) for _ in range(20)]  # 60 blocks > 40 capacity
        with self.assertRaises(SystemExit):
            greedy_place_wgroups(wgroups, max_tries=10, verbose=False)
    
    def test_fill_bofs_simple(self):
        """Test BOF filling into empty grid"""
        # Create empty grid
        grid = [[None] * 8 for _ in range(NUM_BLOCKS)]
        bofs = [("BOF 1", 1), ("BOF 2", 1), ("BOF 3", 1)]
        
        new_grid, leftovers = fill_bofs(grid, bofs, verbose=False)
        
        self.assertEqual(len(leftovers), 0)
        # Count BOFs placed
        placed = sum(1 for row in new_grid for cell in row if cell is not None)
        self.assertEqual(placed, 3)
    
    def test_fill_bofs_overflow(self):
        """Test that too many BOFs leaves leftovers"""
        # Create full grid
        grid = [["WG"] * 8 for _ in range(NUM_BLOCKS)]
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
        grid = [
            ["WG A", "WG B", None, None, None, None, None, None],
            ["WG A", None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None, None],
        ]
        
        out_path = os.path.join(self.test_dir, "output.csv")
        write_schedule(grid, out_path)
        
        # Verify file was written
        self.assertTrue(os.path.exists(out_path))
        
        # Read back and verify format
        with open(out_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(len(header), 8)
            self.assertTrue(header[0].startswith("Room"))
            
            rows = list(reader)
            self.assertEqual(len(rows), 5)
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
            header = [f"Col{i}" for i in range(33)]
            writer.writerow(header)
            row1 = [""] * 33
            row1[32] = "BOF Gamma"
            writer.writerow(row1)
        
        # Run scheduling
        wgroups = read_wgroups(wg_path)
        bofs = read_bofs(bof_path)
        
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


if __name__ == '__main__':
    unittest.main()
