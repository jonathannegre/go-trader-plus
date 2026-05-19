"""
Binance Global ExchangeAdapter — ccxt wrapper for spot + USDⓈ-M futures trading.
Supports binance.com (global, PSAN-registered in France).
Options methods raise NotImplementedError (can be added later for Binance Options).
"""

import sys
import os as _os
import math
from typing import Tuple, Optional, List

sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', 'shared_tools'))


def _get_ccxt_exchange(authenticated: bool = False):
    """Get a ccxt Binance (global) exchange instance.
    
    When authenticated=True, reads BINANCE_API_KEY and BINANCE_API_SECRET
    from environment. Sub-account API keys work transparently — Binance
    sub-account keys are scoped at creation time.
    """
    import ccxt
    config = {"enableRateLimit": True}
    if authenticated:
        api_key = _os.environ.get("BINANCE_API_KEY", "")
        api_secret = _os.environ.get("BINANCE_API_SECRET", "")
        if not (api_key and api_secret):
            raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET env vars required")
        config["apiKey"] = api_key
        config["secret"] = api_secret
    return ccxt.binance(config)


def _get_futures_exchange(authenticated: bool = False):
    """Get a ccxt Binance instance configured for USDⓈ-M futures."""
    import ccxt
    config = {
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    }
    if authenticated:
        api_key = _os.environ.get("BINANCE_API_KEY", "")
        api_secret = _os.environ.get("BINANCE_API_SECRET", "")
        if not (api_key and api_secret):
            raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET env vars required")
        config["apiKey"] = api_key
        config["secret"] = api_secret
    return ccxt.binance(config)


