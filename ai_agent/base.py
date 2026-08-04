import abc
from typing import Any, Dict

class BaseAgent(abc.ABC):
    """
    AI 智能体基类 (支持 RL / LLM Agent)
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @abc.abstractmethod
    def observe(self, state: Any) -> None:
        """
        接收并处理市场状态与特征 (State Representation)
        :param state: 环境返回的观测值 (如 OrderBook 快照、账户资金)
        """
        pass

    @abc.abstractmethod
    def decide(self) -> Any:
        """
        基于当前观测输出交易动作 (Action)
        LLM Agent可在此进行推理，RL Agent在此通过Policy Network进行前向传播
        :return: action
        """
        pass

    @abc.abstractmethod
    def learn(self, reward: float, next_state: Any, done: bool) -> Dict[str, Any]:
        """
        接收环境的奖励反馈，更新策略 (Policy Update)
        :param reward: 环境给出的 PnL 或其他奖励信号
        :param next_state: 动作执行后的新状态
        :param done: 仿真周期是否结束
        :return: 训练相关的指标记录
        """
        pass
