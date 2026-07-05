"""
区间套二次验证："真背驰"是否真的能用次级别结构确认？

背景（用户提问："有没有用区间套的逻辑，二次验证是不是真背驰。"）
----------------------------------------------------------------
缠论原著（106~107课）里的"区间套"是一种用**次级别走势**去精确定位/确认大级别转折点
的方法：大级别一笔正在脱离中枢（可能构成背驰）时，同一时间窗口内的次级别走势如果也
独立走出了自己的"中枢+背驰"结构（次级别自己也力度衰竭、准备转向），就说明这次大级别
的背驰是"实打实"由更细粒度的结构支撑的，而不是大级别K线上偶然的力度差异——这是原著
里用来提升买卖点精确度、区分"真背驰"和"假背驰（看起来力度弱，其实次级别仍在加速）"
的核心机制之一。

操作化定义
----------
对每一对相邻级别 (H=大级别, L=小级别)（这里用 30m->5m、5m->1m 两组级联，与
`run_backtest_multilevel.py`/`run_duan_confluence.py` 一致）：

1. 用 `validate_beichi_zhongshu_anchored.zhongshu_anchored_events` 在 H 和 L 两个
   级别上分别找出全部"中枢锚定背驰事件"（entering_bi vs leaving_bi 力度对比）。
2. 对每个 H 级别背驰事件（leaving_bi_H 方向 = d），检查其"离开笔"覆盖的时间窗口
   `[leaving_bi_H.fx_a.dt, leaving_bi_H.fx_b.dt]`——这正是大级别价格脱离中枢、
   被判定为背驰的那一段行情。若 L 级别在这个窗口内，也存在一个**同方向**的背驰事件
   （leaving_bi_L.fx_b.dt 落在窗口内），则记为"区间套确认"，否则记为"未确认"。
3. 用同样的方法对"H级别非背驰事件"（力度未走弱，即所谓"趋势攻击性延续"）也计算一遍
   "L级别是否恰好在同一窗口内出现背驰"的比例，作为**基线对照**——如果这个比例和
   "H级别背驰事件"的确认率相近，说明"区间套确认"本身不携带信息（次级别背驰到处都有，
   跟大级别是否背驰无关）；如果背驰事件的确认率显著更高，说明区间套确认确实是"背驰"
   特有的伴生现象。
4. 核心检验：把 H 级别背驰事件按"是否被区间套确认"分组，比较两组之后（H级别10/30/100
   根K线）价格朝反转方向运动的胜率/幅度——如果区间套确认真的能挑出"真背驰"，确认组的
   表现应该显著优于未确认组。

因果性：L 级别背驰事件的 `leaving_bi_L.fx_b.dt` 必然 <= H级别信号确认时刻
`leaving_bi_H.fx_b.dt`（窗口本身就是用 H 级别信息定义的，且只在窗口内找 L 事件，
不会引用窗口结束之后才出现的 L 级别信息），因此"区间套确认"这个标签在 H 级别信号
confirm 的同一时刻就可以计算出来，不构成未来函数。
"""
import argparse
import json
import os
import time

import numpy as np
from scipy import stats as sstats

from chanlun_engine import Direction, load_bars
from validate_basic_logic import get_confirmed_bis, HORIZONS
from validate_beichi_zhongshu_anchored import zhongshu_anchored_events

CASCADE = [("30m", "5m"), ("5m", "1m")]  # (H=大级别, L=小级别)


def classify_events(engine, events):
    """把 zhongshu_anchored_events 的结果按"是否背驰"拆成两组，并附带方向和时间窗口

    时间窗口取"中枢起点(entering_bi结束后第一笔) -> leaving_bi结束"这个完整区间，
    覆盖大级别从"进入震荡"到"背驰确认离开"的整个过程——而不是只取 leaving_bi 自身
    的极短时段。这更贴近原著"区间套"里"次级别的走势对应大级别一个完整的中枢+离开"
    这个描述（次级别不需要恰好在大级别最后一笔的时间片里完成自己的背驰，只需要在
    整段大级别中枢的生命周期内完成即可），也让"次级别是否有独立确认"这个检验有
    起码的统计功效（否则窗口窄到几根K线，次级别几乎不可能恰好也形成一个完整的
    中枢+背驰）。
    """
    beichi, non_beichi = [], []
    for ev in events:
        entering_bi, leaving_bi, zs = ev["entering_bi"], ev["leaving_bi"], ev["zs"]
        weaker_price = engine._bi_price_power(leaving_bi) < engine._bi_price_power(entering_bi)
        weaker_macd = engine._bi_macd_area(leaving_bi) < engine._bi_macd_area(entering_bi)
        item = dict(leaving_bi=leaving_bi, entering_bi=entering_bi,
                    direction=leaving_bi.direction,
                    window_start=zs.bis[0].fx_a.dt, window_end=leaving_bi.fx_b.dt)
        (beichi if (weaker_price and weaker_macd) else non_beichi).append(item)
    return beichi, non_beichi