class BinanceExchangeAdapter:
    """
    ExchangeAdapter for Binance Global (binance.com).
    Supports spot trading and USDⓈ-M perpetual futures.
    """

    @property
    def name(self) -> str:
        return "binance"

    def get_spot_price(self, underlying: str) -> float:
        """Fetch current spot price for underlying via Binance global."""
        exchange = _get_ccxt_exchange()
        for suffix in ("/USDT", "/USDC", "/EUR", "/BUSD"):
            try:
                ticker = exchange.fetch_ticker(underlying + suffix)
                price = ticker.get("last") or 0
                if price and price > 0:
                    return float(price)
            except Exception:
                continue
        return 0.0

    def get_perp_price(self, underlying: str) -> float:
        """Fetch current perpetual futures mark price."""
        exchange = _get_futures_exchange()
        try:
            ticker = exchange.fetch_ticker(underlying + "/USDT:USDT")
            price = ticker.get("last") or 0
            return float(price) if price and price > 0 else 0.0
        except Exception:
            return 0.0

    def get_vol_metrics(self, underlying: str) -> Tuple[float, float]:
        """Compute 14-day historical vol and IV rank from daily OHLCV."""
        try:
            exchange = _get_ccxt_exchange()
            ohlcv = exchange.fetch_ohlcv(underlying + "/USDT", "1d", limit=90)
            if not ohlcv or len(ohlcv) < 15:
                return 0.60, 50.0
            closes = [c[4] for c in ohlcv]
            returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
            if len(returns) < 14:
                return 0.60, 50.0
            w = 14
            mean = sum(returns[-w:]) / w
            variance = sum((r - mean) ** 2 for r in returns[-w:]) / w
            vol = math.sqrt(variance) * math.sqrt(365)

            hvs = []
            for i in range(len(returns) - w + 1):
                chunk = returns[i:i + w]
                m = sum(chunk) / w
                v = sum((r - m) ** 2 for r in chunk) / w
                hvs.append(math.sqrt(v) * math.sqrt(365) * 100)
            current_hv = vol * 100
            hv_min, hv_max = min(hvs), max(hvs)
            if hv_max > hv_min:
                iv_rank = (current_hv - hv_min) / (hv_max - hv_min) * 100
                iv_rank = round(min(max(iv_rank, 0.0), 100.0), 1)
            else:
                iv_rank = 50.0
            return round(vol, 4), iv_rank
        except Exception:
            return 0.60, 50.0

    def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 300) -> List:
        """Fetch OHLCV candles from Binance spot."""
        exchange = _get_ccxt_exchange()
        return exchange.fetch_ohlcv(symbol, interval, limit=limit)

    def get_perp_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 300) -> List:
        """Fetch OHLCV candles from Binance USDⓈ-M futures."""
        exchange = _get_futures_exchange()
        perp_symbol = symbol if ":USDT" in symbol else f"{symbol}:USDT"
        return exchange.fetch_ohlcv(perp_symbol, interval, limit=limit)

    def get_balance(self) -> dict:
        """Fetch spot wallet balance. Returns {asset: free_amount}."""
        exchange = _get_ccxt_exchange(authenticated=True)
        balance = exchange.fetch_balance()
        result = {}
        for asset, amount in balance.get("free", {}).items():
            if float(amount) > 0:
                result[asset] = float(amount)
        return result

    def get_futures_balance(self) -> float:
        """Fetch USDⓈ-M futures account total margin balance in USDT."""
        exchange = _get_futures_exchange(authenticated=True)
        balance = exchange.fetch_balance()
        total = balance.get("total", {})
        return float(total.get("USDT", 0))

    def get_total_equity_usdt(self) -> float:
        """Estimate total equity across spot + futures in USDT."""
        spot = self.get_balance()
        futures_balance = self.get_futures_balance()
        
        # Convert spot holdings to USDT
        exchange = _get_ccxt_exchange()
        total_usdt = spot.get("USDT", 0) + spot.get("USDC", 0)
        
        for asset, amount in spot.items():
            if asset in ("USDT", "USDC", "BUSD"):
                continue
            try:
                ticker = exchange.fetch_ticker(f"{asset}/USDT")
                price = ticker.get("last", 0)
                if price:
                    total_usdt += amount * float(price)
            except Exception:
                continue
        
        return total_usdt + futures_balance

    def get_open_positions(self) -> List[dict]:
        """Fetch open perpetual futures positions."""
        exchange = _get_futures_exchange(authenticated=True)
        positions = exchange.fetch_positions()
        open_positions = []
        for pos in positions:
            size = float(pos.get("contracts", 0))
            if size != 0:
                open_positions.append({
                    "symbol": pos.get("symbol", ""),
                    "side": pos.get("side", ""),
                    "size": size,
                    "entry_price": float(pos.get("entryPrice", 0)),
                    "mark_price": float(pos.get("markPrice", 0)),
                    "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
                    "leverage": int(pos.get("leverage", 1)),
                    "margin_type": pos.get("marginMode", "cross"),
                })
        return open_positions

    def place_spot_order(self, symbol: str, side: str, amount: float,
                         order_type: str = "market", price: float = None) -> dict:
        """Place a spot order. Returns order info dict."""
        exchange = _get_ccxt_exchange(authenticated=True)
        params = {}
        if order_type == "limit" and price:
            order = exchange.create_order(symbol, order_type, side, amount, price, params)
        else:
            order = exchange.create_order(symbol, "market", side, amount, None, params)
        return {
            "id": order.get("id"),
            "status": order.get("status"),
            "filled": order.get("filled"),
            "price": order.get("average") or order.get("price"),
        }

    def place_futures_order(self, symbol: str, side: str, amount: float,
                            order_type: str = "market", price: float = None,
                            reduce_only: bool = False) -> dict:
        """Place a USDⓈ-M futures order. Returns order info dict."""
        exchange = _get_futures_exchange(authenticated=True)
        params = {}
        if reduce_only:
            params["reduceOnly"] = True
        perp_symbol = symbol if ":USDT" in symbol else f"{symbol}:USDT"
        if order_type == "limit" and price:
            order = exchange.create_order(perp_symbol, order_type, side, amount, price, params)
        else:
            order = exchange.create_order(perp_symbol, "market", side, amount, None, params)
        return {
            "id": order.get("id"),
            "status": order.get("status"),
            "filled": order.get("filled"),
            "price": order.get("average") or order.get("price"),
        }

    def get_real_expiry(self, underlying: str, target_dte: int) -> Tuple[str, int]:
        raise NotImplementedError("Binance options not yet implemented in go-trader-plus")

    def get_real_strike(self, underlying: str, expiry: str,
                        option_type: str, target_strike: float) -> float:
        raise NotImplementedError("Binance options not yet implemented in go-trader-plus")

    def get_premium_and_greeks(self, underlying: str, option_type: str,
                                strike: float, expiry: str, dte: float,
                                spot: float, vol: float) -> Tuple[float, float, dict]:
        raise NotImplementedError("Binance options not yet implemented in go-trader-plus")
