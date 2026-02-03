#!/bin/bash
# Test runner for breakout-scheduler

set -e

echo "Running unit tests..."
python3 test_scheduler.py -v

echo ""
echo "Testing scheduler help..."
python3 scheduler.py --help > /dev/null

echo ""
echo "✓ All tests passed!"
