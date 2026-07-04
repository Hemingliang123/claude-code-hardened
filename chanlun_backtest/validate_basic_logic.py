"""
验证缠论"基本逻辑"本身——而不是"买卖点信号能不能赚钱"

`LOGIC_ANALYSIS.md` 已经验证过"一二三类买卖点组合成交易信号后，胜率/收益率相对
随机基线如何"，这是一个关于"交易执行层"的复合结论。这里往回退一步，直接检验缠论
最基础的两条因果性断言本身（不掺杂"逢信号必反手"这套执行方式的影响）：

1. 【结构自洽性】笔/中枢的构建过程有没有自相矛盾（方向必须交替、相邻笔必须首尾衔接）？
   这是最基础的"内部一致性"检查，如果连这个都不满足，后面的一切都无从谈起。

2. 【背驰的核心断言】缠论认为"价格创新高/新低，但推动它的力度（价格斜率+MACD面积）
   同时比上一同向笔更弱"，是判断"这一段大概率要走完了"的关键依据。这里做一次干净的
   事件研究：把"创新高/新低的笔"分成"背驰"和"非背驰（力度未走弱，即所谓的
   '趋势攻击性延续'）"两组，比较两组笔端点之后价格的"反转方向收益"是否有统计显著差异——
   如果背驰真的有效，背驰组之后反转的概率和幅度应该显著高于非背驰组。

3. 【中枢的核心断言】缠论认为"中枢内部是震荡消化，中枢之间的移动才是趋势"。这里用
   Kaufman 效率比（净价格变化 / 逐笔波动绝对值之和，越接近1说明走势越"直"，越接近0
   说明越"来回拉锯"）分别统计"中枢内部"和"中枢之间（趋势段）"两类区间，验证前者的
   效率比是否显著低于后者。

方法论说明：这里做的是**描述性统计验证**（验证缠论定义的结构本身是否有真实的统计
含义），不是交易回测，所以直接用完整的 `confirmed_bis`/中枢列表做事后分析是合理的
（不涉及"要不要在实盘时刻就能看到"这个因果性问题——那是 `chanlun_engine.ChanEngine.run()`
本身已经解决的问题）。
"""
import argparse
import json
import os
import time

import numpy as np
from scipy import stats as sstats

from chanlun_engine import ChanEngine, load_bars, Direction

POLL_CHUNK = {"1m": 500, "5m": 200, "30m": 50}
WARMUP = {"1m": 300, "5m": 300, "30m": 150}
HORIZONS = [10, 30, 100]  # 以"笔端点之后第 N 根K线"衡量后续走势，N 为K线数量


def get_confirmed_bis(bars, freq):
    safety_margin = 2
    while True:
        try:
            engine = ChanEngine(bars)
            _, _, c, verify_stats, confirmed_bis = engine.run(
                warmup=WARMUP[freq], poll_chunk=POLL_CHUNK[freq], safety_margin=safety_margin
            )
            return engine, confirmed_bis, verify_stats
        except RuntimeError:
            safety_margin += 2


def check_structural_consistency(bis):
    """检查笔序列是否自洽：方向必须严格交替，相邻笔必须首尾衔接（前一笔的终点=后一笔的起点）"""
    direction_violations = 0
    continuity_violations = 0
    for i in range(len(bis) - 1):
        if bis[i].direction == bis[i + 1].direction:
            direction_violations += 1
        if bis[i].fx_b.dt != bis[i + 1].fx_a.dt or abs(bis[i].fx_b.fx - bis[i + 1].fx_a.fx) > 1e-9:
            continuity_violations += 1
    return {
        "笔总数": len(bis),
        "相邻笔数": max(len(bis) - 1, 0),
        "方向未交替次数": direction_violations,
        "端点未衔接次数": continuity_violations,
        "自洽": direction_violations == 0 and continuity_violations == 0,
    }


