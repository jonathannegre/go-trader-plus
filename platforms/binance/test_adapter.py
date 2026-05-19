#!/usr/bin/env python3
"""Tests for Binance global adapter — public API only (no auth needed)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "platforms", "binance"))

from adapter import BinanceExchangeAdapter


def test_spot_price():
    adapter = BinanceExchangeAdapter()
    price = adapter.get_spot_price("BTC")
    assert price > 0, f"Expected BTC price > 0, got {price}"
    print(f"✓ BTC spot price: ${price:,.2f}")


def test_perp_price():
    adapter = BinanceExchangeAdapter()
    price = adapter.get_perp_price("BTC")
    assert price > 0, f"Expected BTC perp price > 0, got {price}"
    print(f"✓ BTC perp price: ${price:,.2f}")


def test_vol_metrics():
    adapter = BinanceExchangeAdapter()
    vol, iv_rank = adapter.get_vol_metrics("BTC")
    assert 0 < vol < 5, f"Vol out of range: {vol}"
    assert 0 <= iv_rank <= 100, f"IV rank out of range: {iv_rank}"
    print(f"✓ BTC vol: {vol:.4f}, IV rank: {iv_rank:.1f}")


def test_ohlcv():
    adapter = BinanceExchangeAdapter()
    candles = adapter.get_ohlcv("BTC/USDT", "1h", limit=10)
    assert len(candles) == 10, f"Expected 10 candles, got {len(candles)}"
    print(f"✓ Got {len(candles)} spot candles")


def test_perp_ohlcv():
    adapter = BinanceExchangeAdapter()
    candles = adapter.get_perp_ohlcv("BTC/USDT", "1h", limit=10)
    assert len(candles) == 10, f"Expected 10 candles, got {len(candles)}"
    print(f"✓ Got {len(candles)} futures candles")


if __name__ == "__main__":
    test_spot_price()
    test_perp_price()
    test_vol_metrics()
    test_ohlcv()
    test_perp_ohlcv()
    print("\n✅ All public API tests passed!")
