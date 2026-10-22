# 代码结构说明文档（Python）

> 由 **Code → Documentation Workflow** 自动生成  
> Workflow ID：`wf-20261022-224204-e8ef245e` · 生成时间：2026-10-22 22:42:04 +0800 · 模板：`python`

## 1. 摘要

识别为 Python 代码，共 116 行；发现 2 个类、8 个方法、2 个顶层函数和 3 个导入依赖。

| 指标 | 值 |
| --- | --- |
| 识别语言 | **Python** (`python`) |
| 识别置信度 | 1.0 |
| 代码行数 | 116 |
| 非空行数 | 84 |
| 类 / 接口 | 2 |
| 函数 / 方法 | 10 |
| 导入依赖 | 3 |

## 2. 语言识别依据

- 规则得分：python=14，java=0
- 命中特征：Python 函数定义、Python 类定义、Python 主入口、Python 导入语句、Python 装饰器

## 3. 类与对象结构

| 名称 | 类型 | 行号 | 基类 / 实现 | 方法 |
| --- | --- | ---: | --- | --- |
| `Task` | 类 | 16 | — | `toggle`, `to_dict` |
| `TaskRepository` | 类 | 34 | — | `__init__`, `add`, `toggle`, `save`, `load`, `stats` |

## 4. 函数与方法

| 名称 | 类型 | 行号 | 参数 | 返回值 | 作用域 |
| --- | --- | ---: | --- | --- | --- |
| `toggle` | 方法 | 23 | self | None | 方法 |
| `to_dict` | 方法 | 28 | self | dict | 方法 |
| `__init__` | 方法 | 37 | self, path: str = DEFAULT_PATH | None | 方法 |
| `add` | 方法 | 41 | self, title: str, tags: list = None | Task | 方法 |
| `toggle` | 方法 | 50 | self, index: int | Task | 方法 |
| `save` | 方法 | 57 | self | None | 方法 |
| `load` | 方法 | 68 | self | int | 方法 |
| `stats` | 方法 | 85 | self | dict | 方法 |
| `parse_tags` | 函数 | 96 | value: str | list | 顶层函数 |
| `build_summary` | 函数 | 102 | repository: TaskRepository | str | 顶层函数 |

## 5. 依赖与导入

**依赖模块**：`dataclasses`, `json`, `os`

| 行号 | 导入语句 |
| ---: | --- |
| 7 | `import json` |
| 8 | `import os` |
| 9 | `from dataclasses import dataclass, field` |

## 6. 分析备注

- 本分析由正则表达式完成，不构建完整 AST；适合 MVP 快速提取结构。
- 动态生成、多行表达式或非标准语法可能无法被完整识别，建议结合人工复核。

## 7. 示例源码

```python
"""示例输入：一个极简的任务清单模型。

该文件只用于演示 Code → Analysis → Documentation 流程，
包含 import、数据类、普通类、方法、顶层函数与 __main__ 入口。
"""

import json
import os
from dataclasses import dataclass, field


DEFAULT_PATH = "tasks.json"


@dataclass
class Task:
    """单条任务。"""

    title: str
    done: bool = False
    tags: list = field(default_factory=list)

    def toggle(self) -> None:
        """切换完成状态。"""

        self.done = not self.done

    def to_dict(self) -> dict:
        """转换为可 JSON 序列化的字典。"""

        return {"title": self.title, "done": self.done, "tags": list(self.tags)}


class TaskRepository:
    """管理任务集合，并负责本地 JSON 读写。"""

    def __init__(self, path: str = DEFAULT_PATH) -> None:
        self.path = path
        self.tasks: list = []

    def add(self, title: str, tags: list = None) -> Task:
        """新增任务；标题为空时抛出 ValueError。"""

        if not title.strip():
            raise ValueError("title must not be empty")
        task = Task(title=title.strip(), tags=tags or [])
        self.tasks.append(task)
        return task

    def toggle(self, index: int) -> Task:
        """按索引切换任务状态。"""

        task = self.tasks[index]
        task.toggle()
        return task

    def save(self) -> None:
        """把当前任务写入 JSON 文件。"""

        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(
                [task.to_dict() for task in self.tasks],
                handle,
                ensure_ascii=False,
                indent=2,
            )

    def load(self) -> int:
        """从 JSON 文件恢复任务，返回恢复数量。"""

        if not os.path.exists(self.path):
            return 0
        with open(self.path, "r", encoding="utf-8") as handle:
            records = json.load(handle)
        self.tasks = [
            Task(
                title=str(record.get("title", "")),
                done=bool(record.get("done", False)),
                tags=list(record.get("tags", [])),
            )
            for record in records
        ]
        return len(self.tasks)

    def stats(self) -> dict:
        """返回任务完成情况统计。"""

        completed = sum(1 for task in self.tasks if task.done)
        return {
            "total": len(self.tasks),
            "completed": completed,
            "pending": len(self.tasks) - completed,
        }


def parse_tags(value: str) -> list:
    """把逗号分隔的标签字符串解析为去空列表。"""

    return [item.strip() for item in value.split(",") if item.strip()]


def build_summary(repository: TaskRepository) -> str:
    """根据仓库统计信息生成一行摘要。"""

    stats = repository.stats()
    return (
        f"total={stats['total']}, completed={stats['completed']}, "
        f"pending={stats['pending']}"
    )


if __name__ == "__main__":
    repo = TaskRepository()
    item = repo.add("Write workflow MVP", tags=parse_tags("python, mvp"))
    item.toggle()
    print(build_summary(repo))
```

---

_本文件由 DocAgent 使用 Python 模板渲染。分析结果来自 AnalysisAgent 的正则静态扫描，未调用任何外部服务。_
