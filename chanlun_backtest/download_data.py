"""
下载 Binance 历史K线数据（月度归档，来自官方公开数据集 data.binance.vision）。

用途：为缠论回测提供 1年期的 1分钟 / 5分钟 / 30分钟真实历史行情数据。
数据来源：https://github.com/binance/binance-public-data (官方公开、免费、无需API Key)
"""
import io
import os
import sys
import zipfile
from datetime import datetime

import pandas as pd
import requests

BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"

KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "count",
    "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]


def month_range(start: str, end: str):
    """生成 [start, end] 闭区间内的 'YYYY-MM' 月份列表"""
    cur = datetime.strptime(start, "%Y-%m")
    stop = datetime.strptime(end, "%Y-%m")
    out = []
    while cur <= stop:
        out.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return out


def download_month(symbol: str, interval: str, month: str, out_dir: str) -> pd.DataFrame | None:
    url = f"{BASE_URL}/{symbol}/{interval}/{symbol}-{interval}-{month}.zip"
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        print(f"  [跳过] {url} -> HTTP {resp.status_code}")
        return None

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as f:
            raw = f.read()

    # Binance 部分归档文件第一行是表头，部分没有；这里做兼容处理
    first_line = raw.split(b"\n", 1)[0].decode("utf-8", errors="ignore")
    has_header = "open_time" in first_line
    df = pd.read_csv(
        io.BytesIO(raw),
        header=0 if has_header else None,
        names=None if has_header else KLINE_COLUMNS,
    )
    if has_header:
        df.columns = [c.strip() for c in df.columns]

    df = df[["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume"]].copy()
    # open_time 既可能是毫秒时间戳，也可能是微秒（新格式），做自适应处理
    ot = df["open_time"].astype("int64")
    unit = "us" if ot.iloc[0] > 10**14 else "ms"
    df["open_time"] = pd.to_datetime(ot, unit=unit, utc=True)
    ct = df["close_time"].astype("int64")
    unit2 = "us" if ct.iloc[0] > 10**14 else "ms"
    df["close_time"] = pd.to_datetime(ct, unit=unit2, utc=True)
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = df[col].astype(float)
    return df


def download_symbol_interval(symbol: str, interval: str, start: str, end: str, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{symbol}-{interval}-{start}_to_{end}.parquet")
    if os.path.exists(out_path):
        print(f"[已存在] {out_path}")
        return out_path

    frames = []
    for month in month_range(start, end):
        print(f"下载 {symbol} {interval} {month} ...")
        df = download_month(symbol, interval, month, out_dir)
        if df is not None:
            frames.append(df)

    if not frames:
        raise RuntimeError(f"未能下载到任何数据: {symbol} {interval}")

    full = pd.concat(frames, ignore_index=True)
    full = full.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)
    full.to_parquet(out_path, index=False)
    print(f"[完成] {out_path}  行数={len(full)}  区间={full['open_time'].iloc[0]} ~ {full['open_time'].iloc[-1]}")
    return out_path


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "PEPEUSDT"
    start = sys.argv[2] if len(sys.argv) > 2 else "2025-06"
    end = sys.argv[3] if len(sys.argv) > 3 else "2026-05"
    out_dir = os.path.join(os.path.dirname(__file__), "data")

    for interval in ["1m", "5m", "30m"]:
        download_symbol_interval(symbol, interval, start, end, out_dir)
