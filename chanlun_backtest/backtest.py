"""
基于缠论买卖点信号的回测撮合与绩效统计（因果式，无未来函数）

撮合规则
--------
- 每个买/卖点信号被"发现"的时刻记为 exec_bar_id（该信号被确认时，回测程序恰好处理到的那根K线）。
- 实际开平仓价格 = exec_bar_id 的下一根K线的开盘价（绝不使用信号发生那一刻或更早的价格），
  这样即使信号识别本身存在轮询延迟，也只会让策略"更晚"知道信号，不会提前用到未来价格。
- 策略始终只持有一个方向的仓位：出现买点信号且当前不是多头 -> 平任何空头，开多；
  出现卖点信号且当前不是空头 -> 平任何多头，开空。
- 交易成本：默认按币安现货 taker 费率 0.1%/边（双边合计 0.2%），可通过参数调整。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


@dataclass
class Trade:
    side: str          # 'long' or 'short'
    open_dt: object
    open_price: float
    close_dt: object
    close_price: float
    open_reason: str
    close_reason: str
    ret: float          # 扣除手续费后的收益率


def run_backtest(bars, points, exec_bar_ids, fee_rate: float = 0.001):
    """
    :param bars: 原始K线列表（RawBar），按 id 升序、连续
    :param points: BSPoint 列表
    :param exec_bar_ids: 与 points 一一对应的"发现时刻"K线 id
    :param fee_rate: 单边手续费率，默认 0.001 = 0.10%（币安现货 taker 费率）
    """
    bar_by_id = {b.id: b for b in bars}
    max_id = max(bar_by_id.keys())

    trades: List[Trade] = []
    position = 0  # 0 flat, 1 long, -1 short
    open_price = None
    open_dt = None
    open_reason = None

    # 按 exec_bar_id 排序（多个信号在同一根K线被发现时，按原始检测顺序执行）
    order = sorted(range(len(points)), key=lambda i: exec_bar_ids[i])

    for i in order:
        p = points[i]
        exec_id = exec_bar_ids[i]
        fill_id = exec_id + 1
        if fill_id > max_id:
            continue  # 没有下一根K线可供成交，忽略（数据末尾）
        fill_bar = bar_by_id[fill_id]
        fill_price = fill_bar.open
        fill_dt = fill_bar.dt

        desired = 1 if p.side == "buy" else -1
        if desired == position:
            continue  # 已经持有同方向仓位，不重复开仓

        # 先平掉反方向仓位
        if position != 0:
            if position == 1:
                ret = fill_price / open_price - 1 - 2 * fee_rate
            else:
                ret = 1 - fill_price / open_price - 2 * fee_rate
            trades.append(
                Trade(
                    side="long" if position == 1 else "short",
                    open_dt=open_dt,
                    open_price=open_price,
                    close_dt=fill_dt,
                    close_price=fill_price,
                    open_reason=open_reason,
                    close_reason=f"{p.kind}信号平仓",
                    ret=ret,
                )
            )
            position = 0

        # 开新仓
        position = desired
        open_price = fill_price
        open_dt = fill_dt
        open_reason = f"{p.kind}信号开仓"

    # 数据结束时，若仍有持仓，按最后一根K线收盘价强制平仓（标记说明，不计入"信号驱动"交易的胜率主指标，
    # 但计入整体资金曲线，避免遗漏最后一段浮动盈亏）
    if position != 0:
        last_bar = bars[-1]
        if position == 1:
            ret = last_bar.close / open_price - 1 - 2 * fee_rate
        else:
            ret = 1 - last_bar.close / open_price - 2 * fee_rate
        trades.append(
            Trade(
                side="long" if position == 1 else "short",
                open_dt=open_dt,
                open_price=open_price,
                close_dt=last_bar.dt,
                close_price=last_bar.close,
                open_reason=open_reason,
                close_reason="回测结束强制平仓",
                ret=ret,
            )
        )

    return trades


def evaluate_trades(trades: List[Trade]) -> dict:
    if not trades:
        return {
            "交易笔数": 0, "胜率": 0.0, "平均盈亏比例": 0.0,
            "平均盈利": 0.0, "平均亏损": 0.0, "盈亏比": 0.0,
            "累计收益率": 0.0, "最大回撤": 0.0,
        }

    rets = np.array([t.ret for t in trades])
    wins = rets[rets > 0]
    losses = rets[rets <= 0]

    equity = np.cumprod(1 + rets)
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min() if len(drawdown) else 0.0

    win_rate = len(wins) / len(rets)
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = losses.mean() if len(losses) else 0.0
    profit_factor = (wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float("inf")

    long_trades = [t for t in trades if t.side == "long"]
    short_trades = [t for t in trades if t.side == "short"]

    def _sub_stats(sub):
        if not sub:
            return {"笔数": 0, "胜率": 0.0}
        r = np.array([t.ret for t in sub])
        return {"笔数": len(sub), "胜率": round((r > 0).mean(), 4)}

    return {
        "交易笔数": len(trades),
        "胜率": round(win_rate, 4),
        "平均盈利": round(avg_win, 4),
        "平均亏损": round(avg_loss, 4),
        "盈亏比": round(profit_factor, 4) if profit_factor != float("inf") else profit_factor,
        "累计收益率": round(equity[-1] - 1, 4),
        "最大回撤": round(max_dd, 4),
        "多头交易": _sub_stats(long_trades),
        "空头交易": _sub_stats(short_trades),
    }


def trades_to_df(trades: List[Trade]) -> pd.DataFrame:
    return pd.DataFrame([t.__dict__ for t in trades])
