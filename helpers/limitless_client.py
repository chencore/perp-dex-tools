import os
import asyncio
from typing import Any, Dict, Optional, List
from datetime import datetime

import aiohttp

DEFAULT_API_URL = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")
DEFAULT_TIMEOUT = int(os.getenv("POLYMARKET_TIMEOUT", "30"))

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

    async def fetch_crypto_markets(self, symbol: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch active crypto prediction markets for the given symbol from Polymarket.
        Returns markets categorized by timeframe (hourly, 4h, daily, weekly).
        
        Args:
            symbol: Crypto symbol like 'ETH', 'BTC', 'SOL'
        
        Returns:
            Dict with timeframes as keys and lists of relevant markets as values
        """
        # Fetch all markets with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                markets = await self._get("/markets")
                break
            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2)
        
        # Filter and categorize markets by timeframe
        symbol_upper = symbol.upper()
        categorized = {
            "hourly": [],
            "4hour": [],
            "daily": [],
            "weekly": [],
            "other": []
        }
        
        for market in markets:
            if not isinstance(market, dict):
                continue
            
            question = market.get("question", "").upper()
            active = market.get("active", False)
            closed = market.get("closed", True)
            
            # Filter: active, not closed, contains symbol, and likely price-related
            if not (active and not closed and symbol_upper in question):
                continue
            
            if not any(kw in question for kw in ["PRICE", "ABOVE", "BELOW", "REACH", "HIGHER", "LOWER", "CLOSE"]):
                continue
            
            # Classify by timeframe based on question keywords
            if any(kw in question for kw in ["HOUR", "HOURLY", "1H", "1 HOUR"]):
                categorized["hourly"].append(market)
            elif any(kw in question for kw in ["4 HOUR", "4H", "4-HOUR"]):
                categorized["4hour"].append(market)
            elif any(kw in question for kw in ["DAY", "DAILY", "24H", "24 HOUR", "TODAY", "TOMORROW"]):
                categorized["daily"].append(market)
            elif any(kw in question for kw in ["WEEK", "WEEKLY", "7 DAY"]):
                categorized["weekly"].append(market)
            else:
                categorized["other"].append(market)
        
        return categorized

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
                "summary": f"未找到 {symbol} 的活跃预测市场",
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
        
        # 中文方向映射
        direction_cn = {"buy": "做多", "sell": "做空", "neutral": "中性"}
        strength_cn = {"strong": "强", "moderate": "中等", "weak": "弱", "none": "无"}
        
        summary = f"分析了 {len(markets)} 个 {symbol} 预测市场。"
        summary += f"看涨概率: {avg_bullish:.1%}，看跌概率: {avg_bearish:.1%}。"
        summary += f"建议: {direction_cn.get(direction, direction)} ({strength_cn.get(signal_strength, signal_strength)}信号)"
        
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
    """Demo function to fetch and analyze Polymarket crypto predictions by timeframe."""
    async with PolymarketClient() as c:
        categorized_markets = await c.fetch_crypto_markets(symbol)
        
        results = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "timeframes": {}
        }
        
        # Analyze each timeframe
        for timeframe, markets in categorized_markets.items():
            if markets:  # Only analyze if there are markets
                analysis = c.analyze_markets(markets, symbol)
                results["timeframes"][timeframe] = analysis
        
        # Generate overall recommendation based on all timeframes
        all_markets = []
        for markets in categorized_markets.values():
            all_markets.extend(markets)
        
        if all_markets:
            results["overall"] = c.analyze_markets(all_markets, symbol)
        else:
            results["overall"] = {
                "direction": "neutral",
                "confidence": 0.0,
                "signal_strength": "none",
                "summary": f"未找到 {symbol} 的活跃预测市场"
            }
        
        return results

async def debug_markets(symbol: str = "ETH", limit: int = 10):
    """Debug function to show sample markets for inspection."""
    async with PolymarketClient() as c:
        markets = await c._get("/markets")
        
        symbol_upper = symbol.upper()
        matching = []
        
        for market in markets[:200]:  # Check first 200 markets
            if not isinstance(market, dict):
                continue
            
            question = market.get("question", "")
            active = market.get("active", False)
            closed = market.get("closed", True)
            
            # Show markets that contain the symbol
            if symbol_upper in question.upper():
                matching.append({
                    "question": question,
                    "active": active,
                    "closed": closed,
                    "volume": market.get("volume", "0"),
                    "outcomePrices": market.get("outcomePrices", "")
                })
                if len(matching) >= limit:
                    break
        
        return {
            "symbol": symbol,
            "total_checked": min(200, len(markets)),
            "matching_markets": len(matching),
            "samples": matching
        }

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description="Polymarket crypto prediction client")
    parser.add_argument("--symbol", "-s", default="ETH", help="Crypto symbol (ETH, BTC, SOL, etc.)")
    parser.add_argument("--timeframe", "-t", choices=["hourly", "4hour", "daily", "weekly", "all"], 
                        default="all", help="Specific timeframe to analyze")
    parser.add_argument("--debug", action="store_true", help="Show sample markets for debugging")
    args = parser.parse_args()
    
    if args.debug:
        # Debug mode: show sample markets
        debug_result = asyncio.run(debug_markets(args.symbol, limit=20))
        print(json.dumps(debug_result, ensure_ascii=False, indent=2))
    else:
        # Normal mode
        rec = asyncio.run(demo(args.symbol))
        
        # Filter output by timeframe if specified
        if args.timeframe != "all" and "timeframes" in rec:
            if args.timeframe in rec["timeframes"]:
                output = {
                    "symbol": rec["symbol"],
                    "timestamp": rec["timestamp"],
                    "timeframe": args.timeframe,
                    "analysis": rec["timeframes"][args.timeframe]
                }
                print(json.dumps(output, ensure_ascii=False, indent=2))
            else:
                print(json.dumps({"error": f"No markets found for {args.timeframe} timeframe"}, indent=2))
        else:
            print(json.dumps(rec, ensure_ascii=False, indent=2))
