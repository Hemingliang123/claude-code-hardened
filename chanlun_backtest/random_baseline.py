"""
随机基线蒙特卡洛显著性检验（可复用模块）

方法：在与真实策略完全相同的成交笔数下，随机选取 n_trades+1 个开平仓时间点
（严格递增、互不相同），按多空交替生成 n_trades 笔随机交易，开平仓价格均取
对应K线的开盘价，手续费与真实回测完全一致，重复 n_sims 次得到随机策略的
胜率/累计收益率分布，再计算真实策略的指标在这个分布里的 z-score 和百分位。

这与 LOGIC_ANALYSIS.md 第3节里对缠论买卖点做的蒙特卡洛检验是同一套方法，
之前是一次性脚本、结果口述记录在文档里；这里把它落成可复用模块，供 SMC
信号复用同一套显著性检验流程，保证方法论一致、结果可复现。
"""
from __future__ import annotations

import numpy as np


def random_baseline_test(bars, n_trades: int, fee_rate: float = 0.001, n_sims: int = 300, seed: int = 42):
    """返回 (win_rates, cum_rets)，均为长度 n_sims 的 numpy 数组。"""
    if n_trades <= 0:
        return np.array([]), np.array([])
    rng = np.random.default_rng(seed)
    opens = np.array([b.open for b in bars])
    n = len(bars)
    if n_trades + 1 > n:
        raise ValueError("n_trades 超过了可用K线数量，无法生成不重复的随机时间点")

    win_rates = np.zeros(n_sims)
    cum_rets = np.zeros(n_sims)
    for s in range(n_sims):
        idx = np.sort(rng.choice(n, size=n_trades + 1, replace=False))
        side = 1 if rng.random() < 0.5 else -1
        rets = np.empty(n_trades)
        for i in range(n_trades):
            open_p = opens[idx[i]]
            close_p = opens[idx[i + 1]]
            if side == 1:
                rets[i] = close_p / open_p - 1 - 2 * fee_rate
            else:
                rets[i] = 1 - close_p / open_p - 2 * fee_rate
            side *= -1
        win_rates[s] = (rets > 0).mean()
        cum_rets[s] = np.prod(1 + rets) - 1
    return win_rates, cum_rets


def significance_report(actual_win_rate: float, actual_cum_ret: float, baseline_win_rates, baseline_cum_rets) -> dict:
    def _z_and_pct(actual, dist):
        if len(dist) == 0 or dist.std() == 0:
            return 0.0, 50.0
        z = (actual - dist.mean()) / dist.std()
        pct = (dist < actual).mean() * 100
        return float(z), float(pct)

    wz, wpct = _z_and_pct(actual_win_rate, baseline_win_rates)
    rz, rpct = _z_and_pct(actual_cum_ret, baseline_cum_rets)
    return {
        "实盘胜率": round(actual_win_rate, 4),
        "随机基线胜率均值": round(float(baseline_win_rates.mean()), 4) if len(baseline_win_rates) else None,
        "胜率分位": round(wpct, 1),
        "胜率z值": round(wz, 2),
        "实盘收益": round(actual_cum_ret, 4),
        "随机基线收益均值": round(float(baseline_cum_rets.mean()), 4) if len(baseline_cum_rets) else None,
        "收益分位": round(rpct, 1),
        "收益z值": round(rz, 2),
    }