def event_study_beichi(engine: ChanEngine, bars, bis, global_groups=None):
    """背驰组 vs 非背驰组：笔端点之后价格"反转方向收益"的事件研究

    :param global_groups: 若提供，同时把每笔样本追加进这个跨数据集共享的容器，
        用于之后做样本量更大、统计功效更高的汇总检验。
    """
    closes = np.array([b.close for b in bars])
    bar_id_to_idx = {b.id: i for i, b in enumerate(bars)}

    groups = {h: {"beichi": [], "non_beichi": [], "all": []} for h in HORIZONS}
    n_extreme_beichi = 0
    n_extreme_non_beichi = 0
    n_extreme_total = 0

    for i in range(2, len(bis)):
        last = bis[i]
        prev2 = bis[i - 2]  # 笔方向严格交替，i 与 i-2 天然同方向
        price_new_extreme = (
            last.low < prev2.low if last.direction == Direction.Down else last.high > prev2.high
        )

        bar_id = last.fx_b.raw_bars[-1].id
        idx = bar_id_to_idx.get(bar_id)
        if idx is None:
            continue

        if price_new_extreme:
            n_extreme_total += 1
            weaker_price = engine._bi_price_power(last) < engine._bi_price_power(prev2)
            weaker_macd = engine._bi_macd_area(last) < engine._bi_macd_area(prev2)
            beichi = weaker_price and weaker_macd
            if beichi:
                n_extreme_beichi += 1
            else:
                n_extreme_non_beichi += 1

        for h in HORIZONS:
            if idx + h >= len(closes):
                continue
            raw_ret = (closes[idx + h] - closes[idx]) / closes[idx]
            favorable = raw_ret if last.direction == Direction.Down else -raw_ret
            groups[h]["all"].append(favorable)
            if price_new_extreme:
                if beichi:
                    groups[h]["beichi"].append(favorable)
                else:
                    groups[h]["non_beichi"].append(favorable)
            if global_groups is not None:
                g = global_groups.setdefault(h, {"beichi": [], "non_beichi": [], "all": []})
                g["all"].append(favorable)
                if price_new_extreme:
                    (g["beichi"] if beichi else g["non_beichi"]).append(favorable)

    result = {
        "创新高新低的笔总数": n_extreme_total,
        "其中背驰": n_extreme_beichi,
        "其中非背驰(力度未走弱)": n_extreme_non_beichi,
        "按horizon统计": {},
    }
    for h in HORIZONS:
        b = np.array(groups[h]["beichi"])
        nb = np.array(groups[h]["non_beichi"])
        a = np.array(groups[h]["all"])
        entry = {
            "背驰组": {"n": len(b), "均值收益": round(float(b.mean()), 5) if len(b) else None,
                     "胜率(>0)": round(float((b > 0).mean()), 4) if len(b) else None},
            "非背驰组": {"n": len(nb), "均值收益": round(float(nb.mean()), 5) if len(nb) else None,
                      "胜率(>0)": round(float((nb > 0).mean()), 4) if len(nb) else None},
            "全部笔端点基线": {"n": len(a), "均值收益": round(float(a.mean()), 5) if len(a) else None,
                        "胜率(>0)": round(float((a > 0).mean()), 4) if len(a) else None},
        }
        if len(b) >= 5 and len(nb) >= 5:
            u_stat, p_value = sstats.mannwhitneyu(b, nb, alternative="greater")
            entry["背驰组是否显著优于非背驰组(Mann-Whitney U, one-sided p)"] = round(float(p_value), 5)
        result["按horizon统计"][f"{h}根K线后"] = entry
    return result


def efficiency_ratio(closes, i0, i1):
    seg = closes[i0:i1 + 1]
    if len(seg) < 2:
        return None
    net = abs(seg[-1] - seg[0])
    path = np.abs(np.diff(seg)).sum()
    if path == 0:
        return None
    return net / path


