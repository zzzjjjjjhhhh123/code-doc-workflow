"""所有 Agent 的统一抽象接口。"""

from abc import ABC, abstractmethod

from core.message import Message


class BaseAgent(ABC):
    """Agent 基类。

    契约：
    1. 只通过 ``run(message, state)`` 接收任务；
    2. 把本节点的产出写入共享状态；
    3. 返回一个新的 ``Message`` 作为结果，而不是返回裸字典。

    执行器只依赖该接口，因此新增 Agent 时无需修改执行器。
    """

    name = "base_agent"
    description = "Base agent"

    @abstractmethod
    def run(self, message: Message, state) -> Message:
        """处理一条任务消息并返回结果消息。"""

        raise NotImplementedError

    def make_result(self, request: Message, payload: dict) -> Message:
        """构造标准结果消息，自动继承 trace_id 并回复给请求方。"""

        if not isinstance(request, Message):
            raise TypeError("Agent 只能处理 Message 类型的输入")

        return Message.create(
            sender=self.name,
            receiver=request.sender,
            msg_type="result",
            payload=payload,
            trace_id=request.trace_id,
        )
