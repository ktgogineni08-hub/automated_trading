#!/usr/bin/env python3
"""
Quick script to check current Kite positions for duplicates
"""

import sys
from collections import defaultdict

try:
    from kiteconnect import KiteConnect
except ImportError:
    print("❌ Error: kiteconnect module not installed")
    print("Install with: pip install kiteconnect")
    sys.exit(1)


def check_positions(api_key, access_token):
    """Check Kite positions for duplicates"""

    print("=" * 80)
    print("POSITION DUPLICATE CHECK")
    print("=" * 80)
    print()

    try:
        # Connect to Kite
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)

        # Fetch positions
        print("📊 Fetching positions from Kite...")
        positions = kite.positions()
        net_positions = positions.get('net', [])

        if not net_positions:
            print("✅ No positions found in account")
            return

        # Filter active positions (non-zero quantity)
        active_positions = [
            p for p in net_positions
            if p.get('quantity', 0) != 0
        ]

        if not active_positions:
            print("✅ No active positions (all closed)")
            return

        print(f"Found {len(active_positions)} active position(s)\n")

        # Group by symbol to detect duplicates
        position_groups = defaultdict(list)
        total_value = 0
        total_pnl = 0

        for pos in active_positions:
            symbol = pos.get('tradingsymbol', '')
            position_groups[symbol].append(pos)
            total_value += float(pos.get('value', 0))
            total_pnl += float(pos.get('pnl', 0))

        # Check for duplicates
        duplicates_found = False

        print("POSITION ANALYSIS:")
        print("-" * 80)

        for symbol, positions_list in sorted(position_groups.items()):
            is_duplicate = len(positions_list) > 1

            if is_duplicate:
                duplicates_found = True
                print(f"\n🔴 DUPLICATE: {symbol} ({len(positions_list)} entries)")
            else:
                print(f"\n✅ {symbol}")

            # Aggregate quantities and values
            total_qty = sum(p.get('quantity', 0) for p in positions_list)
            total_pos_value = sum(p.get('value', 0) for p in positions_list)
            total_pos_pnl = sum(p.get('pnl', 0) for p in positions_list)

            print(f"   Total Quantity: {total_qty}")
            print(f"   Total Value: ₹{total_pos_value:,.2f}")
            print(f"   Total P&L: ₹{total_pos_pnl:,.2f} ({(total_pos_pnl/abs(total_pos_value)*100):.2f}%)")

            # Show individual entries if duplicate
            if is_duplicate:
                for i, pos in enumerate(positions_list, 1):
                    qty = pos.get('quantity', 0)
                    avg_price = float(pos.get('average_price', 0))
                    last_price = float(pos.get('last_price', 0))
                    pnl = float(pos.get('pnl', 0))
                    product = pos.get('product', 'N/A')

                    print(f"   Entry {i}:")
                    print(f"     Qty: {qty} | Avg: ₹{avg_price:.2f} | LTP: ₹{last_price:.2f}")
                    print(f"     P&L: ₹{pnl:,.2f} | Product: {product}")

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total Active Positions: {len(active_positions)}")
        print(f"Unique Symbols: {len(position_groups)}")
        print(f"Total Portfolio Value: ₹{total_value:,.2f}")
        print(f"Total P&L: ₹{total_pnl:,.2f}")

        if total_value != 0:
            pnl_pct = (total_pnl / abs(total_value)) * 100
            print(f"P&L Percentage: {pnl_pct:+.2f}%")

        print()

        if duplicates_found:
            print("🔴 ACTION REQUIRED: Duplicate positions detected!")
            print()
            print("Recommended Actions:")
            print("1. Close all duplicate entries via Kite web interface")
            print("2. OR use the cleanup guide: CLEANUP_DUPLICATE_POSITIONS_GUIDE.md")
            print("3. Verify no duplicates before restarting trading system")
            print()
            return False
        else:
            print("✅ NO DUPLICATES FOUND - Safe to restart trading system")
            print()
            return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()

    # Try to read credentials from config
    try:
        import json
        import os

        config_path = "config.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get('api_key')
                access_token = config.get('access_token')

                if api_key and access_token:
                    print("📋 Using credentials from config.json\n")
                    result = check_positions(api_key, access_token)
                    sys.exit(0 if result else 1)

    except Exception as e:
        print(f"Could not read config.json: {e}")

    # Manual input
    print("Please provide Kite credentials:")
    print()

    api_key = input("API Key: ").strip()
    if not api_key:
        print("❌ API Key required")
        sys.exit(1)

    access_token = input("Access Token: ").strip()
    if not access_token:
        print("❌ Access Token required")
        sys.exit(1)

    print()
    result = check_positions(api_key, access_token)
    sys.exit(0 if result else 1)
