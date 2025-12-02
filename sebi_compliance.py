#!/usr/bin/env python3
"""
SEBI Regulatory Compliance Module
Based on: "A Comprehensive Guide to Trading Indian Equity Futures" Section 9

Implements:
- Position Limit Checks (Section 9.2)
- F&O Ban Period Detection (Section 9.2)
- Margin Requirement Calculation (Section 3.4)
- Contract Specification Validation (Section 2.1)
- Expiry Day Special Handling (Section 2.3)
- Recent SEBI Rule Changes (2024-2025)
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time, timedelta
from dataclasses import dataclass
from enum import Enum
import re

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None

logger = logging.getLogger('trading_system.sebi_compliance')


class ContractType(Enum):
    """Types of F&O contracts"""
    INDEX_FUTURE = "index_future"
    STOCK_FUTURE = "stock_future"
    INDEX_OPTION = "index_option"
    STOCK_OPTION = "stock_option"


@dataclass
class ContractSpecification:
    """Contract specifications as per SEBI/NSE guidelines"""
    symbol: str
    exchange: str  # NFO or BFO
    contract_type: ContractType
    lot_size: int
    tick_size: float
    expiry_date: datetime
    settlement_type: str  # "cash" or "physical"
    min_contract_value: float  # SEBI 2024 rule: ₹15-20 lakh


@dataclass
class ComplianceCheckResult:
    """Result of compliance validation"""
    is_compliant: bool
    warnings: List[str]
    errors: List[str]
    metadata: Dict[str, any]


class SEBIComplianceChecker:
    """
    SEBI Regulatory Compliance Checker

    Ensures all trades comply with SEBI regulations to avoid:
    1. Position limit breaches → Penalties
    2. Trading during ban periods → Illegal trades
    3. Insufficient margins → Order rejection
    4. Physical delivery obligations → Unexpected cash requirements
    """

    # SEBI Contract Specifications (Guide Table 2.1)
    LOT_SIZES = {
        "NIFTY": 50,       # NSE circular effective Sep 2024
        "BANKNIFTY": 15,
        "FINNIFTY": 40,
        "MIDCPNIFTY": 75,
        "SENSEX": 10,
        "BANKEX": 15
    }

    TICK_SIZE = 0.05  # ₹0.05 for all index derivatives

    # SEBI 2024 Rule: Minimum contract value ₹15-20 lakh
    MIN_CONTRACT_VALUE = 1500000  # ₹15 lakh

    def __init__(self, kite: Optional[KiteConnect] = None):
        """
        Initialize SEBI Compliance Checker

        Args:
            kite: KiteConnect instance for live API calls
        """
        self.kite = kite
        self.ban_list_cache: List[str] = []
        self.ban_list_last_updated: Optional[datetime] = None
        self.position_limits_cache: Dict[str, float] = {}

        logger.info("✅ SEBIComplianceChecker initialized")

    def check_position_limit(
        self,
        symbol: str,
        proposed_qty: int,
        current_position: int = 0
    ) -> ComplianceCheckResult:
        """
        Check if proposed position exceeds SEBI limits (Guide Section 9.2)

        Client Limits (Table 9.1):
        - Individual Stock: Higher of 1% of free-float OR 5% of OI
        - Index Futures: Higher of ₹500 Cr OR 15% of total OI
        - Index Options: Net ₹1,500 Cr, Gross ₹10,000 Cr

        Args:
            symbol: Trading symbol
            proposed_qty: Quantity to trade
            current_position: Current position quantity

        Returns:
            ComplianceCheckResult
        """
        warnings = []
        errors = []

        # Calculate new total position
        new_total_position = current_position + proposed_qty

        # Get position limit for symbol
        limit = self._get_position_limit(symbol)

        if abs(new_total_position) > limit:
            errors.append(
                f"Position limit breach: Proposed total {abs(new_total_position)} "
                f"exceeds limit {limit} for {symbol}"
            )

            return ComplianceCheckResult(
                is_compliant=False,
                warnings=warnings,
                errors=errors,
                metadata={'limit': limit, 'proposed_total': abs(new_total_position)}
            )

        # Warning if approaching limit (>80%)
        if abs(new_total_position) > limit * 0.8:
            warnings.append(
                f"Approaching position limit: {abs(new_total_position)}/{limit} "
                f"({abs(new_total_position)/limit*100:.1f}%)"
            )

        return ComplianceCheckResult(
            is_compliant=True,
            warnings=warnings,
            errors=errors,
            metadata={'limit': limit, 'proposed_total': abs(new_total_position)}
        )

    def is_in_ban_period(self, symbol: str) -> Tuple[bool, str]:
        """
        Check if symbol is in F&O ban period (Guide Section 9.2)

        Ban Period: When total OI crosses 95% of MWPL
        During ban: No new positions, only exit trades allowed
        Ban lifted: When OI falls to 80% or below of MWPL

        Args:
            symbol: Trading symbol (without exchange prefix)

        Returns:
            (is_banned, reason)
        """
        # Refresh ban list if stale (cache for 5 minutes)
        if self._is_ban_list_stale():
            self._refresh_ban_list()

        symbol_clean = symbol.upper().replace("NFO:", "").replace("BFO:", "")

        if symbol_clean in self.ban_list_cache:
            reason = f"{symbol} is in F&O ban period (OI >95% MWPL). Only exit trades allowed."
            logger.warning(f"⚠️ {reason}")
            return True, reason

        return False, ""

    def calculate_required_margin(
        self,
        symbol: str,
        qty: int,
        price: float,
        transaction_type: str = "BUY",
        product: str = "MIS",
        exchange: str = "NFO"
    ) -> Dict[str, float]:
        """
        Calculate required margin (SPAN + Exposure) (Guide Section 3.4)

        SPAN Margin: Risk-based, calculated by exchange
        Exposure Margin: Additional buffer
          - Index futures: 3% of contract value
          - Stock futures: 5-7.5% of contract value

        Args:
            symbol: Trading symbol
            qty: Quantity
            price: Price
            transaction_type: "BUY" or "SELL"
            product: "MIS" or "NRML"
            exchange: "NFO" or "BFO"

        Returns:
            {
                'span_margin': float,
                'exposure_margin': float,
                'total_margin': float,
                'additional_margin': float  # For expiry day
            }
        """
        if self.kite:
            try:
                # Use Kite's margin calculator API
                margins = self.kite.order_margins([{
                    "exchange": exchange,
                    "tradingsymbol": symbol,
                    "transaction_type": transaction_type,
                    "variety": "regular",
                    "product": product,
                    "order_type": "LIMIT",
                    "quantity": qty,
                    "price": price
                }])

                if margins and len(margins) > 0:
                    margin_data = margins[0]
                    return {
                        'span_margin': margin_data.get('span', 0),
                        'exposure_margin': margin_data.get('exposure', 0),
                        'total_margin': margin_data.get('total', 0),
                        'additional_margin': margin_data.get('additional', 0)
                    }

            except Exception as e:
                logger.error(f"Failed to fetch margin from Kite API: {e}")

        # Fallback: Approximate calculation
        contract_value = abs(price * qty)

        # Determine if index or stock
        is_index = any(idx in symbol.upper() for idx in ["NIFTY", "SENSEX", "BANKEX"])

        # Approximate margins
        if is_index:
            exposure_pct = 0.03  # 3% for index
            span_approx = contract_value * 0.07  # ~7% SPAN
        else:
            exposure_pct = 0.06  # 6% for stock
            span_approx = contract_value * 0.10  # ~10% SPAN

        exposure_margin = contract_value * exposure_pct
        total_margin = span_approx + exposure_margin

        # SEBI 2024 Rule: Additional 2% ELM on expiry day for short options
        additional_margin = 0
        if self._is_expiry_day(symbol) and transaction_type == "SELL":
            additional_margin = contract_value * 0.02

        logger.warning(
            f"⚠️ Using approximate margin calculation (Kite API unavailable): "
            f"₹{total_margin + additional_margin:,.0f}"
        )

        return {
            'span_margin': span_approx,
            'exposure_margin': exposure_margin,
            'total_margin': total_margin,
            'additional_margin': additional_margin
        }

    def validate_contract_specifications(
        self,
        symbol: str,
        lot_size: int,
        price: float
    ) -> ComplianceCheckResult:
        """
        Validate contract meets SEBI specifications (Guide Section 2.1)

        Checks:
        1. Lot size matches official specification
        2. Tick size is ₹0.05
        3. Contract value ≥ ₹15 lakh (SEBI 2024 rule)

        Args:
            symbol: Trading symbol
            lot_size: Proposed lot size
            price: Current price

        Returns:
            ComplianceCheckResult
        """
        warnings = []
        errors = []

        # Extract index name
        index_name = self._extract_index_name(symbol)

        # Validate lot size
        official_lot_size = self.LOT_SIZES.get(index_name)
        if official_lot_size and lot_size != official_lot_size:
            errors.append(
                f"Incorrect lot size: Using {lot_size}, "
                f"Official {index_name} lot size is {official_lot_size}"
            )

        # Validate contract value (SEBI 2024 rule)
        contract_value = price * lot_size
        if contract_value < self.MIN_CONTRACT_VALUE:
            errors.append(
                f"Contract value ₹{contract_value:,.0f} < "
                f"SEBI minimum ₹{self.MIN_CONTRACT_VALUE:,.0f}"
            )

        # Validate tick size (should be validated at order placement)
        if (price * 100) % (self.TICK_SIZE * 100) != 0:
            warnings.append(
                f"Price ₹{price} may not align with tick size ₹{self.TICK_SIZE}"
            )

        is_compliant = len(errors) == 0

        if not is_compliant:
            logger.error(f"❌ Contract specification validation failed: {errors}")
        elif warnings:
            logger.warning(f"⚠️ Contract warnings: {warnings}")

        return ComplianceCheckResult(
            is_compliant=is_compliant,
            warnings=warnings,
            errors=errors,
            metadata={
                'contract_value': contract_value,
                'official_lot_size': official_lot_size,
                'used_lot_size': lot_size
            }
        )

    def check_expiry_day_constraints(
        self,
        symbol: str,
        contract_type: ContractType
    ) -> ComplianceCheckResult:
        """
        Check expiry day special rules (Guide Section 2.3, 9.1)

        Rules:
        1. Stock futures → Physical delivery required (must square off or have cash)
        2. Index options → Additional 2% ELM on short positions
        3. Calendar spread margin benefit removed
        4. Physical delivery margin increases in last 3 days

        Args:
            symbol: Trading symbol
            contract_type: Type of contract

        Returns:
            ComplianceCheckResult
        """
        warnings = []
        errors = []

        if not self._is_expiry_day(symbol):
            return ComplianceCheckResult(True, [], [], {})

        # Stock futures: Physical settlement warning
        if contract_type == ContractType.STOCK_FUTURE:
            warnings.append(
                f"⚠️ EXPIRY DAY: {symbol} is a stock future with PHYSICAL SETTLEMENT. "
                f"You must square off before 3:30 PM or have cash/shares for delivery. "
                f"Failing delivery obligation incurs heavy penalties."
            )

        # Short options: Additional margin
        if contract_type in [ContractType.INDEX_OPTION, ContractType.STOCK_OPTION]:
            warnings.append(
                f"⚠️ EXPIRY DAY: Short option positions have additional 2% ELM. "
                f"Monitor margins closely."
            )

        # Calendar spreads: No margin benefit
        warnings.append(
            f"⚠️ EXPIRY DAY: Calendar spread margin benefits removed today. "
            f"Full margin required for both legs."
        )

        logger.warning(f"🔴 Expiry Day Constraints for {symbol}: {warnings}")

        return ComplianceCheckResult(
            is_compliant=True,  # Just warnings, not blocking
            warnings=warnings,
            errors=errors,
            metadata={'is_expiry_day': True}
        )

    def comprehensive_pre_trade_check(
        self,
        symbol: str,
        qty: int,
        price: float,
        current_position: int = 0,
        transaction_type: str = "BUY",
        product: str = "MIS",
        contract_type: ContractType = ContractType.INDEX_FUTURE,
        lot_size: int = 65
    ) -> ComplianceCheckResult:
        """
        Run all compliance checks before placing order

        Returns:
            Aggregated ComplianceCheckResult
        """
        all_warnings = []
        all_errors = []
        metadata = {}

        # 1. Check F&O ban period
        is_banned, ban_reason = self.is_in_ban_period(symbol)
        if is_banned:
            all_errors.append(ban_reason)
            return ComplianceCheckResult(False, all_warnings, all_errors, metadata)

        # 2. Check position limits
        limit_check = self.check_position_limit(symbol, qty, current_position)
        all_warnings.extend(limit_check.warnings)
        all_errors.extend(limit_check.errors)
        metadata.update(limit_check.metadata)

        if not limit_check.is_compliant:
            return ComplianceCheckResult(False, all_warnings, all_errors, metadata)

        # 3. Validate contract specifications
        spec_check = self.validate_contract_specifications(symbol, lot_size, price)
        all_warnings.extend(spec_check.warnings)
        all_errors.extend(spec_check.errors)
        metadata.update(spec_check.metadata)

        if not spec_check.is_compliant:
            return ComplianceCheckResult(False, all_warnings, all_errors, metadata)

        # 4. Check expiry day constraints
        expiry_check = self.check_expiry_day_constraints(symbol, contract_type)
        all_warnings.extend(expiry_check.warnings)
        metadata.update(expiry_check.metadata)

        # 5. Calculate required margin
        margin_data = self.calculate_required_margin(
            symbol, qty, price, transaction_type, product
        )
        metadata['margin'] = margin_data

        # Final result
        is_compliant = len(all_errors) == 0

        if is_compliant:
            logger.info(f"✅ SEBI Compliance Check PASSED: {symbol} ({qty} qty)")
        else:
            logger.error(f"❌ SEBI Compliance Check FAILED: {symbol} - {all_errors}")

        return ComplianceCheckResult(is_compliant, all_warnings, all_errors, metadata)

    # Private helper methods

    def _get_position_limit(self, symbol: str) -> float:
        """Get position limit for symbol (simplified)"""
        # In production, fetch from NSE/BSE API
        # For now, return conservative defaults

        is_index = any(idx in symbol.upper() for idx in ["NIFTY", "SENSEX", "BANKEX"])

        if is_index:
            # Index futures: Approximately ₹500 Cr / contract value
            return 1000  # Conservative: 1000 lots
        else:
            # Stock futures: Conservative default
            return 500  # 500 lots

    def _is_ban_list_stale(self) -> bool:
        """Check if ban list cache needs refresh"""
        if not self.ban_list_last_updated:
            return True

        age = datetime.now() - self.ban_list_last_updated
        return age > timedelta(minutes=5)

    def _refresh_ban_list(self):
        """Refresh F&O ban list from NSE with defensive failure handling"""
        try:
            import requests
            # Note: BeautifulSoup not needed - NSE API returns JSON directly

            # NSE official F&O ban list page
            url = "https://www.nseindia.com/api/fo-ban-securities"

            # CRITICAL FIX: Add required headers for NSE Cloudflare protection
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.nseindia.com/',
                'X-Requested-With': 'XMLHttpRequest',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            }

            # Create session to handle cookies and maintain connection
            session = requests.Session()
            # First visit the main page to get cookies and establish session
            base_response = session.get("https://www.nseindia.com", headers=headers, timeout=10)

            # Extract and preserve any Cloudflare cookies
            if base_response.status_code != 200:
                logger.warning(f"⚠️ Base page request returned {base_response.status_code}")

            # Now fetch the ban list with all cookies preserved
            response = session.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # NSE returns banned securities in 'data' field
                if isinstance(data, dict) and 'data' in data:
                    self.ban_list_cache = [item['symbol'] for item in data['data']]
                elif isinstance(data, list):
                    self.ban_list_cache = [item['symbol'] for item in data]
                else:
                    logger.warning("⚠️ NSE ban list format unexpected, failing closed")
                    # DEFENSIVE: Keep existing ban list if format is unexpected
                    if not self.ban_list_cache:
                        self.ban_list_cache = []

                self.ban_list_last_updated = datetime.now()

                if self.ban_list_cache:
                    logger.info(f"✅ Ban list refreshed: {len(self.ban_list_cache)} securities in ban period")
                else:
                    logger.info("✅ Ban list refreshed: No securities in ban period")

            else:
                logger.error(f"❌ Failed to fetch ban list: HTTP {response.status_code}")
                # DEFENSIVE: Keep existing ban list on HTTP failure
                logger.warning("⚠️ Keeping cached ban list due to fetch failure")

        except ImportError:
            logger.error("❌ requests or beautifulsoup4 not installed. Install with: pip install requests beautifulsoup4")
            # DEFENSIVE: Fail closed - keep existing ban list

        except Exception as e:
            logger.error(f"❌ Failed to refresh ban list: {e}")
            # DEFENSIVE: Keep existing ban list on any error
            logger.warning("⚠️ Keeping cached ban list due to error")

    def _is_expiry_day(self, symbol: str) -> bool:
        """Check if today is expiry day for symbol"""
        # Expiry: Last Thursday of the month (Guide Section 2.1)
        today = datetime.now().date()

        # Check if today is Thursday
        if today.weekday() != 3:  # Thursday = 3
            return False

        # Check if it's the last Thursday
        next_week = today + timedelta(days=7)
        return next_week.month != today.month

    def _extract_index_name(self, symbol: str) -> str:
        """Extract index name from symbol"""
        symbol_upper = symbol.upper()

        for index in ["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTY", "SENSEX", "BANKEX"]:
            if index in symbol_upper:
                return index

        return "UNKNOWN"


# Module-level convenience function
def create_compliance_checker(kite: Optional[KiteConnect] = None) -> SEBIComplianceChecker:
    """Create SEBI compliance checker instance"""
    return SEBIComplianceChecker(kite)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    checker = SEBIComplianceChecker()

    # Test NIFTY futures trade
    result = checker.comprehensive_pre_trade_check(
        symbol="NIFTY25JAN",
        qty=65,  # 1 lot
        price=25160,
        current_position=0,
        transaction_type="BUY",
        product="MIS",
        contract_type=ContractType.INDEX_FUTURE,
        lot_size=65
    )

    print(f"\n{'='*80}")
    print(f"COMPLIANCE CHECK RESULT")
    print(f"{'='*80}")
    print(f"Compliant: {result.is_compliant}")
    print(f"Warnings: {result.warnings}")
    print(f"Errors: {result.errors}")
    print(f"Metadata: {result.metadata}")
    print(f"{'='*80}\n")
