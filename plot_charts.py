import pandas as pd
import mplfinance as mpf

for symbol in ['btc_usd', 'eth_usd', 'sol_usd']:
    print(f"Generating chart for {symbol}...")
    df = pd.read_csv(f"{symbol}_5m.csv")
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Take the last 500 candles for a readable candlestick chart (about 41 hours)
    recent_df = df.tail(500)
    
    # Plotting
    mpf.plot(
        recent_df, 
        type='candle', 
        style='charles', 
        volume=True, 
        title=f'{symbol.upper().replace("_", "/")} 5m K-Line (Last 500 Bars)',
        savefig=f"{symbol}_5m_chart.png"
    )
print("Charts generated.")
