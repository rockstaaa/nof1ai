"""
🌙 DeepSeek Nof1 Trader
Nof1-style autonomous trading using DeepSeek + HyperLiquid

Usage (Independent Mode):
    cd nof1-agents/
    python agents/deepseek_trader.py
    
    Or customize:
    
    from agents.deepseek_trader import DeepSeekTrader
    
    trader = DeepSeekTrader(
        symbols=['BTC', 'ETH'],
        starting_capital_usd=500,
        max_leverage=20,
        check_interval_minutes=3
    )
    
    trader.run()
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from termcolor import cprint
from typing import Dict, Optional
from dotenv import load_dotenv

# Add project root to path for independent operation
project_root = str(Path(__file__).parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Also add nof1-agents directory for local imports
purellm_root = str(Path(__file__).parent.parent)
if purellm_root not in sys.path:
    sys.path.append(purellm_root)

# Load environment variables from nof1-agents directory
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    cprint(f"🔍 Loading environment from: {env_path}", "cyan")
else:
    cprint(f"⚠️ No .env file found at: {env_path}", "yellow")

from agents.base_pure_agent import BaseNof1Agent
from agents.agent_configs import CONFIG
from models.model_factory import model_factory
class DeepSeekTrader(BaseNof1Agent):
    """
    DeepSeek-powered autonomous trader
    
    Fetches real-time data from HyperLiquid → Sends to DeepSeek → Executes trades
    
    All settings are read from CONFIG by default (agent_configs.py).
    You can override any setting by passing it as an argument.
    """
    
    def __init__(
        self,
        symbols: list = None,
        starting_capital_usd: float = None,
        max_leverage: int = None,
        max_position_percent: float = None,
        check_interval_minutes: int = None,
        min_confidence: float = None,
        stop_loss_percent: float = None,
        take_profit_percent: float = None,
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None,
        verbose: bool = None
    ):
        """
        Initialize DeepSeek Trader
        
        All parameters are optional. If not provided, reads from CONFIG (agent_configs.py).
        
        Args:
            symbols: List of symbols to trade (default: from CONFIG)
            starting_capital_usd: Starting capital (default: from CONFIG)
            max_leverage: Maximum leverage (default: from CONFIG)
            max_position_percent: % of capital per position (default: from CONFIG)
            check_interval_minutes: Check every N minutes (default: from CONFIG)
            min_confidence: Min LLM confidence to trade (default: from CONFIG)
            stop_loss_percent: Auto-exit at -X% (default: from CONFIG)
            take_profit_percent: Auto-exit at +X% (default: from CONFIG)
            model_name: DeepSeek model (default: from CONFIG)
            temperature: LLM temperature (default: from CONFIG)
            max_tokens: Max response tokens (default: from CONFIG)
            verbose: Print detailed logs (default: from CONFIG)
        """
        # Read from CONFIG with overrides
        symbols = symbols or CONFIG['SYMBOLS']
        # Starting capital: support USD (crypto) and INR (Upstox)
        if CONFIG.get('EXCHANGE') == 'upstox':
            starting_capital_usd = starting_capital_usd or CONFIG.get('STARTING_CAPITAL_INR', 100000.0)
        else:
            starting_capital_usd = starting_capital_usd or CONFIG.get('STARTING_CAPITAL_USD', 500.0)
        max_leverage = max_leverage or CONFIG['MAX_LEVERAGE']
        max_position_percent = max_position_percent or CONFIG['MAX_POSITION_PERCENT']
        check_interval_minutes = check_interval_minutes or CONFIG['CHECK_INTERVAL_MINUTES']
        min_confidence = min_confidence or CONFIG['MIN_CONFIDENCE_TO_TRADE']
        stop_loss_percent = stop_loss_percent or CONFIG['STOP_LOSS_PERCENT']
        take_profit_percent = take_profit_percent or CONFIG['TAKE_PROFIT_PERCENT']
        model_name = model_name or CONFIG['MODEL_NAME']
        temperature = temperature or CONFIG['TEMPERATURE']
        max_tokens = max_tokens or CONFIG['MAX_TOKENS']
        verbose = verbose if verbose is not None else CONFIG['VERBOSE_MODE']
        
        # Initialize base agent
        super().__init__(
            exchange=CONFIG['EXCHANGE'],
            symbols=symbols,
            check_interval_seconds=check_interval_minutes * 60,
            verbose=verbose
        )
        
        # Trading parameters
        self.starting_capital = starting_capital_usd
        self.max_leverage = max_leverage
        self.max_position_percent = max_position_percent
        self.min_confidence = min_confidence
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        
        # LLM parameters
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize DeepSeek model
        cprint(f"\n🤖 Initializing DeepSeek model: {model_name}", "cyan")
        try:
            self.model = model_factory.get_model('deepseek', model_name)
            
            if not self.model:
                raise RuntimeError(f"❌ Failed to initialize DeepSeek model: {model_name}")
            
            cprint(f"✅ DeepSeek ready: {self.model.model_name}", "green")
        except Exception as e:
            cprint(f"❌ Error initializing DeepSeek model: {e}", "red")
            raise RuntimeError(f"Failed to initialize DeepSeek model: {e}")
        
        # Create logging directory
        self.log_dir = Path(project_root) / "src" / "data" / "nof1_agents"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        (self.log_dir / "reasoning").mkdir(exist_ok=True)
        (self.log_dir / "trades").mkdir(exist_ok=True)
        (self.log_dir / "performance").mkdir(exist_ok=True)
        
        # Log configuration
        self._log_config()

    def _log_config(self):
        """Log the current configuration"""
        cprint("\n📋 DeepSeek Trader Configuration:", "cyan", attrs=['bold'])
        cprint(f"   Exchange: {self.exchange}", "white")
        cprint(f"   Symbols: {self.symbols}", "white")
        cprint(f"   Check Interval: {self.check_interval}s ({self.check_interval/60:.1f} min)", "white")
        currency = 'INR' if CONFIG.get('EXCHANGE') == 'upstox' else 'USD'
        sym = '₹' if currency == 'INR' else '$'
        cprint(f"   Starting Capital: {sym}{self.starting_capital:,.2f} ({currency})", "white")
        cprint(f"   Max Leverage: {self.max_leverage}x", "white")
        cprint(f"   Max Position %: {self.max_position_percent}%", "white")
        cprint(f"   Min Confidence: {self.min_confidence:.1%}", "white")
        cprint(f"   Stop Loss: {self.stop_loss_percent}%", "white")
        cprint(f"   Take Profit: {self.take_profit_percent}%", "white")
        cprint(f"   Model: {self.model_name}", "white")
        cprint(f"   Temperature: {self.temperature}", "white")
        cprint(f"   Max Tokens: {self.max_tokens}", "white")
        cprint(f"   Verbose: {self.verbose}", "white")

    def get_llm_decision(self, prompt: str, system_prompt: str) -> Optional[Dict]:
        # Increment interaction count in base class
        self.interaction_count += 1
        
        # Check if model is initialized
        if not hasattr(self, 'model') or self.model is None:
            cprint("❌ Model not initialized", "red")
            return None
            
        try:
            # Querying DeepSeek for trading decision...
            
            # Call DeepSeek
            response = self.model.generate_response(
                system_prompt=system_prompt,
                user_content=prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            if not response:
                cprint("❌ No response from DeepSeek", "red")
                return None
            
            # Extract text from response
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, list):
                response_text = response[0].text if hasattr(response[0], 'text') else str(response[0])
            else:
                response_text = str(response)
            
            # Response received
            
            # Parse JSON response
            decision = self._parse_response(response_text)
            
            if not decision:
                cprint("❌ Failed to parse DeepSeek response", "red")
                return None
            
            # Log reasoning trace
            self._log_reasoning(decision, response_text)
            
            # Validate decision
            if not self._validate_decision(decision):
                return None
            
            # Adjust position size based on starting capital
            decision = self._adjust_position_size(decision)
            
            return decision
            
        except Exception as e:
            cprint(f"❌ Error getting LLM decision: {e}", "red")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """
        Parse JSON response from DeepSeek
        
        DeepSeek should return JSON like:
        {
            "decision": "OPEN_LONG",
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
        try:
            # Find JSON in response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start == -1 or end == 0:
                cprint("⚠️  No JSON found in response, trying to extract decision...", "yellow")
                # Try to extract decision from text
                return self._extract_decision_from_text(response_text)
            
            json_str = response_text[start:end]
            decision = json.loads(json_str)
            
            # Normalize old/new decision formats
            # New prompt uses: BUY / SELL / CLOSE / DO_NOTHING
            raw_decision = decision.get('decision', '').upper()
            mapping = {
                'BUY': 'OPEN_LONG',
                'SELL': 'OPEN_SHORT',
                'CLOSE': 'CLOSE_POSITION',
                'DO_NOTHING': 'DO_NOTHING'
            }

            if raw_decision in mapping:
                decision['decision'] = mapping[raw_decision]

            # If Upstox style fields present, map them
            if 'entry_price_inr' in decision:
                decision['entry_price'] = decision.get('entry_price_inr')
            if 'quantity_lots' in decision:
                # Keep quantity_lots and lot_size for exchange-specific execution
                decision['quantity_lots'] = int(decision.get('quantity_lots', 0))
                decision['lot_size'] = int(decision.get('lot_size', 1))

            # Ensure at least decision and symbol present
            if 'decision' not in decision or 'symbol' not in decision:
                cprint("⚠️  Missing required field: decision or symbol", "yellow")
                return None

            return decision
            
        except json.JSONDecodeError as e:
            cprint(f"⚠️  JSON parse error: {e}", "yellow")
            # Try to extract from text
            return self._extract_decision_from_text(response_text)
        except Exception as e:
            cprint(f"❌ Error parsing response: {e}", "red")
            return None
    
    def _extract_decision_from_text(self, text: str) -> Optional[Dict]:
        """
        Try to extract decision from plain text response
        
        If DeepSeek doesn't return pure JSON, try to parse the decision
        """
        text_upper = text.upper()
        
        # Extract decision
        if 'OPEN LONG' in text_upper or 'OPEN_LONG' in text_upper or 'BUY' in text_upper:
            decision = 'OPEN_LONG'
        elif 'OPEN SHORT' in text_upper or 'OPEN_SHORT' in text_upper or 'SHORT' in text_upper:
            decision = 'OPEN_SHORT'
        elif 'CLOSE' in text_upper:
            decision = 'CLOSE_POSITION'
        else:
            decision = 'DO_NOTHING'
        
        # Extract symbol
        symbol = None
        for sym in self.symbols:
            if sym in text_upper:
                symbol = sym
                break
        
        if not symbol:
            symbol = self.symbols[0]  # Default to first symbol
        
        return {
            'decision': decision,
            'symbol': symbol,
            'reasoning': text[:500],  # First 500 chars
            'confidence': 0.7,  # Default confidence
            'entry_price': 0,
            'position_size_usd': 0,
            'leverage': self.max_leverage,
            'stop_loss': 0,
            'take_profit': 0
        }
    
    def _validate_decision(self, decision: Dict) -> bool:
        """
        Validate LLM decision against risk parameters
        
        Returns:
            True if valid, False otherwise
        """
        confidence = decision.get('confidence', 0)
        
        # Check minimum confidence
        if confidence < self.min_confidence:
            cprint(f"⚠️  Confidence too low: {confidence:.2%} < {self.min_confidence:.2%}", "yellow")
            cprint(f"   Overriding to DO_NOTHING", "yellow")
            decision['decision'] = 'DO_NOTHING'
            return True
        
        # Check leverage
        leverage = decision.get('leverage', 1)
        if leverage is None:
            leverage = 1  # Default leverage
            decision['leverage'] = leverage
        
        if leverage > self.max_leverage:
            cprint(f"⚠️  Leverage too high: {leverage}x > {self.max_leverage}x", "yellow")
            cprint(f"   Capping at {self.max_leverage}x", "yellow")
            decision['leverage'] = self.max_leverage
        
        # Validate invalidation condition
        invalidation_condition = decision.get('invalidation_condition', '')
        if not invalidation_condition or invalidation_condition.strip() == '':
            cprint("⚠️  Missing invalidation condition - adding default", "yellow")
            decision['invalidation_condition'] = f"Price moves against position by {self.stop_loss_percent}%"
        
        # Check risk/reward ratio
        risk_reward = decision.get('risk_reward_ratio', 0)
        if risk_reward is not None and risk_reward > 0 and risk_reward < 1.0:
            cprint(f"⚠️  Poor risk/reward ratio: {risk_reward:.2f} < 1.0", "yellow")
            cprint("   Consider adjusting stop loss or take profit", "yellow")
        
        return True
    
    def _adjust_position_size(self, decision: Dict) -> Dict:
        """
        Adjust position size based on starting capital
        
        Args:
            decision: LLM decision with position_size_usd
        
        Returns:
            Decision with adjusted position size
        """
        action = decision.get('decision')
        
        if action in ['OPEN_LONG', 'OPEN_SHORT']:
            # Get account balance
            account_data = self.account_formatter.get_account_data()
            available_cash = account_data.get('available_cash', self.starting_capital)
            
            # Calculate position size
            # Max position = available_cash * max_position_percent * leverage
            leverage = decision.get('leverage', self.max_leverage)
            max_position = available_cash * (self.max_position_percent / 100) * leverage
            
            # Use LLM's suggestion or max position (whichever is smaller)
            llm_position = decision.get('position_size_usd', max_position)
            final_position = min(llm_position, max_position)
            
            decision['position_size_usd'] = final_position
            
            cprint(f"\n💰 Position Sizing:", "yellow")
            cprint(f"   Available Cash: ${available_cash:,.2f}", "white")
            cprint(f"   Max Position %: {self.max_position_percent}%", "white")
            cprint(f"   Leverage: {leverage}x", "white")
            cprint(f"   Max Position Size: ${max_position:,.2f} (notional)", "white")
            cprint(f"   Final Position Size: ${final_position:,.2f} (notional)", "green", attrs=['bold'])
            cprint(f"   Margin Required: ${final_position / leverage:,.2f}", "white")
        
        return decision
    
    def _log_reasoning(self, decision: Dict, full_response: str):
        """
        Log DeepSeek reasoning trace (Nof1 style)
        
        Saves to: src/data/nof1_agents/reasoning/deepseek_YYYY-MM-DD.txt
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            date_str = datetime.now().strftime("%Y-%m-%d")
            
            log_file = self.log_dir / "reasoning" / f"deepseek_{date_str}.txt"
            
            # Format reasoning trace
            entry_price = decision.get('entry_price', 0) or 0
            position_size = decision.get('position_size_usd', 0) or 0
            stop_loss = decision.get('stop_loss', 0) or 0
            take_profit = decision.get('take_profit', 0) or 0
            risk_reward = decision.get('risk_reward_ratio', 0) or 0
            
            trace = f"""
{'='*60}
[{timestamp}] DEEPSEEK REASONING TRACE
{'='*60}
DECISION: {decision.get('decision', 'UNKNOWN')} {decision.get('symbol', '')}
CONFIDENCE: {decision.get('confidence', 0) or 0:.0%}

REASONING:
{decision.get('reasoning') or full_response[:500] or 'No reasoning provided'}

TRADE PARAMETERS:
- Symbol: {decision.get('symbol', 'N/A')}
- Entry Price: ${entry_price:,.2f}
- Position Size: ${position_size:,.2f} (notional)
- Leverage: {decision.get('leverage', 1)}x
- Stop Loss: ${stop_loss:,.2f}
- Take Profit: ${take_profit:,.2f}
- Risk/Reward: {risk_reward:.2f}
- Invalidation: {decision.get('invalidation_condition', 'N/A')}

FULL LLM RESPONSE:
{full_response}
{'='*60}

"""
            
            # Print to console
            cprint(trace, "cyan")
            
            # Append to file
            with open(log_file, 'a') as f:
                f.write(trace)
            
        except Exception as e:
            cprint(f"⚠️  Error logging reasoning: {e}", "yellow")
    
    def _log_trade(self, decision: Dict, success: bool):
        """
        Log trade execution
        
        Saves to: src/data/nof1_agents/trades/YYYY-MM-DD_trades.json
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            date_str = datetime.now().strftime("%Y-%m-%d")
            
            log_file = self.log_dir / "trades" / f"{date_str}_trades.json"
            
            trade_log = {
                'timestamp': timestamp,
                'decision': decision.get('decision'),
                'symbol': decision.get('symbol'),
                'confidence': decision.get('confidence'),
                'position_size_usd': decision.get('position_size_usd'),
                'leverage': decision.get('leverage'),
                'entry_price': decision.get('entry_price'),
                'stop_loss': decision.get('stop_loss'),
                'take_profit': decision.get('take_profit'),
                'success': success
            }
            
            # Load existing trades
            trades = []
            if log_file.exists():
                with open(log_file, 'r') as f:
                    trades = json.load(f)
            
            # Append new trade
            trades.append(trade_log)
            
            # Save
            with open(log_file, 'w') as f:
                json.dump(trades, f, indent=2)
            
        except Exception as e:
            cprint(f"⚠️  Error logging trade: {e}", "yellow")
    
    def execute_decision(self, decision: Dict) -> bool:
        """Override to add trade logging"""
        success = super().execute_decision(decision)
        self._log_trade(decision, success)
        return success
def main():
    """
    Main entry point
    
    Run with:
        python src/nof1_agents/agents/deepseek_trader.py
    
    All settings are read from CONFIG (agent_configs.py).
    To change settings, edit agent_configs.py or pass arguments.
    """
    cprint("\n" + "="*60, "white", "on_blue")
    cprint("🌙 DeepSeek Nof1 Trader - Alpha Arena Style", "white", "on_blue", attrs=['bold'])
    cprint("="*60, "white", "on_blue")
    cprint("📝 All settings from: agent_configs.py → CONFIG", "white", "on_blue")
    cprint("="*60, "white", "on_blue")
    
    # Initialize trader with CONFIG defaults
    # No arguments needed - everything comes from CONFIG!
    trader = DeepSeekTrader()
    
    # Run trading loop
    trader.run()
if __name__ == "__main__":
    main()
