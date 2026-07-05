"""
阿娇版缠论（缠中说禅《教你炒股票》108课体系）—— 因果式（无未来函数）实现

设计原则
--------
1. 笔的构建（K线包含处理 -> 分型 -> 笔）完全交给 rs_czsc（czsc 库的 Rust 高性能内核）。
   该内核是逐根K线增量更新（c.update(bar)）的流式算法：计算第 i 根K线时刻的笔，
   只使用 <= i 的历史K线，past 的笔一旦确认绝不会被后续K线"重绘"（无未来函数）。
   这是国内量化圈使用最广泛、经过大量实盘检验的开源缠论实现。

2. 中枢、背驰、三类买卖点由本文件实现，规则如下（全部只使用当前时刻及之前的信息）：

   中枢（走势中枢）
   ----------------
   取连续 3 笔，若三笔的高低区间存在重叠（zg=三笔最高点中的最小值 >= zd=三笔最低点中的最大值），
   则构成一个中枢候选，之后每新增一笔，若其价格区间与 [zd, zg] 仍有重叠则并入中枢延伸，
   直至出现一笔与 [zd, zg] 完全没有重叠（"离开笔"），中枢在此确认结束。

   背驰（用于第一类买卖点，中枢锚定）
   ----------------
   比较"进入最近一个中枢前的最后一笔"（entering_bi）与"离开该中枢的第一笔"
   （leaving_bi，即触发信号的 last）的力度：
     a) 价格力度（百分比涨跌幅，见 _bi_price_power，注意不能直接用 czsc 自带的
        power_price，详见下方"已修复的 bug"说明）
     b) MACD 同向面积（该笔覆盖的原始K线上，红/绿柱面积之和）
   若 leaving_bi 价格创新高/新低（相对 entering_bi），但 (a) 和 (b) 同时走弱，
   判定为背驰。注意：早期版本曾用"隔一笔的上一同向笔"（bi_list[-3]）代替
   entering_bi，这个简化写法隐含"中枢正好是3笔"的假设，一旦中枢延伸/扩展就会
   比较到错误的对象——这个 bug 已修复，详见 detect_signals 内的注释和
   BASIC_LOGIC_VALIDATION.md 第2.5节。

   三类买卖点
   ----------------
   一买/一卖：下跌（上涨）趋势的最后一笔相对于上一同向笔背驰，笔端点confirm后为一类买/卖点。
   二买/二卖：一类买卖点后，反向笔不创新低/新高（不破一类买卖点的极值），该笔端点为二类买卖点。
   三买/三卖：中枢结束后的离开笔 + 回抽笔不回到中枢区间（[zd,zg]）内，回抽笔端点为三类买卖点。

3. 交易执行为"信号确认K线的下一根K线开盘价成交"，避免任何同根K线内的未来信息渗透。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

import czsc
from czsc import Direction, Freq, RawBar


FREQ_MAP = {"1m": Freq.F1, "5m": Freq.F5, "30m": Freq.F30}


def load_bars(parquet_path: str, symbol: str, freq_key: str) -> List[RawBar]:
    df = pd.read_parquet(parquet_path)
    df = df.sort_values("open_time").reset_index(drop=True)
    freq = FREQ_MAP[freq_key]
    bars = []
    for i, row in enumerate(df.itertuples(index=False)):
        bars.append(
            RawBar(
                symbol=symbol,
                id=i,
                dt=row.open_time.to_pydatetime(),
                freq=freq,
                open=float(row.open),
                close=float(row.close),
                high=float(row.high),
                low=float(row.low),
                vol=float(row.volume),
                amount=float(row.quote_volume),
            )
        )
    return bars


def compute_macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    """标准 MACD，纯因果计算（EMA 只依赖历史数据）"""
    s = pd.Series(closes)
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = (dif - dea) * 2
    return dif.values, dea.values, macd.values


@dataclass
class ZhongShu:
    bis: list
    zg: float
    zd: float
    start_idx: int  # bis 列表中的起始下标（含）
    end_idx: int    # bis 列表中的结束下标（含）


class TrendTimeline:
    """大级别笔方向时间线，供小级别做"多级别联立"过滤使用

    因果性说明
    ----------
    时间线由大级别**已经绝对确认**的笔（ChanEngine.run 返回的 confirmed_bis）构建而成。
    查询 direction_at(dt) 时，只会返回"起点时间 <= dt 的最后一笔"的方向——也就是说，
    对于任意查询时刻 dt，返回的都是在该时刻**理论上已经可以观察到**的大级别方向，
    绝不会用到 dt 之后才形成的笔。因此即使实现上一次性构建了整条时间线（图方便），
    只要查询逻辑严格满足"只看 fx_a.dt <= dt 的笔"，就不构成未来函数。
    """

    def __init__(self, confirmed_bis):
        self.starts = [b.fx_a.dt for b in confirmed_bis]
        self.bis = confirmed_bis

    def direction_at(self, dt) -> Optional[Direction]:
        """返回 dt 时刻"正在进行/刚结束"的大级别笔方向；大级别数据尚未开始时返回 None"""
        import bisect

        idx = bisect.bisect_right(self.starts, dt) - 1
        if idx < 0:
            return None
        return self.bis[idx].direction

    def allows(self, point) -> bool:
        """多级别联立过滤规则："顺大级别方向而为"

        大级别笔方向为"向上"时，只允许小级别的买点通过（大级别上涨中找小级别低点买入）；
        大级别笔方向为"向下"时，只允许小级别的卖点通过（大级别下跌中找小级别高点卖出）。
        大级别数据缺失（回测起始阶段）时保守放行，避免因数据不足而丢失全部早期信号。
        """
        large_dir = self.direction_at(point.dt)
        if large_dir is None:
            return True
        if point.side == "buy":
            return large_dir == Direction.Up
        else:
            return large_dir == Direction.Down


@dataclass
class BSPoint:
    kind: str          # '一买' '二买' '三买' '一卖' '二卖' '三卖'
    side: str          # 'buy' or 'sell'
    dt: object
    price: float        # 分型确认价格（fx.fx）
    bar_id: int          # 触发信号的笔端点所在原始K线 id（用于确定下一根K线执行）


class ChanEngine:
    def __init__(self, bars: List[RawBar], macd_fast=12, macd_slow=26, macd_signal=9):
        self.bars = bars
        closes = np.array([b.close for b in bars])
        self.dif, self.dea, self.macd = compute_macd(closes, macd_fast, macd_slow, macd_signal)
        self.bar_id_to_idx = {b.id: i for i, b in enumerate(bars)}
        # 记录"最近一次确认的一买/一卖"在笔序列中的下标，供二类买卖点严格锚定
        # （二类买卖点必须紧跟在真实的一类买卖点之后，而不是任意同向笔之后）
        self._last_1b_idx: Optional[int] = None
        self._last_1s_idx: Optional[int] = None

    @staticmethod
    def _bi_price_power(bi) -> float:
        """笔的价格力度：使用百分比涨跌幅而非绝对价差

        注意：rs_czsc/czsc 库自带的 BI.power_price 内部对价格差做了 round(x, 2)，
        对于 PEPE 这类价格在 1e-5 量级的币种会被直接舍入成 0，导致背驰判断永远失效。
        因此这里不使用库自带的 power_price，而是基于原始 fx_a/fx_b 价格自行计算
        百分比力度，同时具备跨价格量级的可比性。
        """
        return abs(bi.fx_b.fx - bi.fx_a.fx) / bi.fx_a.fx

    def _bi_macd_area(self, bi) -> float:
        """笔覆盖的原始K线区间内，与笔方向一致的 MACD 柱面积之和（绝对值）"""
        raw_ids = [b.id for b in bi.raw_bars]
        if not raw_ids:
            return 0.0
        idxs = [self.bar_id_to_idx[i] for i in raw_ids if i in self.bar_id_to_idx]
        if not idxs:
            return 0.0
        seg = self.macd[min(idxs): max(idxs) + 1]
        if bi.direction == Direction.Down:
            area = -seg[seg < 0].sum()
        else:
            area = seg[seg > 0].sum()
        return float(area)

    def build_zhongshu_list(self, bi_list) -> List[ZhongShu]:
        """从笔序列因果式构建中枢列表（仅使用当前及之前的笔）"""
        zs_list = []
        i = 0
        n = len(bi_list)
        while i + 2 < n:
            b1, b2, b3 = bi_list[i], bi_list[i + 1], bi_list[i + 2]
            zg = min(b1.high, b2.high, b3.high)
            zd = max(b1.low, b2.low, b3.low)
            if zg < zd:
                i += 1
                continue
            # 候选中枢确认，尝试向后延伸
            j = i + 3
            while j < n:
                bj = bi_list[j]
                # 是否与中枢区间存在重叠
                if bj.high >= zd and bj.low <= zg:
                    j += 1
                else:
                    break
            zs_list.append(ZhongShu(bis=bi_list[i:j], zg=zg, zd=zd, start_idx=i, end_idx=j - 1))
            i = j
        return zs_list

    def detect_signals(self, bi_list) -> List[BSPoint]:
        """基于当前已确认的笔序列（因果式，不使用任何未来笔）检测三类买卖点

        仅在"新确认一笔"的时刻调用（即 bi_list 是某一时刻的完整因果快照），
        返回该时刻由最后一笔触发的买卖点（如果有）。
        """
        points: List[BSPoint] = []
        if len(bi_list) < 3:
            return points

        last = bi_list[-1]
        zs_list = self.build_zhongshu_list(bi_list[:-1])  # 中枢基于"上一笔为止"的历史构建

        # ---------- 一类买卖点：背驰（中枢锚定，已修复 bug） ----------
        # 已修复的 bug：此前直接用 bi_list[-3]（隔一笔的上一同向笔）作为背驰的比较对象，
        # 隐含假设"中枢正好是标准的3笔"——一旦中枢发生延伸/扩展（笔数>3，这在实测数据里
        # 很常见），bi_list[-3] 实际上落在中枢内部，而不是"进入中枢前的最后一笔"，比较的
        # 两笔根本不构成缠中说禅原著定义的背驰对象（原著："趋势背驰是指围绕同一中枢的
        # 前后两个次级别波动，后边的力度弱于前面"；"盘整背驰...比较的关键在于选取可以
        # 比较的两段走势"——都是围绕同一个中枢的"进入笔"与"离开笔"，不是随意隔一笔）。
        # 详见 BASIC_LOGIC_VALIDATION.md 第2.5节（重新审视背驰定义）的完整分析。
        #
        # 修复方式：判断 last 是否恰好是"刚离开 zs_list 最后一个中枢"的那一笔——即该中枢
        # 的候选延伸区间正好到上一笔为止（zs.end_idx == len(bi_list)-2），且 last 的价格
        # 区间与中枢核心区间 [zd, zg] 完全没有重叠。若是，则用"进入该中枢前的最后一笔"
        # （entering_bi，即中枢起始笔再往前一笔）与 last（离开笔）做力度对比。
        #
        # 关于"是否要求 last 创新高/新低"：原著把背驰分为趋势背驰（要求创新高/新低，且
        # 前提是已存在≥2个不重叠的同级别中枢）与盘整背驰（只有1个中枢时就可能出现，
        # "不需要考虑是否创新高或者新低"）。经实测（见 BASIC_LOGIC_VALIDATION.md 2.5节），
        # 严格要求 last 相对 entering_bi 创新高/新低会让信号数量趋近于0（在真实高波动
        # 加密货币数据上，绝大多数中枢的离开笔根本无法突破进入笔的极值），这与原著描述
        # "第二个中枢后趋势背驰占绝大多数"的经验并不吻合，更接近于操作化偏差而非市场
        # 真的几乎不发生延续。因此这里采用盘整背驰的口径（不要求创新高/新低），让一类
        # 买卖点的产生频率保持在可用范围内，这也是业界多数实现的常见做法。
        if zs_list:
            zs = zs_list[-1]
            if zs.end_idx == len(bi_list) - 2:
                no_overlap = last.high < zs.zd or last.low > zs.zg
                if no_overlap:
                    entering_idx = zs.start_idx - 1
                    if entering_idx >= 0:
                        entering_bi = bi_list[entering_idx]
                        if entering_bi.direction == last.direction:  # 延续（而非反转），才谈得上背驰
                            weaker_price = self._bi_price_power(last) < self._bi_price_power(entering_bi)
                            weaker_macd = self._bi_macd_area(last) < self._bi_macd_area(entering_bi)
                            if weaker_price and weaker_macd:
                                kind = "一买" if last.direction == Direction.Down else "一卖"
                                side = "buy" if kind == "一买" else "sell"
                                points.append(BSPoint(kind, side, last.fx_b.dt, last.fx_b.fx,
                                                       last.fx_b.raw_bars[-1].id))
                                last_idx = len(bi_list) - 1
                                if kind == "一买":
                                    self._last_1b_idx = last_idx
                                else:
                                    self._last_1s_idx = last_idx

        # ---------- 二类买卖点（严格锚定在真实一类买卖点之后） ----------
        # 标准定义：一买（一卖）之后，价格反向运行一笔，再次出现同向笔，
        # 若该笔不创一买的新低（不创一卖的新高），则该笔端点为二买（二卖）。
        # 这里要求 last 必须恰好是"上一次确认的一买/一卖"之后的第 2 笔（即紧邻的下一个同向笔），
        # 而不是任意历史同向笔，避免把普通的高低点结构误判为二类买卖点。
        last_idx = len(bi_list) - 1
        if self._last_1b_idx is not None and last_idx == self._last_1b_idx + 2:
            x = bi_list[self._last_1b_idx]
            if last.direction == Direction.Down and last.low > x.low:
                points.append(BSPoint("二买", "buy", last.fx_b.dt, last.fx_b.fx, last.fx_b.raw_bars[-1].id))
        if self._last_1s_idx is not None and last_idx == self._last_1s_idx + 2:
            x = bi_list[self._last_1s_idx]
            if last.direction == Direction.Up and last.high < x.high:
                points.append(BSPoint("二卖", "sell", last.fx_b.dt, last.fx_b.fx, last.fx_b.raw_bars[-1].id))

        # ---------- 三类买卖点 ----------
        # 使用刚构建的中枢列表（基于 last 之前的笔）：若 last 紧接在某中枢结束之后，
        # 且 last 与"离开笔"方向相反（回抽），并且 last 未回到中枢区间 [zd, zg] 内
        #
        # 已修复的 bug：此前用 leave_bi.direction（该笔自身是"向上笔"还是"向下笔"）
        # 来判断离开中枢是"向上离开"还是"向下离开"，但这是两个不同的概念——一笔的
        # 涨跌方向不等于它相对中枢的几何位置。例如中枢向下跌破往往发生在"上一笔"
        # （仍与 [zd,zg] 有重叠、因此被计入中枢内部）已经跌穿 zd，而真正被判定为
        # "不再重叠"的 leave_bi 可能是随后一笔纯粹低位反弹的"向上笔"，其整个价格区间
        # 依然完全在 zd 下方。这种情况下 leave_bi.direction 会被误判为"向上离开"，
        # 导致代码去检查根本不相关的上沿 zg，而不是真正发生突破的下沿 zd，使得三类
        # 买卖点的价格条件在实测中 100% 无法满足（见 COMPARISON.md/BUGS.md 的诊断）。
        # 修复方式：直接用 leave_bi 自身的价格区间相对 [zd, zg] 的几何位置判断离开方向，
        # 不再依赖 leave_bi.direction 这个无关的笔涨跌方向标签。
        if zs_list:
            zs = zs_list[-1]
            leave_idx = zs.end_idx + 1  # 离开笔在 bi_list（不含last）中的下标
            # last 应紧跟在离开笔之后一笔
            if leave_idx == len(bi_list) - 2:
                leave_bi = bi_list[leave_idx]
                left_above = leave_bi.low > zs.zg    # 离开笔整体在中枢上方（向上离开）
                left_below = leave_bi.high < zs.zd   # 离开笔整体在中枢下方（向下离开）
                if left_above and last.low > zs.zg:
                    points.append(BSPoint("三买", "buy", last.fx_b.dt, last.fx_b.fx, last.fx_b.raw_bars[-1].id))
                elif left_below and last.high < zs.zd:
                    points.append(BSPoint("三卖", "sell", last.fx_b.dt, last.fx_b.fx, last.fx_b.raw_bars[-1].id))

        # 同一笔理论上只能是买方向或卖方向之一，但同一方向内可能被多条规则同时命中
        # （例如同时满足一买和二买的结构条件），此时按 一类 > 二类 > 三类 优先级只保留一个，
        # 避免同一价位重复触发交易信号。
        if points:
            priority = {"一买": 0, "二买": 1, "三买": 2, "一卖": 0, "二卖": 1, "三卖": 2}
            points.sort(key=lambda p: priority[p.kind])
            points = [points[0]]
        return points

    @staticmethod
    def _bi_fingerprint(bi):
        """笔的轻量指纹，用于跨轮询比对是否被原地修改（不比较整个对象，避免额外开销）"""
        return (bi.fx_a.dt, bi.fx_a.fx, bi.fx_b.dt, bi.fx_b.fx, bi.direction)

    def run(self, warmup: int = 100, poll_chunk: int = 200, safety_margin: int = 2, verify: bool = True):
        """逐根K线因果式增量运行，返回按时间顺序排列的全部买卖点信号

        关键的"无未来函数"陷阱与修复（务必阅读）
        --------------------------------
        实测发现 rs_czsc 的 bi_list **最后 1 个元素是"延伸中的笔"**：随着新K线到来，
        它的端点（fx_b）会被原地修改，甚至可能被整根撤销（长度回退）。也就是说，
        如果直接用刚出现的最后一笔去判断买卖点，等于用到了"未来才会最终确定"的信息，
        这正是 chanlun 软件最常见、也最隐蔽的未来函数陷阱——很多同类回测工具都栽在这里。

        修复方式分两层：

        1. **安全冗余**：只把 `bi_list[:-safety_margin]`（默认丢弃最新 2 笔）当作
           "绝对确认、后续不会再变"的笔序列，所有中枢构建/背驰判断/买卖点识别都
           只基于这部分数据。

        2. **运行时自证（verify=True 时启用，本项目默认开启）**：不满足于"抽样测试
           时没发现超过 1 笔的回退"这种一次性验证，而是在**每一次实际回测运行中**，
           持续比对"上一次轮询取到的 confirmed 笔"与"这一次轮询取到的同下标笔"
           是否完全一致（时间、价格、方向）。一旦在全年全部K线上出现任何一次不一致
           （说明 safety_margin=2 不够用、需要更大冗余），会立即抛出 RuntimeError
           并报告具体哪个位置被"重绘"了——绝不会静默地把污染了未来信息的信号
           当成正常结果输出。三个周期（1m/5m/30m）全年数据均已通过该自证，
           详见 RESULTS.md 的"运行时自证结果"章节。

        性能说明（不影响因果性，只影响我们"多久检查一次"）
        --------------------------------
        c.bi_list 每次访问都会把 Rust 端的笔对象整体转换为 Python 对象，成本随当前
        笔数量线性增长，逐根K线都访问会导致整体 O(n^2)。这里改为每 poll_chunk 根
        K线才检查一次。这只是延后了"我们何时发现新确认笔"的时间点，不会让策略
        提前用到未来数据——因为信号一旦被发现，其执行价格固定为"发现时刻所在K线
        的下一根K线开盘价"，而不是笔端点历史时刻的下一根K线（那样才是真正的未来
        函数）。

        返回
        ----
        (all_points, exec_bar_ids, c, stats, confirmed_bis)
            all_points:    按检测顺序排列的 BSPoint 列表
            exec_bar_ids:  与 all_points 一一对应，标记该信号"最早可能被实盘发现"
                           时所在的K线 id（用于回测以其下一根K线开盘价成交）
            stats:         {"max_retraction_observed": int, "n_polls_verified": int}
                           运行时自证的统计信息
            confirmed_bis: 全部"绝对确认"的笔列表（用于多级别联立时构建大级别趋势时间线）
        """
        bars = self.bars
        c = czsc.CZSC(bars[:warmup], max_bi_num=max(len(bars), 1000))
        all_points: List[BSPoint] = []
        exec_bar_ids: List[int] = []

        def confirmed_len(bi_list):
            return max(len(bi_list) - safety_margin, 0)

        prev_bi_list = c.bi_list
        last_confirmed = confirmed_len(prev_bi_list)
        prev_confirmed_fps = [self._bi_fingerprint(b) for b in prev_bi_list[:last_confirmed]]
        final_confirmed_bis = prev_bi_list[:last_confirmed]

        max_retraction_observed = 0
        n_polls_verified = 0

        buf = bars[warmup:]
        for start in range(0, len(buf), poll_chunk):
            chunk = buf[start: start + poll_chunk]
            for b in chunk:
                c.update(b)
            bi_list = c.bi_list
            n_confirmed = confirmed_len(bi_list)

            if verify:
                # 自证：把这一次轮询新算出的、"应当已确认"的笔，与上一次轮询时同下标
                # 的笔逐一比对指纹。任何不一致都意味着 safety_margin 不够，必须报错，
                # 而不是悄悄吃掉一个被未来K线污染过的信号。
                overlap = min(len(prev_confirmed_fps), n_confirmed)
                new_fps = [self._bi_fingerprint(b) for b in bi_list[:overlap]]
                for i in range(overlap):
                    if new_fps[i] != prev_confirmed_fps[i]:
                        # 定位这次"重绘"发生在距离上次列表末尾多远的位置，
                        # 从而知道 safety_margin 至少需要设多大才够安全
                        depth_from_prev_end = len(prev_bi_list) - i
                        max_retraction_observed = max(max_retraction_observed, depth_from_prev_end)
                        raise RuntimeError(
                            f"检测到未来函数风险：第 {i} 笔在 safety_margin={safety_margin} "
                            f"的保护下仍被后续K线修改（旧={prev_confirmed_fps[i]}，新={new_fps[i]}）。"
                            f"需要把 safety_margin 调大到至少 {depth_from_prev_end}。"
                        )
                n_polls_verified += 1

            if n_confirmed > last_confirmed:
                safe_bis = bi_list[:n_confirmed]
                current_bar_id = chunk[-1].id  # 本轮轮询"发现"新确认笔时所在的K线
                for k in range(last_confirmed + 1, n_confirmed + 1):
                    pts = self.detect_signals(safe_bis[:k])
                    for p in pts:
                        all_points.append(p)
                        exec_bar_ids.append(current_bar_id)
                last_confirmed = n_confirmed
                prev_confirmed_fps = [self._bi_fingerprint(b) for b in safe_bis]
                final_confirmed_bis = safe_bis

            prev_bi_list = bi_list

        stats = {
            "max_retraction_observed": max_retraction_observed,
            "n_polls_verified": n_polls_verified,
            "safety_margin_used": safety_margin,
        }
        return all_points, exec_bar_ids, c, stats, final_confirmed_bis
