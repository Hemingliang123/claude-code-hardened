"""
深入验证"背驰"的核心理论——不满足于只测一种操作化定义

`BASIC_LOGIC_VALIDATION.md` 用"价格百分比力度 + MACD同向面积同时走弱"这一种最常见的
操作化方式检验了背驰，结论是"没有通过显著性检验"。但缠中说禅原著对"力度"本身没有
给出严格的数学定义，业界至少存在好几种互不相同、都能自称"忠实于原著"的操作化方式。
这里把"背驰"的核心理论——**"价格创新高/新低，但推动它的力度比上一段同向行情更弱，
预示这一段大概率快走完了"**——拆成 6 种具体的、互不相同的量化实现，在同样的
9 个数据集（PEPE/ORDI/ZEC × 1m/5m/30m）上跑同一套事件研究方法，逐一检验：
换一种"力度"的量化方式，背驰的核心理论能不能站得住？

候选定义
--------
D1 复合定义（原始基线，chanlun_engine.py 目前使用的定义）：
   价格百分比力度 AND MACD同向面积 同时比上一同向笔更弱
D2 纯MACD面积背驰（最常见的"指标背离"式定义，很多资讯站说的"MACD背离"就是这个）：
   只要求 MACD同向面积 比上一同向笔更弱，不管价格力度
D3 MACD峰值背驰（原著里"力度"也常被解读为"峰值高度"而不是"面积累加"）：
   该笔覆盖K线区间内 MACD柱的最大绝对值(peak) 比上一同向笔更弱
D4 量价背驰（最古老的技术分析式"量价背离"，常与缠论背驰混用）：
   该笔覆盖K线区间的成交量总和 比上一同向笔更小
D5 斜率力度背驰（原著更强调"用更少的时间走出更小的空间"是力度减弱，
   而不是单纯比总幅度——这里用"价格变化 / 笔跨越的K线数"衡量"速度"）：
   价格斜率力度 比上一同向笔更弱
D6 严格复合定义（价格力度、MACD面积、MACD峰值三者同时走弱——更严格是否更精确？）：
   D1 的条件 AND MACD峰值也走弱
D7 量价复合定义（用户提问"背驰应该被配合[成交]量吧"——注意这跟 D4 不同：D4 是
   "只用成交量"单独定义背驰，D7 是在 D1 的价格+MACD复合条件之上，额外要求成交量
   也同步萎缩，即"量价配合"作为背驰的加强确认条件，而不是替代条件）：
   D1 的条件 AND 成交量也比上一同向笔更小
"""
import argparse
import json
import os
import time

import numpy as np
from scipy import stats as sstats

from chanlun_engine import ChanEngine, Direction, load_bars
from validate_basic_logic import get_confirmed_bis, HORIZONS

DEFINITIONS = ["D1_复合(价格+MACD面积)", "D2_纯MACD面积", "D3_MACD峰值",
               "D4_量价背驰", "D5_斜率力度", "D6_严格复合(价格+面积+峰值)",
               "D7_量价配合复合(价格+MACD+成交量三者同时走弱)"]


def bi_macd_peak(engine: ChanEngine, bi) -> float:
    raw_ids = [b.id for b in bi.raw_bars]
    idxs = [engine.bar_id_to_idx[i] for i in raw_ids if i in engine.bar_id_to_idx]
    if not idxs:
        return 0.0
    seg = engine.macd[min(idxs): max(idxs) + 1]
    if bi.direction == Direction.Down:
        vals = -seg[seg < 0]
    else:
        vals = seg[seg > 0]
    return float(vals.max()) if len(vals) else 0.0


def bi_volume(bi) -> float:
    return float(sum(b.vol for b in bi.raw_bars))


def bi_slope_power(bi) -> float:
    n_bars = max(len(bi.raw_bars), 1)
    price_power = abs(bi.fx_b.fx - bi.fx_a.fx) / bi.fx_a.fx
    return price_power / n_bars


