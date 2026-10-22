"""项目入口：读取示例代码，执行 Workflow，输出 Markdown 与日志。"""

import logging
import os

from workflow.workflow_def import build_executor


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_PATH = os.path.join(BASE_DIR, "examples", "sample.py")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DOCUMENT_PATH = os.path.join(OUTPUT_DIR, "document.md")
LOG_PATH = os.path.join(OUTPUT_DIR, "run.log")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def print_header() -> None:
    print("=" * 66)
    print(" Code -> Documentation Workflow MVP")
    print(" AnalysisAgent -> 条件分支 -> DocAgent")
    print("=" * 66)


def main() -> int:
    print_header()
    print(f"[1/3] 读取示例代码：{os.path.relpath(SAMPLE_PATH, BASE_DIR)}")
    try:
        code = read_text(SAMPLE_PATH)
    except (OSError, UnicodeError) as exc:
        print(f"      读取失败：{type(exc).__name__}: {exc}")
        return 1

    print(f"      共 {len(code.splitlines())} 行，{len(code)} 个字符")
    print("[2/3] 执行 Workflow ...")

    try:
        executor = build_executor(template_dir=TEMPLATE_DIR, output_dir=OUTPUT_DIR)
        state = executor.run(code)
    except Exception as exc:  # 防御性兜底：初始化/落盘等非节点错误也不崩溃
        print(f"      Workflow 初始化失败：{type(exc).__name__}: {exc}")
        logging.shutdown()
        return 1

    if state.status != "done":
        print("[3/3] 流程失败，未生成文档")
        print("-" * 66)
        print(f"Workflow ID : {state.workflow_id}")
        print(f"状态        : {state.status}")
        print(f"失败节点    : {state.current_node}")
        print(f"错误        : {state.error}")
        print(f"日志        : {os.path.relpath(LOG_PATH, BASE_DIR)}")
        print(f"日志条目    : {len(state.logs)}")
        print("-" * 66)
        logging.shutdown()
        return 1

    if not state.document.strip():
        print("      DocAgent 未产生文档内容，流程视为异常")
        logging.shutdown()
        return 1

    print("[3/3] 写入文档与日志 ...")
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(DOCUMENT_PATH, "w", encoding="utf-8") as handle:
            handle.write(state.document)
            if not state.document.endswith("\n"):
                handle.write("\n")
    except OSError as exc:
        print(f"      写入失败：{type(exc).__name__}: {exc}")
        logging.shutdown()
        return 1

    metrics = state.analysis.get("metrics", {})
    print("-" * 66)
    print(f"Workflow ID : {state.workflow_id}")
    print(f"状态        : {state.status}")
    print(f"识别语言    : {state.language} ({state.analysis.get('language_label', '')})")
    print(f"结构统计    : 类={metrics.get('class_count', 0)}, "
          f"函数/方法={metrics.get('function_count', 0)}, "
          f"依赖={metrics.get('dependency_count', 0)}")
    print(f"节点位置    : {state.current_node}")
    print(f"消息数量    : {len(state.messages)}")
    print(f"日志条目    : {len(state.logs)}")
    print(f"耗时        : {state.duration_ms} ms")
    print(f"Markdown    : {os.path.relpath(DOCUMENT_PATH, BASE_DIR)} "
          f"({len(state.document)} 字符)")
    print(f"运行日志    : {os.path.relpath(LOG_PATH, BASE_DIR)}")
    print("-" * 66)
    print("完成：工作流状态为 done，文档已生成。")
    logging.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