def has_nested_confirmation(window_start, window_end, direction, l_beichi_sorted_ends):
    """检查 L 级别背驰事件里，是否有同方向、fx_b.dt 落在 [window_start, window_end] 的"""
    ends = l_beichi_sorted_ends.get(str(direction), [])
    import bisect
    lo = bisect.bisect_left(ends, window_start)
    hi = bisect.bisect_right(ends, window_end)
    return hi > lo


def run_pair(symbol, freq_h, freq_l, data_dir):
    ph = os.path.join(data_dir, f"{symbol}-{freq_h}-2025-06_to_2026-05.parquet")
    pl = os.path.join(data_dir, f"{symbol}-{freq_l}-2025-06_to_2026-05.parquet")
    bars_h, bars_l = load_bars(ph, symbol, freq_h), load_bars(pl, symbol, freq_l)

    engine_h, bis_h, _ = get_confirmed_bis(bars_h, freq_h)
    engine_l, bis_l, _ = get_confirmed_bis(bars_l, freq_l)

    zs_h = engine_h.build_zhongshu_list(bis_h)
    zs_l = engine_l.build_zhongshu_list(bis_l)
    events_h = zhongshu_anchored_events(engine_h, bis_h, zs_h)
    events_l = zhongshu_anchored_events(engine_l, bis_l, zs_l)

    h_beichi, h_non_beichi = classify_events(engine_h, events_h)
    l_beichi, _ = classify_events(engine_l, events_l)

    l_ends_by_dir = {str(Direction.Up): [], str(Direction.Down): []}
    for item in l_beichi:
        l_ends_by_dir[str(item["direction"])].append(item["window_end"])
    for d in l_ends_by_dir:
        l_ends_by_dir[d].sort()

    closes_h = np.array([b.close for b in bars_h])
    bar_id_to_idx = {b.id: i for i, b in enumerate(bars_h)}

    def forward_returns(item):
        bar_id = item["leaving_bi"].fx_b.raw_bars[-1].id
        idx = bar_id_to_idx.get(bar_id)
        if idx is None:
            return {}
        out = {}
        for h in HORIZONS:
            if idx + h >= len(closes_h):
                continue
            raw_ret = (closes_h[idx + h] - closes_h[idx]) / closes_h[idx]
            out[h] = raw_ret if item["direction"] == Direction.Down else -raw_ret
        return out

    def confirm_rate(items):
        if not items:
            return None, 0, 0
        n_confirmed = sum(
            1 for it in items
            if has_nested_confirmation(it["window_start"], it["window_end"], it["direction"], l_ends_by_dir)
        )
        return n_confirmed / len(items), n_confirmed, len(items)

    beichi_confirm_rate, n_bc, n_b_total = confirm_rate(h_beichi)
    non_beichi_confirm_rate, n_nbc, n_nb_total = confirm_rate(h_non_beichi)

    confirmed_returns = {h: [] for h in HORIZONS}
    unconfirmed_returns = {h: [] for h in HORIZONS}
    for it in h_beichi:
        confirmed = has_nested_confirmation(it["window_start"], it["window_end"], it["direction"], l_ends_by_dir)
        rets = forward_returns(it)
        target = confirmed_returns if confirmed else unconfirmed_returns
        for h, r in rets.items():
            target[h].append(r)

    return {
        "H背驰事件数": n_b_total, "H背驰区间套确认数": n_bc,
        "H背驰区间套确认率": round(beichi_confirm_rate, 4) if beichi_confirm_rate is not None else None,
        "H非背驰事件数": n_nb_total, "H非背驰区间套确认数": n_nbc,
        "H非背驰区间套确认率(基线对照)": round(non_beichi_confirm_rate, 4) if non_beichi_confirm_rate is not None else None,
        "confirmed_returns": confirmed_returns, "unconfirmed_returns": unconfirmed_returns,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["PEPEUSDT", "ORDIUSDT", "ZECUSDT"])
    args = ap.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    result_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(result_dir, exist_ok=True)

    per_pair = {}
    global_confirmed = {h: [] for h in HORIZONS}
    global_unconfirmed = {h: [] for h in HORIZONS}
    total_b_confirm, total_b, total_nb_confirm, total_nb = 0, 0, 0, 0

    for symbol in args.symbols:
        for freq_h, freq_l in CASCADE:
            key = f"{symbol}_{freq_h}to{freq_l}"
            print(f"\n=== {key} ===")
            t0 = time.time()
            r = run_pair(symbol, freq_h, freq_l, data_dir)
            print(f"H背驰={r['H背驰事件数']} 确认={r['H背驰区间套确认数']}({r['H背驰区间套确认率']}) | "
                  f"H非背驰={r['H非背驰事件数']} 确认={r['H非背驰区间套确认数']}({r['H非背驰区间套确认率(基线对照)']}) "
                  f"耗时={time.time()-t0:.1f}s")
            per_pair[key] = {k: v for k, v in r.items() if k not in ("confirmed_returns", "unconfirmed_returns")}
            total_b_confirm += r["H背驰区间套确认数"]
            total_b += r["H背驰事件数"]
            total_nb_confirm += r["H非背驰区间套确认数"]
            total_nb += r["H非背驰事件数"]
            for h in HORIZONS:
                global_confirmed[h].extend(r["confirmed_returns"][h])
                global_unconfirmed[h].extend(r["unconfirmed_returns"][h])

    print("\n\n======= 汇总 =======")
    print(f"H背驰事件总数={total_b} 区间套确认率={total_b_confirm/total_b:.4f}" if total_b else "无H背驰事件")
    print(f"H非背驰事件总数={total_nb} 区间套确认率(基线)={total_nb_confirm/total_nb:.4f}" if total_nb else "无H非背驰事件")

    summary = {
        "H背驰事件总数": total_b, "H背驰区间套确认数": total_b_confirm,
        "H背驰区间套确认率": round(total_b_confirm / total_b, 4) if total_b else None,
        "H非背驰事件总数": total_nb, "H非背驰区间套确认数": total_nb_confirm,
        "H非背驰区间套确认率(基线对照)": round(total_nb_confirm / total_nb, 4) if total_nb else None,
    }
    # 确认率本身的显著性：背驰组确认率是否显著高于非背驰组（基线）
    if total_b and total_nb:
        table = [[total_b_confirm, total_b - total_b_confirm], [total_nb_confirm, total_nb - total_nb_confirm]]
        _, p_rate, _, _ = sstats.chi2_contingency(table)
        summary["确认率差异p值(卡方检验,背驰vs非背驰基线)"] = round(float(p_rate), 6)
        print(f"确认率差异p值(背驰组 vs 非背驰组基线): {p_rate:.6f}")

    horizon_summary = {}
    for h in HORIZONS:
        c = np.array(global_confirmed[h])
        u = np.array(global_unconfirmed[h])
        entry = {
            "区间套确认组": {"n": len(c), "胜率(>0)": round(float((c > 0).mean()), 4) if len(c) else None,
                        "均值收益": round(float(c.mean()), 5) if len(c) else None},
            "未确认组": {"n": len(u), "胜率(>0)": round(float((u > 0).mean()), 4) if len(u) else None,
                      "均值收益": round(float(u.mean()), 5) if len(u) else None},
        }
        if len(c) >= 5 and len(u) >= 5:
            _, p_ret = sstats.mannwhitneyu(c, u, alternative="greater")
            entry["收益p值(确认组显著优于未确认组,one-sided)"] = round(float(p_ret), 6)
            c_win, u_win = (c > 0).astype(int), (u > 0).astype(int)
            table2 = [[c_win.sum(), len(c_win) - c_win.sum()], [u_win.sum(), len(u_win) - u_win.sum()]]
            _, p_chi2, _, _ = sstats.chi2_contingency(table2)
            entry["胜率p值(卡方检验)"] = round(float(p_chi2), 6)
        else:
            entry["备注"] = "样本量不足(<5)，不做显著性检验"
        horizon_summary[f"{h}根H级别K线后"] = entry
        print(f"  {h}根后: 确认组(n={len(c)})胜率={entry['区间套确认组']['胜率(>0)']} "
              f"未确认组(n={len(u)})胜率={entry['未确认组']['胜率(>0)']} "
              f"收益p值={entry.get('收益p值(确认组显著优于未确认组,one-sided)')} "
              f"胜率p值={entry.get('胜率p值(卡方检验)')}")

    out_path = os.path.join(result_dir, "interval_nesting_validation.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"逐级联对": per_pair, "汇总": summary, "事件研究": horizon_summary}, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
