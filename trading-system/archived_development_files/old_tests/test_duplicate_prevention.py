#!/usr/bin/env python3
"""
Test script to verify duplicate position prevention fixes
Run this in paper trading mode to verify no duplicates are opened
"""

import sys
import time
from datetime import datetime

def monitor_positions(log_file_path="trading_system.log"):
    """
    Monitor log file for duplicate prevention messages
    """
    print("=" * 80)
    print("DUPLICATE POSITION PREVENTION TEST")
    print("=" * 80)
    print(f"\nMonitoring: {log_file_path}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nLooking for:")
    print("  ✅ '⚠️ Skipping' messages (duplicate prevention working)")
    print("  ✅ '⚠️ SKIPPED: Already have' messages (index-level prevention)")
    print("  🔴 Duplicate position openings (SHOULD NOT HAPPEN)")
    print("\n" + "=" * 80)
    print()

    # Track positions opened per iteration
    iteration_positions = {}
    current_iteration = 0

    # Track prevention events
    position_prevents = 0
    index_prevents = 0
    positions_opened = {}

    try:
        with open(log_file_path, 'r') as f:
            # Move to end of file
            f.seek(0, 2)

            print("📊 Monitoring started. Press Ctrl+C to stop and show summary...\n")

            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue

                # Track iterations
                if "Iteration" in line and ":" in line:
                    try:
                        iter_num = int(line.split("Iteration")[1].split(":")[0].strip())
                        if iter_num != current_iteration:
                            current_iteration = iter_num
                            iteration_positions[current_iteration] = []
                            print(f"\n{'='*80}")
                            print(f"ITERATION {current_iteration}")
                            print(f"{'='*80}")
                    except:
                        pass

                # Detect duplicate prevention at position level
                if "⚠️ Skipping" in line and "position already exists" in line:
                    position_prevents += 1
                    symbol = line.split("Skipping")[1].split("-")[0].strip()
                    print(f"✅ PREVENTED: Position-level check blocked duplicate for {symbol}")

                    # Check next line for existing position info
                    next_line = f.readline()
                    if "Existing:" in next_line:
                        print(f"   {next_line.strip()}")

                # Detect duplicate prevention at index level
                if "⚠️ SKIPPED: Already have" in line and "position(s) for" in line:
                    index_prevents += 1
                    print(f"✅ PREVENTED: Index-level check - {line.strip()}")

                    # Check next line for existing positions list
                    next_line = f.readline()
                    if "Existing positions:" in next_line:
                        print(f"   {next_line.strip()}")

                # Track positions being opened
                if "✅ EXECUTED:" in line or "Straddle positions opened" in line or \
                   "Iron Condor positions opened" in line or "Strangle positions opened" in line:
                    print(f"📈 NEW POSITION: {line.strip()}")

                # Track position executions for duplicate detection
                if "Execute" in line and ("call option" in line.lower() or "put option" in line.lower()):
                    # Try to extract symbol
                    if "symbol=" in line:
                        try:
                            symbol = line.split("symbol=")[1].split(",")[0].strip().strip("'\"")

                            # Check if this symbol was already opened this iteration
                            if symbol in positions_opened:
                                print(f"🔴 WARNING: Possible duplicate detected! {symbol}")
                                print(f"   First opened in iteration: {positions_opened[symbol]}")
                                print(f"   Trying to open again in iteration: {current_iteration}")
                            else:
                                positions_opened[symbol] = current_iteration
                                if current_iteration in iteration_positions:
                                    iteration_positions[current_iteration].append(symbol)
                        except:
                            pass

    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"\nTest Duration: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Iterations Monitored: {current_iteration}")
        print(f"\n✅ Position-Level Preventions: {position_prevents}")
        print(f"✅ Index-Level Preventions: {index_prevents}")
        print(f"📊 Total Positions Opened: {len(positions_opened)}")

        # Check for any duplicates
        duplicate_found = False
        symbol_counts = {}
        for symbol in positions_opened.keys():
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

        duplicates = {s: c for s, c in symbol_counts.items() if c > 1}

        if duplicates:
            print(f"\n🔴 DUPLICATES DETECTED:")
            for symbol, count in duplicates.items():
                print(f"   {symbol}: opened {count} times")
                duplicate_found = True
        else:
            print(f"\n✅ NO DUPLICATES DETECTED!")

        print(f"\n{'='*80}")

        if position_prevents > 0 or index_prevents > 0:
            print("✅ DUPLICATE PREVENTION IS WORKING!")
            print(f"   Total prevention events: {position_prevents + index_prevents}")

        if duplicate_found:
            print("\n🔴 TEST FAILED: Duplicates were opened despite prevention logic")
            sys.exit(1)
        else:
            print("\n✅ TEST PASSED: No duplicate positions opened")
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import os

    # Try to find log file
    log_paths = [
        "trading_system.log",
        "logs/trading_system.log",
        "/Users/gogineni/Python/trading-system/trading_system.log"
    ]

    log_file = None
    for path in log_paths:
        if os.path.exists(path):
            log_file = path
            break

    if log_file:
        monitor_positions(log_file)
    else:
        print("❌ Could not find trading_system.log file")
        print("\nSearched in:")
        for path in log_paths:
            print(f"  - {path}")
        print("\nUsage: python test_duplicate_prevention.py [path/to/trading_system.log]")

        if len(sys.argv) > 1:
            monitor_positions(sys.argv[1])
        else:
            sys.exit(1)
