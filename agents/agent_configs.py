"""
🌙 Nof1 Trading Agent Configuration
SINGLE SOURCE OF TRUTH - Edit all settings here

To use:
    from src.nof1_agents.agents.agent_configs import CONFIG
    
    trader = DeepSeekTrader(
        symbols=CONFIG['SYMBOLS'],
        starting_capital_usd=CONFIG['STARTING_CAPITAL_USD'],
        ...
    )
    
    Or just run with defaults:
    trader = DeepSeekTrader()  # Uses all CONFIG defaults
"""

# ============================================================================
# 🏦 EXCHANGE & CAPITAL CONFIGURATION
# ============================================================================

CONFIG = {
    # Exchange
    'EXCHANGE': 'hyperliquid',           # Only HyperLiquid supported in standalone version
    
    # Capital
    'STARTING_CAPITAL_USD': 500,         # Starting capital ($500 default)
    
    # Symbols to Trade (match Nof1 default universe)
    'SYMBOLS': ['BTC', 'ETH', 'SOL', 'BNB', 'DOGE', 'XRP'],  # 6-coin set like Nof1
    
    # ============================================================================
    # 💰 POSITION SIZING & LEVERAGE
    # ============================================================================
    
    # Leverage
    'MAX_LEVERAGE': 20,                  # Maximum leverage (1-50x on HyperLiquid)
    
    # Position Sizing
    'MAX_POSITION_PERCENT': 90,          # Use 90% of capital per position
                                         # With $500 capital:
                                         # - Margin: $500 × 90% = $450
                                         # - Notional at 20x: $450 × 20 = $9,000
    
    'MAX_POSITIONS': 3,                  # Maximum concurrent positions
    'MAX_POSITION_SIZE_USD': 200000,     # Maximum notional position size
    
    # ============================================================================
    # 🤖 LLM CONFIGURATION (DeepSeek)
    # ============================================================================
    
    'MODEL_NAME': 'deepseek-chat',       # Options: 'deepseek-chat', 'deepseek-reasoner'
    'TEMPERATURE': 0.7,                  # LLM temperature (0-1, higher = more creative)
    'MAX_TOKENS': 4096,                  # Max tokens for LLM response
    
    # ============================================================================
    # ⏰ TIMING (Nof1 Style)
    # ============================================================================
    
    'CHECK_INTERVAL_MINUTES': 5,         # Check every 5 minutes (like Nof1)
    'MONITOR_INTERVAL_SECONDS': 5,       # Check P&L every 5 seconds when position open
    
    # ============================================================================
    # 🛡️ RISK MANAGEMENT
    # ============================================================================
    
    # Stop Loss & Take Profit
    'STOP_LOSS_PERCENT': 5.0,            # Auto-exit at -5% loss
    'TAKE_PROFIT_PERCENT': 10.0,         # Auto-exit at +10% gain
    
    # Confidence Thresholds
    'MIN_CONFIDENCE_TO_TRADE': 0.65,     # Only trade if LLM confidence >= 65%
    'MIN_CONFIDENCE_TO_CLOSE': 0.60,     # Close position if confidence drops below 60%
    
    # Account Protection
    'MAX_ACCOUNT_DRAWDOWN': 20.0,        # Stop trading if down 20%
    'MIN_ACCOUNT_BALANCE_USD': 100,      # Minimum balance to keep trading
    'MAX_RISK_PER_TRADE_PERCENT': 2.0,   # Max 2% of account per trade
    
    # ============================================================================
    # 📊 DATA COLLECTION (Matches Your Screenshots)
    # ============================================================================
    
    # Intraday Data (3-minute bars)
    'INTRADAY_TIMEFRAME': '3m',
    'INTRADAY_BARS': 20,                 # Last 20 bars (60 minutes)
    
    # Longer-term Context (4-hour bars)
    'LONGTERM_TIMEFRAME': '4h',
    'LONGTERM_BARS': 10,                 # Last 10 bars (40 hours)
    
    # Perpetuals Data
    'INCLUDE_PERPETUALS_DATA': True,     # Include OI & funding rate
    
    # ============================================================================
    # 📝 LOGGING & MONITORING
    # ============================================================================
    
    'SAVE_REASONING_TRACES': True,       # Save all LLM reasoning
    'SAVE_TRADE_LOGS': True,             # Save all trades
    'TRACK_PERFORMANCE': True,           # Track P&L, Sharpe, etc.
    
    # Log Directories
    'REASONING_LOG_DIR': 'src/data/nof1_agents/reasoning/',
    'TRADE_LOG_DIR': 'src/data/nof1_agents/trades/',
    'PERFORMANCE_LOG_DIR': 'src/data/nof1_agents/performance/',
    
    # ============================================================================
    # 🎯 EXECUTION SETTINGS
    # ============================================================================
    
    'ORDER_TYPE': 'limit',               # 'limit' or 'market'
    'SLIPPAGE_TOLERANCE': 0.001,         # 0.1% slippage for limit orders
    
    # ============================================================================
    # 💬 PROMPT SETTINGS
    # ============================================================================
    
    'USE_NOF1_STYLE_PROMPT': True,       # Use Nof1-inspired prompt format
    'INCLUDE_TIMESTAMP': True,           # Include timestamp in prompt
    'INCLUDE_ACCOUNT_INFO': True,        # Include account balance
    'INCLUDE_POSITION_INFO': True,       # Include current positions
    
    # ============================================================================
    # 🖥️ UI SETTINGS
    # ============================================================================
    
    'VERBOSE_MODE': True,                # Print detailed logs to console
}

# ============================================================================
# 🎨 QUICK PRESETS
# ============================================================================

# Conservative preset (lower risk)
CONSERVATIVE_CONFIG = CONFIG.copy()
CONSERVATIVE_CONFIG.update({
    'MAX_LEVERAGE': 10,                  # Lower leverage
    'MAX_POSITION_PERCENT': 50,          # Only use 50% of capital
    'STOP_LOSS_PERCENT': 3.0,            # Tighter stop
    'MIN_CONFIDENCE_TO_TRADE': 0.75,     # Higher confidence required
})

# Aggressive preset (higher risk)
AGGRESSIVE_CONFIG = CONFIG.copy()
AGGRESSIVE_CONFIG.update({
    'MAX_LEVERAGE': 30,                  # Higher leverage
    'MAX_POSITION_PERCENT': 95,          # Use 95% of capital
    'STOP_LOSS_PERCENT': 7.0,            # Wider stop
    'MIN_CONFIDENCE_TO_TRADE': 0.60,     # Lower confidence threshold
})

# Multi-symbol preset
MULTI_SYMBOL_CONFIG = CONFIG.copy()
MULTI_SYMBOL_CONFIG.update({
    'SYMBOLS': ['BTC', 'ETH', 'SOL'],    # Trade multiple coins
    'MAX_POSITION_PERCENT': 30,          # 30% per symbol = 90% max
    'CHECK_INTERVAL_MINUTES': 5,         # Slower checks with more symbols
})
