"""duan_engine.build_duan_list 的单元测试：用手工构造的笔序列验证线段切分是否符合预期"""
import datetime as dt
from dataclasses import dataclass

from czsc import Direction


@dataclass
class FakeFX:
    dt: object
    fx: float


@dataclass
class FakeBi:
    fx_a: FakeFX
    fx_b: FakeFX
    direction: Direction

    @property
    def high(self):
        return max(self.fx_a.fx, self.fx_b.fx)

    @property
    def low(self):
        return min(self.fx_a.fx, self.fx_b.fx)


def make_bis(points, base=dt.datetime(2026, 1, 1)):
    """points: 价格序列（严格交替涨跌的转折点），依次连成笔"""
    bis = []
    for i in range(len(points) - 1):
        t0 = base + dt.timedelta(minutes=i)
        t1 = base + dt.timedelta(minutes=i + 1)
        direction = Direction.Up if points[i + 1] > points[i] else Direction.Down
        bis.append(FakeBi(FakeFX(t0, points[i]), FakeFX(t1, points[i + 1]), direction))
    return bis


def test_single_clean_uptrend_then_downtrend():
    """一段干净的上涨线段（每次回调都比前一次回调点位更高），随后开始下跌，
    下跌几笔后应该在上涨的最高点处切出线段边界"""
    from duan_engine import build_duan_list

    # 上涨线段：100 -> 130(回调到105) -> 140(回调到115) -> 150(回调到125) -> 160，
    # 每次回调的高点(105,115,125)持续升高，特征序列（回调笔）不会出现顶分型；
    # 随后开始下跌：160 -> 145(反弹到150) -> 148(反弹到146)，
    # 此时反弹笔的高点(150,146)在下降，说明160这个点确实是顶——
    # 特征序列（这里用下跌笔本身，因为是在下跌方向找底分型）：
    # 实际上要制造"上涨线段的顶分型"，需要在【下跌笔】特征序列里出现顶——
    # 即：160->150(第一个回调，高点160，低点150)，然后到140附近再反弹，
    # 让第二个回调笔的高点比第一个回调笔更低，第三个回调笔的高点比第二个更低。
    points = [100, 130, 105, 140, 115, 150, 125, 160,   # 干净上涨，回调点持续抬高
              140, 155, 130, 145]                        # 顶部出现后，反弹高点持续走低(160->155->145)
    bis = make_bis(points)
    duans = build_duan_list(bis)

    assert len(duans) >= 2, f"应至少切出2段，实际={len(duans)}"
    first = duans[0]
    assert first.direction == Direction.Up
    # 第一段应该在触及全局最高点 160 时结束
    assert first.fx_b.fx == 160, f"第一段结束点应为160（顶点），实际={first.fx_b.fx}"

    second = duans[1]
    assert second.direction == Direction.Down


def test_single_clean_downtrend_then_uptrend():
    """镜像测试：下跌线段后接上涨"""
    from duan_engine import build_duan_list

    points = [200, 170, 195, 160, 185, 150, 175, 140,   # 干净下跌，反弹点持续走低
              160, 145, 170, 155]                        # 底部出现后，回调低点持续走高(140->145->155)
    bis = make_bis(points)
    duans = build_duan_list(bis)

    assert len(duans) >= 2
    first = duans[0]
    assert first.direction == Direction.Down
    assert first.fx_b.fx == 140, f"第一段结束点应为140（底点），实际={first.fx_b.fx}"

    second = duans[1]
    assert second.direction == Direction.Up


def test_no_reversal_stays_one_open_duan():
    """如果一直没有出现特征序列分型（持续单边上涨，每次回调都比上次高），
    应该只切出一个（尚未走完的）线段，覆盖全部笔"""
    from duan_engine import build_duan_list

    points = [100, 130, 110, 145, 125, 160, 140, 175]  # 持续新高，回调点持续抬高，永不反转
    bis = make_bis(points)
    duans = build_duan_list(bis)

    assert len(duans) == 1
    assert duans[0].direction == Direction.Up
    assert duans[0].bis == bis  # 全部笔都在这一个尚未走完的线段里


if __name__ == "__main__":
    test_single_clean_uptrend_then_downtrend()
    test_single_clean_downtrend_then_uptrend()
    test_no_reversal_stays_one_open_duan()
    print("全部测试通过")
