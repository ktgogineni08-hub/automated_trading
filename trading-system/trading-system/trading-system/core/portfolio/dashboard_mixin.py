#!/usr/bin/env python3
"""Dashboard sync mixin for UnifiedPortfolio."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from safe_file_ops import atomic_write_json
from trading_utils import format_ist_timestamp

logger = logging.getLogger('trading_system.portfolio')


class DashboardSyncMixin:
    def _capture_portfolio_snapshot(self, price_map: Optional[Dict[str, float]] = None) -> Dict:
        price_map = price_map or {}
        positions_snapshot = {}
        for symbol, pos in self.positions.items():
            entry_price = float(pos.get('entry_price', 0.0))
            shares = int(pos.get('shares', 0))
            current_price = float(price_map.get(symbol, entry_price))
            pnl = (current_price - entry_price) * shares
            positions_snapshot[symbol] = {
                'shares': shares,
                'entry_price': entry_price,
                'current_price': current_price,
                'confidence': float(pos.get('confidence', 0.5)),
                'sector': pos.get('sector', 'Other'),
                'strategy': pos.get('strategy', 'unknown'),
                'pnl': pnl,
            }

        total_value = self.calculate_total_value(price_map)
        return {
            'timestamp': format_ist_timestamp(datetime.now()),
            'trading_mode': getattr(self, 'trading_mode', 'paper'),
            'cash': float(getattr(self, 'cash', 0.0)),
            'positions': positions_snapshot,
            'total_value': total_value,
        }

    def save_state_to_files(self, price_map: Optional[Dict[str, float]] = None) -> Dict:
        snapshot = self._capture_portfolio_snapshot(price_map)
        shared_path = Path(self.shared_state_file_path)
        current_path = Path(self.current_state_file_path)
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        current_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(shared_path, snapshot, create_backup=True)
        atomic_write_json(current_path, snapshot, create_backup=True)
        return snapshot

    def send_dashboard_update(self, price_map: Optional[Dict[str, float]] = None):
        snapshot = self.save_state_to_files(price_map)
        dashboard = getattr(self, 'dashboard', None)
        if not dashboard:
            return None

        positions = snapshot['positions']
        total_value = snapshot['total_value']
        initial_cash = float(getattr(self, 'initial_cash', total_value))
        total_pnl = total_value - initial_cash

        dashboard.send_portfolio_update(
            total_value=total_value,
            cash=snapshot['cash'],
            positions_count=len(positions),
            total_pnl=total_pnl,
            positions=positions,
        )

        trades_count = int(getattr(self, 'trades_count', 0))
        winning_trades = int(getattr(self, 'winning_trades', 0))
        win_rate = (winning_trades / trades_count * 100) if trades_count else 0.0

        dashboard.send_performance_update(
            trades_count=trades_count,
            win_rate=win_rate,
            total_pnl=total_pnl,
            best_trade=float(getattr(self, 'best_trade', 0.0)),
            worst_trade=float(getattr(self, 'worst_trade', 0.0)),
        )

        return positions
