#!/usr/bin/env python3
"""
Database Migration Script
Migrates trading system data from JSON files to PostgreSQL
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import execute_values, Json
from decimal import Decimal

class DatabaseMigration:
    """Handles migration from JSON files to PostgreSQL"""
    
    def __init__(self, db_config: Dict[str, str], data_dir: str):
        """
        Initialize migration
        
        Args:
            db_config: Database connection config
            data_dir: Directory containing JSON data files
        """
        self.db_config = db_config
        self.data_dir = Path(data_dir)
        self.conn = None
        self.cursor = None
        
        self.stats = {
            "instruments": 0,
            "positions": 0,
            "orders": 0,
            "trades": 0,
            "signals": 0,
            "audit_logs": 0,
            "errors": []
        }
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 5432),
                database=self.db_config.get("database", "trading_system"),
                user=self.db_config.get("user", "postgres"),
                password=self.db_config.get("password", "")
            )
            self.cursor = self.conn.cursor()
            print("✅ Database connection established")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            sys.exit(1)
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("✅ Database connection closed")
    
    def load_json_file(self, filename: str) -> Optional[Dict]:
        """Load data from JSON file"""
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            print(f"⚠️  File not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            print(f"✅ Loaded {filename}")
            return data
        except Exception as e:
            print(f"❌ Error loading {filename}: {e}")
            self.stats["errors"].append(f"Load error: {filename} - {e}")
            return None
    
    def migrate_instruments(self):
        """Migrate instrument/symbol data"""
        print("\n📊 Migrating instruments...")
        
        # Load NIFTY 50 symbols
        nifty_50 = [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR",
            "ICICIBANK", "HDFC", "KOTAKBANK", "SBIN", "BHARTIARTL",
            "ITC", "AXISBANK", "LT", "ASIANPAINT", "MARUTI",
            "BAJFINANCE", "HCLTECH", "WIPRO", "TITAN", "ULTRACEMCO",
            "NESTLEIND", "BAJAJFINSV", "SUNPHARMA", "ONGC", "NTPC",
            "POWERGRID", "M&M", "TATASTEEL", "TECHM", "DIVISLAB",
            "TATAMOTORS", "INDUSINDBK", "ADANIPORTS", "DRREDDY", "JSWSTEEL",
            "GRASIM", "BRITANNIA", "CIPLA", "EICHERMOT", "HEROMOTOCO",
            "COALINDIA", "SHREECEM", "UPL", "TATACONSUM", "SBILIFE",
            "BAJAJ-AUTO", "HINDALCO", "APOLLOHOSP", "BPCL", "HDFCLIFE"
        ]
        
        instruments_data = []
        for symbol in nifty_50:
            instruments_data.append((
                symbol,
                "NSE",
                "EQUITY",
                f"{symbol} Ltd.",
                1,  # lot_size
                0.05,  # tick_size
                True,  # is_active
                Json({})  # metadata
            ))
        
        # Insert instruments
        insert_query = """
            INSERT INTO instruments (symbol, exchange, instrument_type, name, lot_size, tick_size, is_active, metadata)
            VALUES %s
            ON CONFLICT (symbol) DO UPDATE SET
                exchange = EXCLUDED.exchange,
                instrument_type = EXCLUDED.instrument_type,
                updated_at = CURRENT_TIMESTAMP
        """
        
        try:
            execute_values(self.cursor, insert_query, instruments_data)
            self.conn.commit()
            self.stats["instruments"] = len(instruments_data)
            print(f"✅ Migrated {len(instruments_data)} instruments")
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error migrating instruments: {e}")
            self.stats["errors"].append(f"Instruments migration: {e}")
    
    def migrate_positions(self):
        """Migrate position data"""
        print("\n📊 Migrating positions...")
        
        # Load positions from JSON
        positions_file = self.load_json_file("positions.json")
        if not positions_file:
            print("⚠️  No positions file found, skipping")
            return
        
        positions_data = []
        
        # Handle different JSON structures
        positions = positions_file.get("positions", positions_file)
        if isinstance(positions, list):
            for pos in positions:
                positions_data.append((
                    pos.get("symbol"),
                    pos.get("side", "BUY"),
                    int(pos.get("quantity", 0)),
                    Decimal(str(pos.get("entry_price", 0))),
                    Decimal(str(pos.get("current_price", 0))),
                    Decimal(str(pos.get("stop_loss", 0))) if pos.get("stop_loss") else None,
                    Decimal(str(pos.get("take_profit", 0))) if pos.get("take_profit") else None,
                    Decimal(str(pos.get("pnl", 0))),
                    Decimal(str(pos.get("pnl_percentage", 0))),
                    pos.get("status", "OPEN"),
                    pos.get("strategy"),
                    datetime.fromisoformat(pos.get("entry_time")) if pos.get("entry_time") else datetime.now(),
                    datetime.fromisoformat(pos.get("exit_time")) if pos.get("exit_time") else None,
                    Decimal(str(pos.get("exit_price", 0))) if pos.get("exit_price") else None,
                    pos.get("exit_reason"),
                    Json(pos.get("metadata", {}))
                ))
        
        if positions_data:
            insert_query = """
                INSERT INTO positions (
                    symbol, side, quantity, entry_price, current_price, stop_loss,
                    take_profit, pnl, pnl_percentage, status, strategy, entry_time,
                    exit_time, exit_price, exit_reason, metadata
                ) VALUES %s
                ON CONFLICT DO NOTHING
            """
            
            try:
                execute_values(self.cursor, insert_query, positions_data)
                self.conn.commit()
                self.stats["positions"] = len(positions_data)
                print(f"✅ Migrated {len(positions_data)} positions")
            except Exception as e:
                self.conn.rollback()
                print(f"❌ Error migrating positions: {e}")
                self.stats["errors"].append(f"Positions migration: {e}")
        else:
            print("⚠️  No position data found")
    
    def migrate_orders(self):
        """Migrate order data"""
        print("\n📊 Migrating orders...")
        
        orders_file = self.load_json_file("orders.json")
        if not orders_file:
            print("⚠️  No orders file found, skipping")
            return
        
        orders_data = []
        orders = orders_file.get("orders", orders_file)
        
        if isinstance(orders, list):
            for order in orders:
                orders_data.append((
                    order.get("symbol"),
                    order.get("side", "BUY"),
                    order.get("order_type", "MARKET"),
                    int(order.get("quantity", 0)),
                    Decimal(str(order.get("price", 0))) if order.get("price") else None,
                    Decimal(str(order.get("trigger_price", 0))) if order.get("trigger_price") else None,
                    order.get("status", "PENDING"),
                    order.get("exchange_order_id"),
                    int(order.get("filled_quantity", 0)),
                    Decimal(str(order.get("average_price", 0))) if order.get("average_price") else None,
                    order.get("product"),
                    order.get("validity", "DAY"),
                    datetime.fromisoformat(order.get("placed_at")) if order.get("placed_at") else None,
                    datetime.fromisoformat(order.get("executed_at")) if order.get("executed_at") else None,
                    datetime.fromisoformat(order.get("cancelled_at")) if order.get("cancelled_at") else None,
                    order.get("rejection_reason"),
                    Json(order.get("metadata", {}))
                ))
        
        if orders_data:
            insert_query = """
                INSERT INTO orders (
                    symbol, side, order_type, quantity, price, trigger_price, status,
                    exchange_order_id, filled_quantity, average_price, product, validity,
                    placed_at, executed_at, cancelled_at, rejection_reason, metadata
                ) VALUES %s
                ON CONFLICT DO NOTHING
            """
            
            try:
                execute_values(self.cursor, insert_query, orders_data)
                self.conn.commit()
                self.stats["orders"] = len(orders_data)
                print(f"✅ Migrated {len(orders_data)} orders")
            except Exception as e:
                self.conn.rollback()
                print(f"❌ Error migrating orders: {e}")
                self.stats["errors"].append(f"Orders migration: {e}")
        else:
            print("⚠️  No order data found")
    
    def migrate_trades(self):
        """Migrate trade execution data"""
        print("\n📊 Migrating trades...")
        
        trades_file = self.load_json_file("trades.json")
        if not trades_file:
            print("⚠️  No trades file found, skipping")
            return
        
        trades_data = []
        trades = trades_file.get("trades", trades_file)
        
        if isinstance(trades, list):
            for trade in trades:
                trades_data.append((
                    trade.get("symbol"),
                    trade.get("side", "BUY"),
                    int(trade.get("quantity", 0)),
                    Decimal(str(trade.get("price", 0))),
                    Decimal(str(trade.get("value", 0))),
                    Decimal(str(trade.get("commission", 0))),
                    datetime.fromisoformat(trade.get("executed_at")) if trade.get("executed_at") else datetime.now(),
                    trade.get("exchange_trade_id"),
                    Json(trade.get("metadata", {}))
                ))
        
        if trades_data:
            insert_query = """
                INSERT INTO trades (
                    symbol, side, quantity, price, value, commission,
                    executed_at, exchange_trade_id, metadata
                ) VALUES %s
                ON CONFLICT DO NOTHING
            """
            
            try:
                execute_values(self.cursor, insert_query, trades_data)
                self.conn.commit()
                self.stats["trades"] = len(trades_data)
                print(f"✅ Migrated {len(trades_data)} trades")
            except Exception as e:
                self.conn.rollback()
                print(f"❌ Error migrating trades: {e}")
                self.stats["errors"].append(f"Trades migration: {e}")
        else:
            print("⚠️  No trade data found")
    
    def migrate_all(self):
        """Run full migration"""
        print("\n" + "="*70)
        print("🔄 STARTING DATABASE MIGRATION")
        print("="*70)
        print(f"Data directory: {self.data_dir}")
        print(f"Database: {self.db_config['database']}")
        print(f"Host: {self.db_config['host']}")
        print("="*70 + "\n")
        
        self.connect()
        
        try:
            # Run migrations in order
            self.migrate_instruments()
            self.migrate_positions()
            self.migrate_orders()
            self.migrate_trades()
            
            # Print summary
            self.print_summary()
            
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            self.stats["errors"].append(f"General migration error: {e}")
        finally:
            self.disconnect()
    
    def print_summary(self):
        """Print migration summary"""
        print("\n" + "="*70)
        print("📊 MIGRATION SUMMARY")
        print("="*70)
        print(f"✅ Instruments: {self.stats['instruments']}")
        print(f"✅ Positions: {self.stats['positions']}")
        print(f"✅ Orders: {self.stats['orders']}")
        print(f"✅ Trades: {self.stats['trades']}")
        print(f"✅ Signals: {self.stats['signals']}")
        print(f"✅ Audit Logs: {self.stats['audit_logs']}")
        
        if self.stats["errors"]:
            print(f"\n❌ Errors: {len(self.stats['errors'])}")
            for error in self.stats["errors"]:
                print(f"  - {error}")
        else:
            print("\n✅ No errors encountered")
        
        total_records = sum([
            self.stats['instruments'],
            self.stats['positions'],
            self.stats['orders'],
            self.stats['trades'],
            self.stats['signals'],
            self.stats['audit_logs']
        ])
        
        print(f"\n📈 Total Records Migrated: {total_records}")
        print("="*70 + "\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate trading data to PostgreSQL")
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", type=int, default=5432, help="Database port")
    parser.add_argument("--database", default="trading_system", help="Database name")
    parser.add_argument("--user", default="postgres", help="Database user")
    parser.add_argument("--password", required=True, help="Database password")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    
    args = parser.parse_args()
    
    db_config = {
        "host": args.host,
        "port": args.port,
        "database": args.database,
        "user": args.user,
        "password": args.password
    }
    
    migration = DatabaseMigration(db_config, args.data_dir)
    migration.migrate_all()


if __name__ == "__main__":
    main()
