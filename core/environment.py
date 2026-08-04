import abc
from typing import Any, Dict, Tuple

class TradingEnv(abc.ABC):
    """
    市场仿真环境抽象基类 (契合 OpenAI Gym/Gymnasium 规范)
    用于为强化学习(RL)或任何策略提供标准化交互接口。
    """
    
    @abc.abstractmethod
    def reset(self) -> Tuple[Any, Dict[str, Any]]:
        """
        重置环境状态至初始阶段或特定时间戳
        :return: (initial_state, info) 
        """
        pass

    @abc.abstractmethod
    def step(self, action: Any) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
        """
        执行交易动作，推进市场时间 (Event Sourcing / utick step)
        :param action: 交易动作 (如开仓、平仓、修改订单等)
        :return: (next_state, reward, terminated, truncated, info)
        """
        pass

    @abc.abstractmethod
    def render(self):
        """
        可视化当前市场状态、订单簿(OrderBook)与账户资金流
        """
        pass

    @abc.abstractmethod
    def close(self):
        """
        关闭环境并释放资源 (如数据库连接、WebSocket流等)
        """
        pass
