"""
补齐线段（Duan）的结构自洽性检验——对齐 validate_basic_logic.py 对"笔"做的同等检验。

用户问："笔，线段，中枢，是通过检验的对吗？"

现状核查发现：BASIC_LOGIC_VALIDATION.md 第1节对"笔"、第3节对"中枢"都做了独立的、
基于9个真实数据集的统计检验。但"线段"此前只有：
    1. test_duan_engine.py 的3个合成数据单元测试（验证构建算法在人为构造场景下的正确性）
    2. DUAN_CONFLUENCE.md 里把线段方向当"大级别过滤器"用于多级别联立回测（这是"有没有用"
       的检验，不是"构建出来的线段本身自洽/有意义"的结构检验）
没有对"线段"做过等同于"笔"那一级的独立结构自洽性检验。这个脚本补上这一块：

1. 结构自洽性：线段方向必须严格交替（上涨线段后必接下跌线段），相邻线段必须首尾衔接
   （前一线段的终点 = 后一线段的起点）——这是构建算法本身"有没有逻辑漏洞"的检验，
   与 validate_basic_logic.py 对"笔"做的检验完全对应。
2. 结构有效性：线段的高低点范围是否真的比其内部单笔的高低点范围更极端（即线段确实是
   "多笔构成的更大结构"，而不是退化成跟单笔等价的东西）——用"线段跨越笔数"分布和
   "线段是否严格包含其内部所有笔的价格区间"两个指标衡量。
"""
import os
import time

import numpy as np

from chanlun_engine import ChanEngine, load_bars
from duan_engine import build_duan_list

POLL_CHUNK = {"1m": 500, "5m": 200, "30m": 50}
WARMUP = {"1m": 300, "5m": 300, "30m": 150}
DATASETS = [(sym, freq) for sym in ["PEPEUSDT", "ORDIUSDT", "ZECUSDT"] for freq in ["1m", "5m", "30m"]]
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
START, END = "2025-06", "2026-05"


def get_confirmed_bis(bars, freq):
    safety_margin = 2
    while True:
        try:
            engine = ChanEngine(bars)
            _, _, c, verify_stats, confirmed_bis = engine.run(
                warmup=WARMUP[freq], poll_chunk=POLL_CHUNK[freq], safety_margin=safety_margin
            )
            return confirmed_bis
        except RuntimeError:
            safety_margin += 2


def check_duan_consistency(duans):
    direction_violations = 0
    continuity_violations = 0
    containment_violations = 0
    bi_counts = []
    for i, d in enumerate(duans):
        bi_counts.append(len(d.bis))
        # 结构有效性：线段高/低点必须等于其内部各笔高/低点的最大/最小值（否则 high/low 属性定义就自相矛盾）
        inner_high = max(b.high for b in d.bis)
        inner_low = min(b.low for b in d.bis)
        if abs(inner_high - d.high) > 1e-9 or abs(inner_low - d.low) > 1e-9:
            containment_violations += 1
        if i + 1 < len(duans):
            nd = duans[i + 1]
            if d.direction == nd.direction:
                direction_violations += 1
            if d.fx_b.dt != nd.fx_a.dt or abs(d.fx_b.fx - nd.fx_a.fx) > 1e-9:
                continuity_violations += 1
    return {
        "线段总数": len(duans),
        "相邻线段对数": max(len(duans) - 1, 0),
        "方向未交替次数": direction_violations,
        "端点未衔接次数": continuity_violations,
        "高低点包含关系违反次数": containment_violations,
        "自洽": direction_violations == 0 and continuity_violations == 0 and containment_violations == 0,
        "每线段平均笔数": round(float(np.mean(bi_counts)), 2) if bi_counts else None,
        "笔数分布(1笔/2笔/3笔以上)": {
            "1笔(退化为单笔)": sum(1 for c in bi_counts if c == 1),
            "2笔": sum(1 for c in bi_counts if c == 2),
            "3笔以上": sum(1 for c in bi_counts if c >= 3),
        },
    }


def main():
    results = {}
    for symbol, freq in DATASETS:
        t0 = time.time()
        parquet_path = os.path.join(DATA_DIR, f"{symbol}-{freq}-{START}_to_{END}.parquet")
        bars = load_bars(parquet_path, symbol, freq)
        confirmed_bis = get_confirmed_bis(bars, freq)
        # 与笔序列本身一致的因果性处理：末尾线段可能仍在延伸中，只信任非最后一段
        duans_all = build_duan_list(confirmed_bis)
        duans = duans_all[:-1] if len(duans_all) > 1 else duans_all
        stats = check_duan_consistency(duans)
        results[f"{symbol}_{freq}"] = stats
        print(f"[{symbol} {freq}] 笔数={len(confirmed_bis)} -> {stats} ({time.time()-t0:.1f}s)")

    total_duans = sum(r["线段总数"] for r in results.values())
    total_dir_viol = sum(r["方向未交替次数"] for r in results.values())
    total_cont_viol = sum(r["端点未衔接次数"] for r in results.values())
    total_contain_viol = sum(r["高低点包含关系违反次数"] for r in results.values())
    degenerate_1bi = sum(r["笔数分布(1笔/2笔/3笔以上)"]["1笔(退化为单笔)"] for r in results.values())

    print("\n=== 汇总 ===")
    print(f"线段总数: {total_duans}")
    print(f"方向未交替次数: {total_dir_viol}")
    print(f"端点未衔接次数: {total_cont_viol}")
    print(f"高低点包含关系违反次数: {total_contain_viol}")
    print(f"退化为单笔的线段数: {degenerate_1bi} ({degenerate_1bi/total_duans*100:.1f}%)")
    print(f"全部自洽: {total_dir_viol == 0 and total_cont_viol == 0 and total_contain_viol == 0}")

    import json
    with open("results/duan_structural_consistency.json", "w", encoding="utf-8") as f:
        json.dump({"逐数据集": results, "汇总": {
            "线段总数": total_duans, "方向未交替次数": total_dir_viol,
            "端点未衔接次数": total_cont_viol, "高低点包含关系违反次数": total_contain_viol,
            "退化为单笔的线段数": degenerate_1bi,
            "退化比例": round(degenerate_1bi / total_duans, 4) if total_duans else None,
        }}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