def label_beichi(engine, last, prev2, cache: dict) -> dict:
    """返回 {定义名: True/False}，cache 用于避免同一个 bi 的力度指标重复计算"""
    def get(bi, key, fn):
        c = cache.setdefault(id(bi), {})
        if key not in c:
            c[key] = fn(bi)
        return c[key]

    price_power_last = get(last, "price_power", engine._bi_price_power)
    price_power_prev = get(prev2, "price_power", engine._bi_price_power)
    macd_area_last = get(last, "macd_area", lambda b: engine._bi_macd_area(b))
    macd_area_prev = get(prev2, "macd_area", lambda b: engine._bi_macd_area(b))
    macd_peak_last = get(last, "macd_peak", lambda b: bi_macd_peak(engine, b))
    macd_peak_prev = get(prev2, "macd_peak", lambda b: bi_macd_peak(engine, b))
    vol_last = get(last, "volume", bi_volume)
    vol_prev = get(prev2, "volume", bi_volume)
    slope_last = get(last, "slope_power", bi_slope_power)
    slope_prev = get(prev2, "slope_power", bi_slope_power)

    weaker_price = price_power_last < price_power_prev
    weaker_area = macd_area_last < macd_area_prev
    weaker_peak = macd_peak_last < macd_peak_prev
    weaker_vol = vol_last < vol_prev
    weaker_slope = slope_last < slope_prev

    return {
        "D1_复合(价格+MACD面积)": weaker_price and weaker_area,
        "D2_纯MACD面积": weaker_area,
        "D3_MACD峰值": weaker_peak,
        "D4_量价背驰": weaker_vol,
        "D5_斜率力度": weaker_slope,
        "D6_严格复合(价格+面积+峰值)": weaker_price and weaker_area and weaker_peak,
        "D7_量价配合复合(价格+MACD+成交量三者同时走弱)": weaker_price and weaker_area and weaker_vol,
    }


