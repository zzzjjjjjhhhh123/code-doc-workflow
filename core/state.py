"""Workflow 共享状态。

``WorkflowState`` 是同一次流程执行中所有节点共享的上下文：
上游写入分析结果，下游读取；执行器写入状态、日志、错误信息。
"""

from dataclasses import dataclass, field
from datetime import datetime


STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


def now_iso() -> str:
    """返回带本地时区的 ISO-8601 时间戳。"""

    return datetime.now().astimezone().isoformat(timespec="milliseconds")


@dataclass
class WorkflowState:
    """一次 Workflow 运行的可观测共享状态。

    Required fields:
        workflow_id: 本次运行 ID，同时作为消息 trace_id。
        code: 输入源码。
        language: AnalysisAgent 识别出的语言。
        analysis: AnalysisAgent 生成的结构化分析结果。
        document: DocAgent 生成的 Markdown。
        status: ``pending`` / ``running`` / ``done`` / ``failed``。
        current_node: 当前正在执行的节点；完成后为 ``END``。
        logs: 带时间戳、节点名、输入/输出摘要的执行日志。
        error: 最终失败原因（成功时为空字符串）。
    """

    workflow_id: str
    code: str
    language: str = "unknown"
    analysis: dict = field(default_factory=dict)
    document: str = ""
    status: str = STATUS_PENDING
    current_node: str = ""
    logs: list = field(default_factory=list)
    error: str = ""
    messages: list = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0

    def mark_running(self) -> None:
        """进入 running 状态并记录开始时间。"""

        self.status = STATUS_RUNNING
        self.current_node = "START"
        self.started_at = now_iso()

    def mark_done(self, duration_ms: int) -> None:
        """流程正常到达 END。"""

        self.status = STATUS_DONE
        self.current_node = "END"
        self.error = ""
        self.finished_at = now_iso()
        self.duration_ms = max(0, int(duration_ms))

    def mark_failed(self, node: str, error: str, duration_ms: int) -> None:
        """流程最终失败；不抛出异常，由调用方读取状态。"""

        self.status = STATUS_FAILED
        self.current_node = node or "UNKNOWN"
        self.error = str(error)
        self.finished_at = now_iso()
        self.duration_ms = max(0, int(duration_ms))

    def add_log(
        self,
        node: str,
        event: str,
        agent: str = "",
        status: str = "",
        attempt: int = 0,
        input_summary: str = "",
        output_summary: str = "",
        duration_ms: int = 0,
        error: str = "",
    ) -> dict:
        """追加一条结构化日志，并返回该日志项。

        每条日志都固定携带时间戳、节点名与输入/输出摘要，满足可追踪要求。
        """

        entry = {
            "timestamp": now_iso(),
            "node": node,
            "agent": agent,
            "event": event,
            "status": status,
            "attempt": int(attempt),
            "input_summary": input_summary,
            "output_summary": output_summary,
            "duration_ms": max(0, int(duration_ms)),
            "error": str(error) if error else "",
        }
        self.logs.append(entry)
        return entry

    def add_message(self, message) -> None:
        """把消息写入可追踪的消息历史。"""

        self.messages.append(message.to_dict())

    def to_dict(self) -> dict:
        """返回状态快照，便于序列化或调试。"""

        return {
            "workflow_id": self.workflow_id,
            "code": self.code,
            "language": self.language,
            "analysis": self.analysis,
            "document": self.document,
            "status": self.status,
            "current_node": self.current_node,
            "logs": list(self.logs),
            "error": self.error,
            "messages": list(self.messages),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
        }
