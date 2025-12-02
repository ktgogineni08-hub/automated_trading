#!/usr/bin/env python3
"""
Script to cleanup duplicate positions in Kite account
"""

import sys
import json
from collections import defaultdict
from kiteconnect import KiteConnect


def load_credentials():
    """Load credentials from config files"""
    try:
        # Load from trading config
        with open('trading_config.json', 'r') as f:
            config = json.load(f)
            api_key = config['api']['zerodha']['api_key']

        # Load access token
        with open('zerodha_tokens.json', 'r') as f:
            tokens = json.load(f)
            access_token = tokens['access_token']

        return api_key, access_token
    except Exception as e:
        print(f"❌ Error loading credentials: {e}")
        return None, None


def get_duplicate_positions(kite):
    """Identify duplicate positions"""
    print("📊 Fetching current positions from Kite...")
    positions = kite.positions()
    net_positions = positions.get('net', [])

    if not net_positions:
        print("✅ No positions found in account")
        return {}

    # Filter active F&O positions
    active_positions = [
        p for p in net_positions
        if p.get('quantity', 0) != 0 and p.get('exchange') in ['NFO', 'BFO']
    ]

    if not active_positions:
        print("✅ No active F&O positions")
        return {}

    print(f"Found {len(active_positions)} active F&O position(s)")

    # Group by symbol
    position_groups = defaultdict(list)
    for pos in active_positions:
        symbol = pos.get('tradingsymbol', '')
        position_groups[symbol].append(pos)

    # Find duplicates
    duplicates = {}
    for symbol, positions_list in position_groups.items():
        if len(positions_list) > 1:
            duplicates[symbol] = positions_list

    return duplicates


def display_duplicates(duplicates):
    """Display duplicate positions"""
    if not duplicates:
        print("\n✅ NO DUPLICATES FOUND!")
        return False

    print("\n" + "="*80)
    print("🔴 DUPLICATE POSITIONS DETECTED")
    print("="*80)

    total_duplicate_value = 0

    for symbol, positions_list in duplicates.items():
        print(f"\n🔴 {symbol}: {len(positions_list)} entries")

        total_qty = sum(p.get('quantity', 0) for p in positions_list)
        total_value = sum(abs(p.get('value', 0)) for p in positions_list)
        total_pnl = sum(p.get('pnl', 0) for p in positions_list)
        total_duplicate_value += total_value

        print(f"   Combined: {total_qty} shares | Value: ₹{total_value:,.2f} | P&L: ₹{total_pnl:,.2f}")

        for i, pos in enumerate(positions_list, 1):
            qty = pos.get('quantity', 0)
            avg_price = float(pos.get('average_price', 0))
            last_price = float(pos.get('last_price', 0))
            pnl = float(pos.get('pnl', 0))
            product = pos.get('product', 'N/A')
            exchange = pos.get('exchange', 'N/A')

            print(f"   Entry {i}: {qty} shares @ ₹{avg_price:.2f} | LTP: ₹{last_price:.2f} | P&L: ₹{pnl:,.2f} | {product}")

    print("\n" + "="*80)
    print(f"Total Duplicate Value: ₹{total_duplicate_value:,.2f}")
    print("="*80)

    return True


def close_all_positions(kite, duplicates):
    """Close ALL positions (duplicates and originals)"""
    print("\n⚠️  CLOSING ALL POSITIONS (Clean Slate Strategy)")
    print("="*80)

    closed_count = 0
    failed_count = 0

    for symbol, positions_list in duplicates.items():
        print(f"\n📍 Closing all entries for {symbol}...")

        for i, pos in enumerate(positions_list, 1):
            qty = abs(pos.get('quantity', 0))
            exchange = pos.get('exchange', 'NFO')
            product = pos.get('product', kite.PRODUCT_MIS)

            # Determine transaction type (opposite of current position)
            current_qty = pos.get('quantity', 0)
            if current_qty > 0:
                transaction_type = kite.TRANSACTION_TYPE_SELL  # Close long
            else:
                transaction_type = kite.TRANSACTION_TYPE_BUY   # Close short

            try:
                print(f"   Entry {i}: Closing {qty} shares ({transaction_type})...")

                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange=exchange,
                    tradingsymbol=symbol,
                    transaction_type=transaction_type,
                    quantity=qty,
                    product=product,
                    order_type=kite.ORDER_TYPE_MARKET
                )

                print(f"   ✅ Order placed: {order_id}")
                closed_count += 1

            except Exception as e:
                print(f"   ❌ Failed to close: {e}")
                failed_count += 1

    print("\n" + "="*80)
    print(f"✅ Closed: {closed_count} positions")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count} positions")
    print("="*80)

    return closed_count, failed_count


