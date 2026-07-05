"""
线段（Duan）构建 —— 用于检验缠论"小转大"（级别的结构递归定义）

背景：用户提问"缠论有个小转大，考虑了吗？"

之前 `chanlun_engine.TrendTimeline` 做"多级别联立"时，"大级别"直接取的是**固定时钟周期**
的K线（1m的大级别用5m，5m的大级别用30m）重新走一遍笔构建流程。这是国内量化圈最常见的
简化做法，但严格来说**不等于**缠论原著里"级别"的真正定义——原著里"级别"是纯结构性、
递归定义的：K线->分型->笔->线段->中枢->走势，而这个"走势"本身在下一级别里就被看成"一笔"。
也就是说，级别的划分理论上不需要绑定任何具体的固定时钟周期，一段足够复杂的低级别走势
（典型地，笔经过特征序列分解后被识别为一个完整的"线段"），本身就应该被看成上一级别的
一笔——这就是"小转大"：不是"resample成更大的K线"，而是"低级别的结构复杂到了一定程度，
自动升级成了大级别的构件"。

这个模块实现标准的"特征序列法"线段构建算法，让"大级别方向"可以完全从**同一份低级别数据
自身的结构**里递归推导出来，而不依赖任何固定时钟周期的重采样——用来检验：
    "用固定时钟周期重采样得到的大级别方向"和"用结构递归（线段）得到的大级别方向"，
    到底有多大差异？这个差异有多大程度上影响了多级别联立回测的结果？

标准算法（缠论"论线段"一课的核心规则，这里是简化实现，见 build_duan_list 文档字符串
里的"已知简化"）：
1. 线段方向 = 其第一笔方向。
2. 用线段方向"反向"的笔构造特征序列（每个元素是该反向笔的 [low, high] 区间），
   对特征序列做包含处理（合并规则与K线包含处理一致，方向服从线段方向）。
3. 在处理后的特征序列上找分型（连续3个元素，中间元素的高点/低点为极值）——
   出现分型即为线段结束信号，分型对应的"反向笔"之前的最后一笔（达到极值的同向笔）
   为本线段的最后一笔，新线段从该反向笔开始。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from czsc import Direction


@dataclass
class Duan:
    bis: list
    direction: Direction

    @property
    def fx_a(self):
        return self.bis[0].fx_a

    @property
    def fx_b(self):
        return self.bis[-1].fx_b

    @property
    def high(self) -> float:
        return max(b.high for b in self.bis)

    @property
    def low(self) -> float:
        return min(b.low for b in self.bis)


def _merge_char_seq(char_seq: list, new_elem: tuple, direction: Direction) -> bool:
    """特征序列包含处理。返回是否发生了合并（False=作为新元素追加）"""
    lo, hi = new_elem
    if char_seq:
        plo, phi = char_seq[-1]
        contains = (lo >= plo and hi <= phi) or (lo <= plo and hi >= phi)
        if contains:
            if direction == Direction.Up:
                char_seq[-1] = (max(lo, plo), max(hi, phi))
            else:
                char_seq[-1] = (min(lo, plo), min(hi, phi))
            return True
    char_seq.append((lo, hi))
    return False


def build_duan_list(bi_list) -> List[Duan]:
    """从笔序列构建线段（特征序列法，简化实现）

    已知简化/局限（详见 DUAN_CONFLUENCE.md 的方法论说明章节）：
    - 未实现标准算法里"分型确认后还需要后续笔价格突破分型笔极值"这一额外确认步骤，
      分型本身出现即视为线段结束，是相对宽松的近似（可能略微提前判定线段结束）。
    - 未处理"缺口线段"（一笔缺口过大时可以不需要典型分型直接判定线段结束）等特殊情形。
    - 新旧线段是否共享分界笔，本身在缠论原著和各家实现里就存在争议，这里采用
      "反向笔归入新线段"的最常见约定。
    - 序列末尾如果一直没有出现分型，剩余的笔构成一个"尚未走完"的线段（与笔序列本身
      "最后几笔可能是延伸中的"这个因果性问题一致，使用时应同样只信任非最后一段）。
    """
    duans: List[Duan] = []
    n = len(bi_list)
    if n < 3:
        return duans

    i = 0
    while i < n:
        direction = bi_list[i].direction
        char_seq: list = []
        char_seq_bi_idx: list = []
        end_idx = n - 1
        found_end = False
        j = i + 1
        while j < n:
            bj = bi_list[j]
            if bj.direction != direction:
                merged = _merge_char_seq(char_seq, (bj.low, bj.high), direction)
                if merged:
                    char_seq_bi_idx[-1] = j
                else:
                    char_seq_bi_idx.append(j)
                if len(char_seq) >= 3:
                    a, b, c = char_seq[-3], char_seq[-2], char_seq[-1]
                    if direction == Direction.Up:
                        is_fractal = b[1] > a[1] and b[1] > c[1]
                    else:
                        is_fractal = b[0] < a[0] and b[0] < c[0]
                    if is_fractal:
                        reversal_bi_idx = char_seq_bi_idx[-2]
                        end_idx = max(reversal_bi_idx - 1, i)
                        found_end = True
                        break
            j += 1
        duans.append(Duan(bis=bi_list[i:end_idx + 1], direction=direction))
        i = end_idx + 1 if found_end else n
    return duans
