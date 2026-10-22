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
