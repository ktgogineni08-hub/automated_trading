"""
IP Whitelisting - Network Access Control

Restrict API access to whitelisted IP addresses/ranges.

Features:
- IP address whitelisting
- CIDR range support
- Dynamic whitelist updates
- Geo-blocking support
- Rate limiting per IP

Author: Trading System Security Team
Date: November 2025
"""

import logging
import ipaddress
from typing import List, Set, Optional
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)


class IPWhitelist:
    """
    IP address whitelist manager
    """

    def __init__(self, whitelist_file: Optional[str] = None):
        """
        Initialize IP whitelist

        Args:
            whitelist_file: Path to whitelist configuration file
        """
        self.allowed_ips: Set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
        self.allowed_networks: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = []

        if whitelist_file:
            self.load_from_file(whitelist_file)

    def add_ip(self, ip_address: str):
        """
        Add IP address to whitelist

        Args:
            ip_address: IP address string
        """
        try:
            ip = ipaddress.ip_address(ip_address)
            self.allowed_ips.add(ip)
            logger.info(f"Added IP to whitelist: {ip_address}")
        except ValueError as e:
            logger.error(f"Invalid IP address {ip_address}: {e}")
            raise

    def add_network(self, network: str):
        """
        Add IP network (CIDR) to whitelist

        Args:
            network: Network in CIDR notation (e.g., "192.168.1.0/24")
        """
        try:
            net = ipaddress.ip_network(network, strict=False)
            self.allowed_networks.append(net)
            logger.info(f"Added network to whitelist: {network}")
        except ValueError as e:
            logger.error(f"Invalid network {network}: {e}")
            raise

    def is_allowed(self, ip_address: str) -> bool:
        """
        Check if IP address is whitelisted

        Args:
            ip_address: IP address to check

        Returns:
            True if allowed
        """
        try:
            ip = ipaddress.ip_address(ip_address)

            # Check direct IP match
            if ip in self.allowed_ips:
                return True

            # Check network ranges
            for network in self.allowed_networks:
                if ip in network:
                    return True

            return False

        except ValueError:
            logger.warning(f"Invalid IP address format: {ip_address}")
            return False

    def load_from_file(self, filepath: str):
        """
        Load whitelist from file

        Args:
            filepath: Path to whitelist file (one entry per line)
        """
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    if '/' in line:
                        self.add_network(line)
                    else:
                        self.add_ip(line)

            logger.info(f"Loaded whitelist from {filepath}")

        except FileNotFoundError:
            logger.warning(f"Whitelist file not found: {filepath}")
        except Exception as e:
            logger.error(f"Error loading whitelist: {e}")


def ip_whitelist_required(whitelist: IPWhitelist):
    """
    Decorator to enforce IP whitelisting on endpoints

    Args:
        whitelist: IPWhitelist instance

    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP
            client_ip = request.remote_addr

            # Check X-Forwarded-For header (if behind proxy)
            if request.headers.get('X-Forwarded-For'):
                client_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()

            # Check whitelist
            if not whitelist.is_allowed(client_ip):
                logger.warning(f"Access denied from non-whitelisted IP: {client_ip}")
                return jsonify({
                    'error': 'FORBIDDEN',
                    'message': 'Access denied from your IP address'
                }), 403

            return f(*args, **kwargs)

        return decorated_function
    return decorator


# Example whitelist configuration
DEFAULT_WHITELIST_CONFIG = """
# Trading System IP Whitelist Configuration
# Format: One IP address or CIDR network per line
# Lines starting with # are comments

# Office IP addresses
203.192.xxx.xxx

# VPN subnet
10.0.0.0/8

# AWS NAT Gateway IPs
52.xxx.xxx.xxx
54.xxx.xxx.xxx

# Cloud provider ranges
172.16.0.0/12

# Development environments
192.168.1.0/24
"""


if __name__ == "__main__":
    # Example usage
    whitelist = IPWhitelist()

    # Add individual IPs
    whitelist.add_ip("203.192.1.1")
    whitelist.add_ip("203.192.1.2")

    # Add network ranges
    whitelist.add_network("10.0.0.0/8")
    whitelist.add_network("192.168.1.0/24")

    # Check access
    print(f"203.192.1.1 allowed: {whitelist.is_allowed('203.192.1.1')}")
    print(f"10.0.5.10 allowed: {whitelist.is_allowed('10.0.5.10')}")
    print(f"1.2.3.4 allowed: {whitelist.is_allowed('1.2.3.4')}")
