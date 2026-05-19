#!/usr/bin/env python3
"""
check_binance.py — Fetch Binance global account positions and balance.

Usage:
    python3 check_binance.py [--futures]

Outputs JSON:
    {
        "balance_usdt": 12345.67,
        "spot": {"BTC": 0.5, "ETH": 2.0, ...},
        "futures_positions": [...],
    }

Requires env vars: BINANCE_API_KEY, BINANCE_API_SECRET
"""

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "platforms", "binance"))

from adapter import BinanceExchangeAdapter


def main():
    include_futures = "--futures" in sys.argv

    try:
        adapter = BinanceExchangeAdapter()

        # Spot balances
        spot = adapter.get_balance()

        result = {
            "balance_usdt": adapter.get_total_equity_usdt(),
            "spot": spot,
        }

        # Futures positions (optional)
        if include_futures:
            try:
                result["futures_positions"] = adapter.get_open_positions()
                result["futures_balance_usdt"] = adapter.get_futures_balance()
            except Exception as e:
                result["futures_positions"] = []
                result["futures_error"] = str(e)

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e), "balance_usdt": 0}))
        sys.exit(1)


if __name__ == "__main__":
    main()
