"""DocAgent：根据代码语言选择模板并渲染 Markdown 文档。"""

import os
import re
from datetime import datetime

from core.base_agent import BaseAgent
from core.message import Message


class DocAgent(BaseAgent):
    """消费 AnalysisAgent 的结果，按模板生成 Markdown。"""

    name = "doc_agent"
    description = "根据语言模板把结构化分析结果渲染为 Markdown 文档"

    _LANGUAGE_LABELS = {"python": "Python", "java": "Java", "generic": "Generic"}
    _SCOPE_LABELS = {
        "top-level": "顶层函数",
        "method": "方法",
        "nested": "嵌套函数",
    }
    _KIND_LABELS = {
        "class": "类",
        "interface": "接口",
        "enum": "枚举",
        "function": "函数",
        "method": "方法",
        "constructor": "构造器",
    }

    def __init__(self, template_dir: str = "") -> None:
        if template_dir:
            self.template_dir = os.path.abspath(template_dir)
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.template_dir = os.path.join(project_root, "templates")

    def run(self, message: Message, state) -> Message:
        if not isinstance(message, Message):
            raise TypeError("DocAgent 只能处理 Message 类型的输入")

        language = str(
            message.payload.get("language") or state.language or "generic"
        ).strip().lower()
        analysis = message.payload.get("analysis")
        if not isinstance(analysis, dict) or not analysis:
            analysis = state.analysis
        if not isinstance(analysis, dict) or not analysis:
            raise ValueError("DocAgent 缺少 AnalysisAgent 的结构化分析结果")

        code = message.payload.get("code")
        if not isinstance(code, str):
            code = state.code

        node_config = message.payload.get("config")
        if not isinstance(node_config, dict):
            node_config = {}
        requested_template = str(node_config.get("template") or language).strip().lower()
        template_name = self._resolve_template_name(requested_template)
        template = self._load_template(template_name)

        context = self._build_context(
            workflow_id=message.trace_id,
            language=language,
            analysis=analysis,
            code=code,
            template_name=template_name,
        )
        document = self._render(template, context)
        if not document.strip():
            raise ValueError("模板渲染结果为空")

        state.document = document
        if not state.language or state.language == "unknown":
            state.language = language

        return self.make_result(
            message,
            {
                "language": language,
                "template": template_name,
                "document": document,
                "document_chars": len(document),
            },
        )

    # ------------------------------------------------------------------
    # 模板管理
    # ------------------------------------------------------------------
    def _resolve_template_name(self, requested: str) -> str:
        candidate = requested if re.fullmatch(r"[a-z0-9_]+", requested or "") else "generic"
        candidate_path = os.path.join(self.template_dir, candidate + ".md")
        if os.path.isfile(candidate_path):
            return candidate

        fallback_path = os.path.join(self.template_dir, "generic.md")
        if candidate != "generic" and os.path.isfile(fallback_path):
            return "generic"
        raise FileNotFoundError(
            f"未找到文档模板：{candidate_path}（且 generic.md 不可用）"
        )

    def _load_template(self, template_name: str) -> str:
        path = os.path.join(self.template_dir, template_name + ".md")
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def _render(self, template: str, context: dict) -> str:
        placeholders = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", template))
        unknown = sorted(placeholders - set(context))
        if unknown:
            raise ValueError("模板包含未知占位符：" + ", ".join(unknown))

        def replace(match):
            return str(context[match.group(1)])

        return re.sub(r"\{\{([A-Z0-9_]+)\}\}", replace, template)

    # ------------------------------------------------------------------
    # 渲染上下文
    # ------------------------------------------------------------------
    def _build_context(
        self,
        workflow_id: str,
        language: str,
        analysis: dict,
        code: str,
        template_name: str,
    ) -> dict:
        metrics = analysis.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}
        label = analysis.get("language_label") or self._LANGUAGE_LABELS.get(
            language, "Generic"
        )
        generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")

        return {
            "TITLE": f"代码结构说明文档（{label}）",
            "WORKFLOW_ID": workflow_id,
            "GENERATED_AT": generated_at,
            "LANGUAGE": language,
            "LANGUAGE_LABEL": label,
            "TEMPLATE_NAME": template_name,
            "SUMMARY": str(analysis.get("summary") or "未提供摘要。"),
            "OVERVIEW": self._format_overview(analysis, label),
            "DETECTION": self._format_detection(analysis.get("detection", {})),
            "CLASSES": self._format_classes(analysis.get("classes", [])),
            "FUNCTIONS": self._format_functions(analysis.get("functions", [])),
            "IMPORTS": self._format_imports(
                analysis.get("imports", []),
                analysis.get("dependencies", []),
            ),
            "NOTES": self._format_notes(analysis.get("notes", [])),
            "CODE_BLOCK": self._format_code_block(code, language),
            "METRICS": self._format_metrics(metrics),
            "DEPENDENCIES": self._format_dependencies(
                analysis.get("dependencies", [])
            ),
        }

    def _format_overview(self, analysis: dict, label: str) -> str:
        metrics = analysis.get("metrics", {})
        detection = analysis.get("detection", {})
        confidence = detection.get("confidence", 0.0) if isinstance(detection, dict) else 0.0
        return "\n".join(
            [
                "| 指标 | 值 |",
                "| --- | --- |",
                f"| 识别语言 | **{self._cell(label)}** (`{self._cell(analysis.get('language', 'generic'))}`) |",
                f"| 识别置信度 | {confidence} |",
                f"| 代码行数 | {metrics.get('line_count', 0)} |",
                f"| 非空行数 | {metrics.get('non_empty_line_count', 0)} |",
                f"| 类 / 接口 | {metrics.get('class_count', 0)} |",
                f"| 函数 / 方法 | {metrics.get('function_count', 0)} |",
                f"| 导入依赖 | {metrics.get('dependency_count', 0)} |",
            ]
        )

    def _format_detection(self, detection: dict) -> str:
        if not isinstance(detection, dict) or not detection:
            return "_未提供语言识别依据。_"
        evidence = detection.get("evidence") or []
        scores = detection.get("scores") or {}
        score_text = "，".join(f"{key}={value}" for key, value in scores.items()) or "无"
        lines = [f"- 规则得分：{score_text}"]
        if evidence:
            lines.append("- 命中特征：" + "、".join(str(item) for item in evidence))
        else:
            lines.append("- 未命中特定语言强特征，回退到通用模板。")
        return "\n".join(lines)

    def _format_classes(self, classes: list) -> str:
        if not classes:
            return "_未识别到类、接口或枚举定义。_"

        lines = [
            "| 名称 | 类型 | 行号 | 基类 / 实现 | 方法 |",
            "| --- | --- | ---: | --- | --- |",
        ]
        for item in classes:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "?")
            kind = self._KIND_LABELS.get(item.get("kind", ""), item.get("kind", "类"))
            bases = item.get("bases") or []
            bases_text = "<br>".join(self._cell(base) for base in bases) if bases else "—"
            methods = item.get("methods") or []
            methods_text = (
                ", ".join(f"`{self._cell(method)}`" for method in methods)
                if methods
                else "—"
            )
            lines.append(
                f"| `{self._cell(name)}` | {kind} | {item.get('line', '?')} | "
                f"{bases_text} | {methods_text} |"
            )
        return "\n".join(lines)

    def _format_functions(self, functions: list) -> str:
        if not functions:
            return "_未识别到函数或方法定义。_"

        lines = [
            "| 名称 | 类型 | 行号 | 参数 | 返回值 | 作用域 |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
        for item in functions:
            if not isinstance(item, dict):
                continue
            kind = self._KIND_LABELS.get(item.get("kind", ""), item.get("kind", "函数"))
            scope = self._SCOPE_LABELS.get(
                item.get("scope", ""), item.get("scope", "—")
            )
            args = item.get("args") or []
            args_text = ", ".join(self._cell(arg) for arg in args) if args else "—"
            returns = item.get("returns") or "—"
            lines.append(
                f"| `{self._cell(item.get('name', '?'))}` | {kind} | "
                f"{item.get('line', '?')} | {args_text} | {self._cell(returns)} | {scope} |"
            )
        return "\n".join(lines)

    def _format_imports(self, imports: list, dependencies: list) -> str:
        if not imports and not dependencies:
            return "_未识别到导入依赖。_"

        lines = []
        if dependencies:
            lines.append(
                "**依赖模块**："
                + ", ".join(f"`{self._cell(item)}`" for item in dependencies)
            )
            lines.append("")
        if imports:
            lines.extend(["| 行号 | 导入语句 |", "| ---: | --- |"])
            for item in imports:
                if not isinstance(item, dict):
                    continue
                statement = str(item.get("statement", "")).replace("`", "'")
                lines.append(f"| {item.get('line', '?')} | `{statement}` |")
        return "\n".join(lines)

    def _format_notes(self, notes: list) -> str:
        if not notes:
            return "_无额外说明。_"
        return "\n".join(f"- {self._cell(note)}" for note in notes)

    def _format_code_block(self, code: str, language: str) -> str:
        hint = language if language in {"python", "java"} else "text"
        fence = "```"
        while fence in code:
            fence += "`"
        return f"{fence}{hint}\n{code.rstrip()}\n{fence}"

    def _format_metrics(self, metrics: dict) -> str:
        if not metrics:
            return "_无指标。_"
        return ", ".join(f"{key}={value}" for key, value in metrics.items())

    def _format_dependencies(self, dependencies: list) -> str:
        if not dependencies:
            return "_无。_"
        return ", ".join(f"`{self._cell(item)}`" for item in dependencies)

    def _cell(self, value) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
