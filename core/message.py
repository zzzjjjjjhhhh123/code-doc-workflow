"""统一的 Agent 消息结构。

所有 Agent 之间不直接调用方法，只接收/返回本模块定义的 ``Message``。
``trace_id`` 在同一次 Workflow 执行中保持不变，便于串联完整调用链。
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


def now_iso() -> str:
    """返回带本地时区的 ISO-8601 时间戳。"""

    return datetime.now().astimezone().isoformat(timespec="milliseconds")


@dataclass
class Message:
    """Workflow 内部唯一的消息载体。

    Attributes:
        sender: 发送方名称，例如 ``executor`` / ``analysis_agent``。
        receiver: 接收方名称。
        msg_type: 消息类型，MVP 使用 ``task`` 与 ``result``。
        payload: 消息数据（必须可 JSON 序列化）。
        trace_id: 同一次 Workflow 运行共享的追踪 ID。
        timestamp: 消息创建时间。
        message_id: 单条消息的唯一 ID。
    """

    sender: str
    receiver: str
    msg_type: str
    payload: dict = field(default_factory=dict)
    trace_id: str = ""
    timestamp: str = field(default_factory=now_iso)
    message_id: str = field(default_factory=lambda: uuid4().hex)

    @classmethod
    def create(
        cls,
        sender: str,
        receiver: str,
        msg_type: str,
        payload: dict,
        trace_id: str,
    ) -> "Message":
        """创建消息的显式工厂方法，避免调用方重复处理元数据。"""

        return cls(
            sender=sender,
            receiver=receiver,
            msg_type=msg_type,
            payload=payload,
            trace_id=trace_id,
        )

    def to_dict(self) -> dict:
        """转换为可落盘/可记录的普通字典。"""

        return {
            "message_id": self.message_id,
            "trace_id": self.trace_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "msg_type": self.msg_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
