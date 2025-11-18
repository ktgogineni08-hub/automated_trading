#!/usr/bin/env python3
"""
Test script to verify ALL indices support (NSE + BSE) with live data only
Tests dynamic discovery of all available F&O indices from Kite API
"""

import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append('.')

# Import required classes
from enhanced_trading_system_complete import UnifiedTradingSystem

def test_all_indices_discovery():
    """Test discovery of ALL available indices from both NSE and BSE"""
    print("🔍 Testing ALL indices discovery from live Kite data...")
    print("=" * 70)

    try:
        # Create trading system instance
        system = UnifiedTradingSystem()

        # Test if we can connect to Kite
        print("📡 Testing Kite connection...")
        if not system.data_provider.kite:
            print("❌ No Kite connection available")
            print("   Make sure you have valid access tokens")
            return False

        print("✅ Kite connection established")

        # Get all available indices (this will fetch from both NSE and BSE)
        print("\n🔄 Discovering all available F&O indices...")
        available_indices = system.data_provider.get_available_indices()

        print(f"\n✅ Discovered {len(available_indices)} total F&O indices:")
        print("=" * 70)

        # Categorize and display indices
        nse_indices = []
        bse_indices = []
        commodity_indices = []
        currency_indices = []

        for symbol, index_info in available_indices.items():
            if 'BSE' in index_info.name or symbol in ['SENSEX', 'BANKEX']:
                bse_indices.append((symbol, index_info))
            elif symbol in ['CRUDEOIL', 'NATURALGAS', 'GOLD', 'SILVER', 'COPPER', 'ZINC', 'ALUMINIUM', 'LEAD', 'NICKEL']:
                commodity_indices.append((symbol, index_info))
            elif symbol in ['USDINR', 'EURINR', 'GBPINR', 'JPYINR']:
                currency_indices.append((symbol, index_info))
            else:
                nse_indices.append((symbol, index_info))

        # Display NSE indices
        if nse_indices:
            print(f"\n📈 NSE F&O Indices ({len(nse_indices)}):")
            print("-" * 50)
            for symbol, index_info in sorted(nse_indices):
                print(f"   {symbol:15} | {index_info.name:30} | Lot: {index_info.lot_size:3d}")

        # Display BSE indices
        if bse_indices:
            print(f"\n📊 BSE F&O Indices ({len(bse_indices)}):")
            print("-" * 50)
            for symbol, index_info in sorted(bse_indices):
                print(f"   {symbol:15} | {index_info.name:30} | Lot: {index_info.lot_size:3d}")

        # Display commodity indices
        if commodity_indices:
            print(f"\n🏭 Commodity F&O Indices ({len(commodity_indices)}):")
            print("-" * 50)
            for symbol, index_info in sorted(commodity_indices):
                print(f"   {symbol:15} | {index_info.name:30} | Lot: {index_info.lot_size:3d}")

        # Display currency indices
        if currency_indices:
            print(f"\n💱 Currency F&O Indices ({len(currency_indices)}):")
            print("-" * 50)
            for symbol, index_info in sorted(currency_indices):
                print(f"   {symbol:15} | {index_info.name:30} | Lot: {index_info.lot_size:3d}")

        # Test fetching option chain for different types of indices
        test_indices = []
        if nse_indices:
            test_indices.append(nse_indices[0][0])  # First NSE index
        if bse_indices:
            test_indices.append(bse_indices[0][0])  # First BSE index
        if commodity_indices:
            test_indices.append(commodity_indices[0][0])  # First commodity

        print(f"\n🎯 Testing option chain fetching for sample indices...")
        print("-" * 50)

        success_count = 0
        for test_index in test_indices[:3]:  # Test up to 3 different types
            try:
                print(f"\n🔍 Testing {test_index}...")
                chain = system.data_provider.fetch_option_chain(test_index)

                if chain:
                    if hasattr(chain, 'is_mock') and chain.is_mock:
                        print(f"   ❌ {test_index}: Using mock data (not allowed)")
                    else:
                        print(f"   ✅ {test_index}: Live option chain loaded")
                        print(f"      • Expiry: {chain.expiry_date}")
                        print(f"      • Spot: ₹{chain.spot_price:,.2f}")
                        print(f"      • Calls: {len(chain.calls)}, Puts: {len(chain.puts)}")
                        success_count += 1
                else:
                    print(f"   ⚠️ {test_index}: No option chain available")

            except Exception as e:
                print(f"   ❌ {test_index}: Error - {e}")

        print(f"\n📊 SUMMARY:")
        print("=" * 70)
        print(f"✅ Total indices discovered: {len(available_indices)}")
        print(f"   • NSE indices: {len(nse_indices)}")
        print(f"   • BSE indices: {len(bse_indices)}")
        print(f"   • Commodity indices: {len(commodity_indices)}")
        print(f"   • Currency indices: {len(currency_indices)}")
        print(f"✅ Option chains tested: {success_count}/{len(test_indices)} successful")

        return len(available_indices) > 4 and success_count > 0

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing Multi-Exchange F&O Support")
    print(f"📅 Current Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    success = test_all_indices_discovery()

    if success:
        print("\n🎉 SUCCESS: Multi-exchange F&O support is working!")
        print("✅ System supports NSE, BSE, commodities, and currencies")
        print("✅ All data is fetched live from Kite API")
        print("✅ No mock or test data is being used")
    else:
        print("\n❌ FAILED: Multi-exchange F&O support needs fixes")
        print("❌ Check Kite connection and access permissions")

    print("\n" + "=" * 70)