"""多级别联立回测："大级别定方向，小级别找精确买卖点"

级联关系：30分钟（大级别，定方向）-> 5分钟（用 30分钟方向过滤自己的买卖点）
          5分钟（大级别，定方向）  -> 1分钟（用 5分钟方向过滤自己的买卖点）

过滤规则见 chanlun_engine.TrendTimeline.allows：大级别笔向上时只放行小级别买点，
大级别笔向下时只放行小级别卖点（顺大级别方向而为，是缠论"多级别联立"最基础的用法）。

因果性：TrendTimeline 查询任意时刻 dt 的大级别方向时，只使用"起点时间 <= dt"的大级别笔，
不会用到 dt 之后才形成的大级别笔，因此不引入未来函数（详见 TrendTimeline 类的说明）。
"""
import argparse
import json
import os
import time

from chanlun_engine import ChanEngine, TrendTimeline, load_bars
from backtest import run_backtest, evaluate_trades, trades_to_df

POLL_CHUNK = {"1m": 500, "5m": 200, "30m": 50}
WARMUP = {"1m": 300, "5m": 300, "30m": 150}

CASCADE = [("30m", "5m"), ("5m", "1m")]  # (大级别, 小级别)


def run_single(freq, bars):
    safety_margin = 2
    while True:
        try:
            engine = ChanEngine(bars)
            points, exec_bar_ids, c, verify_stats, confirmed_bis = engine.run(
                warmup=WARMUP[freq], poll_chunk=POLL_CHUNK[freq], safety_margin=safety_margin
            )
            return points, exec_bar_ids, c, verify_stats, confirmed_bis
        except RuntimeError as e:
            print(f"[{freq} 自证失败，safety_margin={safety_margin}] {e}")
            safety_margin += 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="PEPEUSDT")
    ap.add_argument("--start", default="2025-06")
    ap.add_argument("--end", default="2026-05")
    ap.add_argument("--fee", type=float, default=0.001)
    args = ap.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    result_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(result_dir, exist_ok=True)

    all_freqs = sorted({f for pair in CASCADE for f in pair})
    cache = {}
    for freq in all_freqs:
        parquet_path = os.path.join(data_dir, f"{args.symbol}-{freq}-{args.start}_to_{args.end}.parquet")
        print(f"\n=== 单周期计算：{args.symbol} {freq} ===")
        t0 = time.time()
        bars = load_bars(parquet_path, args.symbol, freq)
        points, exec_bar_ids, c, verify_stats, confirmed_bis = run_single(freq, bars)
        print(f"K线={len(bars)} 笔={len(c.bi_list)} 信号={len(points)} "
              f"耗时={time.time()-t0:.1f}s 自证={verify_stats}")
        cache[freq] = dict(bars=bars, points=points, exec_bar_ids=exec_bar_ids, confirmed_bis=confirmed_bis)

    summary = {}
    for large_freq, small_freq in CASCADE:
        print(f"\n=== 多级别联立：{large_freq}(定方向) -> {small_freq}(找买卖点) ===")
        timeline = TrendTimeline(cache[large_freq]["confirmed_bis"])

        small = cache[small_freq]
        filtered_points, filtered_exec_ids = [], []
        for p, bid in zip(small["points"], small["exec_bar_ids"]):
            if timeline.allows(p):
                filtered_points.append(p)
                filtered_exec_ids.append(bid)

        print(f"{small_freq} 原始信号数: {len(small['points'])}  联立过滤后: {len(filtered_points)}")

        trades = run_backtest(small["bars"], filtered_points, filtered_exec_ids, fee_rate=args.fee)
        stats = evaluate_trades(trades)
        stats["原始信号数"] = len(small["points"])
        stats["联立过滤后信号数"] = len(filtered_points)
        stats["大级别"] = large_freq
        stats["小级别"] = small_freq
        print(json.dumps(stats, ensure_ascii=False, indent=2))

        key = f"{small_freq}_ml_{large_freq}"
        summary[key] = stats

        df = trades_to_df(trades)
        csv_path = os.path.join(result_dir, f"{args.symbol}_{key}_trades.csv")
        df.to_csv(csv_path, index=False)
        print(f"交易明细已保存: {csv_path}")

    summary_path = os.path.join(result_dir, f"{args.symbol}_multilevel_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n多级别联立汇总结果已保存: {summary_path}")


if __name__ == "__main__":
    main()
