import yfinance as yf
import pandas as pd
import numpy as np

def remove_inclusion(df: pd.DataFrame) -> pd.DataFrame:
    """严格处理K线包含关系，同时保留合并后的时间戳和收盘价"""
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    timestamps = df['timestamp'].values
    n = len(df)
    
    if n < 3:
        return df

    direction = 1 if highs[1] >= highs[0] and lows[1] >= lows[0] else -1

    new_highs = [highs[0]]
    new_lows = [lows[0]]
    new_closes = [closes[0]]
    new_timestamps = [timestamps[0]]

    for i in range(1, n):
        h1, l1 = new_highs[-1], new_lows[-1]
        h2, l2, c2, t2 = highs[i], lows[i], closes[i], timestamps[i]

        # 判断包含关系: (h2 >= h1 and l2 <= l1) or (h2 <= h1 and l2 >= l1)
        if (h2 >= h1 and l2 <= l1) or (h2 <= h1 and l2 >= l1):
            if direction == 1:  # 向上合并：取高高，低取高
                new_highs[-1] = max(h1, h2)
                new_lows[-1] = max(l1, l2)
            else:  # 向下合并：取低低，高取低
                new_highs[-1] = min(h1, h2)
                new_lows[-1] = min(l1, l2)
            new_closes[-1] = c2 # 保留最新的收盘价
            new_timestamps[-1] = t2 # 保留最新的时间戳
        else:
            if h2 > h1:
                direction = 1
            elif h2 < h1:
                direction = -1
            new_highs.append(h2)
            new_lows.append(l2)
            new_closes.append(c2)
            new_timestamps.append(t2)

    res = pd.DataFrame({
        'timestamp': new_timestamps,
        'high': new_highs,
        'low': new_lows,
        'close': new_closes
    })
    return res

def find_fractals(df: pd.DataFrame) -> pd.DataFrame:
    """寻找顶分型与底分型"""
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)
    fractals = np.zeros(n, dtype=int)

    for i in range(1, n - 1):
        h_prev, h_curr, h_next = highs[i - 1], highs[i], highs[i + 1]
        l_prev, l_curr, l_next = lows[i - 1], lows[i], lows[i + 1]

        # 顶分型判定
        if h_curr > h_prev and h_curr > h_next and l_curr > l_prev and l_curr > l_next:
            fractals[i] = 1
        # 底分型判定
        elif l_curr < l_prev and l_curr < l_next and h_curr < h_prev and h_curr < h_next:
            fractals[i] = -1

    df['fractal_type'] = fractals
    return df

def fetch_yfinance_data(symbol='BTC-USD', interval='30m', period='60d'):
    """通过 yfinance 获取数据 (注意：yfinance 对30m数据最多只支持最近60天)"""
    print(f"正在获取 {symbol} 最近 {period} 的 {interval} 数据...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        print(f"未能获取到 {symbol} 的数据")
        return pd.DataFrame()
    
    df = df.reset_index()
    # Rename columns to lowercase
    df = df.rename(columns={'Datetime': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close'})
    if 'timestamp' not in df.columns and 'Date' in df.columns:
        df = df.rename(columns={'Date': 'timestamp'})
        
    return df

def run_fractal_backtest(df, symbol):
    """
    基于最基础的顶底分型进行无脑回测
    买入：确认底分型形成（即第i+1根K线收盘时）
    卖出：确认顶分型形成（即第i+1根K线收盘时）
    """
    capital = 10000.0
    initial_capital = capital
    position = 0.0
    
    trades = []
    
    for i in range(1, len(df)-1):
        if df['fractal_type'].iloc[i-1] == -1 and position == 0:
            # 形成底分型，买入
            buy_price = df['close'].iloc[i]
            position = capital / buy_price
            capital = 0
            trades.append({'time': df['timestamp'].iloc[i], 'type': 'buy', 'price': buy_price})
        
        elif df['fractal_type'].iloc[i-1] == 1 and position > 0:
            # 形成顶分型，卖出
            sell_price = df['close'].iloc[i]
            capital = position * sell_price
            position = 0
            trades.append({'time': df['timestamp'].iloc[i], 'type': 'sell', 'price': sell_price})

    # 强制平仓
    if position > 0:
        final_price = df['close'].iloc[-1]
        capital = position * final_price
        trades.append({'time': df['timestamp'].iloc[-1], 'type': 'sell', 'price': final_price})

    total_trades = len(trades) // 2
    win_trades = 0
    
    for j in range(0, len(trades)-1, 2):
        if trades[j+1]['price'] > trades[j]['price']:
            win_trades += 1
            
    win_rate = win_trades / total_trades if total_trades > 0 else 0
    roi = (capital - initial_capital) / initial_capital * 100
    
    buy_hold_return = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100

    print(f"\n[{symbol}] 回测结果 (测试区间：60天 30分钟线):")
    print(f"初始资金: ${initial_capital}")
    print(f"最终资金: ${capital:.2f}")
    print(f"策略总收益率: {roi:.2f}%")
    print(f"同期死拿收益率: {buy_hold_return:.2f}%")
    print(f"交易次数: {total_trades} 次")
    print(f"胜率: {win_rate*100:.2f}%")

if __name__ == "__main__":
    symbols = ['BTC-USD', 'ETH-USD']
    
    for sym in symbols:
        # yfinance API limits 30m to 60 days max. 
        # I will use 60d 30m to verify the mathematical conditions and geometry logic.
        raw_df = fetch_yfinance_data(sym, interval='30m', period='60d')
        if len(raw_df) == 0:
            continue
            
        # 缠论几何拓扑计算
        cleaned_df = remove_inclusion(raw_df)
        print(f"[{sym}] 处理包含关系后，K线数量由 {len(raw_df)} 合并为 {len(cleaned_df)}")
        
        fractal_df = find_fractals(cleaned_df)
        
        # 回测执行
        run_fractal_backtest(fractal_df, sym)
