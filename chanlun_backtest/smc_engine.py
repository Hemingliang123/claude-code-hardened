"""
SMC（Smart Money Concepts）因果式特征提取引擎 —— 重写修复版

背景：用户贴过来一版 SMC 引擎代码做审查，发现了几个会实际影响结果正确性的问题：
1. 用 `pd.read_csv(chunksize=...)` 分块流式读取，但 `rolling()`/`shift()` 这类需要
   跨行上下文的算子在每个 chunk 内部独立计算，导致每个 chunk 边界处的信号被静默
   丢失或用错误的（残缺的）均线值计算——用最小复现例子验证过，chunk_size=10 时
   一个横跨边界的真实 FVG 信号会被完全漏掉。
2. `shift(-2)` 引入了未来函数：判断第 i 根K线的 FVG 需要用到第 i+2 根K线的价格，
   但原代码没有任何机制记录"这个信号最早在什么时刻才能被观察到"，如果直接拿信号
   所在行的时间戳去回测/实盘执行，就是提前用到了 2 根K线之后才存在的信息。
3. 订单块（OB）方向判断自相矛盾：`is_bullish_fvg.shift(1)` 把标记搬到了"制造向上
   跳空的位移K线本身"，然后又要求这根位移K线是阴线——一个看涨位移不太可能同时是
   阴线，逻辑上说不通。
4. 文档承诺的 BOS/CHoCH（结构突变）完全没有实现。

本文件按 `chanlun_engine.py` 同一套因果性标准重新实现，修复以上全部问题：
- 不做分块流式读取。我们的数据集最大 52.56万行K线，一次性放进内存完全没有压力，
  分块反而会引入上面第1条的边界断档 bug，因此改为一次性向量化计算整段数据。
- 每一个信号都显式记录 `bar_id`（该信号最早可能被观察到时所在的K线 id），下游
  一律用"这个 bar_id 对应K线的下一根K线开盘价"成交（复用 `backtest.run_backtest`
  的撮合逻辑，与缠论买卖点回测完全一致的因果性保证）。
- 订单块方向判断修正为：FVG 触发行（第 i 行，即 3 根K线结构里最前面那根）自身
  是否为反向K线，而不是位移K线（第 i+1 行）。
- 新增摆点（swing high/low）识别与 BOS（结构延续）/CHoCH（结构反转）判断。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd


@dataclass
class SMCPoint:
    kind: str    # '看涨FVG' '看跌FVG' '看涨OB' '看跌OB' 'BOS多' 'BOS空' 'CHoCH多' 'CHoCH空'
    side: str    # 'buy' 或 'sell'，与 chanlun_engine.BSPoint 保持同一接口，可直接复用 backtest.run_backtest
    dt: object   # 信号触发所在K线的时间（仅展示用，不用于成交）
    price: float
    bar_id: int  # 该信号最早可能被观察到时所在的K线 id（用于下一根K线开盘价成交，避免未来函数）


class SMCEngine:
    def __init__(
        self,
        bars,
        swing_window: int = 3,
        volume_ma_window: int = 20,
        fvg_vol_mult: float = 1.5,
    ):
        """
        :param bars: RawBar 列表（与 chanlun_engine.load_bars 输出格式一致）
        :param swing_window: 摆点确认所需的左右各多少根K线（越大，摆点越"重要"但确认越滞后）
        :param volume_ma_window: 成交量均线窗口
        :param fvg_vol_mult: FVG 位移K线的放量倍数阈值
        """
        self.bars = bars
        self.swing_window = swing_window
        self.volume_ma_window = volume_ma_window
        self.fvg_vol_mult = fvg_vol_mult
        self.df = self._build_frame(bars)

    @staticmethod
    def _build_frame(bars) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "id": [b.id for b in bars],
                "dt": [b.dt for b in bars],
                "open": [b.open for b in bars],
                "high": [b.high for b in bars],
                "low": [b.low for b in bars],
                "close": [b.close for b in bars],
                "volume": [b.vol for b in bars],
            }
        )

    def _detect_fvg_and_ob(self, df: pd.DataFrame) -> List[SMCPoint]:
        """FVG（失衡区）与订单块（OB）。整段一次性向量化计算，不分块，杜绝 chunk 边界断档。"""
        vol_ma = df["volume"].rolling(window=self.volume_ma_window, min_periods=self.volume_ma_window).mean()

        # 位移K线是第 i+1 行（3根K线结构里中间那根），放量应该看它，而不是触发行自己
        vol_mid = df["volume"].shift(-1)
        vol_ma_mid = vol_ma.shift(-1)
        low_fwd2 = df["low"].shift(-2)
        high_fwd2 = df["high"].shift(-2)

        is_bullish_fvg = (low_fwd2 > df["high"]) & (vol_mid > vol_ma_mid * self.fvg_vol_mult)
        is_bearish_fvg = (high_fwd2 < df["low"]) & (vol_mid > vol_ma_mid * self.fvg_vol_mult)
        is_bullish_fvg = is_bullish_fvg.fillna(False)
        is_bearish_fvg = is_bearish_fvg.fillna(False)

        # 订单块 = FVG 触发行（第 i 行）自身是反向K线，而不是位移K线（原代码的 bug）
        is_bullish_ob = is_bullish_fvg & (df["close"] < df["open"])
        is_bearish_ob = is_bearish_fvg & (df["close"] > df["open"])

        # confirmed_bar_id：第 i 行的信号要用到第 i+2 行的价格，所以最早在第 i+2 行才能被观察到。
        # 最后两行没有 i+2，天然无法确认，NaN 会被 notna() 过滤掉——这是正确的因果边界，不是 bug。
        confirmed_id = df["id"].shift(-2)
        valid = confirmed_id.notna()

        points: List[SMCPoint] = []

        def _collect(mask: pd.Series, kind: str, side: str):
            sel = mask & valid
            for dt, price, cid in zip(df.loc[sel, "dt"], df.loc[sel, "close"], confirmed_id[sel]):
                points.append(SMCPoint(kind, side, dt, float(price), int(cid)))

        _collect(is_bullish_fvg, "看涨FVG", "buy")
        _collect(is_bearish_fvg, "看跌FVG", "sell")
        _collect(is_bullish_ob, "看涨OB", "buy")
        _collect(is_bearish_ob, "看跌OB", "sell")
        return points

    def _detect_structure(self, df: pd.DataFrame) -> List[SMCPoint]:
        """摆点识别 + BOS/CHoCH 判断。

        摆点确认：第 i 行是摆高点，要求它是 [i-w, i+w] 窗口内的最高点——这必然要等到
        第 i+w 行走完才能确认，因此摆高/摆低点的"可观察时刻"是 i+w，不是 i 本身。

        结构状态机：维护"当前趋势方向"和"下一个待突破的摆高/摆低"（取最近一个已确认
        的摆点，而不是历史最高/最低点——这是 BOS/CHoCH 的标准定义：只关心离现在最近
        的结构关键位）。逐K线扫描收盘价：
        - 收盘价突破待突破的摆高点：若之前趋势不是"多头"，判定为 CHoCH多（结构反转）；
          若之前已经是多头，判定为 BOS多（结构延续）；随后趋势状态更新为多头，
          待突破摆高点清空，等待下一个新确认的摆高点。
        - 收盘价跌破待突破的摆低点：对称处理。
        全程只使用"扫描到当前行为止、已经满足确认条件"的摆点，不会用到未来数据。
        """
        w = self.swing_window
        n = len(df)
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        ids = df["id"].to_numpy()
        dts = df["dt"].to_numpy()

        # 摆点识别：用居中滚动窗口的极值做向量化判断（比逐行 python 循环快得多）
        roll_max = df["high"].rolling(window=2 * w + 1, center=True).max()
        roll_min = df["low"].rolling(window=2 * w + 1, center=True).min()
        is_swing_high = (df["high"] == roll_max) & roll_max.notna()
        is_swing_low = (df["low"] == roll_min) & roll_min.notna()
        swing_high_idx = np.flatnonzero(is_swing_high.to_numpy())
        swing_low_idx = np.flatnonzero(is_swing_low.to_numpy())

        points: List[SMCPoint] = []
        trend = None  # None / 'up' / 'down'
        pending_high = None  # (price, confirmed_at_idx)
        pending_low = None
        sh_ptr = 0
        sl_ptr = 0

        for i in range(n):
            # 把这一时刻已经"确认"（idx+w <= i）的新摆点纳入候选，始终取最近一个（覆盖旧的）
            while sh_ptr < len(swing_high_idx) and swing_high_idx[sh_ptr] + w <= i:
                idx = swing_high_idx[sh_ptr]
                pending_high = (highs[idx], idx)
                sh_ptr += 1
            while sl_ptr < len(swing_low_idx) and swing_low_idx[sl_ptr] + w <= i:
                idx = swing_low_idx[sl_ptr]
                pending_low = (lows[idx], idx)
                sl_ptr += 1

            if pending_high is not None and closes[i] > pending_high[0]:
                kind = "BOS多" if trend == "up" else "CHoCH多"
                points.append(SMCPoint(kind, "buy", dts[i], float(closes[i]), int(ids[i])))
                trend = "up"
                pending_high = None
            if pending_low is not None and closes[i] < pending_low[0]:
                kind = "BOS空" if trend == "down" else "CHoCH空"
                points.append(SMCPoint(kind, "sell", dts[i], float(closes[i]), int(ids[i])))
                trend = "down"
                pending_low = None

        return points

    def run(self) -> Tuple[List[SMCPoint], List[int]]:
        """返回 (points, exec_bar_ids)，exec_bar_ids 即每个信号的 confirmed bar_id，
        与 chanlun_engine 的用法完全一致：下游一律用 exec_bar_id 对应K线的下一根
        K线开盘价成交。"""
        points = self._detect_fvg_and_ob(self.df) + self._detect_structure(self.df)
        points.sort(key=lambda p: p.bar_id)

        # 自证：任何信号的 confirmed bar_id 都不应该早于该信号自身触发行的时间——
        # 这是最基本的因果性检查，防止未来重构时不小心引入未来函数
        dt_by_id = {int(row.id): row.dt for row in self.df.itertuples(index=False)}
        for p in points:
            if p.bar_id not in dt_by_id:
                raise RuntimeError(f"信号的 confirmed bar_id={p.bar_id} 不在K线序列范围内，存在越界风险")
            if dt_by_id[p.bar_id] < p.dt:
                raise RuntimeError(
                    f"检测到未来函数：信号 {p.kind}@{p.dt} 的确认K线时间 {dt_by_id[p.bar_id]} "
                    f"早于信号触发时间，说明确认时刻计算有误"
                )

        exec_bar_ids = [p.bar_id for p in points]
        return points, exec_bar_ids
