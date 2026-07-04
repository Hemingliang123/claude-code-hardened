"""驱动脚本：对指定币种在 1分钟/5分钟/30分钟三个周期上分别跑一遍缠论买卖点回测"""
import argparse
import json
import os
import time

from chanlun_engine import ChanEngine, load_bars
from backtest import run_backtest, evaluate_trades, trades_to_df

POLL_CHUNK = {"1m": 500, "5m": 200, "30m": 50}
WARMUP = {"1m": 300, "5m": 300, "30m": 150}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="PEPEUSDT")
    ap.add_argument("--start", default="2025-06")
    ap.add_argument("--end", default="2026-05")
    ap.add_argument("--fee", type=float, default=0.001)
    ap.add_argument("--freqs", nargs="+", default=["1m", "5m", "30m"])
    args = ap.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    result_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(result_dir, exist_ok=True)

    summary_path = os.path.join(result_dir, f"{args.symbol}_summary.json")
    summary = {}
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

    for freq in args.freqs:
        parquet_path = os.path.join(data_dir, f"{args.symbol}-{freq}-{args.start}_to_{args.end}.parquet")
        print(f"\n=== {args.symbol} {freq} ===")
        t0 = time.time()
        bars = load_bars(parquet_path, args.symbol, freq)
        print(f"K线数量: {len(bars)}")

        # 若运行时自证发现 safety_margin 不够（说明某一笔被回退的深度超出预期），
        # 自动加大冗余重跑，直到全年数据都通过自证为止，绝不带着未验证的假设出结果。
        safety_margin = 2
        while True:
            try:
                engine = ChanEngine(bars)
                points, exec_bar_ids, c, verify_stats, _confirmed_bis = engine.run(
                    warmup=WARMUP[freq], poll_chunk=POLL_CHUNK[freq], safety_margin=safety_margin
                )
                break
            except RuntimeError as e:
                print(f"[自证失败，safety_margin={safety_margin}] {e}")
                safety_margin += 2
                print(f"提高 safety_margin 至 {safety_margin} 后重试...")
        print(f"笔数量: {len(c.bi_list)}  信号数量: {len(points)}  耗时: {time.time()-t0:.1f}s")
        print(f"未来函数自证通过: {verify_stats}")

        trades = run_backtest(bars, points, exec_bar_ids, fee_rate=args.fee)
        stats = evaluate_trades(trades)
        stats["笔总数"] = len(c.bi_list)
        stats["信号总数"] = len(points)
        stats["K线数量"] = len(bars)
        stats["未来函数自证"] = verify_stats
        print(json.dumps(stats, ensure_ascii=False, indent=2))

        df = trades_to_df(trades)
        csv_path = os.path.join(result_dir, f"{args.symbol}_{freq}_trades.csv")
        df.to_csv(csv_path, index=False)
        print(f"交易明细已保存: {csv_path}")

        summary[freq] = stats

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n汇总结果已保存: {summary_path}")


if __name__ == "__main__":
    main()