def zhongshu_efficiency_test(engine: ChanEngine, bars, bis, min_len=5, global_eff=None):
    """中枢内部 vs 中枢之间(趋势段)的 Kaufman 效率比对比"""
    closes = np.array([b.close for b in bars])
    bar_id_to_idx = {b.id: i for i, b in enumerate(bars)}

    zs_list = engine.build_zhongshu_list(bis)
    if not zs_list:
        return {"中枢数量": 0}

    def span_idx(zs):
        start_bar_id = zs.bis[0].fx_a.raw_bars[0].id
        end_bar_id = zs.bis[-1].fx_b.raw_bars[-1].id
        return bar_id_to_idx.get(start_bar_id), bar_id_to_idx.get(end_bar_id)

    zs_spans = [span_idx(zs) for zs in zs_list]
    zs_spans = [(a, b) for a, b in zs_spans if a is not None and b is not None and b - a >= min_len]

    trend_spans = []
    for k in range(len(zs_spans) - 1):
        gap_start = zs_spans[k][1]
        gap_end = zs_spans[k + 1][0]
        if gap_end - gap_start >= min_len:
            trend_spans.append((gap_start, gap_end))

    zs_eff = [e for e in (efficiency_ratio(closes, a, b) for a, b in zs_spans) if e is not None]
    trend_eff = [e for e in (efficiency_ratio(closes, a, b) for a, b in trend_spans) if e is not None]

    if global_eff is not None:
        global_eff["zs"].extend(zs_eff)
        global_eff["trend"].extend(trend_eff)

    result = {
        "中枢数量": len(zs_list),
        "有效中枢区间数(长度>={})".format(min_len): len(zs_eff),
        "趋势段数量(中枢之间)": len(trend_eff),
        "中枢内效率比": {
            "均值": round(float(np.mean(zs_eff)), 4) if zs_eff else None,
            "中位数": round(float(np.median(zs_eff)), 4) if zs_eff else None,
        },
        "趋势段效率比": {
            "均值": round(float(np.mean(trend_eff)), 4) if trend_eff else None,
            "中位数": round(float(np.median(trend_eff)), 4) if trend_eff else None,
        },
    }
    if len(zs_eff) >= 5 and len(trend_eff) >= 5:
        u_stat, p_value = sstats.mannwhitneyu(trend_eff, zs_eff, alternative="greater")
        result["趋势段效率比是否显著高于中枢内(Mann-Whitney U, one-sided p)"] = round(float(p_value), 5)
    return result


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

    summary = {}
    global_beichi_groups = {}
    global_eff = {"zs": [], "trend": []}

    for symbol in args.symbols:
        for freq in args.freqs:
            key = f"{symbol}_{freq}"
            parquet_path = os.path.join(data_dir, f"{symbol}-{freq}-{args.start}_to_{args.end}.parquet")
            print(f"\n=== {key} ===")
            t0 = time.time()
            bars = load_bars(parquet_path, symbol, freq)
            engine, bis, verify_stats = get_confirmed_bis(bars, freq)
            print(f"K线={len(bars)} 笔={len(bis)} 耗时={time.time()-t0:.1f}s")

            consistency = check_structural_consistency(bis)
            print(f"结构自洽性: {consistency}")

            beichi_result = event_study_beichi(engine, bars, bis, global_groups=global_beichi_groups)
            print(f"背驰事件研究: 创新高新低笔={beichi_result['创新高新低的笔总数']} "
                  f"背驰={beichi_result['其中背驰']} 非背驰={beichi_result['其中非背驰(力度未走弱)']}")
            for h_key, entry in beichi_result["按horizon统计"].items():
                print(f"  {h_key}: 背驰组胜率={entry['背驰组']['胜率(>0)']} "
                      f"非背驰组胜率={entry['非背驰组']['胜率(>0)']} "
                      f"p值={entry.get('背驰组是否显著优于非背驰组(Mann-Whitney U, one-sided p)')}")

            zs_result = zhongshu_efficiency_test(engine, bars, bis, global_eff=global_eff)
            print(f"中枢效率比检验: {zs_result}")

            summary[key] = {
                "结构自洽性": consistency,
                "背驰事件研究": beichi_result,
                "中枢效率比检验": zs_result,
            }

    # 跨全部数据集的汇总检验（样本量更大，统计功效更高）
    print("\n\n======= 跨全部数据集的汇总检验 =======")
    aggregate = {"背驰事件研究(全部数据集合并)": {}, "中枢效率比检验(全部数据集合并)": {}}
    for h in HORIZONS:
        g = global_beichi_groups.get(h, {"beichi": [], "non_beichi": [], "all": []})
        b, nb, a = np.array(g["beichi"]), np.array(g["non_beichi"]), np.array(g["all"])
        entry = {
            "背驰组": {"n": len(b), "均值收益": round(float(b.mean()), 5) if len(b) else None,
                     "胜率(>0)": round(float((b > 0).mean()), 4) if len(b) else None},
            "非背驰组": {"n": len(nb), "均值收益": round(float(nb.mean()), 5) if len(nb) else None,
                      "胜率(>0)": round(float((nb > 0).mean()), 4) if len(nb) else None},
            "全部笔端点基线": {"n": len(a), "均值收益": round(float(a.mean()), 5) if len(a) else None,
                        "胜率(>0)": round(float((a > 0).mean()), 4) if len(a) else None},
        }
        if len(b) >= 5 and len(nb) >= 5:
            _, p_ret = sstats.mannwhitneyu(b, nb, alternative="greater")
            entry["背驰组收益是否显著优于非背驰组(Mann-Whitney U, one-sided p)"] = round(float(p_ret), 6)
            b_win = (b > 0).astype(int)
            nb_win = (nb > 0).astype(int)
            from scipy.stats import chi2_contingency
            table = [[b_win.sum(), len(b_win) - b_win.sum()], [nb_win.sum(), len(nb_win) - nb_win.sum()]]
            _, p_chi2, _, _ = chi2_contingency(table)
            entry["背驰组胜率是否与非背驰组有显著差异(卡方检验 p值)"] = round(float(p_chi2), 6)
        aggregate["背驰事件研究(全部数据集合并)"][f"{h}根K线后"] = entry
        print(f"[汇总] {h}根K线后: 背驰组(n={len(b)})胜率={entry['背驰组']['胜率(>0)']} "
              f"非背驰组(n={len(nb)})胜率={entry['非背驰组']['胜率(>0)']} "
              f"收益p值={entry.get('背驰组收益是否显著优于非背驰组(Mann-Whitney U, one-sided p)')} "
              f"胜率p值={entry.get('背驰组胜率是否与非背驰组有显著差异(卡方检验 p值)')}")

    zs_eff = np.array(global_eff["zs"])
    trend_eff = np.array(global_eff["trend"])
    eff_entry = {
        "中枢内区间数(全部数据集)": len(zs_eff),
        "趋势段区间数(全部数据集)": len(trend_eff),
        "中枢内效率比均值": round(float(zs_eff.mean()), 4) if len(zs_eff) else None,
        "趋势段效率比均值": round(float(trend_eff.mean()), 4) if len(trend_eff) else None,
    }
    if len(zs_eff) >= 5 and len(trend_eff) >= 5:
        _, p_eff = sstats.mannwhitneyu(trend_eff, zs_eff, alternative="greater")
        eff_entry["趋势段效率比是否显著高于中枢内(Mann-Whitney U, one-sided p)"] = round(float(p_eff), 6)
    aggregate["中枢效率比检验(全部数据集合并)"] = eff_entry
    print(f"[汇总] 中枢效率比: {eff_entry}")

    summary["汇总检验"] = aggregate

    out_path = os.path.join(result_dir, "basic_logic_validation.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n汇总结果已保存: {out_path}")


if __name__ == "__main__":
    main()
