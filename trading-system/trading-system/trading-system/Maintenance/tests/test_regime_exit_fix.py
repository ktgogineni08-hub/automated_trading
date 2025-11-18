#!/usr/bin/env python3
"""Test regime exit fix"""
import sys
sys.path.insert(0, '/Users/gogineni/Python/trading-system')

from enhanced_trading_system_complete import EnhancedSignalAggregator

print("Testing Regime Filter Exit Fix...")
print("=" * 60)

aggregator = EnhancedSignalAggregator(min_agreement=0.3)
aggregator.market_bias = 'bullish'

# Create sell signals
sell_signals = [
    {'signal': -1, 'strength': 0.8, 'reason': 'Take profit'},
    {'signal': -1, 'strength': 0.7, 'reason': 'RSI overbought'}
]

# Test 1: Exit should be allowed (is_exit=True)
print("\n1. Testing sell exit during bullish regime (is_exit=True):")
result = aggregator.aggregate_signals(sell_signals, 'RELIANCE', is_exit=True)
print(f"   Result: {result['action']}")
if result['action'] == 'sell':
    print("   ✅ PASS: Exit allowed!")
else:
    print("   ❌ FAIL: Exit blocked!")

# Test 2: New entry should be blocked (is_exit=False)
print("\n2. Testing sell entry during bullish regime (is_exit=False):")
result = aggregator.aggregate_signals(sell_signals, 'RELIANCE', is_exit=False)
print(f"   Result: {result['action']}")
if result['action'] == 'hold':
    print("   ✅ PASS: Entry blocked as expected!")
else:
    print("   ❌ FAIL: Entry should be blocked!")

print("\n" + "=" * 60)
print("✅ Test complete!")
