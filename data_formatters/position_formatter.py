"""
🌙 Position Formatter for Pure LLM Agents
Formats current positions and P&L data
"""

from typing import Dict, List, Optional
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)
class PositionFormatter:
    """
    Formats position data for LLM consumption
    Matches the format from user's screenshots
    """
    
    def __init__(self, exchange='hyperliquid'):
        """
        Initialize formatter
        
        Args:
            exchange: 'hyperliquid', 'aster', or 'solana'
        """
        self.exchange = exchange
        
        # Import appropriate exchange adapter
        if exchange == 'hyperliquid':
            from exchange import nice_funcs_hyperliquid as nf
        elif exchange == 'upstox':
            from exchange import upstox_marketdata as nf
        else:
            raise ValueError(f"Unsupported exchange for PositionFormatter: {exchange}")

        self.nf = nf
    
    def get_all_positions(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        Get all open positions formatted for LLM
        
        Args:
            symbols: List of symbols to check (None = check all)
        
        Returns:
            Dict mapping symbol to position info:
            {
                'BTC': {
                    'quantity': 1.96,
                    'entry_price': 107993.0,
                    'current_price': 111100.5,
                    'liquidation_price': 103988.99,
                    'unrealized_pnl': 6090.7,
                    'leverage': 20,
                    'exit_plan': {...},
                    'confidence': 0.88,
                    'risk_usd': 403.75,
                    'notional_usd': 217756.98
                }
            }
        """
        positions = {}
        
        try:
            if self.exchange in ['hyperliquid', 'aster']:
                # Get positions from futures exchange
                positions = self._get_perpetuals_positions(symbols)
            elif self.exchange == 'upstox':
                positions = self._get_perpetuals_positions(symbols)
            else:
                # Solana - get token balances
                positions = self._get_spot_positions(symbols)
            
            return positions
            
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            return {}
    
    def _get_perpetuals_positions(self, symbols: Optional[List[str]] = None) -> Dict:
        """Get positions from HyperLiquid or Aster"""
        positions = {}
        
        try:
            # Get all positions if symbols not specified
            if self.exchange == 'upstox':
                all_pos = self.nf.get_all_positions() or {}
                # If symbols not specified, use all keys
                if symbols is None:
                    symbols = list(all_pos.keys())

                for symbol in symbols:
                    p = all_pos.get(symbol)
                    if not p:
                        continue
                    qty = p.get('quantity', 0)
                    avg = p.get('avg_price', p.get('entry_price', 0))
                    cur = p.get('current_price', self.nf.get_current_price(symbol))
                    unrealized = p.get('unrealized_pnl', (cur - avg) * qty)

                    positions[symbol] = {
                        'quantity': abs(qty),
                        'side': 'LONG' if qty > 0 else 'SHORT',
                        'entry_price': avg,
                        'current_price': cur,
                        'liquidation_price': 0,
                        'unrealized_pnl': unrealized,
                        'leverage': 1,
                        'exit_plan': self._get_exit_plan(symbol, {'quantity': qty, 'entry_price': avg}),
                        'confidence': 0.0,
                        'risk_usd': abs((cur * qty) * 0.02),
                        'notional_usd': abs(cur * qty),
                        'pnl_percentage': (unrealized / (abs(avg * qty) + 1e-9)) * 100 if avg and qty else 0,
                    }
                return positions

            # legacy/hyperliquid path
            if symbols is None:
                if hasattr(self.nf, 'get_all_positions'):
                    all_pos = self.nf.get_all_positions()
                    symbols = list(all_pos.keys())
                else:
                    return {}

            for symbol in symbols:
                # Get account info first
                account = self.nf._get_account_from_env()
                if not account:
                    print(f"❌ Could not get account info for {symbol}")
                    continue

                pos_result = self.nf.get_position(symbol, account)
                # get_position returns: (positions_list, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, is_long)
                positions_list, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, is_long = pos_result

                if im_in_pos and pos_size != 0:
                    # Format position data from tuple values
                    quantity = float(pos_size)
                    entry_price = float(entry_px)
                    current_price = entry_price  # We'll need to get current price separately
                    unrealized_pnl = float(pnl_perc) / 100  # Convert percentage to decimal
                    leverage = 1  # Default leverage, could be extracted from positions[0] if needed

                    # Calculate notional value
                    notional_usd = abs(quantity) * current_price

                    # Calculate liquidation price (estimate)
                    liquidation_price = self._estimate_liquidation_price(
                        entry_price,
                        leverage,
                        is_long=(quantity > 0)
                    )

                    # Format position
                    positions[symbol] = {
                        'quantity': abs(quantity),
                        'side': 'LONG' if quantity > 0 else 'SHORT',
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'liquidation_price': liquidation_price,
                        'unrealized_pnl': unrealized_pnl,
                        'leverage': leverage,
                        'exit_plan': self._get_exit_plan(symbol, {'quantity': quantity, 'entry_price': entry_price}),
                        'confidence': 0.0,  # Default confidence
                        'risk_usd': abs(notional_usd / leverage * 0.02),  # 2% of margin
                        'notional_usd': notional_usd,
                        'pnl_percentage': unrealized_pnl * 100,  # Convert to percentage
                    }
            
            return positions
            
        except Exception as e:
            print(f"❌ Error getting perpetuals positions: {e}")
            return {}
    
    def _get_spot_positions(self, symbols: Optional[List[str]] = None) -> Dict:
        """Get spot positions (Solana)"""
        positions = {}
        
        try:
            # Solana support disabled - focus on HyperLiquid
            print("⚠️ Solana spot trading not supported in standalone nof1-agents")
            return {}
            
        except Exception as e:
            print(f"❌ Error getting spot positions: {e}")
            return {}
    
    def _estimate_liquidation_price(self, entry_price: float, leverage: int, is_long: bool) -> float:
        """
        Estimate liquidation price
        
        Formula:
        - Long: liq_price = entry_price * (1 - 1/leverage * 0.9)
        - Short: liq_price = entry_price * (1 + 1/leverage * 0.9)
        
        0.9 factor accounts for maintenance margin
        """
        if leverage <= 1:
            return 0
        
        margin_fraction = 1 / leverage * 0.9
        
        if is_long:
            return entry_price * (1 - margin_fraction)
        else:
            return entry_price * (1 + margin_fraction)
    
    def _get_exit_plan(self, symbol: str, position: Dict) -> Dict:
        """
        Get or create exit plan for position
        
        Returns:
            {
                'invalidation_condition': 'Price closes below X',
                'profit_target': <price>,
                'stop_loss': <price>
            }
        """
        try:
            # Check if exit plan already exists in position
            if 'exit_plan' in position:
                return position['exit_plan']
            
            # Create default exit plan
            entry_price = position.get('entry_price', 0)
            current_price = position.get('mark_price', 0) or position.get('current_price', 0)
            quantity = position.get('position_amount', 0)
            is_long = quantity > 0
            
            if is_long:
                # Long position
                profit_target = current_price * 1.05  # +5%
                stop_loss = entry_price * 0.95  # -5%
                invalidation = f"4-hour close below ${stop_loss:,.2f}"
            else:
                # Short position
                profit_target = current_price * 0.95  # -5%
                stop_loss = entry_price * 1.05  # +5%
                invalidation = f"4-hour close above ${stop_loss:,.2f}"
            
            return {
                'invalidation_condition': invalidation,
                'profit_target': profit_target,
                'stop_loss': stop_loss
            }
            
        except Exception as e:
            print(f"❌ Error creating exit plan: {e}")
            return {}
    
    def get_position_summary(self) -> Dict:
        """
        Get summary of all positions
        
        Returns:
            {
                'total_positions': 3,
                'total_notional': 500000.0,
                'total_unrealized_pnl': 12500.0,
                'long_positions': 2,
                'short_positions': 1,
                'total_risk_usd': 5000.0
            }
        """
        positions = self.get_all_positions()
        
        summary = {
            'total_positions': len(positions),
            'total_notional': sum(p['notional_usd'] for p in positions.values()),
            'total_unrealized_pnl': sum(p['unrealized_pnl'] for p in positions.values()),
            'long_positions': sum(1 for p in positions.values() if p['side'] == 'LONG'),
            'short_positions': sum(1 for p in positions.values() if p['side'] == 'SHORT'),
            'total_risk_usd': sum(p['risk_usd'] for p in positions.values()),
        }
        
        return summary
