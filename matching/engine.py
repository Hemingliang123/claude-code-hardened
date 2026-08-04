import abc
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Order:
    order_id: str
    symbol: str
    price: float
    quantity: float
    side: str  # 'BUY' or 'SELL'
    order_type: str # 'LIMIT', 'MARKET', 'CANCEL'
    timestamp: datetime
    status: str = "PENDING"

class MatchingEngine(abc.ABC):
    """
    交易所级撮合引擎接口 (Matching Engine Contract)
    """
    
    @abc.abstractmethod
    def submit_order(self, order: Order) -> bool:
        """
        提交订单至撮合队列
        :param order: 订单对象
        :return: 提交是否成功
        """
        pass

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        撤销订单
        :param order_id: 订单唯一标识
        :return: 撤单是否成功
        """
        pass

    @abc.abstractmethod
    def match(self) -> List[Dict]:
        """
        执行撮合逻辑 (Price-Time Priority)
        :return: 撮合生成的成交回报列表 (Fill Events)
        """
        pass
    
    @abc.abstractmethod
    def get_orderbook_snapshot(self, depth: int = 20) -> Dict:
        """
        获取当前订单簿快照 (L2/L3)
        :param depth: 获取的档位深度
        :return: 包含 Bid/Ask 堆的字典快照
        """
        pass
