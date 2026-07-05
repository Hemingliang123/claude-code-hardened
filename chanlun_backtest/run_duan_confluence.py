"""检验"小转大"：结构递归级别（线段）vs 固定时钟级别（重采样K线），差异有多大？

`run_backtest_multilevel.py` 的多级别联立用的是"固定时钟周期"当"级别"的代理——
1分钟的大级别用5分钟K线重新走一遍笔构建，5分钟的大级别用30分钟K线。这是国内量化圈
最常见的简化，但严格来说不等于缠论原著里"级别"的真正定义：原著里级别是纯结构性、
递归定义的，一段足够复杂的低级别走势（被特征序列分解识别为一个完整的"线段"）本身就
应该被看成上一级别的一笔——这就是用户问的"小转大"，跟"是不是换了张更大的K线图"完全
是两回事。

这个脚本做两件事：
1. 量化"结构递归级别方向"（用 duan_engine.build_duan_list 从小级别笔自身递归构建的
   线段方向）与"固定时钟级别方向"（重采样到大级别K线后走一遍笔构建）到底有多大差异
   ——在同一堵时间线上逐点比较两者。
2. 用"结构递归级别方向"替换 TrendTimeline 里的固定时钟大级别方向，重跑一遍多级别联立
   回测，对比三种方式（不联立/固定时钟联立/结构递归联立）的胜率和收益率。

因果性：Duan 对象直接复用小级别笔自身的 fx_a/fx_b（均为小级别"绝对确认笔"的端点），
不引入任何额外的未来信息；DuanTimeline 复用 TrendTimeline 完全相同的查询逻辑
（只返回 fx_a.dt <= 查询时刻 的最后一段），因此同样不构成未来函数。
"""
import argparse
import json
import os
import time

from chanlun_engine import ChanEngine, TrendTimeline, load_bars
from duan_engine import build_duan_list
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


def agreement_rate(timeline_a, timeline_b, query_dts):
    agree, total = 0, 0
    for dt in query_dts:
        da, db = timeline_a.direction_at(dt), timeline_b.direction_at(dt)
        if da is None or db is None:
            continue
        total += 1
        if da == db:
            agree += 1
    return {"总比较点数(双方均有数据)": total, "方向一致次数": agree,
            "一致率": round(agree / total, 4) if total else None}


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
        duan_list = build_duan_list(confirmed_bis)
        print(f"K线={len(bars)} 笔={len(confirmed_bis)} 线段={len(duan_list)} 信号={len(points)} "
              f"耗时={time.time()-t0:.1f}s 自证={verify_stats}")
        cache[freq] = dict(bars=bars, points=points, exec_bar_ids=exec_bar_ids,
                            confirmed_bis=confirmed_bis, duan_list=duan_list)

    summary = {}
    for large_freq, small_freq in CASCADE:
        print(f"\n=== {large_freq}(定方向) -> {small_freq}(找买卖点)：固定时钟 vs 结构递归(线段/小转大) ===")

        small = cache[small_freq]
        large = cache[large_freq]

        fixed_clock_timeline = TrendTimeline(large["confirmed_bis"])          # 固定时钟大级别（重采样K线）
        structural_timeline = TrendTimeline(small["duan_list"])               # 结构递归大级别（小级别自身线段）

        query_dts = [b.fx_b.dt for b in small["confirmed_bis"]]
        agreement = agreement_rate(fixed_clock_timeline, structural_timeline, query_dts)
        print(f"固定时钟级别 vs 结构递归级别(线段) 方向一致性: {agreement}")

        def run_variant(timeline, label):
            if timeline is None:
                filtered_points, filtered_exec_ids = small["points"], small["exec_bar_ids"]
            else:
                filtered_points, filtered_exec_ids = [], []
                for p, bid in zip(small["points"], small["exec_bar_ids"]):
                    if timeline.allows(p):
                        filtered_points.append(p)
                        filtered_exec_ids.append(bid)
            trades = run_backtest(small["bars"], filtered_points, filtered_exec_ids, fee_rate=args.fee)
            stats = evaluate_trades(trades)
            stats["信号数"] = len(filtered_points)
            print(f"  [{label}] 信号数={len(filtered_points)} 胜率={stats.get('胜率')} "
                  f"累计收益率={stats.get('累计收益率')}")
            return stats, trades

        stats_none, _ = run_variant(None, "不联立(基线)")
        stats_fixed, trades_fixed = run_variant(fixed_clock_timeline, f"固定时钟联立({large_freq}重采样K线)")
        stats_struct, trades_struct = run_variant(structural_timeline, f"结构递归联立({small_freq}自身线段/小转大)")

        key = f"{small_freq}_duan_confluence_{large_freq}"
        summary[key] = {
            "大级别": large_freq, "小级别": small_freq,
            "方向一致性": agreement,
            "不联立(基线)": stats_none,
            "固定时钟联立": stats_fixed,
            "结构递归联立(小转大)": stats_struct,
        }

        trades_to_df(trades_struct).to_csv(
            os.path.join(result_dir, f"{args.symbol}_{key}_trades.csv"), index=False
        )

    summary_path = os.path.join(result_dir, f"{args.symbol}_duan_confluence_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n小转大(结构递归级别)对比结果已保存: {summary_path}")


if __name__ == "__main__":
    main()
