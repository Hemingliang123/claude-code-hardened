"""smc_engine.py 的最小自测：合成数据验证 FVG/OB/BOS/CHoCH 检测逻辑与因果性。"""
import datetime as dt

from czsc import RawBar, Freq
from smc_engine import SMCEngine


def make_bar(i, o, h, l, c, v, base=dt.datetime(2026, 1, 1)):
    return RawBar(
        symbol="TEST", id=i, dt=base + dt.timedelta(minutes=i), freq=Freq.F1,
        open=o, high=h, low=l, close=c, vol=v, amount=v * c,
    )


def test_bullish_fvg_and_ob():
    bars = []
    # 铺垫20根平稳K线，把成交量均线抬到 100 左右
    for i in range(20):
        bars.append(make_bar(i, 10, 10.5, 9.5, 10, 100))
    # 第20行：阴线（未来的看涨OB候选）
    bars.append(make_bar(20, 10, 10.2, 9.8, 9.9, 100))
    # 第21行：位移K线，放量拉升（成交量 > 1.5倍均量）
    bars.append(make_bar(21, 9.9, 13.0, 9.9, 12.8, 500))
    # 第22行：留下向上跳空缺口，low(22) > high(20)
    bars.append(make_bar(22, 12.8, 13.5, 12.5, 13.2, 200))
    # 收尾再铺几根，保证有足够 confirm 空间
    for i in range(23, 30):
        bars.append(make_bar(i, 13, 13.2, 12.8, 13, 100))

    engine = SMCEngine(bars, swing_window=3, volume_ma_window=20, fvg_vol_mult=1.5)
    points, exec_bar_ids = engine.run()
    kinds = [p.kind for p in points]
    assert "看涨FVG" in kinds, f"应检测到看涨FVG，实际信号: {kinds}"
    assert "看涨OB" in kinds, f"应检测到看涨OB（第20行阴线），实际信号: {kinds}"

    ob_points = [p for p in points if p.kind == "看涨OB"]
    assert ob_points[0].bar_id == 22, f"看涨OB的确认bar应为第22行(id=22)，实际={ob_points[0].bar_id}"
    print("看涨FVG/OB 检测 + 因果确认id: 通过")


def test_no_lookahead_violation():
    """随机造点数据，只要 run() 不抛因果性 RuntimeError 就说明自证通过。"""
    import random
    random.seed(42)
    bars = []
    price = 100.0
    for i in range(500):
        o = price
        c = price + random.uniform(-2, 2)
        h = max(o, c) + random.uniform(0, 1)
        l = min(o, c) - random.uniform(0, 1)
        v = random.uniform(50, 500)
        bars.append(make_bar(i, o, h, l, c, v))
        price = c
    engine = SMCEngine(bars, swing_window=3, volume_ma_window=20, fvg_vol_mult=1.5)
    points, exec_bar_ids = engine.run()
    assert all(b >= 0 for b in exec_bar_ids)
    assert exec_bar_ids == sorted(exec_bar_ids)
    print(f"随机500根K线自证通过，共检测到 {len(points)} 个信号，未触发未来函数报警")


def test_bos_choch():
    # 下跌 -> 途中一个明确的局部反弹高点(摆高点) -> 继续下跌 -> 之后一波强势拉升
    # 突破前面那个摆高点，应该被判定为 CHoCH多（此前趋势是下跌/未定）
    prices = [100, 92, 84, 76, 68, 60, 65, 70, 66, 62, 58, 54,
              60, 68, 76, 85, 95, 108, 122, 138, 150]
    bars = []
    for i, p in enumerate(prices):
        bars.append(make_bar(i, p, p + 1, p - 1, p, 100))
    for k in range(6):
        i = len(prices) + k
        bars.append(make_bar(i, 150, 151, 149, 150, 100))

    engine = SMCEngine(bars, swing_window=2, volume_ma_window=20, fvg_vol_mult=1.5)
    points, exec_bar_ids = engine.run()
    kinds = [p.kind for p in points]
    assert any(k.startswith("CHoCH") or k.startswith("BOS") for k in kinds), f"应至少检测到一次结构突破，实际: {kinds}"
    print(f"BOS/CHoCH 检测: 通过，共检测到结构信号 {[k for k in kinds if 'BOS' in k or 'CHoCH' in k]}")


if __name__ == "__main__":
    test_bullish_fvg_and_ob()
    test_no_lookahead_violation()
    test_bos_choch()
    print("\n全部 smc_engine 自测通过")