def close_duplicates_only(kite, duplicates):
    """Close only duplicate entries, keep first entry"""
    print("\n⚠️  CLOSING DUPLICATE ENTRIES ONLY (Keep First Entry)")
    print("="*80)

    closed_count = 0
    failed_count = 0

    for symbol, positions_list in duplicates.items():
        print(f"\n📍 {symbol}: Keeping first entry, closing {len(positions_list)-1} duplicate(s)...")

        # Keep first, close rest
        for i, pos in enumerate(positions_list[1:], 2):  # Start from second entry
            qty = abs(pos.get('quantity', 0))
            exchange = pos.get('exchange', 'NFO')
            product = pos.get('product', kite.PRODUCT_MIS)

            # Determine transaction type
            current_qty = pos.get('quantity', 0)
            if current_qty > 0:
                transaction_type = kite.TRANSACTION_TYPE_SELL
            else:
                transaction_type = kite.TRANSACTION_TYPE_BUY

            try:
                print(f"   Entry {i}: Closing {qty} shares ({transaction_type})...")

                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange=exchange,
                    tradingsymbol=symbol,
                    transaction_type=transaction_type,
                    quantity=qty,
                    product=product,
                    order_type=kite.ORDER_TYPE_MARKET
                )

                print(f"   ✅ Order placed: {order_id}")
                closed_count += 1

            except Exception as e:
                print(f"   ❌ Failed to close: {e}")
                failed_count += 1

        # Show what we're keeping
        first_pos = positions_list[0]
        qty = first_pos.get('quantity', 0)
        avg_price = float(first_pos.get('average_price', 0))
        print(f"   ✅ Keeping: {qty} shares @ ₹{avg_price:.2f}")

    print("\n" + "="*80)
    print(f"✅ Closed: {closed_count} duplicate positions")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count} positions")
    print("="*80)

    return closed_count, failed_count


def main():
    print("="*80)
    print("DUPLICATE POSITION CLEANUP")
    print("="*80)
    print()

    # Load credentials
    api_key, access_token = load_credentials()
    if not api_key or not access_token:
        print("❌ Could not load credentials")
        sys.exit(1)

    print(f"✅ Credentials loaded")
    print(f"   API Key: {api_key[:10]}...")

    # Connect to Kite
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        print("✅ Connected to Kite")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    # Get duplicates
    duplicates = get_duplicate_positions(kite)

    # Display duplicates
    has_duplicates = display_duplicates(duplicates)

    if not has_duplicates:
        print("\n✅ No cleanup needed. Your positions are clean!")
        sys.exit(0)

    # Ask user what to do
    print("\n" + "="*80)
    print("CLEANUP OPTIONS")
    print("="*80)
    print()
    print("1. Close ALL positions (RECOMMENDED - Clean slate)")
    print("   • Closes everything including duplicates")
    print("   • Trading system will open fresh positions")
    print("   • Simplest and safest option")
    print()
    print("2. Close only duplicate entries (Keep first entry)")
    print("   • Keeps your original positions")
    print("   • Closes the duplicate entries")
    print("   • More complex, need to track carefully")
    print()
    print("3. Exit (cleanup manually via Kite web)")
    print()

    choice = input("Enter choice (1/2/3): ").strip()

    if choice == "1":
        # Confirm
        print("\n⚠️  WARNING: This will close ALL positions!")
        confirm = input("Type 'CLOSE ALL' to confirm: ").strip()

        if confirm == "CLOSE ALL":
            closed, failed = close_all_positions(kite, duplicates)

            if failed == 0:
                print("\n✅ All positions closed successfully!")
                print("✅ Ready to restart trading system")
            else:
                print(f"\n⚠️  Some positions failed to close. Please check manually.")

        else:
            print("❌ Cancelled")

    elif choice == "2":
        # Confirm
        print("\n⚠️  This will close duplicate entries only")
        confirm = input("Type 'CLOSE DUPLICATES' to confirm: ").strip()

        if confirm == "CLOSE DUPLICATES":
            closed, failed = close_duplicates_only(kite, duplicates)

            if failed == 0:
                print("\n✅ All duplicates closed successfully!")
                print("✅ Ready to restart trading system")
            else:
                print(f"\n⚠️  Some duplicates failed to close. Please check manually.")

        else:
            print("❌ Cancelled")

    else:
        print("\n✅ No changes made. Please cleanup manually via Kite web interface:")
        print("   https://kite.zerodha.com")

    print("\n" + "="*80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
