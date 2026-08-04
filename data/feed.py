import abc
from typing import Iterator, Dict

class DataFeed(abc.ABC):
    """
    市场微观数据流接口 (Market Microstructure Data Contract)
    """
    
    @abc.abstractmethod
    def stream_ticks(self, symbol: str) -> Iterator[Dict]:
        """
        流式输出 Tick 级/逐笔成交(Trade Prints)数据
        :param symbol: 交易对 (如 BTC/USDT)
        :return: Yields Tick Event
        """
        pass

    @abc.abstractmethod
    def stream_orderbook(self, symbol: str, depth: int = 20) -> Iterator[Dict]:
        """
        流式输出 L2/L3 OrderBook 数据，支持事件溯源(Event Sourcing)
        :param symbol: 交易对
        :param depth: 深度
        :return: Yields OrderBook Delta Event
        """
        pass
