#!/usr/bin/env python3
"""
Simple launcher for paper trading that bypasses the menu system
"""
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def run_paper_trading_launcher():
    """Launch paper trading with proper error handling"""
    print("🚀 Starting Paper Trading System directly...")
    print("📝 Mode: Paper Trading (Safe Simulation)")
    print("⚖️ Profile: Balanced")
    print("="*50)

    try:
        # Import the main function from the trading system
        from enhanced_trading_system_complete import run_paper_trading

        # Check if run_paper_trading function exists
        if not hasattr(sys.modules['enhanced_trading_system_complete'], 'run_paper_trading'):
            print("⚠️ run_paper_trading function not found, trying alternative approach...")
            from enhanced_trading_system_complete import main

            # Mock inputs for paper trading
            class MockInput:
                def __init__(self, responses):
                    self.responses = iter(responses)

                def __call__(self, prompt=""):
                    try:
                        response = next(self.responses)
                        print(f"{prompt}{response}")
                        return response
                    except StopIteration:
                        return ""

            # Replace input function to automatically select paper trading
            original_input = input
            mock_responses = [
                "1",    # NIFTY 50 Trading
                "1",    # Paper Trading
                "",     # Default capital
            ]

            input = MockInput(mock_responses)

            try:
                main()
            finally:
                input = original_input  # Restore original input
        else:
            run_paper_trading()

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure enhanced_trading_system_complete.py is in the same directory")
        return 1
    except KeyboardInterrupt:
        print("\n🛑 Paper trading stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(run_paper_trading_launcher())