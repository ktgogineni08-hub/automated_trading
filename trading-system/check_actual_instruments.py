#!/usr/bin/env python3
"""
Check what indices are ACTUALLY available in NFO and BFO instruments from Kite
This will tell us the real availability vs our assumptions
"""

import sys
import os
from datetime import datetime
from collections import defaultdict

# Add the current directory to Python path
sys.path.append('/Users/gogineni/Python/trading-system')

# Import required classes
from enhanced_trading_system_complete import UnifiedTradingSystem

def check_actual_instrument_availability():
    """Check what's actually available in NFO and BFO"""
    print("🔍 Checking ACTUAL instrument availability in NFO and BFO...")
    print("=" * 80)

    try:
        # Create trading system instance
        system = UnifiedTradingSystem()

        # Test if we can connect to Kite
        if not system.data_provider.kite:
            print("❌ No Kite connection available")
            return False

        print("✅ Kite connection established")

        # Check NFO instruments
        print("\n📊 Checking NSE F&O (NFO) instruments...")
        try:
            nfo_instruments = system.data_provider.kite.instruments("NFO")
            print(f"✅ Retrieved {len(nfo_instruments)} NFO instruments")

            # Analyze NFO instruments
            nfo_indices = defaultdict(lambda: {'FUT': 0, 'CE': 0, 'PE': 0})
            nfo_sample_instruments = defaultdict(list)

            for inst in nfo_instruments:
                index_name = inst.get('name', '')
                instrument_type = inst.get('instrument_type', '')
                exchange = inst.get('exchange', 'NSE')

                if instrument_type in ['FUT', 'CE', 'PE']:
                    nfo_indices[index_name][instrument_type] += 1
                    if len(nfo_sample_instruments[index_name]) < 3:
                        nfo_sample_instruments[index_name].append({
                            'symbol': inst['tradingsymbol'],
                            'type': instrument_type,
                            'strike': inst.get('strike', 0),
                            'expiry': inst.get('expiry', ''),
                            'lot_size': inst.get('lot_size', 0)
                        })

            print(f"\n📈 NFO Indices found ({len(nfo_indices)}):")
            print("-" * 80)
            for index_name, counts in sorted(nfo_indices.items()):
                total = counts['FUT'] + counts['CE'] + counts['PE']
                if total > 10:  # Only show indices with significant F&O activity
                    print(f"   {index_name:20} | FUT: {counts['FUT']:3d} | CE: {counts['CE']:4d} | PE: {counts['PE']:4d} | Total: {total:4d}")

                    # Show sample instruments
                    if nfo_sample_instruments[index_name]:
                        print(f"      Sample: {nfo_sample_instruments[index_name][0]['symbol']} (Lot: {nfo_sample_instruments[index_name][0]['lot_size']})")

        except Exception as e:
            print(f"❌ Error fetching NFO instruments: {e}")
            nfo_instruments = []

        # Check BFO instruments
        print(f"\n📊 Checking BSE F&O (BFO) instruments...")
        try:
            bfo_instruments = system.data_provider.kite.instruments("BFO")
            print(f"✅ Retrieved {len(bfo_instruments)} BFO instruments")

            # Analyze BFO instruments
            bfo_indices = defaultdict(lambda: {'FUT': 0, 'CE': 0, 'PE': 0})
            bfo_sample_instruments = defaultdict(list)

            for inst in bfo_instruments:
                index_name = inst.get('name', '')
                instrument_type = inst.get('instrument_type', '')
                exchange = inst.get('exchange', 'BSE')

                if instrument_type in ['FUT', 'CE', 'PE']:
                    bfo_indices[index_name][instrument_type] += 1
                    if len(bfo_sample_instruments[index_name]) < 3:
                        bfo_sample_instruments[index_name].append({
                            'symbol': inst['tradingsymbol'],
                            'type': instrument_type,
                            'strike': inst.get('strike', 0),
                            'expiry': inst.get('expiry', ''),
                            'lot_size': inst.get('lot_size', 0)
                        })

            print(f"\n📊 BFO Indices found ({len(bfo_indices)}):")
            print("-" * 80)
            for index_name, counts in sorted(bfo_indices.items()):
                total = counts['FUT'] + counts['CE'] + counts['PE']
                if total > 5:  # Show all BFO indices with any F&O activity
                    print(f"   {index_name:20} | FUT: {counts['FUT']:3d} | CE: {counts['CE']:4d} | PE: {counts['PE']:4d} | Total: {total:4d}")

                    # Show sample instruments
                    if bfo_sample_instruments[index_name]:
                        print(f"      Sample: {bfo_sample_instruments[index_name][0]['symbol']} (Lot: {bfo_sample_instruments[index_name][0]['lot_size']})")

        except Exception as e:
            print(f"❌ Error fetching BFO instruments: {e}")
            print(f"   This might mean BFO is not available or not supported")
            bfo_instruments = []
            bfo_indices = {}

        # Check for commodities and currencies
        print(f"\n🏭 Checking for Commodity instruments...")
        try:
            # Commodities might be in MCX segment
            mcx_instruments = []
            try:
                mcx_instruments = system.data_provider.kite.instruments("MCX")
                print(f"✅ Retrieved {len(mcx_instruments)} MCX instruments")

                # Sample MCX instruments
                mcx_sample = mcx_instruments[:10] if mcx_instruments else []
                for inst in mcx_sample:
                    print(f"   MCX Sample: {inst['tradingsymbol']} | Type: {inst.get('instrument_type', 'N/A')} | Lot: {inst.get('lot_size', 0)}")

            except Exception as e:
                print(f"❌ MCX instruments not available: {e}")

        except Exception as e:
            print(f"❌ Error checking commodity instruments: {e}")

        # Summary
        print(f"\n📋 SUMMARY:")
        print("=" * 80)
        print(f"✅ NFO (NSE F&O): {len(nfo_instruments)} total instruments")
        print(f"   • Indices with F&O: {len([k for k, v in nfo_indices.items() if sum(v.values()) > 10])}")
        print(f"✅ BFO (BSE F&O): {len(bfo_instruments)} total instruments")
        print(f"   • Indices with F&O: {len([k for k, v in bfo_indices.items() if sum(v.values()) > 5])}")

        # List actually available major indices
        major_indices = []
        for index_name, counts in nfo_indices.items():
            if sum(counts.values()) > 50:  # Major indices
                major_indices.append(f"{index_name} (NSE)")

        for index_name, counts in bfo_indices.items():
            if sum(counts.values()) > 10:  # Major BSE indices
                major_indices.append(f"{index_name} (BSE)")

        print(f"\n🎯 Major F&O Indices Actually Available:")
        print("-" * 50)
        for idx in sorted(major_indices):
            print(f"   ✅ {idx}")

        return True

    except Exception as e:
        print(f"❌ Error during check: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Checking Actual F&O Instrument Availability")
    print(f"📅 Current Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    success = check_actual_instrument_availability()

    if success:
        print("\n✅ Instrument availability check completed!")
        print("📊 Use this data to understand what's actually tradeable")
    else:
        print("\n❌ Failed to check instrument availability")

    print("\n" + "=" * 80)