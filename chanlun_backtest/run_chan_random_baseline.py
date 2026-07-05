"""对缠论买卖点回测结果做蒙特卡洛随机基线显著性检验（可复现版本）

背景：LOGIC_ANALYSIS.md 第3节的随机基线检验最初是一次性脚本跑出来的，结果口述
记录在文档里，没有落成可复现的脚本。这里用 `random_baseline.py` 里抽出来的复用
模块，把同一套检验方法应用到"背驰定义修复"之后重新生成的 summary/trades 上，
确保文档里的数字始终对应当前版本的引擎输出。
"""
import argparse
import json
import os

from chanlun_engine import load_bars
from random_baseline import random_baseline_test, significance_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["PEPEUSDT", "ORDIUSDT", "ZECUSDT"])
    ap.add_argument("--freqs", nargs="+", default=["1m", "5m", "30m"])
    ap.add_argument("--start", default="2025-06")
    ap.add_argument("--end", default="2026-05")
    ap.add_argument("--fee", type=float, default=0.001)
    ap.add_argument("--n-sims", type=int, default=300)
    args = ap.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    result_dir = os.path.join(os.path.dirname(__file__), "results")

    report = {}
    for symbol in args.symbols:
        summary_path = os.path.join(result_dir, f"{symbol}_summary.json")
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        report[symbol] = {}
        for freq in args.freqs:
            stats = summary[freq]
            n_trades = stats["交易笔数"]
            parquet_path = os.path.join(data_dir, f"{symbol}-{freq}-{args.start}_to_{args.end}.parquet")
            bars = load_bars(parquet_path, symbol, freq)
            wr, cr = random_baseline_test(bars, n_trades, fee_rate=args.fee, n_sims=args.n_sims)
            rep = significance_report(stats["胜率"], stats["累计收益率"], wr, cr)
            report[symbol][freq] = rep
            print(f"{symbol} {freq}: {json.dumps(rep, ensure_ascii=False)}")

    out_path = os.path.join(result_dir, "chan_random_baseline_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n已保存: {out_path}")


if __name__ == "__main__":
    main()
