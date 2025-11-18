#!/usr/bin/env python3
"""
Data Migration Tool
Migrates trading data from CSV/JSON to SQLite database

Usage:
    python data_migration.py --source-dir ./data --backup
"""

import csv
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import shutil
import argparse

from infrastructure.database_manager import (
    TradingDatabase, Trade, Position, StrategyPerformance
)

logger = logging.getLogger('trading_system.migration')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DataMigration:
    """
    Migrate trading data from CSV/JSON files to SQLite database

    Features:
    - Automatic backup of source files
    - Progress tracking
    - Error handling with rollback
    - Validation of migrated data
    - Duplicate detection
    """

    def __init__(self, source_dir: str, db_path: str = "trading_system.db"):
        """
        Initialize migration tool

        Args:
            source_dir: Directory containing CSV/JSON files
            db_path: Target database path
        """
        self.source_dir = Path(source_dir)
        self.db = TradingDatabase(db_path)

        self.stats = {
            'trades_migrated': 0,
            'positions_migrated': 0,
            'errors': 0,
            'duplicates_skipped': 0
        }

    def backup_source_files(self, backup_dir: str = "data_backup"):
        """
        Create backup of source files before migration

        Args:
            backup_dir: Directory for backups
        """
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = backup_path / f"backup_{timestamp}"

        try:
            shutil.copytree(self.source_dir, backup_subdir)
            logger.info(f"✅ Backup created: {backup_subdir}")
            return True
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return False

    def migrate_trades_csv(self, csv_file: Path) -> int:
        """
        Migrate trades from CSV file

        Expected CSV format:
        trade_id,timestamp,symbol,action,quantity,price,fees,strategy,confidence,pnl

        Args:
            csv_file: Path to trades CSV file

        Returns:
            Number of trades migrated
        """
        if not csv_file.exists():
            logger.warning(f"Trades CSV not found: {csv_file}")
            return 0

        migrated = 0

        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        trade = Trade(
                            trade_id=row['trade_id'],
                            timestamp=datetime.fromisoformat(row['timestamp']),
                            symbol=row['symbol'],
                            action=row['action'],
                            quantity=int(row['quantity']),
                            price=float(row['price']),
                            fees=float(row.get('fees', 0)),
                            strategy=row.get('strategy', 'Unknown'),
                            confidence=float(row.get('confidence', 0)),
                            pnl=float(row['pnl']) if row.get('pnl') else None,
                            tags=row.get('tags')
                        )

                        if self.db.insert_trade(trade):
                            migrated += 1
                        else:
                            self.stats['duplicates_skipped'] += 1

                    except Exception as e:
                        logger.error(f"Error migrating trade row: {row}, error: {e}")
                        self.stats['errors'] += 1

            logger.info(f"✅ Migrated {migrated} trades from {csv_file.name}")

        except Exception as e:
            logger.error(f"❌ Failed to migrate trades from {csv_file}: {e}")

        return migrated

    def migrate_positions_json(self, json_file: Path) -> int:
        """
        Migrate positions from JSON file

        Expected JSON format:
        {
            "positions": [
                {
                    "position_id": "...",
                    "symbol": "...",
                    ...
                }
            ]
        }

        Args:
            json_file: Path to positions JSON file

        Returns:
            Number of positions migrated
        """
        if not json_file.exists():
            logger.warning(f"Positions JSON not found: {json_file}")
            return 0

        migrated = 0

        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            positions_data = data.get('positions', [])

            for pos_data in positions_data:
                try:
                    position = Position(
                        position_id=pos_data['position_id'],
                        symbol=pos_data['symbol'],
                        quantity=int(pos_data['quantity']),
                        entry_price=float(pos_data['entry_price']),
                        current_price=float(pos_data.get('current_price', pos_data['entry_price'])),
                        entry_timestamp=datetime.fromisoformat(pos_data['entry_timestamp']),
                        last_updated=datetime.fromisoformat(pos_data.get('last_updated', pos_data['entry_timestamp'])),
                        strategy=pos_data.get('strategy', 'Unknown'),
                        unrealized_pnl=float(pos_data.get('unrealized_pnl', 0)),
                        status=pos_data.get('status', 'OPEN')
                    )

                    if self.db.upsert_position(position):
                        migrated += 1

                except Exception as e:
                    logger.error(f"Error migrating position: {pos_data}, error: {e}")
                    self.stats['errors'] += 1

            logger.info(f"✅ Migrated {migrated} positions from {json_file.name}")

        except Exception as e:
            logger.error(f"❌ Failed to migrate positions from {json_file}: {e}")

        return migrated

    def migrate_strategy_performance_json(self, json_file: Path) -> int:
        """Migrate strategy performance from JSON"""
        if not json_file.exists():
            logger.warning(f"Strategy performance JSON not found: {json_file}")
            return 0

        migrated = 0

        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            strategies = data.get('strategies', {})

            for strategy_name, metrics in strategies.items():
                try:
                    perf = StrategyPerformance(
                        strategy_name=strategy_name,
                        total_trades=int(metrics.get('total_trades', 0)),
                        winning_trades=int(metrics.get('winning_trades', 0)),
                        losing_trades=int(metrics.get('losing_trades', 0)),
                        total_pnl=float(metrics.get('total_pnl', 0)),
                        win_rate=float(metrics.get('win_rate', 0)),
                        avg_profit=float(metrics.get('avg_profit', 0)),
                        avg_loss=float(metrics.get('avg_loss', 0)),
                        sharpe_ratio=float(metrics['sharpe_ratio']) if metrics.get('sharpe_ratio') else None,
                        max_drawdown=float(metrics.get('max_drawdown', 0)),
                        last_updated=datetime.now()
                    )

                    if self.db.update_strategy_performance(perf):
                        migrated += 1

                except Exception as e:
                    logger.error(f"Error migrating strategy performance: {strategy_name}, error: {e}")
                    self.stats['errors'] += 1

            logger.info(f"✅ Migrated {migrated} strategy performance records")

        except Exception as e:
            logger.error(f"❌ Failed to migrate strategy performance: {e}")

        return migrated

    def run_migration(self, create_backup: bool = True) -> Dict[str, int]:
        """
        Run complete migration process

        Args:
            create_backup: Whether to backup source files

        Returns:
            Migration statistics
        """
        logger.info("🚀 Starting data migration...")

        # Create backup if requested
        if create_backup:
            if not self.backup_source_files():
                logger.error("❌ Backup failed - aborting migration")
                return self.stats

        # Migrate trades
        trades_csv = self.source_dir / "trades.csv"
        trade_history_csv = self.source_dir / "trade_history.csv"

        if trades_csv.exists():
            self.stats['trades_migrated'] += self.migrate_trades_csv(trades_csv)

        if trade_history_csv.exists():
            self.stats['trades_migrated'] += self.migrate_trades_csv(trade_history_csv)

        # Migrate positions
        positions_json = self.source_dir / "positions.json"
        state_json = self.source_dir / "state" / "current_state.json"

        if positions_json.exists():
            self.stats['positions_migrated'] += self.migrate_positions_json(positions_json)

        if state_json.exists():
            self.stats['positions_migrated'] += self.migrate_positions_json(state_json)

        # Migrate strategy performance
        strategy_perf_json = self.source_dir / "strategy_performance.json"
        if strategy_perf_json.exists():
            self.migrate_strategy_performance_json(strategy_perf_json)

        # Get database statistics
        db_stats = self.db.get_statistics()

        logger.info("\n" + "="*70)
        logger.info("📊 MIGRATION COMPLETE")
        logger.info("="*70)
        logger.info(f"Trades migrated:      {self.stats['trades_migrated']:,}")
        logger.info(f"Positions migrated:   {self.stats['positions_migrated']:,}")
        logger.info(f"Duplicates skipped:   {self.stats['duplicates_skipped']:,}")
        logger.info(f"Errors:               {self.stats['errors']:,}")
        logger.info(f"\nDatabase total trades: {db_stats['total_trades']:,}")
        logger.info(f"Database total PnL:    ₹{db_stats['total_realized_pnl']:,.2f}")
        logger.info(f"Database size:         {db_stats['db_size_mb']:.2f} MB")
        logger.info("="*70)

        return self.stats

    def validate_migration(self, source_csv: Path) -> bool:
        """
        Validate migration by comparing source and database counts

        Args:
            source_csv: Source CSV file to validate against

        Returns:
            True if validation passes
        """
        if not source_csv.exists():
            logger.warning(f"Source file not found for validation: {source_csv}")
            return False

        # Count rows in CSV
        with open(source_csv, 'r') as f:
            csv_count = sum(1 for _ in csv.DictReader(f))

        # Count rows in database
        db_stats = self.db.get_statistics()
        db_count = db_stats['total_trades']

        logger.info(f"Validation: CSV={csv_count}, DB={db_count}")

        if csv_count == db_count:
            logger.info("✅ Validation passed: Counts match")
            return True
        else:
            logger.warning(f"⚠️  Validation warning: CSV={csv_count} vs DB={db_count}")
            return False


def main():
    """Main migration script"""
    parser = argparse.ArgumentParser(description='Migrate trading data from CSV/JSON to SQLite')
    parser.add_argument('--source-dir', default='./data', help='Source directory with CSV/JSON files')
    parser.add_argument('--db-path', default='trading_system.db', help='Target database path')
    parser.add_argument('--backup', action='store_true', help='Create backup before migration')
    parser.add_argument('--validate', action='store_true', help='Validate migration after completion')

    args = parser.parse_args()

    migration = DataMigration(args.source_dir, args.db_path)

    # Run migration
    stats = migration.run_migration(create_backup=args.backup)

    # Validate if requested
    if args.validate:
        trades_csv = Path(args.source_dir) / "trades.csv"
        migration.validate_migration(trades_csv)

    # Exit code based on errors
    if stats['errors'] > 0:
        logger.error(f"❌ Migration completed with {stats['errors']} errors")
        exit(1)
    else:
        logger.info("✅ Migration completed successfully")
        exit(0)


if __name__ == "__main__":
    main()