def event_study_multi_def(engine: ChanEngine, bars, bis):
    closes = np.array([b.close for b in bars])
    bar_id_to_idx = {b.id: i for i, b in enumerate(bars)}
    cache: dict = {}

    groups = {d: {h: {"beichi": [], "non_beichi": []} for h in HORIZONS} for d in DEFINITIONS}
    extreme_counts = {d: {"beichi": 0, "non_beichi": 0} for d in DEFINITIONS}

    for i in range(2, len(bis)):
        last = bis[i]
        prev2 = bis[i - 2]
        price_new_extreme = (
            last.low < prev2.low if last.direction == Direction.Down else last.high > prev2.high
        )
        if not price_new_extreme:
            continue

        bar_id = last.fx_b.raw_bars[-1].id
        idx = bar_id_to_idx.get(bar_id)
        if idx is None:
            continue

        labels = label_beichi(engine, last, prev2, cache)

        favorable_by_h = {}
        for h in HORIZONS:
            if idx + h >= len(closes):
                continue
            raw_ret = (closes[idx + h] - closes[idx]) / closes[idx]
            favorable_by_h[h] = raw_ret if last.direction == Direction.Down else -raw_ret

        for d in DEFINITIONS:
            beichi = labels[d]
            extreme_counts[d]["beichi" if beichi else "non_beichi"] += 1
            for h, fav in favorable_by_h.items():
                groups[d][h]["beichi" if beichi else "non_beichi"].append(fav)

        cache.pop(id(prev2), None)  # prev2 之后不会再被用到（比较窗口滑动），及时释放缓存

    return groups, extreme_counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["PEPEUSDT", "ORDIUSDT", "ZECUSDT"])
    ap.add_argument("--freqs", nargs="+", default=["1m", "5m", "30m"])
    ap.add_argument("--start", default="2025-06")
    ap.add_argument("--end", default="2026-05")
    args = ap.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    result_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(result_dir, exist_ok=True)

    global_groups = {d: {h: {"beichi": [], "non_beichi": []} for h in HORIZONS} for d in DEFINITIONS}
    per_dataset = {}

    for symbol in args.symbols:
        for freq in args.freqs:
            key = f"{symbol}_{freq}"
            parquet_path = os.path.join(data_dir, f"{symbol}-{freq}-{args.start}_to_{args.end}.parquet")
            print(f"\n=== {key} ===")
            t0 = time.time()
            bars = load_bars(parquet_path, symbol, freq)
            engine, bis, verify_stats = get_confirmed_bis(bars, freq)
            groups, extreme_counts = event_study_multi_def(engine, bars, bis)
            print(f"K线={len(bars)} 笔={len(bis)} 耗时={time.time()-t0:.1f}s")

            dataset_entry = {}
            for d in DEFINITIONS:
                cnt = extreme_counts[d]
                dataset_entry[d] = {"背驰笔数": cnt["beichi"], "非背驰笔数": cnt["non_beichi"]}
                for h in HORIZONS:
                    b = np.array(groups[d][h]["beichi"])
                    nb = np.array(groups[d][h]["non_beichi"])
                    global_groups[d][h]["beichi"].extend(groups[d][h]["beichi"])
                    global_groups[d][h]["non_beichi"].extend(groups[d][h]["non_beichi"])
            per_dataset[key] = dataset_entry
            print(f"  各定义下的背驰/非背驰笔数: "
                  f"{ {d: (extreme_counts[d]['beichi'], extreme_counts[d]['non_beichi']) for d in DEFINITIONS} }")

    print("\n\n======= 6种背驰定义 × 跨全部数据集的汇总检验 =======")
    summary = {}
    for d in DEFINITIONS:
        print(f"\n--- {d} ---")
        d_summary = {}
        for h in HORIZONS:
            b = np.array(global_groups[d][h]["beichi"])
            nb = np.array(global_groups[d][h]["non_beichi"])
            entry = {
                "背驰组": {"n": len(b), "胜率(>0)": round(float((b > 0).mean()), 4) if len(b) else None,
                         "均值收益": round(float(b.mean()), 5) if len(b) else None},
                "非背驰组": {"n": len(nb), "胜率(>0)": round(float((nb > 0).mean()), 4) if len(nb) else None,
                          "均值收益": round(float(nb.mean()), 5) if len(nb) else None},
            }
            if len(b) >= 5 and len(nb) >= 5:
                _, p_ret = sstats.mannwhitneyu(b, nb, alternative="greater")
                entry["收益p值(背驰组显著优于非背驰组, one-sided)"] = round(float(p_ret), 6)
                from scipy.stats import chi2_contingency
                b_win, nb_win = (b > 0).astype(int), (nb > 0).astype(int)
                table = [[b_win.sum(), len(b_win) - b_win.sum()], [nb_win.sum(), len(nb_win) - nb_win.sum()]]
                _, p_chi2, _, _ = chi2_contingency(table)
                entry["胜率p值(卡方检验)"] = round(float(p_chi2), 6)
            d_summary[f"{h}根K线后"] = entry
            print(f"  {h}根K线后: 背驰(n={len(b)})胜率={entry['背驰组']['胜率(>0)']} "
                  f"非背驰(n={len(nb)})胜率={entry['非背驰组']['胜率(>0)']} "
                  f"收益p值={entry.get('收益p值(背驰组显著优于非背驰组, one-sided)')} "
                  f"胜率p值={entry.get('胜率p值(卡方检验)')}")
        summary[d] = d_summary

    out_path = os.path.join(result_dir, "beichi_alternatives_validation.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"逐数据集背驰笔数分布": per_dataset, "汇总检验": summary}, f, ensure_ascii=False, indent=2)
    print(f"\n汇总结果已保存: {out_path}")


if __name__ == "__main__":
    main()
