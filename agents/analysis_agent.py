"""AnalysisAgent：基于正则的轻量代码语言识别与结构分析。"""

import re

from core.base_agent import BaseAgent
from core.message import Message


class AnalysisAgent(BaseAgent):
    """分析代码语言、类、函数/方法、导入依赖等结构信息。"""

    name = "analysis_agent"
    description = "识别代码语言并用正则提取类、函数和依赖结构"

    PYTHON_CLASS_RE = re.compile(
        r"(?m)^(?P<indent>[ \t]*)class\s+(?P<name>[A-Za-z_]\w*)"
        r"\s*(?:\((?P<bases>[^)]*)\))?\s*:"
    )
    PYTHON_FUNCTION_RE = re.compile(
        r"(?m)^(?P<indent>[ \t]*)def\s+(?P<name>[A-Za-z_]\w*)"
        r"\s*\((?P<args>[^)]*)\)\s*(?:->\s*(?P<returns>[^:\n]+))?\s*:"
    )
    PYTHON_IMPORT_RE = re.compile(
        r"(?m)^[ \t]*(?:from\s+(?P<from>[\w.]+)\s+import\s+(?P<from_names>[^\n#]+)"
        r"|import\s+(?P<modules>[^\n#]+))"
    )

    JAVA_CLASS_RE = re.compile(
        r"(?m)^[ \t]*(?:(?:public|protected|private)\s+)?"
        r"(?:(?:final|abstract|static)\s+)*"
        r"(?P<kind>class|interface|enum)\s+(?P<name>[A-Za-z_]\w*)"
        r"(?:\s+extends\s+(?P<extends>[\w.]+))?"
        r"(?:\s+implements\s+(?P<implements>[\w.,\s]+))?\s*\{"
    )
    JAVA_METHOD_RE = re.compile(
        r"(?m)^[ \t]*(?P<mods>(?:(?:public|protected|private|static|final|abstract|"
        r"synchronized|native|strictfp)\s+)*)"
        r"(?P<returns>[A-Za-z_][\w.<>\[\],? ]*?)\s+"
        r"(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)\s*"
        r"(?:throws\s+[^{]+)?\{"
    )
    JAVA_CONSTRUCTOR_RE = re.compile(
        r"(?m)^[ \t]*(?:public|protected|private)\s+"
        r"(?P<name>[A-Z]\w*)\s*\((?P<args>[^)]*)\)\s*"
        r"(?:throws\s+[^{]+)?\{"
    )
    JAVA_IMPORT_RE = re.compile(
        r"(?m)^[ \t]*import\s+(?:static\s+)?(?P<module>[\w.*]+)\s*;"
    )

    GENERIC_CLASS_RE = re.compile(
        r"(?m)^[ \t]*(?:class|struct|interface)\s+(?P<name>[A-Za-z_]\w*)"
    )
    GENERIC_FUNCTION_RE = re.compile(
        r"(?m)^[ \t]*(?P<prefix>def|function|func)\s+(?P<name>[A-Za-z_]\w*)"
        r"\s*\((?P<args>[^)]*)\)"
    )
    GENERIC_C_FUNCTION_RE = re.compile(
        r"(?m)^[ \t]*(?P<returns>[A-Za-z_][\w*&<>\[\]]*)\s+"
        r"(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)\s*\{"
    )
    GENERIC_IMPORT_RE = re.compile(
        r"(?m)^[ \t]*(?:import|from|#include|require)\s*(?:\(?['\"<]?)(?P<module>[^'\"<>;\s)]+)"
    )

    PYTHON_SIGNALS = [
        ("Python 函数定义", r"(?m)^[ \t]*def\s+[A-Za-z_]\w*\s*\(", 4),
        ("Python 类定义", r"(?m)^[ \t]*class\s+[A-Za-z_]\w*(?:\([^)]*\))?\s*:", 4),
        (
            "Python 主入口",
            r"""(?m)^[ \t]*if\s+__name__\s*==\s*["']__main__["']""",
            4,
        ),
        (
            "Python 导入语句",
            r"(?m)^[ \t]*(?:from\s+[\w.]+\s+import|import\s+[\w.]+)(?![^\n]*;)",
            1,
        ),
        ("Python 装饰器", r"(?m)^[ \t]*@[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*$", 1),
        ("Python 控制流", r"(?m)^[ \t]*(?:elif|except|finally)\b[^\n]*:", 1),
    ]
    JAVA_SIGNALS = [
        ("Java main 方法", r"\bpublic\s+static\s+void\s+main\s*\(", 5),
        (
            "Java 类型定义",
            r"(?m)^[ \t]*(?:public|protected|private)\s+"
            r"(?:(?:final|abstract|static)\s+)*(?:class|interface|enum)\s+\w+",
            4,
        ),
        (
            "Java 无修饰符类型",
            r"(?m)^[ \t]*(?:class|interface|enum)\s+\w+[^\n:]*\{",
            2,
        ),
        ("Java 包/导入", r"(?m)^[ \t]*(?:package|import)\s+[\w.*]+\s*;", 2),
        ("Java 标准输出", r"\bSystem\.out\.print(?:ln)?\s*\(", 2),
        (
            "Java 方法签名",
            r"(?m)^[ \t]*(?:public|protected|private)\s+(?:static\s+)?"
            r"[\w<>\[\],.?]+\s+\w+\s*\([^)]*\)\s*(?:throws\s+[^{]+)?\{",
            2,
        ),
        ("Java 对象创建", r"\bnew\s+[A-Z]\w*\s*\(", 1),
    ]

    _CONTROL_KEYWORDS = {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "synchronized",
        "return",
        "new",
        "do",
        "else",
        "try",
    }

    def run(self, message: Message, state) -> Message:
        if not isinstance(message, Message):
            raise TypeError("AnalysisAgent 只能处理 Message 类型的输入")

        code = message.payload.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("AnalysisAgent 收到的代码为空")

        detection = self._detect_language(code)
        language = detection["language"]

        if language == "python":
            analysis = self._analyze_python(code)
        elif language == "java":
            analysis = self._analyze_java(code)
        else:
            analysis = self._analyze_generic(code)

        analysis["language"] = language
        analysis["language_label"] = detection["label"]
        analysis["detection"] = detection
        analysis["metrics"] = self._build_metrics(analysis)
        analysis["summary"] = self._build_summary(analysis)
        analysis["notes"] = self._build_notes(analysis)

        state.language = language
        state.analysis = analysis

        return self.make_result(
            message,
            {
                "language": language,
                "language_label": detection["label"],
                "detection": detection,
                "analysis": analysis,
            },
        )

    # ------------------------------------------------------------------
    # 语言识别
    # ------------------------------------------------------------------
    def _detect_language(self, code: str) -> dict:
        python_score, python_evidence = self._score_signals(code, self.PYTHON_SIGNALS)
        java_score, java_evidence = self._score_signals(code, self.JAVA_SIGNALS)

        if python_score == 0 and java_score == 0:
            language = "generic"
        elif python_score > java_score:
            language = "python"
        elif java_score > python_score:
            language = "java"
        else:
            # 平局时再检查强特征，避免仅凭注释/字符串产生误判。
            if re.search(r"(?m)^[ \t]*(?:public\s+)?class\s+\w+[^:\n]*\{", code) or re.search(
                r"(?m)^[ \t]*import\s+java\.", code
            ):
                language = "java"
            elif re.search(r"(?m)^[ \t]*def\s+\w+\s*\(", code) and re.search(
                r"(?m)^[ \t]*class\s+\w+[^\n]*:", code
            ):
                language = "python"
            else:
                language = "generic"

        labels = {"python": "Python", "java": "Java", "generic": "Generic"}
        scores = {"python": python_score, "java": java_score}
        total = python_score + java_score
        confidence = round(max(python_score, java_score) / total, 2) if total else 0.0
        evidence = python_evidence if language == "python" else java_evidence
        if language == "generic":
            evidence = []

        return {
            "language": language,
            "label": labels[language],
            "confidence": confidence,
            "scores": scores,
            "evidence": evidence,
        }

    def _score_signals(self, code: str, signals: list) -> tuple:
        score = 0
        evidence = []
        for label, pattern, weight in signals:
            if re.search(pattern, code):
                score += weight
                evidence.append(label)
        return score, evidence

    # ------------------------------------------------------------------
    # Python 分析
    # ------------------------------------------------------------------
    def _analyze_python(self, code: str) -> dict:
        functions = self._extract_python_functions(code)
        classes = self._extract_python_classes(code, functions)
        imports, dependencies = self._extract_python_imports(code)
        return {
            "line_count": len(code.splitlines()),
            "non_empty_line_count": sum(1 for line in code.splitlines() if line.strip()),
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "dependencies": dependencies,
        }

    def _extract_python_functions(self, code: str) -> list:
        functions = []
        for match in self.PYTHON_FUNCTION_RE.finditer(code):
            indent = self._indent_width(match.group("indent"))
            args = self._split_parameters(match.group("args"))
            functions.append(
                {
                    "name": match.group("name"),
                    "line": self._line_number(code, match.start()),
                    "args": args,
                    "returns": (match.group("returns") or "").strip(),
                    "scope": "top-level" if indent == 0 else "nested",
                    "kind": "function",
                    "owner": "",
                    "_indent": indent,
                }
            )
        return functions

    def _extract_python_classes(self, code: str, functions: list) -> list:
        matches = list(self.PYTHON_CLASS_RE.finditer(code))
        classes = []
        total_lines = len(code.splitlines())

        for index, match in enumerate(matches):
            indent = self._indent_width(match.group("indent"))
            start_line = self._line_number(code, match.start())
            end_line = total_lines
            for later in matches[index + 1 :]:
                if self._indent_width(later.group("indent")) <= indent:
                    end_line = self._line_number(code, later.start()) - 1
                    break

            bases = []
            if match.group("bases"):
                bases = [item.strip() for item in match.group("bases").split(",") if item.strip()]

            item = {
                "name": match.group("name"),
                "kind": "class",
                "line": start_line,
                "end_line": end_line,
                "bases": bases,
                "methods": [],
                "_indent": indent,
            }

            candidates = [
                function
                for function in functions
                if start_line < function["line"] <= end_line
                and function["_indent"] > indent
            ]
            if candidates:
                method_indent = min(function["_indent"] for function in candidates)
                for function in candidates:
                    if function["_indent"] == method_indent:
                        function["scope"] = "method"
                        function["kind"] = "method"
                        function["owner"] = item["name"]
                        item["methods"].append(function["name"])

            classes.append(item)

        for item in classes:
            item.pop("_indent", None)
        for function in functions:
            function.pop("_indent", None)
        return classes

    def _extract_python_imports(self, code: str) -> tuple:
        imports = []
        dependencies = []
        lines = code.splitlines()

        for match in self.PYTHON_IMPORT_RE.finditer(code):
            line_no = self._line_number(code, match.start())
            statement = lines[line_no - 1].strip() if line_no <= len(lines) else match.group(0).strip()
            modules = []
            if match.group("from"):
                modules = [match.group("from")]
            else:
                for chunk in (match.group("modules") or "").split(","):
                    module = re.split(r"\s+as\s+", chunk.strip(), maxsplit=1)[0].strip()
                    if module:
                        modules.append(module)

            for module in modules:
                imports.append({"line": line_no, "module": module, "statement": statement})
                if module not in dependencies:
                    dependencies.append(module)

        return imports, sorted(dependencies, key=str.lower)

    # ------------------------------------------------------------------
    # Java 分析
    # ------------------------------------------------------------------
    def _analyze_java(self, code: str) -> dict:
        functions = self._extract_java_methods(code)
        classes = self._extract_java_classes(code, functions)
        imports, dependencies = self._extract_java_imports(code)
        return {
            "line_count": len(code.splitlines()),
            "non_empty_line_count": sum(1 for line in code.splitlines() if line.strip()),
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "dependencies": dependencies,
        }

    def _extract_java_methods(self, code: str) -> list:
        functions = []
        seen = set()

        for match in self.JAVA_METHOD_RE.finditer(code):
            name = match.group("name")
            if name in self._CONTROL_KEYWORDS or name in {"class", "interface", "enum"}:
                continue
            line_no = self._line_number(code, match.start())
            key = (name, line_no)
            if key in seen:
                continue
            seen.add(key)
            functions.append(
                {
                    "name": name,
                    "line": line_no,
                    "args": self._split_parameters(match.group("args")),
                    "returns": (match.group("returns") or "").strip(),
                    "scope": "method",
                    "kind": "method",
                    "owner": "",
                }
            )

        for match in self.JAVA_CONSTRUCTOR_RE.finditer(code):
            name = match.group("name")
            line_no = self._line_number(code, match.start())
            key = (name, line_no)
            if key in seen:
                continue
            seen.add(key)
            functions.append(
                {
                    "name": name,
                    "line": line_no,
                    "args": self._split_parameters(match.group("args")),
                    "returns": name,
                    "scope": "method",
                    "kind": "constructor",
                    "owner": "",
                }
            )

        functions.sort(key=lambda item: item["line"])
        return functions

    def _extract_java_classes(self, code: str, functions: list) -> list:
        matches = list(self.JAVA_CLASS_RE.finditer(code))
        classes = []
        total_lines = len(code.splitlines())

        for index, match in enumerate(matches):
            start_line = self._line_number(code, match.start())
            end_line = total_lines
            for later in matches[index + 1 :]:
                if later.start() > match.start():
                    end_line = self._line_number(code, later.start()) - 1
                    break

            bases = []
            if match.group("extends"):
                bases.append(match.group("extends").strip())
            if match.group("implements"):
                bases.extend(
                    item.strip()
                    for item in match.group("implements").split(",")
                    if item.strip()
                )

            item = {
                "name": match.group("name"),
                "kind": match.group("kind"),
                "line": start_line,
                "end_line": end_line,
                "bases": bases,
                "methods": [],
            }

            for function in functions:
                if start_line < function["line"] <= end_line and not function["owner"]:
                    function["owner"] = item["name"]
                    item["methods"].append(function["name"])

            classes.append(item)

        return classes

    def _extract_java_imports(self, code: str) -> tuple:
        imports = []
        dependencies = []
        lines = code.splitlines()

        for match in self.JAVA_IMPORT_RE.finditer(code):
            line_no = self._line_number(code, match.start())
            module = match.group("module")
            statement = lines[line_no - 1].strip() if line_no <= len(lines) else match.group(0).strip()
            imports.append({"line": line_no, "module": module, "statement": statement})
            if module not in dependencies:
                dependencies.append(module)

        return imports, sorted(dependencies, key=str.lower)

    # ------------------------------------------------------------------
    # Generic 分析
    # ------------------------------------------------------------------
    def _analyze_generic(self, code: str) -> dict:
        functions = []
        classes = []
        seen = set()

        for match in self.GENERIC_FUNCTION_RE.finditer(code):
            name = match.group("name")
            line_no = self._line_number(code, match.start())
            if (name, line_no) in seen:
                continue
            seen.add((name, line_no))
            functions.append(
                {
                    "name": name,
                    "line": line_no,
                    "args": self._split_parameters(match.group("args")),
                    "returns": "",
                    "scope": "top-level",
                    "kind": "function",
                    "owner": "",
                }
            )

        for match in self.GENERIC_C_FUNCTION_RE.finditer(code):
            name = match.group("name")
            if name in self._CONTROL_KEYWORDS:
                continue
            line_no = self._line_number(code, match.start())
            if (name, line_no) in seen:
                continue
            seen.add((name, line_no))
            functions.append(
                {
                    "name": name,
                    "line": line_no,
                    "args": self._split_parameters(match.group("args")),
                    "returns": (match.group("returns") or "").strip(),
                    "scope": "top-level",
                    "kind": "function",
                    "owner": "",
                }
            )

        for match in self.GENERIC_CLASS_RE.finditer(code):
            line_no = self._line_number(code, match.start())
            classes.append(
                {
                    "name": match.group("name"),
                    "kind": "class",
                    "line": line_no,
                    "end_line": len(code.splitlines()),
                    "bases": [],
                    "methods": [],
                }
            )

        imports = []
        dependencies = []
        lines = code.splitlines()
        for match in self.GENERIC_IMPORT_RE.finditer(code):
            line_no = self._line_number(code, match.start())
            module = match.group("module").strip()
            statement = lines[line_no - 1].strip() if line_no <= len(lines) else match.group(0).strip()
            if not module:
                continue
            imports.append({"line": line_no, "module": module, "statement": statement})
            if module not in dependencies:
                dependencies.append(module)

        functions.sort(key=lambda item: item["line"])
        return {
            "line_count": len(code.splitlines()),
            "non_empty_line_count": sum(1 for line in code.splitlines() if line.strip()),
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "dependencies": sorted(dependencies, key=str.lower),
        }

    # ------------------------------------------------------------------
    # 通用辅助
    # ------------------------------------------------------------------
    def _build_metrics(self, analysis: dict) -> dict:
        functions = analysis.get("functions", [])
        return {
            "line_count": analysis.get("line_count", 0),
            "non_empty_line_count": analysis.get("non_empty_line_count", 0),
            "class_count": len(analysis.get("classes", [])),
            "function_count": len(functions),
            "top_level_function_count": sum(
                1 for item in functions if item.get("scope") == "top-level"
            ),
            "method_count": sum(1 for item in functions if item.get("scope") == "method"),
            "import_count": len(analysis.get("imports", [])),
            "dependency_count": len(analysis.get("dependencies", [])),
        }

    def _build_summary(self, analysis: dict) -> str:
        metrics = analysis["metrics"]
        return (
            f"识别为 {analysis['language_label']} 代码，共 {metrics['line_count']} 行；"
            f"发现 {metrics['class_count']} 个类、{metrics['method_count']} 个方法、"
            f"{metrics['top_level_function_count']} 个顶层函数和 "
            f"{metrics['dependency_count']} 个导入依赖。"
        )

    def _build_notes(self, analysis: dict) -> list:
        notes = [
            "本分析由正则表达式完成，不构建完整 AST；适合 MVP 快速提取结构。",
            "动态生成、多行表达式或非标准语法可能无法被完整识别，建议结合人工复核。",
        ]
        if not analysis.get("classes"):
            notes.append("未识别到类定义。")
        if not analysis.get("functions"):
            notes.append("未识别到函数或方法定义。")
        if not analysis.get("imports"):
            notes.append("未识别到导入依赖。")
        return notes

    def _split_parameters(self, raw: str) -> list:
        """按顶层逗号分割参数，兼容泛型/默认值中的嵌套逗号。"""

        if not raw or not raw.strip():
            return []

        parts = []
        current = []
        depth = 0
        quote = ""
        escaped = False

        for char in raw:
            if quote:
                current.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue

            if char in {"'", '"'}:
                quote = char
                current.append(char)
            elif char in "([{<":
                depth += 1
                current.append(char)
            elif char in ")]}>":
                depth = max(0, depth - 1)
                current.append(char)
            elif char == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(char)

        if "".join(current).strip():
            parts.append("".join(current).strip())
        return [part for part in parts if part]

    def _indent_width(self, indent: str) -> int:
        return len(indent.expandtabs(4))

    def _line_number(self, text: str, index: int) -> int:
        return text.count("\n", 0, index) + 1
