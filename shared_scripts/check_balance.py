#!/usr/bin/env python3
"""
check_balance.py — Query wallet balance for supported platforms.

Usage:
    python3 check_balance.py --platform=okx

Outputs JSON: {"balance": 1234.56}
On error: {"balance": 0, "error": "message"}

Supported platforms:
    okx         — via CCXT (requires OKX_API_KEY, OKX_API_SECRET, OKX_PASSPHRASE)
    robinhood   — via robin_stocks (requires ROBINHOOD_USERNAME, ROBINHOOD_PASSWORD, ROBINHOOD_TOTP_SECRET)
"""

import json
import os
import sys


def fetch_okx_balance():
    """Fetch total account equity from OKX via CCXT."""
    import ccxt

    api_key = os.environ.get("OKX_API_KEY", "")
    api_secret = os.environ.get("OKX_API_SECRET", "")
    passphrase = os.environ.get("OKX_PASSPHRASE", "")
    sandbox = os.environ.get("OKX_SANDBOX", "") == "1"

    if not (api_key and api_secret and passphrase):
        raise ValueError("OKX_API_KEY, OKX_API_SECRET, and OKX_PASSPHRASE env vars required")

    config = {
        "apiKey": api_key,
        "secret": api_secret,
        "password": passphrase,
        "enableRateLimit": True,
    }
    if sandbox:
        config["sandbox"] = True

    exchange = ccxt.okx(config)
    balance = exchange.fetch_balance({"type": "trading"})
    # CCXT returns balance['total']['USDT'] for USDT equity
    total = balance.get("total", {})
    usdt = float(total.get("USDT", 0))
    if usdt > 0:
        return usdt
    # Fallback: check info.totalEq (OKX-specific total equity across all currencies)
    info = balance.get("info", {})
    if isinstance(info, dict):
        details = info.get("data", [{}])
        if details:
            total_eq = float(details[0].get("totalEq", 0))
            if total_eq > 0:
                return total_eq
    return usdt


def fetch_robinhood_balance():
    """Fetch crypto buying power from Robinhood."""
    import robin_stocks.robinhood as rh
    import pyotp

    username = os.environ.get("ROBINHOOD_USERNAME", "")
    password = os.environ.get("ROBINHOOD_PASSWORD", "")
    totp_secret = os.environ.get("ROBINHOOD_TOTP_SECRET", "")

    if not (username and password and totp_secret):
        raise ValueError("ROBINHOOD_USERNAME, ROBINHOOD_PASSWORD, and ROBINHOOD_TOTP_SECRET env vars required")

    totp = pyotp.TOTP(totp_secret).now()
    rh.login(username, password, mfa_code=totp)
    try:
        profile = rh.profiles.load_account_profile()
        # Crypto buying power
        buying_power = float(profile.get("crypto_buying_power", 0))
        if buying_power > 0:
            return buying_power
        # Fallback: portfolio cash
        return float(profile.get("portfolio_cash", 0))
    finally:
        rh.logout()


def fetch_binance_balance():
    """Fetch total equity from Binance global (spot + futures) via CCXT."""
    import ccxt

    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")

    if not (api_key and api_secret):
        raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET env vars required")

    config = {
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
    }

    exchange = ccxt.binance(config)
    balance = exchange.fetch_balance()
    total = balance.get("total", {})

    # Sum all assets converted to USDT
    usdt_total = float(total.get("USDT", 0)) + float(total.get("USDC", 0))

    # Add BTC value
    btc_amount = float(total.get("BTC", 0))
    if btc_amount > 0:
        try:
            ticker = exchange.fetch_ticker("BTC/USDT")
            btc_price = float(ticker.get("last", 0))
            usdt_total += btc_amount * btc_price
        except Exception:
            pass

    # Add ETH value
    eth_amount = float(total.get("ETH", 0))
    if eth_amount > 0:
        try:
            ticker = exchange.fetch_ticker("ETH/USDT")
            eth_price = float(ticker.get("last", 0))
            usdt_total += eth_amount * eth_price
        except Exception:
            pass

    return usdt_total


PLATFORM_FETCHERS = {
    "okx": fetch_okx_balance,
    "robinhood": fetch_robinhood_balance,
    "binance": fetch_binance_balance,
}


def main():
    platform = None
    for arg in sys.argv[1:]:
        if arg.startswith("--platform="):
            platform = arg.split("=", 1)[1]

    if not platform:
        print(json.dumps({"balance": 0, "error": "usage: check_balance.py --platform=<name>"}))
        sys.exit(1)

    fetcher = PLATFORM_FETCHERS.get(platform)
    if not fetcher:
        print(json.dumps({"balance": 0, "error": f"unsupported platform: {platform}"}))
        sys.exit(1)

    try:
        balance = fetcher()
        print(json.dumps({"balance": balance}))
    except Exception as e:
        print(json.dumps({"balance": 0, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
