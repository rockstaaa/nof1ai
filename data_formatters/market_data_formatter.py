"""
🌙 Market Data Formatter
Formats OHLCV, indicators, and perpetuals data for LLM consumption
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
from pathlib import Path

# Add project root to path for imports
project_root = str(Path(__file__).parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False
    print("⚠️ pandas_ta not available - using basic indicators only")

class MarketDataFormatter:
    """
    Formats market data for LLM consumption
    
    Collects:
    - OHLCV data
    - Technical indicators
    - Funding rates
    - Open interest
    """
    
    def __init__(self, exchange: str = 'hyperliquid'):
        """
        Initialize market data formatter
        
        Args:
            exchange: Exchange to use (only 'hyperliquid' in standalone version)
        """
        self.exchange = exchange
        # Import the requested exchange adapter
        if exchange == 'hyperliquid':
            from exchange import nice_funcs_hyperliquid as nf
            self.nf = nf
        elif exchange == 'upstox':
            from exchange import upstox_marketdata as nf
            self.nf = nf
        else:
            raise ValueError(f"Unsupported exchange for MarketDataFormatter: {exchange}")
    
    def get_market_data(self, symbols: List[str], timeframe: str = '3m') -> Dict:
        """
        Get formatted market data for all symbols
        
        Args:
            symbols: List of symbols (e.g., ['BTC', 'ETH', 'SOL'])
            timeframe: Timeframe for OHLCV data ('1m', '3m', '5m', '15m', '1h', '4h', '1d')
            
        Returns:
            Dict with formatted market data
        """
        market_data = {
            'timestamp': datetime.now().isoformat(),
            'timeframe': timeframe,
            'symbols': symbols,
            'data': {}
        }
        
        for symbol in symbols:
            try:
                symbol_data = self._get_symbol_data(symbol, timeframe)
                market_data['data'][symbol] = symbol_data
            except Exception as e:
                print(f"❌ Error getting data for {symbol}: {e}")
                market_data['data'][symbol] = {
                    'error': str(e),
                    'price': 0,
                    'change_24h': 0,
                    'volume_24h': 0
                }
        
        return market_data
    
    def _get_symbol_data(self, symbol: str, timeframe: str) -> Dict:
        """
        Get data for a single symbol
        
        Args:
            symbol: Symbol to get data for
            timeframe: Timeframe for OHLCV data
            
        Returns:
            Dict with symbol data
        """
        # Get current price and basic info
        try:
            current_price = self.nf.get_current_price(symbol)
        except Exception:
            current_price = 0

        # Get OHLCV data (returns DataFrame)
        try:
            ohlcv_data = self.nf.get_data(symbol, timeframe, bars=100)
        except Exception:
            ohlcv_data = None
        
        if ohlcv_data is None or ohlcv_data.empty or len(ohlcv_data) < 2:
            return {
                'symbol': symbol,
                'price': current_price,
                'change_24h': 0,
                'volume_24h': 0,
                'error': 'Insufficient data'
            }
        
        # get_data() already returns a processed DataFrame
        df = ohlcv_data
        # DataFrame should already have timestamp column and be sorted
        
        # Calculate basic metrics
        latest_price = df['close'].iloc[-1]
        oldest_price = df['close'].iloc[0] if len(df) > 0 else latest_price
        change_24h = ((latest_price - oldest_price) / oldest_price * 100) if oldest_price > 0 else 0
        
        # Calculate volume
        volume_24h = df['volume'].sum() if 'volume' in df.columns else 0
        
    # Calculate technical indicators if pandas_ta is available
        indicators = {}
        if PANDAS_TA_AVAILABLE and len(df) >= 20:
            try:
                # RSI
                rsi = ta.rsi(df['close'], length=14)
                indicators['rsi'] = float(rsi.iloc[-1]) if not rsi.empty else 50
                indicators['rsi_7'] = float(ta.rsi(df['close'], length=7).iloc[-1]) if len(df) >= 7 else 50
                indicators['rsi_14'] = float(rsi.iloc[-1]) if not rsi.empty else 50
                
                # MACD
                macd_data = ta.macd(df['close'])
                if not macd_data.empty:
                    indicators['macd'] = float(macd_data['MACD_12_26_9'].iloc[-1])
                    indicators['macd_signal'] = float(macd_data['MACDs_12_26_9'].iloc[-1])
                    indicators['macd_histogram'] = float(macd_data['MACDh_12_26_9'].iloc[-1])
                
                # Bollinger Bands
                bb_data = ta.bbands(df['close'], length=20)
                if not bb_data.empty and 'BBU_20_2.0' in bb_data.columns:
                    indicators['bb_upper'] = float(bb_data['BBU_20_2.0'].iloc[-1])
                    indicators['bb_middle'] = float(bb_data['BBM_20_2.0'].iloc[-1])
                    indicators['bb_lower'] = float(bb_data['BBL_20_2.0'].iloc[-1])
                    if 'BBW_20_2.0' in bb_data.columns:
                        indicators['bb_width'] = float(bb_data['BBW_20_2.0'].iloc[-1])
                
                # Moving averages
                indicators['sma_20'] = float(ta.sma(df['close'], length=20).iloc[-1])
                indicators['ema_12'] = float(ta.ema(df['close'], length=12).iloc[-1])
                indicators['ema_26'] = float(ta.ema(df['close'], length=26).iloc[-1])
                indicators['ema_20'] = float(ta.ema(df['close'], length=20).iloc[-1])
                
                # **CRITICAL: Add time series data for Nof1 compatibility**
                # Price series (last 10 prices)
                indicators['price_series'] = df['close'].tail(10).tolist()
                
                # EMA time series
                ema_20_series = ta.ema(df['close'], length=20)
                indicators['ema_20'] = ema_20_series.tail(10).tolist() if not ema_20_series.empty else []
                
                # MACD time series
                macd_series = ta.macd(df['close'])
                if not macd_series.empty and 'MACD_12_26_9' in macd_series.columns:
                    indicators['macd'] = macd_series['MACD_12_26_9'].tail(10).tolist()
                
                # RSI time series
                rsi_7_series = ta.rsi(df['close'], length=7)
                rsi_14_series = ta.rsi(df['close'], length=14)
                indicators['rsi_7'] = rsi_7_series.tail(10).tolist() if not rsi_7_series.empty else []
                indicators['rsi_14'] = rsi_14_series.tail(10).tolist() if not rsi_14_series.empty else []
                
            except Exception as e:
                print(f"⚠️ Error calculating indicators for {symbol}: {e}")
                indicators = {'error': str(e)}
        else:
            # Basic indicators without pandas_ta
            if len(df) >= 20:
                indicators['sma_20'] = float(df['close'].rolling(20).mean().iloc[-1])
            if len(df) >= 12:
                indicators['ema_12'] = float(df['close'].ewm(span=12).mean().iloc[-1])
            if len(df) >= 26:
                indicators['ema_26'] = float(df['close'].ewm(span=26).mean().iloc[-1])
        
        # Funding rates / perpetuals not applicable for NSE; leave zero or use options data if available
        symbol_funding = 0
        # Open interest placeholder - F&O OI can be added via Upstox if implemented
        symbol_oi = 0
        
        return {
            'symbol': symbol,
            'price': float(latest_price),
            'change_24h': round(change_24h, 2),
            'volume_24h': round(volume_24h, 2),
            'funding_rate': round(symbol_funding, 6),
            'open_interest': round(symbol_oi, 2),
            'indicators': indicators,
            'ohlcv_count': len(df),
            'latest_candle': {
                'open': float(df['open'].iloc[-1]),
                'high': float(df['high'].iloc[-1]),
                'low': float(df['low'].iloc[-1]),
                'close': float(df['close'].iloc[-1]),
                'volume': float(df['volume'].iloc[-1]),
                'timestamp': df['timestamp'].iloc[-1].isoformat()
            }
        }
    
    def format_for_llm(self, market_data: Dict) -> str:
        """
        Format market data for LLM consumption
        
        Args:
            market_data: Market data dict from get_market_data()
            
        Returns:
            Formatted string for LLM
        """
        if not market_data or 'data' not in market_data:
            return "❌ No market data available"
        
        output = []
        output.append(f"📊 Market Data ({market_data.get('timeframe', '3m')}) - {market_data.get('timestamp', 'Unknown')}")
        output.append("=" * 60)
        
        for symbol, data in market_data['data'].items():
            if 'error' in data:
                output.append(f"❌ {symbol}: {data['error']}")
                continue
            
            output.append(f"\n💰 {symbol}")
            output.append(f"   Price: ${data['price']:,.2f}")
            output.append(f"   24h Change: {data['change_24h']:+.2f}%")
            output.append(f"   24h Volume: {data['volume_24h']:,.0f}")
            output.append(f"   Funding Rate: {data['funding_rate']:.6f}")
            output.append(f"   Open Interest: ${data['open_interest']:,.0f}")
            
            # Add indicators if available
            if 'indicators' in data and data['indicators']:
                indicators = data['indicators']
                if 'rsi' in indicators:
                    output.append(f"   RSI(14): {indicators['rsi']:.1f}")
                if 'sma_20' in indicators:
                    output.append(f"   SMA(20): ${indicators['sma_20']:,.2f}")
                if 'ema_12' in indicators and 'ema_26' in indicators:
                    output.append(f"   EMA(12): ${indicators['ema_12']:,.2f}")
                    output.append(f"   EMA(26): ${indicators['ema_26']:,.2f}")
                if 'bb_upper' in indicators:
                    output.append(f"   BB Upper: ${indicators['bb_upper']:,.2f}")
                    output.append(f"   BB Lower: ${indicators['bb_lower']:,.2f}")
            
            # Add latest candle info
            if 'latest_candle' in data:
                candle = data['latest_candle']
                output.append(f"   Latest Candle: O:{candle['open']:.2f} H:{candle['high']:.2f} L:{candle['low']:.2f} C:{candle['close']:.2f}")
        
        return "\n".join(output)
    
    def format_for_multiple_symbols(self, symbols: List[str], timeframe: str = '3m') -> Dict:
        """
        Get formatted market data for multiple symbols (alias for get_market_data)
        
        Args:
            symbols: List of symbols to get data for
            timeframe: Timeframe for OHLCV data
            
        Returns:
            Dict with formatted market data
        """
        return self.get_market_data(symbols, timeframe)
