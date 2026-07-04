"""驱动脚本：对指定币种在 1分钟/5分钟/30分钟三个周期上跑 SMC 信号回测。

和 run_backtest.py（缠论买卖点）保持同一套方法论：
- 同一份 backtest.run_backtest / evaluate_trades 撮合与统计基础设施
- 按信号"类别子集"拆解胜率（对照 LOGIC_ANALYSIS.md 里"按买卖点类型拆解胜率"的思路），
  因为 SMCEngine 一次性产出 FVG / OB / BOS / CHoCH 四类信号，不加区分地全部丢进去
  "逢信号必反手"会严重高估交易频率、也掩盖不同信号类别本身的质量差异。
- 额外跑随机基线蒙特卡洛显著性检验（复用 random_baseline.py），回答"这比乱猜强吗"。
"""
import argparse
import json
import os
import time

from chanlun_engine import load_bars
from smc_engine import SMCEngine, SMCPoint
from backtest import run_backtest, evaluate_trades, trades_to_df
from random_baseline import random_baseline_test, significance_report

SUBSETS = {
    "全部信号": None,
    "订单块OB": {"看涨OB", "看跌OB"},
    "CHoCH反转": {"CHoCH多", "CHoCH空"},
    "OB+CHoCH": {"看涨OB", "看跌OB", "CHoCH多", "CHoCH空"},
    "FVG失衡区": {"看涨FVG", "看跌FVG"},
    "BOS延续": {"BOS多", "BOS空"},
}


def _filter(points, exec_bar_ids, kinds):
    if kinds is None:
        return points, exec_bar_ids
    pairs = [(p, e) for p, e in zip(points, exec_bar_ids) if p.kind in kinds]
    if not pairs:
        return [], []
    ps, es = zip(*pairs)
    return list(ps), list(es)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="PEPEUSDT")
    ap.add_argument("--start", default="2025-06")
    ap.add_argument("--end", default="2026-05")
    ap.add_argument("--fee", type=float, default=0.001)
    ap.add_argument("--freqs", nargs="+", default=["1m", "5m", "30m"])
    ap.add_argument("--swing_window", type=int, default=5)
    ap.add_argument("--n_sims", type=int, default=300)
    args = ap.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    result_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(result_dir, exist_ok=True)

    summary_path = os.path.join(result_dir, f"{args.symbol}_smc_summary.json")
    summary = {}
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

    for freq in args.freqs:
        parquet_path = os.path.join(data_dir, f"{args.symbol}-{freq}-{args.start}_to_{args.end}.parquet")
        print(f"\n=== {args.symbol} {freq} (SMC) ===")
        t0 = time.time()
        bars = load_bars(parquet_path, args.symbol, freq)
        print(f"K线数量: {len(bars)}")

        engine = SMCEngine(bars, swing_window=args.swing_window, volume_ma_window=20, fvg_vol_mult=1.5)
        all_points, all_exec_ids = engine.run()
        print(f"信号总数: {len(all_points)}  耗时: {time.time()-t0:.1f}s")

        from collections import Counter
        kind_counter = Counter(p.kind for p in all_points)
        print(f"信号类型分布: {dict(kind_counter)}")

        freq_result = {"K线数量": len(bars), "信号类型分布": dict(kind_counter), "子集回测": {}}

        for subset_name, kinds in SUBSETS.items():
            pts, ids = _filter(all_points, all_exec_ids, kinds)
            trades = run_backtest(bars, pts, ids, fee_rate=args.fee)
            stats = evaluate_trades(trades)
            stats["信号总数"] = len(pts)

            # 随机基线显著性检验：交易笔数太少时蒙特卡洛意义不大，跳过
            if stats["交易笔数"] >= 10:
                bwr, bcr = random_baseline_test(
                    bars, stats["交易笔数"], fee_rate=args.fee, n_sims=args.n_sims, seed=42
                )
                stats["随机基线显著性"] = significance_report(
                    stats["胜率"], stats["累计收益率"], bwr, bcr
                )

            freq_result["子集回测"][subset_name] = stats
            print(f"  [{subset_name}] 信号={len(pts)} 交易={stats['交易笔数']} 胜率={stats['胜率']} 收益={stats['累计收益率']}")

            if pts:
                df = trades_to_df(trades)
                csv_path = os.path.join(result_dir, f"{args.symbol}_{freq}_smc_{subset_name}_trades.csv")
                df.to_csv(csv_path, index=False)

        summary[freq] = freq_result

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n汇总结果已保存: {summary_path}")


if __name__ == "__main__":
    main()
