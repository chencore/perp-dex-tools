import os
import asyncio
from typing import Any, Dict, Optional, List
from datetime import datetime

import aiohttp

DEFAULT_API_URL = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")
DEFAULT_TIMEOUT = int(os.getenv("POLYMARKET_TIMEOUT", "10"))

class PolymarketClient:
    """Client for Polymarket Gamma API to fetch crypto prediction markets."""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or DEFAULT_API_URL).rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()
            self._session = None

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if not self._session:
            raise RuntimeError("Session not initialized. Use 'async with PolymarketClient(...) as c:'")
        url = f"{self.base_url}{path}"
        async with self._session.get(url, params=params or {}) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def fetch_crypto_markets(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetch active crypto prediction markets for the given symbol from Polymarket.
        Returns markets related to price movements (hourly/daily predictions).
        
        Args:
            symbol: Crypto symbol like 'ETH', 'BTC', 'SOL'
        
        Returns:
            List of relevant market data
        """
        # Fetch all markets
        markets = await self._get("/markets")
        
        # Filter for crypto-related markets matching the symbol
        # Look for markets with the symbol in question/title and active status
        symbol_upper = symbol.upper()
        relevant_markets = []
        
        for market in markets:
            if not isinstance(market, dict):
                continue
            
            question = market.get("question", "").upper()
            active = market.get("active", False)
            closed = market.get("closed", True)
            
            # Filter: active, not closed, contains symbol, and likely price-related
            if (active and not closed and 
                symbol_upper in question and
                any(kw in question for kw in ["PRICE", "ABOVE", "BELOW", "REACH", "HIGHER", "LOWER"])):
                relevant_markets.append(market)
        
        return relevant_markets

    @staticmethod
    def analyze_markets(markets: List[Dict[str, Any]], symbol: str) -> Dict[str, Any]:
        """
        Analyze Polymarket crypto markets to generate trading recommendation.
        
        Args:
            markets: List of relevant market data from Polymarket
            symbol: Crypto symbol
        
        Returns:
            {
              'direction': 'buy' | 'sell' | 'neutral',
              'confidence': float in [0,1],
              'signal_strength': 'strong' | 'moderate' | 'weak',
              'markets_analyzed': int,
              'bullish_probability': float,
              'bearish_probability': float,
              'summary': str,
              'markets': list of analyzed markets
            }
        """
        if not markets:
            return {
                "direction": "neutral",
                "confidence": 0.0,
                "signal_strength": "none",
                "markets_analyzed": 0,
                "bullish_probability": 0.5,
                "bearish_probability": 0.5,
                "summary": f"No active prediction markets found for {symbol}",
                "markets": []
            }
        
        bullish_signals = []
        bearish_signals = []
        analyzed = []
        
        for market in markets:
            question = market.get("question", "")
            outcomes = market.get("outcomes", "")
            outcome_prices = market.get("outcomePrices", "")
            
            # Parse outcome prices (format: "0.52,0.48" for YES,NO)
            try:
                if outcome_prices and isinstance(outcome_prices, str):
                    prices = [float(p) for p in outcome_prices.split(",")]
                    yes_price = prices[0] if len(prices) > 0 else 0.5
                else:
                    yes_price = 0.5
            except:
                yes_price = 0.5
            
            # Determine if this is bullish or bearish signal
            question_upper = question.upper()
            is_bullish_question = any(kw in question_upper for kw in ["ABOVE", "HIGHER", "REACH", "EXCEED"])
            is_bearish_question = any(kw in question_upper for kw in ["BELOW", "LOWER", "FALL", "DROP"])
            
            market_info = {
                "question": question,
                "yes_probability": yes_price,
                "no_probability": 1 - yes_price,
                "volume": market.get("volume", "0"),
                "end_date": market.get("endDate", "")
            }
            analyzed.append(market_info)
            
            # Interpret signal
            if is_bullish_question:
                # High YES price = bullish
                bullish_signals.append(yes_price)
                bearish_signals.append(1 - yes_price)
            elif is_bearish_question:
                # High YES price = bearish
                bearish_signals.append(yes_price)
                bullish_signals.append(1 - yes_price)
        
        # Calculate aggregate probabilities
        avg_bullish = sum(bullish_signals) / len(bullish_signals) if bullish_signals else 0.5
        avg_bearish = sum(bearish_signals) / len(bearish_signals) if bearish_signals else 0.5
        
        # Determine direction and confidence
        diff = abs(avg_bullish - avg_bearish)
        
        if avg_bullish > avg_bearish:
            direction = "buy"
            confidence = avg_bullish
        elif avg_bearish > avg_bullish:
            direction = "sell"
            confidence = avg_bearish
        else:
            direction = "neutral"
            confidence = 0.5
        
        # Signal strength based on confidence and difference
        if diff > 0.3 and confidence > 0.7:
            signal_strength = "strong"
        elif diff > 0.15 and confidence > 0.6:
            signal_strength = "moderate"
        else:
            signal_strength = "weak"
        
        summary = f"Analyzed {len(markets)} markets for {symbol}. "
        summary += f"Bullish probability: {avg_bullish:.1%}, Bearish probability: {avg_bearish:.1%}. "
        summary += f"Recommendation: {direction.upper()} with {signal_strength} signal."
        
        return {
            "direction": direction,
            "confidence": round(confidence, 3),
            "signal_strength": signal_strength,
            "markets_analyzed": len(markets),
            "bullish_probability": round(avg_bullish, 3),
            "bearish_probability": round(avg_bearish, 3),
            "summary": summary,
            "markets": analyzed
        }

async def demo(symbol: str = "ETH"):
    """Demo function to fetch and analyze Polymarket crypto predictions."""
    async with PolymarketClient() as c:
        markets = await c.fetch_crypto_markets(symbol)
        rec = c.analyze_markets(markets, symbol)
        return rec

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description="Polymarket crypto prediction client")
    parser.add_argument("--symbol", "-s", default="ETH", help="Crypto symbol (ETH, BTC, SOL, etc.)")
    args = parser.parse_args()
    rec = asyncio.run(demo(args.symbol))
    print(json.dumps(rec, ensure_ascii=False, indent=2))
