import json
from pathlib import Path
from datetime import datetime

from utilities.state_managers import TradingStateManager


def test_save_and_load_state(tmp_path: Path):
    manager = TradingStateManager(base_dir=tmp_path)
    state = {
        'trading_day': '2025-01-10',
        'last_update': datetime(2025, 1, 10, 9, 0, 0),
        'portfolio': {
            'cash': 500000.0,
            'positions': {
                'NIFTY': {
                    'shares': 10,
                    'entry_price': 100.0,
                    'entry_time': datetime(2025, 1, 9, 15, 0, 0)
                }
            }
        }
    }

    manager.save_state(state)
    loaded = manager.load_state()

    assert loaded['trading_day'] == '2025-01-10'
    assert loaded['portfolio']['cash'] == 500000.0
    assert loaded['portfolio']['positions']['NIFTY']['shares'] == 10
    assert loaded['portfolio']['positions']['NIFTY']['entry_price'] == 100.0


def test_archive_and_logs(tmp_path: Path):
    manager = TradingStateManager(base_dir=tmp_path)

    manager.archive_state({'trading_day': '2025-02-20', 'created_at': datetime(2025, 2, 20, 15, 30, 0)})
    archive_file = manager.archive_dir / 'state_2025-02-20.json'
    assert archive_file.exists()

    trade = {'symbol': 'NIFTY', 'qty': 5, 'timestamp': datetime(2025, 2, 20, 11, 0, 0)}
    manager.log_trade(trade, trading_day='2025-02-20')
    trades_file = manager.trades_dir / 'trades_2025-02-20.jsonl'
    with trades_file.open() as f:
        entry = json.loads(f.readline())
    assert entry['symbol'] == 'NIFTY'
    assert entry['qty'] == 5

    summary = {'pnl': 1234.56, 'trades': 3}
    manager.write_daily_summary('2025-02-20', summary)
    summary_file = manager.archive_dir / 'summary_2025-02-20.json'
    data = json.loads(summary_file.read_text())
    assert data['pnl'] == summary['pnl']
    assert data['trades'] == summary['trades']
