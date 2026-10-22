"""Workflow 执行器：按配置调度 Agent，处理条件分支、重试与日志。"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from core.base_agent import BaseAgent
from core.message import Message
from core.state import WorkflowState


END = "END"


@dataclass
class NodeDefinition:
    """流程节点配置。

    ``branch`` 只描述“状态字段值 -> 下一节点”的映射，执行器不认识任何
    具体语言或业务节点，因此新增分支/节点时不需要修改执行器。
    """

    name: str
    agent: str
    description: str = ""
    next_node: str = END
    config: dict = field(default_factory=dict)
    branch_on: str = ""
    branch: dict = field(default_factory=dict)
    max_retries: int = -1


@dataclass
class WorkflowDefinition:
    """完整流程定义。

    ``max_retries`` 是节点默认重试次数（首次执行之外的额外次数）。
    ``max_steps`` 用于防止配置形成无限循环。
    """

    name: str
    start: str
    nodes: dict
    max_retries: int = 3
    max_steps: int = 50


class WorkflowExecutor:
    """通用流程执行器。

    执行器只负责：
    - 根据 ``WorkflowDefinition`` 找到当前节点；
    - 通过统一 ``Message`` 把任务投递给 Agent；
    - 读取 Agent 返回的 ``Message``，更新状态并决定下一节点；
    - 失败重试、记录日志，并在重试耗尽时返回 ``failed`` 状态。
    """

    def __init__(
        self,
        workflow: WorkflowDefinition,
        agents: dict,
        output_dir: str,
    ) -> None:
        self.workflow = workflow
        self.agents = dict(agents)
        self.output_dir = os.path.abspath(output_dir)
        self.log_path = os.path.join(self.output_dir, "run.log")
        self._logger = logging.getLogger("code_doc_workflow")
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self, code: str) -> WorkflowState:
        """执行完整流程；任何节点最终失败都通过状态返回，不向调用方抛出。"""

        workflow_id = self._new_workflow_id()
        state = WorkflowState(workflow_id=workflow_id, code=code if isinstance(code, str) else "")
        state.mark_running()
        started = time.perf_counter()
        self._configure_logging()

        state.add_log(
            node="workflow",
            event="workflow_start",
            agent="executor",
            status="running",
            input_summary=self._code_summary(state.code),
            output_summary=f"workflow={self.workflow.name}, start={self.workflow.start}",
        )
        self._log_file(
            state,
            "WORKFLOW_START",
            "workflow",
            "executor",
            0,
            "running",
            0,
            self._code_summary(state.code),
            f"workflow={self.workflow.name}, start={self.workflow.start}",
        )

        if not isinstance(code, str) or not code.strip():
            self._finish_failed(state, "INPUT", "输入代码为空，无法执行分析流程。", started)
            return state

        try:
            self._validate_definition()
        except ValueError as exc:
            self._finish_failed(state, "CONFIG", str(exc), started)
            return state

        current_node = self.workflow.start
        upstream_message = None
        steps = 0

        while current_node != END:
            if steps >= self.workflow.max_steps:
                self._finish_failed(
                    state,
                    current_node,
                    f"超过最大节点步数 {self.workflow.max_steps}，流程疑似存在环。",
                    started,
                )
                return state

            node = self.workflow.nodes.get(current_node)
            if node is None:
                self._finish_failed(
                    state,
                    current_node,
                    f"找不到节点定义：{current_node}",
                    started,
                )
                return state

            steps += 1
            state.current_node = node.name
            ok, result_message, error = self._execute_node(node, state, upstream_message)

            if not ok:
                self._finish_failed(state, node.name, error, started)
                return state

            upstream_message = result_message
            next_node = self._resolve_next(node, state)
            input_summary = (
                f"node={node.name}, branch_on={node.branch_on or 'none'}, "
                f"language={state.language}"
            )
            output_summary = f"next={next_node}"
            state.add_log(
                node=node.name,
                event="route",
                agent="executor",
                status="running",
                input_summary=input_summary,
                output_summary=output_summary,
            )
            self._log_file(
                state,
                "ROUTE",
                node.name,
                "executor",
                0,
                "running",
                0,
                input_summary,
                output_summary,
            )
            current_node = next_node

        duration_ms = self._elapsed_ms(started)
        state.mark_done(duration_ms)
        state.add_log(
            node="workflow",
            event="workflow_done",
            agent="executor",
            status="done",
            input_summary=f"nodes_executed={steps}",
            output_summary=(
                f"language={state.language}, document_chars={len(state.document)}, "
                f"status=done"
            ),
            duration_ms=duration_ms,
        )
        self._log_file(
            state,
            "WORKFLOW_DONE",
            "workflow",
            "executor",
            0,
            "done",
            duration_ms,
            f"nodes_executed={steps}",
            f"language={state.language}, document_chars={len(state.document)}",
        )
        return state

    # ------------------------------------------------------------------
    # 节点执行与重试
    # ------------------------------------------------------------------
    def _execute_node(self, node: NodeDefinition, state: WorkflowState, upstream_message):
        """执行单个节点，返回 ``(成功, 结果消息, 最终错误)``。"""

        max_retries = (
            node.max_retries if node.max_retries >= 0 else self.workflow.max_retries
        )
        total_attempts = max_retries + 1
        last_error = ""

        for attempt in range(1, total_attempts + 1):
            state.current_node = node.name
            snapshot = self._snapshot_outputs(state)
            payload = self._build_payload(node, state, upstream_message, attempt)
            input_summary = self._summarize_payload(payload)
            request = Message.create(
                sender="executor",
                receiver=node.agent,
                msg_type="task",
                payload=payload,
                trace_id=state.workflow_id,
            )
            state.add_message(request)
            state.add_log(
                node=node.name,
                event="node_start",
                agent=node.agent,
                status="running",
                attempt=attempt,
                input_summary=input_summary,
                output_summary="",
            )
            self._log_file(
                state,
                "NODE_START",
                node.name,
                node.agent,
                attempt,
                "running",
                0,
                input_summary,
                "",
            )

            attempt_started = time.perf_counter()
            try:
                agent = self.agents[node.agent]
                result = agent.run(request, state)

                if not isinstance(result, Message):
                    raise TypeError(
                        "Agent 必须返回 Message，实际返回 "
                        f"{type(result).__name__}"
                    )
                if result.trace_id != state.workflow_id:
                    raise ValueError(
                        "Agent 返回消息的 trace_id 与当前 Workflow 不一致："
                        f"{result.trace_id!r}"
                    )

                duration_ms = self._elapsed_ms(attempt_started)
                output_summary = self._summarize_payload(result.payload)
                state.add_message(result)
                state.add_log(
                    node=node.name,
                    event="node_success",
                    agent=node.agent,
                    status="done",
                    attempt=attempt,
                    input_summary=input_summary,
                    output_summary=output_summary,
                    duration_ms=duration_ms,
                )
                self._log_file(
                    state,
                    "NODE_OK",
                    node.name,
                    node.agent,
                    attempt,
                    "done",
                    duration_ms,
                    input_summary,
                    output_summary,
                )
                return True, result, ""

            except Exception as exc:  # noqa: BLE001 - 节点错误必须被流程捕获
                duration_ms = self._elapsed_ms(attempt_started)
                last_error = f"{type(exc).__name__}: {exc}"
                self._restore_outputs(state, snapshot)
                state.add_log(
                    node=node.name,
                    event="node_error",
                    agent=node.agent,
                    status="retrying" if attempt < total_attempts else "failed",
                    attempt=attempt,
                    input_summary=input_summary,
                    output_summary=f"attempt_failed: {last_error}",
                    duration_ms=duration_ms,
                    error=last_error,
                )

                if attempt < total_attempts:
                    state.add_log(
                        node=node.name,
                        event="node_retry",
                        agent=node.agent,
                        status="retrying",
                        attempt=attempt,
                        input_summary=f"retry {attempt}/{max_retries}",
                        output_summary=f"scheduled_attempt={attempt + 1}",
                        error=last_error,
                    )
                    self._log_file(
                        state,
                        "NODE_RETRY",
                        node.name,
                        node.agent,
                        attempt,
                        "retrying",
                        duration_ms,
                        input_summary,
                        f"attempt_failed={last_error}; next_attempt={attempt + 1}",
                        level=logging.WARNING,
                    )
                else:
                    self._log_file(
                        state,
                        "NODE_ERROR",
                        node.name,
                        node.agent,
                        attempt,
                        "failed",
                        duration_ms,
                        input_summary,
                        f"attempt_failed={last_error}",
                        level=logging.ERROR,
                    )

        final_error = (
            f"节点 {node.name!r} 在 {total_attempts} 次尝试后失败；"
            f"最后错误：{last_error}"
        )
        state.add_log(
            node=node.name,
            event="node_failed",
            agent=node.agent,
            status="failed",
            attempt=total_attempts,
            input_summary=f"node={node.name}, max_retries={max_retries}",
            output_summary=f"status=failed, attempts={total_attempts}",
            error=final_error,
        )
        return False, None, final_error

    # ------------------------------------------------------------------
    # 状态与消息辅助
    # ------------------------------------------------------------------
    def _build_payload(self, node, state, upstream_message, attempt):
        payload = {
            "code": state.code,
            "language": state.language,
            "analysis": state.analysis,
            "document": state.document,
            "node": node.name,
            "attempt": attempt,
            "config": dict(node.config),
        }
        if upstream_message is not None:
            payload["upstream"] = upstream_message.to_dict()
        return payload

    def _resolve_next(self, node: NodeDefinition, state: WorkflowState) -> str:
        """解析下一节点；分支值来自状态字段，执行器不含业务硬编码。"""

        if node.branch:
            raw_value = getattr(state, node.branch_on, "") if node.branch_on else ""
            branch_key = str(raw_value).strip()
            target = node.branch.get(branch_key)
            if target is None:
                target = node.branch.get(branch_key.lower())
            if target is None:
                target = node.branch.get("default")
            if target is None:
                target = node.next_node
        else:
            target = node.next_node

        return target or END

    def _snapshot_outputs(self, state: WorkflowState) -> dict:
        """深拷贝节点可能写入的产出，失败重试时恢复，避免脏状态。"""

        try:
            analysis = json.loads(json.dumps(state.analysis, ensure_ascii=False))
        except (TypeError, ValueError):
            analysis = dict(state.analysis) if isinstance(state.analysis, dict) else {}
        return {
            "language": state.language,
            "analysis": analysis,
            "document": state.document,
        }

    def _restore_outputs(self, state: WorkflowState, snapshot: dict) -> None:
        state.language = snapshot["language"]
        state.analysis = snapshot["analysis"]
        state.document = snapshot["document"]

    def _finish_failed(self, state: WorkflowState, node: str, error: str, started: float) -> None:
        """将流程统一收敛到 failed，并写入日志。"""

        duration_ms = self._elapsed_ms(started)
        state.mark_failed(node, error, duration_ms)
        state.add_log(
            node=node,
            event="workflow_failed",
            agent="executor",
            status="failed",
            input_summary=f"workflow={self.workflow.name}, failed_node={node}",
            output_summary=f"status=failed, attempts_logged={len(state.logs)}",
            duration_ms=duration_ms,
            error=error,
        )
        self._log_file(
            state,
            "WORKFLOW_FAILED",
            node,
            "executor",
            0,
            "failed",
            duration_ms,
            f"workflow={self.workflow.name}",
            f"status=failed, error={error}",
            level=logging.ERROR,
        )

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------
    def _configure_logging(self) -> None:
        """每次运行重建 run.log，避免多次运行互相污染。"""

        os.makedirs(self.output_dir, exist_ok=True)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:  # pragma: no cover - 关闭旧 handler 不应影响主流程
                pass

        file_handler = logging.FileHandler(self.log_path, mode="w", encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self._logger.addHandler(file_handler)

    def _log_file(
        self,
        state: WorkflowState,
        event: str,
        node: str,
        agent: str,
        attempt: int,
        status: str,
        duration_ms: int,
        input_summary: str,
        output_summary: str,
        level: int = logging.INFO,
    ) -> None:
        message = " | ".join(
            [
                f"trace={state.workflow_id}",
                f"event={event}",
                f"node={node}",
                f"agent={agent}",
                f"attempt={attempt}",
                f"status={status}",
                f"duration_ms={duration_ms}",
                f"input={self._one_line(input_summary)}",
                f"output={self._one_line(output_summary)}",
            ]
        )
        self._logger.log(level, message)

    def _summarize_payload(self, payload: dict) -> str:
        """生成不包含完整源码/文档的短摘要。"""

        if not isinstance(payload, dict):
            return self._short(str(payload), 160)

        parts = []
        code = payload.get("code")
        if isinstance(code, str) and code:
            parts.append(self._code_summary(code))
        if payload.get("language"):
            parts.append(f"language={payload['language']}")
        analysis = payload.get("analysis")
        if isinstance(analysis, dict) and analysis:
            metrics = analysis.get("metrics", {})
            if isinstance(metrics, dict):
                parts.append(
                    "analysis("
                    f"classes={metrics.get('class_count', 0)}, "
                    f"functions={metrics.get('function_count', 0)}, "
                    f"imports={metrics.get('import_count', 0)})"
                )
        if payload.get("document"):
            parts.append(f"document_chars={len(str(payload['document']))}")
        if payload.get("template"):
            parts.append(f"template={payload['template']}")
        config = payload.get("config")
        if isinstance(config, dict) and config:
            parts.append(f"config={self._short(json.dumps(config, ensure_ascii=False), 100)}")
        attempt = payload.get("attempt")
        if attempt:
            parts.append(f"attempt={attempt}")

        if not parts:
            return self._short(json.dumps(payload, ensure_ascii=False, default=str), 200)
        return ", ".join(parts)

    def _code_summary(self, code: str) -> str:
        if not isinstance(code, str):
            return "code_chars=0"
        line_count = len(code.splitlines())
        return f"code_chars={len(code)}, lines={line_count}"

    def _short(self, value: str, limit: int) -> str:
        text = self._one_line(value)
        return text if len(text) <= limit else text[: limit - 3] + "..."

    def _one_line(self, value) -> str:
        return " ".join(str(value).split())

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))

    def _new_workflow_id(self) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"wf-{stamp}-{uuid4().hex[:8]}"

    # ------------------------------------------------------------------
    # 配置校验
    # ------------------------------------------------------------------
    def _validate_definition(self) -> None:
        errors = []
        workflow = self.workflow

        if not workflow.name:
            errors.append("workflow.name 不能为空")
        if not workflow.nodes:
            errors.append("workflow.nodes 不能为空")
        if workflow.start not in workflow.nodes:
            errors.append(f"start 节点不存在：{workflow.start!r}")
        if workflow.max_retries < 0:
            errors.append("workflow.max_retries 必须 >= 0")
        if workflow.max_steps <= 0:
            errors.append("workflow.max_steps 必须 > 0")

        def check_target(target, source):
            if target and target != END and target not in workflow.nodes:
                errors.append(f"{source} 指向不存在的节点：{target!r}")

        for key, node in workflow.nodes.items():
            if not isinstance(node, NodeDefinition):
                errors.append(f"节点 {key!r} 必须是 NodeDefinition")
                continue
            if node.name != key:
                errors.append(f"节点键 {key!r} 与 node.name {node.name!r} 不一致")
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", node.name or ""):
                errors.append(f"非法节点名：{node.name!r}")
            agent = self.agents.get(node.agent)
            if agent is None:
                errors.append(f"节点 {node.name!r} 未注册 Agent：{node.agent!r}")
            elif not isinstance(agent, BaseAgent):
                errors.append(f"Agent {node.agent!r} 未实现 BaseAgent")
            elif agent.name != node.agent:
                errors.append(
                    f"Agent 注册键 {node.agent!r} 与 agent.name {agent.name!r} 不一致"
                )
            if not isinstance(node.config, dict):
                errors.append(f"节点 {node.name!r} 的 config 必须是 dict")
            if node.max_retries < -1:
                errors.append(f"节点 {node.name!r} 的 max_retries 必须 >= -1")
            check_target(node.next_node, f"节点 {node.name!r} 的 next_node")
            if node.branch:
                if not node.branch_on:
                    errors.append(f"节点 {node.name!r} 配置了 branch 但缺少 branch_on")
                for branch_key, target in node.branch.items():
                    if branch_key != "default" and not str(branch_key):
                        errors.append(f"节点 {node.name!r} 存在空分支键")
                    check_target(target, f"节点 {node.name!r} 的分支 {branch_key!r}")

        if errors:
            raise ValueError("流程配置无效：\n- " + "\n- ".join(errors))
