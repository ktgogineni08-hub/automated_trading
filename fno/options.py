#!/usr/bin/env python3
"""
Option Contracts and Option Chains
Option contract modeling and option chain analysis
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
import math

logger = logging.getLogger('trading_system.fno.options')


class OptionContract:
    """Represents an individual option contract"""

    def __init__(self, symbol: str, strike_price: float, expiry_date: str,
                 option_type: str, underlying: str, lot_size: int):
        self.symbol = symbol
        self.strike_price = strike_price
        self.expiry_date = expiry_date
        self.option_type = option_type.upper()  # 'CE' or 'PE'
        self.underlying = underlying
        self.lot_size = lot_size

        # Market data
        self.last_price = 0.0
        self.open_interest = 0
        self.change_in_oi = 0
        self.volume = 0
        self.implied_volatility = 0.0
        self.delta = 0.0
        self.gamma = 0.0
        self.theta = 0.0
        self.vega = 0.0
        self.rho = 0.0

        # Calculated metrics
        self.intrinsic_value = 0.0
        self.time_value = 0.0
        self.moneyness = 0.0  # ATM=0, ITM>0, OTM<0

    def calculate_greeks(self, spot_price: float, time_to_expiry: float,
                        volatility: float, risk_free_rate: float = 0.06):
        """Calculate option Greeks using Black-Scholes model without SciPy dependency"""
        try:
            S = max(1e-9, float(spot_price))
            K = max(1e-9, float(self.strike_price))
            T = float(time_to_expiry)
            r = float(risk_free_rate)
            sigma = float(volatility) / 100.0  # Convert percentage to decimal

            if T <= 0 or sigma <= 0:
                return

            # Standard normal PDF and CDF using math.erf
            def _norm_pdf(x: float) -> float:
                return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

            def _norm_cdf(x: float) -> float:
                return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

            d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)

            if self.option_type == 'CE':  # Call option
                self.delta = _norm_cdf(d1)
                self.gamma = _norm_pdf(d1) / (S * sigma * math.sqrt(T))
                self.theta = (
                    -S * _norm_pdf(d1) * sigma / (2 * math.sqrt(T))
                    - r * K * math.exp(-r * T) * _norm_cdf(d2)
                ) / 365.0
                self.vega = S * math.sqrt(T) * _norm_pdf(d1) / 100.0
                self.rho = K * T * math.exp(-r * T) * _norm_cdf(d2) / 100.0
            else:  # Put option
                self.delta = -_norm_cdf(-d1)
                self.gamma = _norm_pdf(d1) / (S * sigma * math.sqrt(T))
                self.theta = (
                    -S * _norm_pdf(d1) * sigma / (2 * math.sqrt(T))
                    + r * K * math.exp(-r * T) * _norm_cdf(-d2)
                ) / 365.0
                self.vega = S * math.sqrt(T) * _norm_pdf(d1) / 100.0
                self.rho = -K * T * math.exp(-r * T) * _norm_cdf(-d2) / 100.0

        except Exception as e:
            logger.error(f"Error calculating Greeks for {self.symbol}: {e}")

    def calculate_moneyness(self, spot_price: float):
        """Calculate moneyness of the option"""
        if self.option_type == 'CE':
            self.moneyness = (spot_price - self.strike_price) / self.strike_price
        else:
            self.moneyness = (self.strike_price - spot_price) / self.strike_price

    def update_intrinsic_value(self, spot_price: float):
        """Update intrinsic and time value"""
        if self.option_type == 'CE':
            self.intrinsic_value = max(0, spot_price - self.strike_price)
        else:
            self.intrinsic_value = max(0, self.strike_price - spot_price)

        self.time_value = max(0, self.last_price - self.intrinsic_value)

    def is_atm(self, tolerance: float = 0.02) -> bool:
        """Check if option is at-the-money"""
        return abs(self.moneyness) <= tolerance

    def is_itm(self) -> bool:
        """Check if option is in-the-money"""
        return self.moneyness > 0

    def is_otm(self) -> bool:
        """Check if option is out-of-the-money"""
        return self.moneyness < 0

    def __str__(self):
        return f"{self.symbol} {self.strike_price} {self.option_type} @ {self.last_price:.2f}"

class OptionChain:
    """Represents an option chain for a specific expiry"""

    def __init__(self, underlying: str, expiry_date: str, lot_size: int, is_mock: bool = False):
        self.underlying = underlying
        self.expiry_date = expiry_date
        self.lot_size = lot_size
        self.calls: Dict[float, OptionContract] = {}
        self.puts: Dict[float, OptionContract] = {}
        self.spot_price = 0.0
        self.timestamp = datetime.now()
        self.is_mock = is_mock

    def add_option(self, option: OptionContract):
        """Add an option to the chain"""
        if option.option_type == 'CE':
            self.calls[option.strike_price] = option
        else:
            self.puts[option.strike_price] = option

    def get_atm_strike(self, spot_price: float = None) -> float:
        """Get ATM strike price"""
        spot = spot_price or self.spot_price
        if not spot:
            return 0.0

        # Find closest strike to ATM
        all_strikes = sorted(list(self.calls.keys()) + list(self.puts.keys()))
        if not all_strikes:
            # If chain is empty, approximate ATM by rounding spot to nearest 50
            # This avoids min() on empty sequence during early construction
            try:
                return float(int(round(spot / 50.0) * 50))
            except Exception:
                return float(spot)
        return min(all_strikes, key=lambda x: abs(x - spot))

    def get_strikes_around_spot(self, spot_price: float, num_strikes: int = 5) -> List[float]:
        """Get strikes around spot price"""
        all_strikes = sorted(list(self.calls.keys()) + list(self.puts.keys()))
        spot = spot_price or self.spot_price

        if not all_strikes:
            return []

        # Find the index closest to spot
        closest_idx = min(range(len(all_strikes)), key=lambda i: abs(all_strikes[i] - spot))

        # Get strikes around the closest one
        start_idx = max(0, closest_idx - num_strikes // 2)
        end_idx = min(len(all_strikes), start_idx + num_strikes)

        return all_strikes[start_idx:end_idx]

    def calculate_max_pain(self) -> float:
        """Calculate max pain point for the option chain"""
        all_strikes = sorted(list(self.calls.keys()) + list(self.puts.keys()))

        if not all_strikes:
            return 0.0

        max_pain = 0
        min_pain = float('inf')

        for strike in all_strikes:
            total_pain = 0

            # Calculate pain for calls
            for call_strike, call in self.calls.items():
                if call_strike >= strike:
                    total_pain += call.open_interest * (call_strike - strike)
                else:
                    total_pain += call.open_interest * (strike - call_strike)

            # Calculate pain for puts
            for put_strike, put in self.puts.items():
                if put_strike <= strike:
                    total_pain += put.open_interest * (strike - put_strike)
                else:
                    total_pain += put.open_interest * (put_strike - strike)

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain = strike

        return max_pain

    def get_high_oi_strikes(self, top_n: int = 5) -> List[Tuple[float, int]]:
        """Get strikes with highest open interest"""
        strike_oi = []

        for strike, option in self.calls.items():
            strike_oi.append((strike, option.open_interest, 'CE'))

        for strike, option in self.puts.items():
            strike_oi.append((strike, option.open_interest, 'PE'))

        # Sort by OI and return top N
        strike_oi.sort(key=lambda x: x[1], reverse=True)
        return [(strike, oi) for strike, oi, _ in strike_oi[:top_n]]

    def get_high_volume_strikes(self, top_n: int = 5) -> List[Tuple[float, int]]:
        """Get strikes with highest volume"""
        strike_vol = []

        for strike, option in self.calls.items():
            strike_vol.append((strike, option.volume, 'CE'))

        for strike, option in self.puts.items():
            strike_vol.append((strike, option.volume, 'PE'))

        # Sort by volume and return top N
        strike_vol.sort(key=lambda x: x[1], reverse=True)
        return [(strike, vol) for strike, vol, _ in strike_vol[:top_n]]
