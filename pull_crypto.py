import yfinance as yf
import pandas as pd

# ========== 配置 ==========
SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD']  # yfinance的交易对格式
TIMEFRAME = '5m'
PERIOD = '60d'        # yfinance 5分钟级别最大支持拉取最近 60 天的数据
OUTPUT_DIR = './'
# =========================

for symbol in SYMBOLS:
    print(f"拉取 {symbol} {TIMEFRAME}...")
    try:
        # 下载数据
        df = yf.download(symbol, period=PERIOD, interval=TIMEFRAME, progress=False)
        if df.empty:
            print(f"  ✗ 未获取到 {symbol} 的数据")
            continue
            
        # 展平多层索引（如果出现的话）
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 重置索引，将 Datetime 作为一列
        df.reset_index(inplace=True)
        
        # 重命名列以匹配 ccxt 输出风格
        df.rename(columns={'Datetime': 'time', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
        
        # 整理所需列
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
        
        fname = f"{OUTPUT_DIR}{symbol.replace('-', '_').lower()}_{TIMEFRAME}.csv"
        df.to_csv(fname, index=False)
        print(f"  ✓ {fname} | {len(df)} 条 | {df['time'].min()} ~ {df['time'].max()}")
    except Exception as e:
        print(f"  ✗ 失败: {e}")

print("\n搞定。CSV文件已生成。")