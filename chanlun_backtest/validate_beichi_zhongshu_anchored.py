"""重新审视背驰的定义：中枢锚定 vs 之前"隔一笔比较"的简化版本

问题的由来
----------
用户建议"再看一遍阿娇版缠论"，找此前"背驰验证不显著"这个结论背后的原因。回去
逐字核对缠中说禅原著/阿娇版注解后发现，`chanlun_engine.ChanEngine.detect_signals`
（以及 `validate_basic_logic.py`/`validate_beichi_alternatives.py` 里全部6种操作化
定义）里的背驰比较对象都是 `bi_list[-1]` vs `bi_list[-3]`——即"当前笔"和"隔一笔的
上一同向笔"，这是一个隐含假设"中枢正好是标准的3笔"的简化写法，**并不是**缠论原著
对背驰真正的定义。

原著对背驰的精确定义（缠中说禅108课 + 多篇权威解读交叉印证）：

> 趋势背驰：围绕同一中枢的前后两个次级别波动，后边的力度弱于前面。前提是当下
> 已经存在至少两个不重叠的同级别中枢（没有趋势就没有趋势背驰），且背驰段价格
> 必须创新高/新低。
>
> 盘整背驰：在只有一个中枢的情况下，比较"进中枢的笔/段"与"出中枢的笔/段"的力度，
> **不需要创新高/新低**。

关键差异：正确的比较对象应该是"进入某个中枢的笔"（entering_bi，即该中枢开始
前的最后一笔）与"离开该中枢的笔"（leaving_bi，即该中枢结束后的第一笔），而不是
简单地"隔一笔"——只有当中枢正好是最小的3笔时，"隔一笔"才恰好等于"进出中枢"；
一旦中枢发生延伸/扩展（笔数>3，这在实测数据里很常见），"隔一笔"比较的其实是
"离开笔"和"中枢内部某一笔"，根本不构成有意义的背驰比较。

这个脚本用中枢锚定的正确定义重新做一次事件研究，检验："背驰验证不显著"这个此前
的结论，是不是因为用错了比较对象导致的？
"""
import argparse
import json
import os
import time

import numpy as np
from scipy import stats as sstats

from chanlun_engine import ChanEngine, Direction, load_bars
from validate_basic_logic import get_confirmed_bis, HORIZONS

DEFINITIONS = [
    "Z1_中枢锚定不分类(entering vs leaving)",
    "Z2_趋势背驰(>=2不重叠中枢+创新高低)",
    "Z3_盘整背驰(仅1中枢+不要求创新高低)",
]


def zhongshu_anchored_events(engine: ChanEngine, bis, zs_list):
    """遍历全部中枢，找出entering_bi/leaving_bi方向一致（延续而非反转）的中枢，
    返回每个事件的 (leaving_bi, entering_bi, is_trend, price_new_extreme)

    "趋势 vs 盘整"的判定：build_zhongshu_list 是贪婪合并算法，任何两个被拆分成不同
    对象的相邻中枢，其"进入笔"和"离开笔"必然满足 zs_list[k].bis[0] ==
    bi_list[zs_list[k-1].end_idx + 1]——也就是说当前中枢的 entering_bi 恰好就是上一个
    中枢的 leaving_bi（同一个对象）。据此可以正确地"链式"追踪"连续多少个同方向的延续型
    中枢没有被反转打断"：如果链长 >= 2，说明在当前中枢之前，已经存在至少一个同方向、
    不重叠的中枢，构成原著"至少两个同级别中枢"的趋势条件，属于趋势背驰的适用范围；
    如果链长 == 1（当前中枢是链条里第一个，前面要么没有中枢、要么上一个中枢是反转型），
    说明这是一段新方向走势里的"第一个中枢"，只适用盘整背驰。
    """
    infos = []
    for zs in zs_list:
        entering_idx = zs.start_idx - 1
        leaving_idx = zs.end_idx + 1
        entering_bi = bis[entering_idx] if entering_idx >= 0 else None
        leaving_bi = bis[leaving_idx] if leaving_idx < len(bis) else None
        is_continuation = (
            entering_bi is not None and leaving_bi is not None
            and entering_bi.direction == leaving_bi.direction
        )
        infos.append(dict(zs=zs, entering_bi=entering_bi, leaving_bi=leaving_bi,
                           is_continuation=is_continuation))

    events = []
    chain_len = 0
    prev_dir = None
    for info in infos:
        if not info["is_continuation"]:
            chain_len = 0
            prev_dir = None
            continue

        direction = info["leaving_bi"].direction
        chain_len = chain_len + 1 if direction == prev_dir else 1
        prev_dir = direction
        is_trend = chain_len >= 2

        entering_bi, leaving_bi, zs = info["entering_bi"], info["leaving_bi"], info["zs"]
        # "创新高/新低"的正确参照点：不是entering_bi本身（那只是进入中枢前的最后一笔，
        # 中枢内部的震荡本身可能已经比entering_bi走得更远），而应该是"entering_bi与中枢
        # 内部全部笔"共同构成的、在leaving_bi出现之前已经达到过的最高/最低点——只有
        # leaving_bi突破了这个更大范围的极值，才算真正意义上的"创新高/新低"。
        zs_high = max(entering_bi.high, max(b.high for b in zs.bis))
        zs_low = min(entering_bi.low, min(b.low for b in zs.bis))
        price_new_extreme = (
            leaving_bi.low < zs_low if direction == Direction.Down else leaving_bi.high > zs_high
        )
        events.append(dict(entering_bi=entering_bi, leaving_bi=leaving_bi, zs=zs,
                            is_trend=is_trend, price_new_extreme=price_new_extreme))
    return events


