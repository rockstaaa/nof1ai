"""
🌙 Account Formatter for Pure LLM Agents
Formats account balance, performance, and risk metrics
"""

from typing import Dict
from datetime import datetime, timedelta
import pandas as pd
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)
class AccountFormatter:
    """
    Formats account data for LLM consumption
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
            raise ValueError(f"Unsupported exchange for AccountFormatter: {exchange}")

        self.nf = nf
        
        # Track starting balance for return calculation
        self.start_balance = None
        self.start_time = None
    
    def get_account_data(self) -> Dict:
        """
        Get comprehensive account data
        
        Returns:
            {
                'total_return_percent': 66.69,
                'available_cash': 97.8,
                'account_value': 16669.35,
                'sharpe_ratio': 0.224,
                'equity': 16669.35,
                'margin_used': 5000.0,
                'margin_available': 11669.35,
                'total_pnl': 6669.35,
                'total_pnl_percent': 66.69
            }
        """
        try:
            # Get current account value
            if self.exchange == 'upstox':
                acct = self.nf.get_account_balance()
                account_value = acct.get('account_value_inr', acct.get('account_value', 0))
                available = acct.get('available_cash_inr', acct.get('available_cash', 0))
            elif self.exchange in ['hyperliquid', 'aster']:
                account_value = self._get_futures_account_value()
                available = 0
            else:
                account_value = self._get_spot_account_value()
                available = account_value
            
            # Initialize starting balance if not set
            if self.start_balance is None:
                self.start_balance = account_value
                self.start_time = datetime.now()
            
            # Calculate returns
            total_pnl = account_value - self.start_balance
            total_return_percent = (total_pnl / self.start_balance * 100) if self.start_balance > 0 else 0
            
            # Calculate Sharpe ratio (simplified)
            sharpe_ratio = self._calculate_sharpe_ratio()
            
            # Get margin info
            margin_info = self._get_margin_info() if self.exchange != 'upstox' else {'available': available, 'used': 0, 'unrealized_pnl': 0}

            return {
                'total_return_percent': round(total_return_percent, 2),
                'available_cash': round(margin_info.get('available', available), 2),
                'account_value': round(account_value, 2),
                'sharpe_ratio': round(sharpe_ratio, 3),
                'equity': round(account_value, 2),
                'margin_used': round(margin_info.get('used', 0), 2),
                'margin_available': round(margin_info.get('available', 0), 2),
                'total_pnl': round(total_pnl, 2),
                'total_pnl_percent': round(total_return_percent, 2),
                'unrealized_pnl': round(margin_info.get('unrealized_pnl', 0), 2),
                'currency': 'INR' if self.exchange == 'upstox' else 'USD'
            }
            
        except Exception as e:
            print(f"❌ Error getting account data: {e}")
            return {
                'total_return_percent': 0.0,
                'available_cash': 0.0,
                'account_value': 0.0,
                'sharpe_ratio': 0.0
            }
    
    def _get_futures_account_value(self) -> float:
        """Get account value from HyperLiquid or Aster"""
        try:
            if self.exchange == 'aster':
                balance_dict = self.nf.get_account_balance()
                return balance_dict.get('total_equity', 0)
            else:  # HyperLiquid
                account = self.nf._get_account_from_env()
                if not account:
                    print("❌ No account found")
                    return 0.0
                
                # Get user state to access all balance information
                # Use the actual wallet address for balance queries, not the API wallet
                import os
                actual_wallet_address = os.getenv('HYPER_LIQUID_MASTER_ADDRESS')
                if not actual_wallet_address:
                    raise ValueError("HYPER_LIQUID_MASTER_ADDRESS not found in environment")
                print(f"🔍 DEBUG: Querying account address: {actual_wallet_address}")
                print(f"🔍 DEBUG: API wallet address: {account.address}")
                print(f"🔍 DEBUG: Account type: {type(account)}")
                if hasattr(account, 'public_key'):
                    print(f"🔍 DEBUG: Public key: {account.public_key}")
                
                info = self.nf.Info(self.nf.constants.MAINNET_API_URL, skip_ws=True)
                user_state = info.user_state(actual_wallet_address)
                
                # DEBUG: Print the entire user_state to see what we're getting
                print(f"🔍 DEBUG: Full user_state keys: {list(user_state.keys())}")
                if "marginSummary" in user_state:
                    print(f"🔍 DEBUG: marginSummary keys: {list(user_state['marginSummary'].keys())}")
                    print(f"🔍 DEBUG: marginSummary values: {user_state['marginSummary']}")
                print(f"🔍 DEBUG: withdrawable: {user_state.get('withdrawable', 'NOT_FOUND')}")
                print(f"🔍 DEBUG: assetPositions count: {len(user_state.get('assetPositions', []))}")
                
                # For trading, we want total account equity, not just withdrawable
                # This includes margin used in positions
                if "marginSummary" in user_state and "accountValue" in user_state["marginSummary"]:
                    total_equity = float(user_state["marginSummary"]["accountValue"])
                    print(f"💰 HyperLiquid total equity (for trading): ${total_equity:,.2f}")
                    return total_equity
                else:
                    # Fallback to withdrawable if marginSummary not available
                    withdrawable = float(user_state.get("withdrawable", 0))
                    print(f"💰 HyperLiquid withdrawable balance (fallback): ${withdrawable:,.2f}")
                    return withdrawable
        except Exception as e:
            print(f"❌ Error getting futures account value: {e}")
            import traceback
            traceback.print_exc()
            return 0.0
    
    def _get_spot_account_value(self) -> float:
        """Get account value from Solana (spot)"""
        try:
            # Solana support disabled - focus on HyperLiquid
            print("⚠️ Solana spot trading not supported in standalone nof1-agents")
            return 0.0
            
        except Exception as e:
            print(f"❌ Error getting spot account value: {e}")
            return 0.0
    
    def _get_margin_info(self) -> Dict:
        """Get margin usage information"""
        try:
            if self.exchange == 'aster':
                balance_dict = self.nf.get_account_balance()
                return {
                    'available': balance_dict.get('available', 0),
                    'used': balance_dict.get('total_equity', 0) - balance_dict.get('available', 0),
                    'unrealized_pnl': balance_dict.get('unrealized_pnl', 0)
                }
            elif self.exchange == 'hyperliquid':
                # Get account state from HyperLiquid API
                account = self.nf._get_account_from_env()
                if not account:
                    return {'available': 0, 'used': 0, 'unrealized_pnl': 0}
                
                # Get user state to access detailed balance info
                # Use the actual wallet address for balance queries, not the API wallet
                import os
                actual_wallet_address = os.getenv('HYPER_LIQUID_MASTER_ADDRESS')
                if not actual_wallet_address:
                    raise ValueError("HYPER_LIQUID_MASTER_ADDRESS not found in environment")
                info = self.nf.Info(self.nf.constants.MAINNET_API_URL, skip_ws=True)
                user_state = info.user_state(actual_wallet_address)
                
                # Extract balance information for trading
                withdrawable = float(user_state.get("withdrawable", 0))
                total_equity = float(user_state.get("marginSummary", {}).get("accountValue", 0))
                margin_used = float(user_state.get("marginSummary", {}).get("totalMarginUsed", 0))
                unrealized_pnl = float(user_state.get("marginSummary", {}).get("totalUnrealizedPnl", 0))
                
                # For trading, available = total_equity - margin_used (what's available for new positions)
                available_for_trading = total_equity - margin_used
                
                print(f"💰 HyperLiquid margin info: total_equity=${total_equity:,.2f}, margin_used=${margin_used:,.2f}, available_for_trading=${available_for_trading:,.2f}, unrealized_pnl=${unrealized_pnl:,.2f}")
                
                return {
                    'available': available_for_trading,  # What's available for new positions
                    'used': margin_used,  # Margin used in existing positions
                    'unrealized_pnl': unrealized_pnl
                }
            else:
                # Solana - no margin concept
                account_value = self._get_spot_account_value()
                return {
                    'available': account_value,
                    'used': 0,
                    'unrealized_pnl': 0
                }
                
        except Exception as e:
            print(f"❌ Error getting margin info: {e}")
            return {'available': 0, 'used': 0, 'unrealized_pnl': 0}
    
    def _calculate_sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio
        
        Sharpe = (Average Return - Risk-Free Rate) / Std Dev of Returns
        
        Uses historical returns from performance log if available
        """
        try:
            # Try to load historical returns from performance log
            performance_file = Path(__file__).parent.parent.parent / "src" / "data" / "nof1-agents" / "performance" / "daily_returns.csv"
            
            if performance_file.exists():
                # Load historical returns
                df = pd.read_csv(performance_file)
                if 'daily_return' in df.columns and len(df) > 1:
                    returns = df['daily_return'].dropna()
                    
                    if len(returns) > 1:
                        # Calculate Sharpe ratio
                        mean_return = returns.mean()
                        std_return = returns.std()
                        
                        # Risk-free rate (assume 0% for simplicity)
                        risk_free_rate = 0.0
                        
                        if std_return > 0:
                            sharpe = (mean_return - risk_free_rate) / std_return
                            return sharpe
            
            # Fallback: Simple calculation based on current performance
            if self.start_balance and self.start_balance > 0:
                current_value = self._get_futures_account_value() if self.exchange in ['hyperliquid', 'aster'] else self._get_spot_account_value()
                total_return = (current_value - self.start_balance) / self.start_balance
                
                # Estimate Sharpe based on return and time elapsed
                if self.start_time:
                    days_elapsed = (datetime.now() - self.start_time).days
                    if days_elapsed > 0:
                        daily_return = total_return / days_elapsed
                        # Estimate volatility (simplified)
                        estimated_volatility = abs(daily_return) * 2  # Rough estimate
                        if estimated_volatility > 0:
                            return daily_return / estimated_volatility
            
            # Default fallback
            return 0.0
            
        except Exception as e:
            print(f"❌ Error calculating Sharpe ratio: {e}")
            return 0.0
    
    def reset_starting_balance(self, balance: float = None):
        """Reset the starting balance for return calculations"""
        if balance is None:
            if self.exchange in ['hyperliquid', 'aster']:
                balance = self._get_futures_account_value()
            else:
                balance = self._get_spot_account_value()
        
        self.start_balance = balance
        self.start_time = datetime.now()
        print(f"✅ Starting balance reset to ${balance:,.2f}")
    
    def get_risk_metrics(self) -> Dict:
        """
        Get risk metrics
        
        Returns:
            {
                'max_drawdown': -0.15,
                'win_rate': 0.65,
                'profit_factor': 1.8,
                'risk_adjusted_return': 2.5
            }
        """
        # TODO: Implement proper risk metrics calculation
        return {
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'risk_adjusted_return': 0.0
        }
