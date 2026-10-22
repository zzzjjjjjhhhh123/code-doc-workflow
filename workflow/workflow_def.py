"""配置化 Workflow 定义。

修改节点、分支或重试策略只需编辑本文件；``WorkflowExecutor`` 不包含任何
业务节点名称或语言判断。新增 Agent 时在 ``build_agent_registry`` 注册即可。
"""

from agents.analysis_agent import AnalysisAgent
from agents.doc_agent import DocAgent
from core.executor import END, NodeDefinition, WorkflowDefinition, WorkflowExecutor


WORKFLOW_DEF = WorkflowDefinition(
    name="code_to_documentation",
    start="analyze_code",
    max_retries=3,
    max_steps=10,
    nodes={
        "analyze_code": NodeDefinition(
            name="analyze_code",
            agent="analysis_agent",
            description="识别语言并分析类、函数、导入依赖",
            next_node="generate_generic_docs",
            branch_on="language",
            branch={
                "python": "generate_python_docs",
                "java": "generate_java_docs",
                "default": "generate_generic_docs",
            },
        ),
        "generate_python_docs": NodeDefinition(
            name="generate_python_docs",
            agent="doc_agent",
            description="使用 Python 模板生成 Markdown 文档",
            next_node=END,
            config={"template": "python"},
        ),
        "generate_java_docs": NodeDefinition(
            name="generate_java_docs",
            agent="doc_agent",
            description="使用 Java 模板生成 Markdown 文档",
            next_node=END,
            config={"template": "java"},
        ),
        "generate_generic_docs": NodeDefinition(
            name="generate_generic_docs",
            agent="doc_agent",
            description="使用通用模板生成 Markdown 文档",
            next_node=END,
            config={"template": "generic"},
        ),
    },
)


def build_agent_registry(template_dir: str) -> dict:
    """Agent 注册表：执行器只按配置中的 key 查找，不直接依赖具体类。"""

    return {
        "analysis_agent": AnalysisAgent(),
        "doc_agent": DocAgent(template_dir=template_dir),
    }


def build_executor(template_dir: str, output_dir: str) -> WorkflowExecutor:
    """组装流程定义、Agent 注册表与执行器。"""

    return WorkflowExecutor(
        workflow=WORKFLOW_DEF,
        agents=build_agent_registry(template_dir),
        output_dir=output_dir,
    )