def event_study_zhongshu_anchored(engine: ChanEngine, bars, bis):
    closes = np.array([b.close for b in bars])
    bar_id_to_idx = {b.id: i for i, b in enumerate(bars)}

    zs_list = engine.build_zhongshu_list(bis)
    events = zhongshu_anchored_events(engine, bis, zs_list)

    groups = {d: {h: {"beichi": [], "non_beichi": []} for h in HORIZONS} for d in DEFINITIONS}
    counts = {d: {"beichi": 0, "non_beichi": 0} for d in DEFINITIONS}

    for ev in events:
        leaving_bi = ev["leaving_bi"]
        entering_bi = ev["entering_bi"]
        weaker_price = engine._bi_price_power(leaving_bi) < engine._bi_price_power(entering_bi)
        weaker_macd = engine._bi_macd_area(leaving_bi) < engine._bi_macd_area(entering_bi)
        beichi = weaker_price and weaker_macd

        bar_id = leaving_bi.fx_b.raw_bars[-1].id
        idx = bar_id_to_idx.get(bar_id)
        if idx is None:
            continue

        favorable_by_h = {}
        for h in HORIZONS:
            if idx + h >= len(closes):
                continue
            raw_ret = (closes[idx + h] - closes[idx]) / closes[idx]
            favorable_by_h[h] = raw_ret if leaving_bi.direction == Direction.Down else -raw_ret

        applies = {
            "Z1_中枢锚定不分类(entering vs leaving)": True,
            "Z2_趋势背驰(>=2不重叠中枢+创新高低)": ev["is_trend"] and ev["price_new_extreme"],
            "Z3_盘整背驰(仅1中枢+不要求创新高低)": not ev["is_trend"],
        }
        for d in DEFINITIONS:
            if not applies[d]:
                continue
            counts[d]["beichi" if beichi else "non_beichi"] += 1
            for h, fav in favorable_by_h.items():
                groups[d][h]["beichi" if beichi else "non_beichi"].append(fav)

    return groups, counts, len(events), len(zs_list)


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
            groups, counts, n_events, n_zs = event_study_zhongshu_anchored(engine, bars, bis)
            print(f"K线={len(bars)} 笔={len(bis)} 中枢={n_zs} 延续类中枢事件={n_events} 耗时={time.time()-t0:.1f}s")
            print(f"  各定义下背驰/非背驰事件数: "
                  f"{ {d: (counts[d]['beichi'], counts[d]['non_beichi']) for d in DEFINITIONS} }")

            dataset_entry = {"中枢总数": n_zs, "延续类中枢事件数": n_events}
            for d in DEFINITIONS:
                dataset_entry[d] = {"背驰事件数": counts[d]["beichi"], "非背驰事件数": counts[d]["non_beichi"]}
                for h in HORIZONS:
                    global_groups[d][h]["beichi"].extend(groups[d][h]["beichi"])
                    global_groups[d][h]["non_beichi"].extend(groups[d][h]["non_beichi"])
            per_dataset[key] = dataset_entry

    print("\n\n======= 中枢锚定的背驰定义 × 跨全部数据集的汇总检验 =======")
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
            else:
                entry["备注"] = "样本量不足(<5)，不做显著性检验"
            d_summary[f"{h}根K线后"] = entry
            print(f"  {h}根K线后: 背驰(n={len(b)})胜率={entry['背驰组']['胜率(>0)']} "
                  f"非背驰(n={len(nb)})胜率={entry['非背驰组']['胜率(>0)']} "
                  f"收益p值={entry.get('收益p值(背驰组显著优于非背驰组, one-sided)')} "
                  f"胜率p值={entry.get('胜率p值(卡方检验)')}")
        summary[d] = d_summary

    out_path = os.path.join(result_dir, "beichi_zhongshu_anchored_validation.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"逐数据集事件分布": per_dataset, "汇总检验": summary}, f, ensure_ascii=False, indent=2)
    print(f"\n汇总结果已保存: {out_path}")


if __name__ == "__main__":
    main()
