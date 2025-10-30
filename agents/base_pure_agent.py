"""
🌙 Base Nof1 Agent
Core agent class for Nof1-style AI-driven trading
"""

import json
import time
from datetime import datetime
from typing import Dict, Optional
from abc import ABC, abstractmethod
from termcolor import cprint
import sys
from pathlib import Path

# Add project root to path for independent operation
project_root = str(Path(__file__).parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Also add nof1-agents directory for local imports
purellm_root = str(Path(__file__).parent.parent)
if purellm_root not in sys.path:
    sys.path.append(purellm_root)

# Import prompts at module level
from prompts.nof1_style_prompt import NOF1_SYSTEM_PROMPT


class BaseNof1Agent(ABC):
    """
    Base class for Nof1-style trading agents

    This class handles:
    - Data collection (account, positions, market data)
    - Prompt formatting
    - Decision execution
    - Main trading loop

    Subclasses implement get_llm_decision()
    """
    
    def __init__(
        self,
        exchange: str = 'hyperliquid',
        symbols: list = None,
        check_interval_seconds: int = 180,
        verbose: bool = True
    ):
        """
        Initialize base agent
        
        Args:
            exchange: 'hyperliquid', 'aster', or 'solana'
            symbols: List of symbols to trade (e.g., ['BTC', 'ETH', 'SOL'])
            check_interval_seconds: How often to check (default: 180 = 3 minutes)
            verbose: Print detailed logs
        """
        self.exchange = exchange
        self.symbols = symbols or ['BTC', 'ETH', 'SOL']
        self.check_interval = check_interval_seconds
        self.verbose = verbose
        
        # Track start time for Nof1-style prompts
        from datetime import datetime
        self.start_time = datetime.now()
        self.interaction_count = 0
        
        # Initialize data formatters
        from data_formatters.market_data_formatter import MarketDataFormatter
        from data_formatters.position_formatter import PositionFormatter
        from data_formatters.account_formatter import AccountFormatter
        
        self.market_formatter = MarketDataFormatter(exchange=exchange)
        self.position_formatter = PositionFormatter(exchange=exchange)
        self.account_formatter = AccountFormatter(exchange=exchange)
        
        # Import exchange adapter (HyperLiquid, Upstox, etc.)
        if exchange == 'hyperliquid':
            from exchange import nice_funcs_hyperliquid as nf
        elif exchange == 'upstox':
            from exchange import upstox_marketdata as nf
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

        self.nf = nf
        
        # Trading state
        self.is_running = False
        self.iteration = 0
        
        cprint(f"\n🌙 Nof1 Agent Initialized", "cyan", attrs=['bold'])
        cprint(f"   Exchange: {exchange}", "white")
        cprint(f"   Symbols: {symbols}", "white")
        cprint(f"   Check Interval: {check_interval_seconds}s ({check_interval_seconds/60:.1f} min)", "white")
    
    def collect_all_data(self) -> Dict:
        """
        Collect all data from HyperLiquid before each decision
        
        Returns:
            {
                'timestamp': '2025-10-24 08:57:11',
                'account': {...},
                'positions': {...},
                'market_data': {...}
            }
        """
        cprint("\n📊 Collecting real-time data from HyperLiquid...", "cyan", attrs=['bold'])
        
        # Current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Get account data (balance, P&L, returns)
        if self.verbose:
            cprint("   💰 Fetching account data...", "yellow")
        account_data = self.account_formatter.get_account_data()
        if self.verbose:
            currency = account_data.get('currency', 'USD')
            symbol = '₹' if str(currency).upper() == 'INR' else '$'
            cprint(f"      Account Value: {symbol}{account_data.get('account_value', 0):,.2f}", "white")
            cprint(f"      Available Cash: {symbol}{account_data.get('available_cash', 0):,.2f}", "white")
            cprint(f"      Total Return: {account_data.get('total_return_percent', 0):.2f}%", "white")
        
        # 2. Get current positions (if any)
        if self.verbose:
            cprint("   📈 Fetching current positions...", "yellow")
        positions = self.position_formatter.get_all_positions(self.symbols)
        if self.verbose:
            ccy_symbol = '₹' if account_data.get('currency', 'USD').upper() == 'INR' else '$'
            if positions:
                for p_symbol, pos in positions.items():
                    cprint(f"      {p_symbol}: {pos.get('quantity',0):.4f} @ {ccy_symbol}{pos.get('current_price',0):,.2f} | P&L: {ccy_symbol}{pos.get('unrealized_pnl',0):,.2f}", "white")
            else:
                cprint("      No open positions", "white")
        
        # 3. Get market data for all symbols
        if self.verbose:
            cprint("   📊 Fetching market data...", "yellow")
        market_data = self.market_formatter.format_for_multiple_symbols(self.symbols)
        if self.verbose:
            for symbol in self.symbols:
                if 'data' in market_data and symbol in market_data['data'] and 'price' in market_data['data'][symbol]:
                    price = market_data['data'][symbol].get('price', 0)
                    cprint(f"      {symbol}: ${price:,.2f}", "white")
                else:
                    cprint(f"      {symbol}: No data available", "red")
        
        cprint("✅ Data collection complete!", "green")
        
        # Extract the actual market data from the formatter response
        if isinstance(market_data, dict) and 'data' in market_data:
            formatted_market_data = market_data['data']
        else:
            formatted_market_data = market_data
        
        # Debug: Print market data structure
        if self.verbose:
            cprint(f"   📊 Market data structure: {list(formatted_market_data.keys()) if isinstance(formatted_market_data, dict) else 'Not a dict'}", "cyan")
            for symbol in self.symbols:
                if symbol in formatted_market_data:
                    symbol_data = formatted_market_data[symbol]
                    if isinstance(symbol_data, dict):
                        cprint(f"      {symbol}: {list(symbol_data.keys())}", "white")
                    else:
                        cprint(f"      {symbol}: {type(symbol_data)}", "white")
        
        return {
            'timestamp': timestamp,
            'account': account_data,
            'positions': positions,
            'market_data': formatted_market_data
        }
    
    def format_prompt(self, data: Dict) -> str:
        """
        Format data into Nof1-style prompt
        
        Args:
            data: Dict from collect_all_data()
        
        Returns:
            Formatted prompt string
        """
        from prompts.nof1_style_prompt import format_nof1_user_prompt
        
        return format_nof1_user_prompt(
            account_data=data['account'],
            positions=data['positions'],
            market_data=data['market_data'],
            timestamp=data['timestamp'],
            interaction_count=self.interaction_count,
            start_time=self.start_time
        )

    def _is_market_open(self, config: dict) -> bool:
        """
        Simple NSE market hours & holiday check (India Standard Time)
        Expects config to contain 'MARKET_OPEN_TIME', 'MARKET_CLOSE_TIME', 'MARKET_HOLIDAYS'
        """
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            tz = ZoneInfo('Asia/Kolkata')
            now = datetime.now(tz)

            # Weekends closed
            if now.weekday() >= 5:
                return False

            # Holidays
            date_str = now.strftime('%Y-%m-%d')
            if date_str in config.get('MARKET_HOLIDAYS', []) :
                return False

            # Parse times
            from datetime import time as dt_time
            open_str = config.get('MARKET_OPEN_TIME', '09:15')
            close_str = config.get('MARKET_CLOSE_TIME', '15:30')
            open_t = datetime.strptime(open_str, '%H:%M').time()
            close_t = datetime.strptime(close_str, '%H:%M').time()

            now_t = now.time()
            return open_t <= now_t <= close_t
        except Exception:
            # On any error, return True to avoid accidental misses; caller should handle conservatively
            return True
    
    @abstractmethod
    def get_llm_decision(self, prompt: str, system_prompt: str) -> Dict:
        """
        Get decision from LLM (implemented by subclass)
        
        Args:
            prompt: Formatted market data prompt
            system_prompt: System instructions
        
        Returns:
            {
                "decision": "OPEN_LONG" | "OPEN_SHORT" | "CLOSE_POSITION" | "DO_NOTHING",
                "symbol": "BTC",
                "reasoning": "...",
                "confidence": 0.88,
                "entry_price": 111113.5,
                "position_size_usd": 10000,
                "leverage": 20,
                "stop_loss": 105000,
                "take_profit": 115000
            }
        """
        pass
    
    def execute_decision(self, decision: Dict) -> bool:
        """
        Execute trading decision on HyperLiquid
        
        Args:
            decision: LLM decision dict
        
        Returns:
            True if successful, False otherwise
        """
        try:
            action = decision.get('decision', 'DO_NOTHING')
            symbol = decision.get('symbol')
            
            if action == 'DO_NOTHING':
                cprint(f"\n⏸️  DO NOTHING - Waiting for better setup", "white", "on_blue")
                return True
            
            if action == 'CLOSE_POSITION':
                return self._close_position(symbol, decision)
            
            if action in ['OPEN_LONG', 'OPEN_SHORT']:
                return self._open_position(symbol, decision)
            
            return False
            
        except Exception as e:
            cprint(f"❌ Error executing decision: {e}", "red")
            return False
    
    def _open_position(self, symbol: str, decision: Dict) -> bool:
        """Open new position (long or short)"""
        try:
            action = decision.get('decision')
            position_size = decision.get('position_size_usd', 0)
            leverage = decision.get('leverage', 20)
            entry_price = decision.get('entry_price', 0)
            stop_loss = decision.get('stop_loss', 0)
            take_profit = decision.get('take_profit', 0)
            
            cprint(f"\n🚀 OPENING {action}: {symbol}", "white", "on_green")
            # Currency-aware prints
            currency = 'INR' if getattr(self, 'exchange', '') == 'upstox' else 'USD'
            sym = '₹' if currency == 'INR' else '$'
            if currency == 'INR':
                # Use INR-aware fields where available
                pos_display = decision.get('position_size_inr', position_size)
                cprint(f"   Position Size: {sym}{pos_display:,.2f} ({currency} notional)", "white")
                cprint(f"   Leverage: {leverage}x", "white")
                cprint(f"   Entry: {sym}{entry_price:,.2f}", "white")
                cprint(f"   Stop Loss: {sym}{stop_loss:,.2f}", "white")
                cprint(f"   Take Profit: {sym}{take_profit:,.2f}", "white")
            else:
                cprint(f"   Position Size: ${position_size:,.2f} (notional)", "white")
                cprint(f"   Leverage: {leverage}x", "white")
                cprint(f"   Entry: ${entry_price:,.2f}", "white")
                cprint(f"   Stop Loss: ${stop_loss:,.2f}", "white")
                cprint(f"   Take Profit: ${take_profit:,.2f}", "white")
            
            # Exchange-specific execution
            if getattr(self, 'exchange', '') == 'upstox':
                # Upstox expects quantity in shares or lots. Prefer explicit quantity_lots from decision.
                quantity = None
                lot_size = decision.get('lot_size')
                quantity_lots = decision.get('quantity_lots')
                try:
                    if not lot_size and hasattr(self.nf, 'get_lot_size'):
                        lot_size = self.nf.get_lot_size(symbol)
                except Exception:
                    lot_size = lot_size or 1

                if quantity_lots:
                    quantity = int(quantity_lots) * int(lot_size or 1)
                else:
                    # Derive from notional if provided
                    notional = decision.get('position_size_inr') or decision.get('position_size_usd')
                    current_price = None
                    try:
                        current_price = self.nf.get_current_price(symbol)
                    except Exception:
                        current_price = None
                    if notional and current_price and current_price > 0:
                        approx_qty = int((notional / current_price) // (lot_size or 1)) * (lot_size or 1)
                        quantity = max(approx_qty, lot_size or 1)
                    else:
                        quantity = lot_size or 1

                # Place market order via Upstox adapter
                if action == 'OPEN_LONG':
                    success = self.nf.market_buy(symbol, quantity, price=entry_price)
                else:
                    success = self.nf.market_sell(symbol, quantity, price=entry_price)
            else:
                # Execute on HyperLiquid
                if action == 'OPEN_LONG':
                    success = self.nf.ai_entry(symbol, position_size, leverage=leverage)
                else:  # OPEN_SHORT
                    if hasattr(self.nf, 'open_short'):
                        success = self.nf.open_short(symbol, position_size, slippage=0.001, leverage=leverage)
                    else:
                        success = self.nf.market_sell(symbol, position_size, slippage=0.001, leverage=leverage)
            
            if success:
                cprint("✅ Position opened successfully!", "white", "on_green")
                
                # TODO: Set stop loss and take profit orders
                # This requires implementing stop/limit order functions in nice_funcs_hyperliquid
                
                return True
            else:
                cprint("❌ Failed to open position", "white", "on_red")
                return False
                
        except Exception as e:
            cprint(f"❌ Error opening position: {e}", "red")
            return False
    
    def _close_position(self, symbol: str, decision: Dict) -> bool:
        """Close existing position"""
        try:
            cprint(f"\n🔄 CLOSING POSITION: {symbol}", "white", "on_yellow")
            
            # Get account object first
            account = self.nf._get_account_from_env()
            if not account:
                cprint("❌ Could not get account to close position", "red")
                return False

            # Get current position
            positions_list, im_in_pos, _, _, _, _, _ = self.nf.get_position(symbol, account)
            
            if not im_in_pos or not positions_list:
                cprint("⚠️  No position to close", "yellow")
                return True
            
            position = positions_list[0] # Get the first position details
            
            # Close position by sending opposite order
            is_long = float(position.get('szi', 0)) > 0
            size = float(position.get('szi', 0))
            
            cprint(f"   Closing {'LONG' if is_long else 'SHORT'} position of size {abs(size):.4f} {symbol}", "white")

            # For closing, we send a reduce-only order for the exact size of the position
            # Compute an aggressive limit price to ensure closing fills
            try:
                ask, bid, _ = self.nf.ask_bid(symbol)
                if is_long:
                    close_price = bid * 0.999  # undersell to close long
                else:
                    close_price = ask * 1.001  # overbid to close short
                # Basic rounding: BTC whole dollars, others 0.1
                close_price = round(close_price) if symbol == 'BTC' else round(close_price, 1)
            except Exception:
                # Fallback to current_price from position if ask/bid fails
                close_price = float(position.get('entryPx', 0)) or 0

            success = self.nf.limit_order(symbol, is_buy=not is_long, sz=abs(size), limit_px=close_price, reduce_only=True, account=account)
            
            # limit_order returns a dict; treat presence of 'response' as success
            if isinstance(success, dict) and ('response' in success or 'statuses' in success.get('response', {}).get('data', {})):
                cprint("✅ Position closed successfully!", "white", "on_green")
                return True
            else:
                error_msg = success.get('error', 'Unknown error') if isinstance(success, dict) else 'Unknown error'
                cprint(f"❌ Failed to close position: {error_msg}", "white", "on_red")
                return False
                
        except Exception as e:
            cprint(f"❌ Error closing position: {e}", "red")
            return False
    
    def run_single_iteration(self):
        """Run one complete trading iteration"""
        try:
            self.iteration += 1
            cprint(f"\n{'='*60}", "cyan")
            cprint(f"🌙 ITERATION #{self.iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "cyan", attrs=['bold'])
            cprint(f"{'='*60}", "cyan")
            
            # 1. Market hours check (for exchanges with sessions like Upstox/NSE)
            try:
                if self.exchange == 'upstox':
                    from agents.agent_configs import CONFIG
                    if not self._is_market_open(CONFIG):
                        cprint("⏰ Market is currently closed (NSE hours / holiday). Skipping this iteration.", "yellow")
                        return
            except Exception:
                pass

            # 2. Collect all data from exchange
            data = self.collect_all_data()
            
            # 2. Format into Nof1-style prompt
            prompt = self.format_prompt(data)
            
            # 3. Get LLM decision (implemented by subclass)
            decision = self.get_llm_decision(prompt, NOF1_SYSTEM_PROMPT)
            
            if not decision:
                cprint("❌ No decision from LLM", "red")
                return
            
            # 4. Execute decision on HyperLiquid
            self.execute_decision(decision)
            
        except KeyboardInterrupt:
            raise
        except Exception as e:
            cprint(f"❌ Error in iteration: {e}", "red")
            import traceback
            traceback.print_exc()
    
    def run(self):
        """
        Main trading loop
        
        Runs continuously:
        1. Collect data from HyperLiquid
        2. Format prompt (Nof1 style)
        3. Get LLM decision
        4. Execute on HyperLiquid
        5. Sleep X minutes
        6. Repeat
        """
        self.is_running = True
        
        cprint("\n🚀 Starting Nof1 Trading Agent...", "white", "on_blue")
        cprint(f"   Press Ctrl+C to stop", "white", "on_blue")
        cprint(f"   Check interval: {self.check_interval}s ({self.check_interval/60:.1f} min)", "white", "on_blue")
        
        try:
            while self.is_running:
                # Run one iteration
                self.run_single_iteration()
                
                # Sleep until next check
                next_check = datetime.now().timestamp() + self.check_interval
                next_check_time = datetime.fromtimestamp(next_check).strftime('%H:%M:%S')
                
                cprint(f"\n😴 Sleeping until {next_check_time}...", "cyan")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            cprint("\n👋 Shutting down gracefully...", "yellow")
            self.is_running = False
        except Exception as e:
            cprint(f"\n❌ Fatal error: {e}", "red")
            import traceback
            traceback.print_exc()
            self.is_running = False
