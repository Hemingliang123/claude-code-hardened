"""缠论买卖点 + SMC 订单块/CHoCH 确认层组合测试

思路：缠论买卖点定义的是"这里应该反转"，SMC 的订单块(OB)/结构反转(CHoCH)定义的是
"聪明钱在这个位置留下了痕迹"——两者理论出发点不同（缠论看的是笔/中枢的几何结构和
背驰，SMC 看的是量能失衡和结构突破），如果两者在同一个方向、同一段时间窗口内同时
给出信号，直觉上应该比单独任何一个更可信。本脚本只做最朴素的验证：

    只在"最近 window 根K线内出现过同方向 SMC OB/CHoCH 信号"的缠论买卖点才允许成交，
    其余缠论信号一律丢弃，其它撮合规则、手续费与原始回测完全一致。

因果性保证：判断"是否存在同方向 SMC 信号"时，只使用 SMC 信号自身 confirmed 的
bar_id <= 缠论信号的 exec_bar_id 的记录，绝不会用到缠论信号发现时刻之后才确认的
SMC 信号。
"""
import argparse
import json
import os
import time
import bisect

from chanlun_engine import ChanEngine, load_bars
from smc_engine import SMCEngine
from backtest import run_backtest, evaluate_trades, trades_to_df

POLL_CHUNK = {"1m": 500, "5m": 200, "30m": 50}
WARMUP = {"1m": 300, "5m": 300, "30m": 150}


def build_confluence_filter(smc_points, smc_exec_ids, window: int):
    """返回一个函数 has_confirm(side, exec_bar_id) -> bool"""
    buy_ids = sorted(e for p, e in zip(smc_points, smc_exec_ids) if p.side == "buy" and p.kind in ("看涨OB", "CHoCH多"))
    sell_ids = sorted(e for p, e in zip(smc_points, smc_exec_ids) if p.side == "sell" and p.kind in ("看跌OB", "CHoCH空"))

    def has_confirm(side, exec_bar_id):
        ids = buy_ids if side == "buy" else sell_ids
        lo = exec_bar_id - window
        pos = bisect.bisect_left(ids, lo)
        return pos < len(ids) and ids[pos] <= exec_bar_id

    return has_confirm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="PEPEUSDT")
    ap.add_argument("--start", default="2025-06")
    ap.add_argument("--end", default="2026-05")
    ap.add_argument("--fee", type=float, default=0.001)
    ap.add_argument("--freqs", nargs="+", default=["1m", "5m", "30m"])
    ap.add_argument("--window", type=int, default=30, help="确认窗口（根K线数）")
    args = ap.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    result_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(result_dir, exist_ok=True)

    summary = {}
    for freq in args.freqs:
        parquet_path = os.path.join(data_dir, f"{args.symbol}-{freq}-{args.start}_to_{args.end}.parquet")
        print(f"\n=== {args.symbol} {freq} 缠论+SMC组合 ===")
        t0 = time.time()
        bars = load_bars(parquet_path, args.symbol, freq)

        safety_margin = 2
        while True:
            try:
                engine = ChanEngine(bars)
                chan_points, chan_exec_ids, c, verify_stats, _ = engine.run(
                    warmup=WARMUP[freq], poll_chunk=POLL_CHUNK[freq], safety_margin=safety_margin
                )
                break
            except RuntimeError:
                safety_margin += 2

        smc_engine = SMCEngine(bars, swing_window=5, volume_ma_window=20, fvg_vol_mult=1.5)
        smc_points, smc_exec_ids = smc_engine.run()

        has_confirm = build_confluence_filter(smc_points, smc_exec_ids, args.window)

        filtered_points, filtered_ids = [], []
        for p, e in zip(chan_points, chan_exec_ids):
            if has_confirm(p.side, e):
                filtered_points.append(p)
                filtered_ids.append(e)

        print(
            f"缠论原始信号={len(chan_points)}  SMC信号={len(smc_points)}  "
            f"组合后保留信号={len(filtered_points)} ({len(filtered_points)/max(len(chan_points),1)*100:.1f}%)  "
            f"耗时={time.time()-t0:.1f}s"
        )

        trades_base = run_backtest(bars, chan_points, chan_exec_ids, fee_rate=args.fee)
        stats_base = evaluate_trades(trades_base)

        trades_conf = run_backtest(bars, filtered_points, filtered_ids, fee_rate=args.fee)
        stats_conf = evaluate_trades(trades_conf)

        print(f"  纯缠论:      交易={stats_base['交易笔数']:>5}  胜率={stats_base['胜率']:.4f}  收益={stats_base['累计收益率']:.4f}")
        print(f"  缠论+SMC确认: 交易={stats_conf['交易笔数']:>5}  胜率={stats_conf['胜率']:.4f}  收益={stats_conf['累计收益率']:.4f}")

        summary[freq] = {
            "缠论原始信号数": len(chan_points),
            "SMC信号数": len(smc_points),
            "组合后保留信号数": len(filtered_points),
            "纯缠论": stats_base,
            "缠论+SMC确认": stats_conf,
        }

        if filtered_points:
            df = trades_to_df(trades_conf)
            df.to_csv(os.path.join(result_dir, f"{args.symbol}_{freq}_chan_smc_confluence_trades.csv"), index=False)

    summary_path = os.path.join(result_dir, f"{args.symbol}_chan_smc_confluence_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n汇总结果已保存: {summary_path}")


if __name__ == "__main__":
    main()
