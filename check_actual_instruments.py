#!/usr/bin/env python3
"""Inspect which indices are actually available in Kite F&O segments."""

from collections import defaultdict
from datetime import datetime
from typing import Optional

from kiteconnect import KiteConnect

from config import get_config
from zerodha_token_manager import ZerodhaTokenManager


def get_authenticated_kite(auto_prompt_for_token: bool = True) -> Optional[KiteConnect]:
    """Return an authenticated Kite client or None if authentication fails."""
    cfg = get_config()
    api_key, api_secret = cfg.get_api_credentials()

    if not api_key or not api_secret:
        print("❌ Zerodha API credentials are not configured. Update trading_config.json or set environment variables.")
        return None

    token_file = cfg.get("api.zerodha.token_file")
    manager = ZerodhaTokenManager(api_key, api_secret, token_file=token_file)

    cached_token = None
    if manager.fernet:
        cached_token = manager.load_tokens()
        if cached_token:
            try:
                manager.kite.set_access_token(cached_token)
                manager.kite.profile()  # Quick validation that the token still works
                print("✅ Using cached Zerodha access token")
                return manager.kite
            except Exception as exc:
                print(f"⚠️ Cached token is invalid: {exc}. Trying to obtain a fresh token...")
    elif manager.token_file.exists():
        print("⚠️ ZERODHA_TOKEN_KEY not set; cached token cannot be decrypted.")

    if not auto_prompt_for_token:
        print("ℹ️ Run `python zerodha_token_manager.py` to generate a fresh token, then re-run this script.")
        return None

    try:
        fresh_token = manager.get_valid_token(auto_use_existing=True)
        if fresh_token:
            print("✅ Obtained new Zerodha access token")
            return manager.kite
    except Exception as exc:
        print(f"❌ Authentication failed: {exc}")

    return None


def check_actual_instrument_availability():
    """Check what's actually available in NFO and BFO."""
    print("🔍 Checking ACTUAL instrument availability in NFO and BFO...")
    print("=" * 80)

    kite = get_authenticated_kite(auto_prompt_for_token=True)
    if not kite:
        print("❌ Unable to continue without a valid Zerodha connection.")
        return False

    try:
        print("✅ Kite connection established")

        # Prepare containers for summaries
        nfo_instruments = []
        bfo_instruments = []
        nfo_indices = defaultdict(lambda: {'FUT': 0, 'CE': 0, 'PE': 0})
        bfo_indices = defaultdict(lambda: {'FUT': 0, 'CE': 0, 'PE': 0})
        nfo_sample_instruments = defaultdict(list)
        bfo_sample_instruments = defaultdict(list)

        # Check NFO instruments
        print("\n📊 Checking NSE F&O (NFO) instruments...")
        try:
            nfo_instruments = kite.instruments("NFO")
            print(f"✅ Retrieved {len(nfo_instruments)} NFO instruments")

            for inst in nfo_instruments:
                index_name = inst.get('name') or 'UNKNOWN'
                instrument_type = inst.get('instrument_type', '')

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
                    if nfo_sample_instruments[index_name]:
                        sample = nfo_sample_instruments[index_name][0]
                        print(f"      Sample: {sample['symbol']} (Lot: {sample['lot_size']})")

        except Exception as exc:
            print(f"❌ Error fetching NFO instruments: {exc}")
            nfo_instruments = []

        # Check BFO instruments
        print(f"\n📊 Checking BSE F&O (BFO) instruments...")
        try:
            bfo_instruments = kite.instruments("BFO")
            print(f"✅ Retrieved {len(bfo_instruments)} BFO instruments")

            for inst in bfo_instruments:
                index_name = inst.get('name') or 'UNKNOWN'
                instrument_type = inst.get('instrument_type', '')

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
                    if bfo_sample_instruments[index_name]:
                        sample = bfo_sample_instruments[index_name][0]
                        print(f"      Sample: {sample['symbol']} (Lot: {sample['lot_size']})")

        except Exception as exc:
            print(f"❌ Error fetching BFO instruments: {exc}")
            print(f"   This might mean BFO is not available or not supported")
            bfo_instruments = []

        # Check for commodities and currencies
        print(f"\n🏭 Checking for Commodity instruments...")
        try:
            mcx_instruments = kite.instruments("MCX")
            print(f"✅ Retrieved {len(mcx_instruments)} MCX instruments")

            mcx_sample = mcx_instruments[:10] if mcx_instruments else []
            for inst in mcx_sample:
                print(f"   MCX Sample: {inst['tradingsymbol']} | Type: {inst.get('instrument_type', 'N/A')} | Lot: {inst.get('lot_size', 0)}")

        except Exception as exc:
            print(f"❌ MCX instruments not available: {exc}")

        # Summary
        print(f"\n📋 SUMMARY:")
        print("=" * 80)

        nfo_index_count = len([k for k, v in nfo_indices.items() if sum(v.values()) > 10])
        bfo_index_count = len([k for k, v in bfo_indices.items() if sum(v.values()) > 5])

        print(f"✅ NFO (NSE F&O): {len(nfo_instruments)} total instruments")
        print(f"   • Indices with F&O: {nfo_index_count}")
        print(f"✅ BFO (BSE F&O): {len(bfo_instruments)} total instruments")
        print(f"   • Indices with F&O: {bfo_index_count}")

        major_indices = []
        for index_name, counts in nfo_indices.items():
            if sum(counts.values()) > 50:
                major_indices.append(f"{index_name} (NSE)")

        for index_name, counts in bfo_indices.items():
            if sum(counts.values()) > 10:
                major_indices.append(f"{index_name} (BSE)")

        print(f"\n🎯 Major F&O Indices Actually Available:")
        print("-" * 50)
        for idx in sorted(major_indices):
            print(f"   ✅ {idx}")

        return True

    except Exception as exc:
        print(f"❌ Error during check: {exc}")
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
