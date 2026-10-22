代码文档生成 Workflow

这个项目是一个课程作业。程序读取一段源代码，先由 AnalysisAgent 识别语言并分析结构，再由 DocAgent 根据语言选择模板，生成一份 Markdown 文档。整个流程由 WorkflowExecutor 调度，两个 Agent 之间通过 Message 传递任务和结果，不直接调用对方的方法。

一次正常运行的最终状态是 done，文档写入 output/document.md，执行日志写入 output/run.log。项目只使用 Python 标准库，不需要安装其他包，也不访问网络或外部服务。

一、项目说明

这个 MVP 的目标是把代码分析和文档生成拆成两个独立 Agent，并用一个通用执行器把两个步骤串起来。AnalysisAgent 负责识别 Python、Java 或通用代码，提取类、函数、方法、导入依赖等信息。DocAgent 负责读取分析结果，选择对应模板，生成 Markdown。执行器只按照流程配置调度节点，不关心语言识别和模板渲染的具体实现。

项目要求的四个基本能力都已经实现。两个 Agent 协作完成分析到文档的完整流程；Agent 之间使用统一的 Message 结构，由执行器投递和转发；流程按照分析、条件分支、文档生成的顺序执行；输入 examples/sample.py 后能够端到端生成文档，最终状态为 done。

加分部分也包含在项目里。AnalysisAgent 会识别 python、java 或 generic，DocAgent 会根据节点配置或语言选择模板；节点失败会自动重试，最多重试 3 次；WorkflowState 记录当前节点、状态、日志和错误，日志同时写入 output/run.log；流程节点、顺序、分支和重试次数都在 WORKFLOW_DEF 中配置；DESIGN.md 中使用 Mermaid 画出了主流程、消息时序、状态机和重试流程。

二、运行环境

运行环境要求 Python 3.9 或更高版本。项目只使用 Python 标准库，所以不需要执行 pip install，也不需要创建虚拟环境。Windows、macOS 和 Linux 都可以运行。代码在 Python 3.9.12 上做过完整验证。

三、运行方法和输出

在项目根目录执行下面的命令即可：

```bash
python main.py
```

Windows PowerShell 中也使用同一条命令。程序会读取 examples/sample.py，依次执行 AnalysisAgent 和 DocAgent，最后在控制台打印本次运行的编号、状态、识别语言、结构统计、耗时和输出文件位置。

运行后会生成两个文件。output/document.md 是最终文档，内容包括语言识别依据、类结构、函数和方法列表、导入依赖、分析备注以及示例源码。output/run.log 是本次运行的日志，记录开始、节点执行、路由、重试、完成或失败等事件。

程序会自动创建 output 目录。run.log 每次运行采用覆盖写，只保留最近一次运行的日志。document.md 也只在流程成功结束并且文档内容非空时写入。

四、预期运行结果

正常执行后，控制台会给出类似下面的结果：

```text
状态：done
识别语言：python，标签为 Python
结构统计：类 2 个，函数和方法 10 个，导入依赖 3 个
当前节点：END
消息数量：4
日志条目：8
文档位置：output/document.md
日志位置：output/run.log
```

Workflow ID、耗时、文档字符数和日志条数会随运行情况变化。判断流程成功的主要依据是状态为 done、当前节点为 END、识别语言为 python，以及文档和日志文件都存在。

五、课堂演示步骤

第一步，打开 examples/sample.py，说明这段代码包含 import、dataclass、普通类、类方法、顶层函数和主入口，适合展示结构提取。

第二步，在终端执行 python main.py，让观众看到状态为 done，识别语言为 python，当前节点为 END。

第三步，打开 output/document.md，展示语言识别依据、类表、方法表、依赖表和源码附录。文档中的表格和代码块都是由 DocAgent 根据模板生成的。

第四步，打开 output/run.log，指出 WORKFLOW_START、NODE_START、NODE_OK、ROUTE 和 WORKFLOW_DONE 这些事件，说明每个节点都有尝试次数、耗时和输入输出摘要。

第五步，打开 workflow/workflow_def.py，展示 analyze_code 的 branch 配置和三个文档节点，说明条件分支和模板选择都写在配置里。

第六步，如果时间允许，打开 templates/python.md、templates/java.md 和 templates/generic.md，对比三套模板的差异，再展示 DESIGN.md 中的流程图。

六、功能与实现位置

两个 Agent 分别在 agents/analysis_agent.py 和 agents/doc_agent.py。AnalysisAgent 完成语言识别和结构分析，DocAgent 消费分析结果并生成文档。

消息机制在 core/message.py 和 core/executor.py。所有任务和结果都是 Message，执行器负责创建任务消息、接收结果消息、校验 trace_id 并把上游结果放进下一个节点的消息中。Agent 之间没有直接函数调用。

顺序流程控制在 workflow/workflow_def.py 和 core/executor.py。执行器按照 start、next_node 和 branch 推进，到达 END 后结束。

端到端入口在 main.py。它读取示例代码，调用 build_executor 组装流程，然后调用 executor.run，最后写出文档。

条件分支由 WORKFLOW_DEF 中的 branch_on 和 branch 控制。AnalysisAgent 把识别结果写入 state.language，执行器根据这个值选择 Python、Java 或通用文档节点。

失败重试在 WorkflowExecutor 的节点执行方法中实现。默认 max_retries 为 3，节点最多执行 4 次。重试耗尽后状态置为 failed，错误写入 WorkflowState 和 run.log，执行器正常返回，不向 main.py 抛出节点异常。

共享状态与日志由 core/state.py 和 core/executor.py 负责。WorkflowState 保存代码、语言、分析结果、文档、状态、当前节点、日志、错误和消息历史。

配置化和扩展能力由 workflow/workflow_def.py 和 core/base_agent.py 提供。流程以数据形式描述，Agent 统一实现 run 方法，执行器不包含具体业务节点名称。

七、流程说明

入口文件 main.py 负责读取示例代码、组装执行器并调用 run 方法，它不参与语言判断，也不直接调用 Agent。

AnalysisAgent 收到任务消息后，从消息中取出代码。它使用一组带权重的正则规则判断代码更接近 Python、Java 还是通用文本，然后提取类、函数或方法、导入依赖和代码行数等信息。分析结果既会写入共享状态 WorkflowState，也会放进返回的 Message 中。

执行器拿到分析结果后，根据 WorkflowState 中的 language 字段选择下一个节点。语言为 python 时进入 Python 文档节点，为 java 时进入 Java 文档节点，其他情况进入通用文档节点。这个映射写在 workflow/workflow_def.py 的 WORKFLOW_DEF 中，执行器本身没有写死 Python 或 Java 这些业务名称。

DocAgent 从消息中读取分析结果和代码，根据节点配置选择模板，准备渲染上下文，最后生成 Markdown。它同样会更新共享状态并返回结果消息。执行器收到结果后继续判断下一节点，直到到达 END。

执行器的主要步骤是读取当前节点、创建任务消息、调用 Agent、校验返回消息、写入日志、解析下一节点。任何一步出现可捕获的错误都会进入重试流程。重试耗尽后流程停止并返回 failed 状态。

八、消息与共享状态

Message 包含 sender、receiver、msg_type、payload、trace_id、timestamp 和 message_id。一次 Workflow 中所有消息使用同一个 trace_id，因此可以把 Agent 之间的往返消息和日志对应起来。

Agent 不导入另一个 Agent，也不调用另一个 Agent 的方法。执行器创建 task 消息并调用 Agent 的 run 方法，Agent 返回 result 消息。执行器校验消息类型和 trace_id，然后把上游结果作为 upstream 放入下一个节点的任务消息。每条消息都会追加到 state.messages，形成完整的通信历史。

WorkflowState 保存本次运行的 workflow_id、原始代码、识别语言、分析结果、文档内容、当前状态、当前节点、日志、错误信息和消息历史。状态从 pending 进入 running，正常结束时变为 done，重试耗尽或配置出错时变为 failed。

每次执行节点前，执行器会对 language、analysis 和 document 做一次快照。如果本次尝试抛出异常，就恢复快照，避免失败尝试留下的半成品影响下一次重试。日志和消息历史不会被恢复，它们用于保留完整的执行过程。

九、条件分支

AnalysisAgent 会把语言识别结果写入 language。执行器读取这个字段，再按照配置中的 branch 映射选择下一节点。

python 对应 generate_python_docs，使用 templates/python.md。java 对应 generate_java_docs，使用 templates/java.md。其他值或 generic 对应 generate_generic_docs，使用 templates/generic.md。

DocAgent 优先使用节点配置中的 template 参数，如果没有这个参数，就根据 language 选择模板。这样既可以通过流程配置指定模板，也保留了按语言自动选择的能力。以后增加新语言时，需要增加识别规则、模板文件和一条分支配置，不需要修改执行器。

如果 branch 中没有匹配到具体值，执行器会尝试 default。如果连 default 也没有，就使用 next_node。没有 branch 的节点直接走 next_node。next_node 为 END 时流程结束。

十、错误处理与恢复

每个节点默认执行一次，失败后最多再重试 3 次，也就是最多 4 次尝试。每次尝试都会生成新的消息和日志，attempt 字段会递增。每次失败日志都会记录异常类型、错误信息、耗时和尝试序号。重试期间 status 保持 running，只要有一次成功，流程就继续往下走。

如果所有尝试都失败，执行器会把状态改为 failed，把失败节点和最后一次错误写进 WorkflowState，同时写入 run.log，然后返回状态对象，不向 main.py 抛出异常。输入为空、流程配置错误、节点路由不存在、超过最大节点步数等情况也会进入 failed 状态，不会让程序崩溃。

失败尝试的中间产出会被恢复。执行器在每次尝试前保存 language、analysis 和 document 的快照，捕获异常后恢复这三个字段，再进入下一次尝试。这样第二次尝试不会接着使用第一次留下的半成品数据。

重试成功后最终状态仍然是 done。重试耗尽后状态才是 failed。正常日志中可以看到 NODE_RETRY；最终失败时可以看到 NODE_ERROR 和 WORKFLOW_FAILED。

已经验证了两条重试路径。故障 Agent 前两次抛异常、第三次成功时，最终状态为 done，日志中存在 NODE_RETRY。故障 Agent 每次都抛异常时，执行器尝试 4 次后把状态改为 failed，错误写入 state.error 和 run.log，run 方法没有抛出异常。

十一、日志与状态追踪

共享状态中的 logs 保存结构化日志。每条日志包含时间戳、节点名、Agent 名、事件名、状态、尝试次数、输入摘要、输出摘要、耗时和错误信息。

一次日志项包含的字段如下：

```text
timestamp
node
agent
event
status
attempt
input_summary
output_summary
duration_ms
error
```

输入摘要只记录代码长度、行数和当前语言，输出摘要只记录语言、类数量、函数数量、文档长度和模板名，不把完整代码和文档写进日志。例如分析节点成功时，输出摘要会包含 language、classes、functions 和 imports；文档节点成功时，输出摘要会包含 document_chars 和 template。

run.log 把同样的信息写成单行文本，并额外带上 trace。一次运行的 workflow_id 和 trace_id 相同，因此可以从控制台摘要找到对应日志，再从日志找到对应的 Agent 消息。

正常的日志顺序一般是：

```text
WORKFLOW_START
NODE_START analyze_code attempt 1
NODE_OK analyze_code
ROUTE analyze_code 到 generate_python_docs
NODE_START generate_python_docs attempt 1
NODE_OK generate_python_docs
ROUTE generate_python_docs 到 END
WORKFLOW_DONE
```

发生重试时会出现 NODE_RETRY，最终失败时会出现 NODE_ERROR 和 WORKFLOW_FAILED。日志中的 status 会随事件变化，例如 running、done、retrying 和 failed。

十二、项目结构

项目文件和目录如下：

```text
项目根目录
  README.md
  DESIGN.md
  main.py
  core
    __init__.py
    message.py
    state.py
    base_agent.py
    executor.py
  agents
    __init__.py
    analysis_agent.py
    doc_agent.py
  workflow
    __init__.py
    workflow_def.py
  templates
    python.md
    java.md
    generic.md
  examples
    sample.py
  output
    document.md
    run.log
```

core 目录存放基础设施代码。message.py 定义 Message，state.py 定义 WorkflowState，base_agent.py 定义 BaseAgent 接口，executor.py 实现流程调度、条件分支、重试和日志。

agents 目录存放两个 Agent。analysis_agent.py 负责语言识别和结构分析，doc_agent.py 负责模板选择和 Markdown 渲染。

workflow 目录存放流程配置。workflow_def.py 中定义了 WORKFLOW_DEF、Agent 注册表和组装执行器的函数。

templates 目录存放三套文档模板。examples 目录存放示例代码 sample.py。output 目录用来保存运行后生成的文档和日志。

十三、架构速览与消息流

项目从入口到 Agent 的层次关系如下：

```text
main.py
  build_executor
    WORKFLOW_DEF
    Agent 注册表
    WorkflowExecutor
      Message
      WorkflowState
      BaseAgent
```

执行器只认识 NodeDefinition、WorkflowDefinition 和 BaseAgent，不认识 Python、Java 或文档这些业务概念。Agent 只实现 run 方法，从消息读取输入，向状态写入产出，再返回消息。流程配置负责节点名、Agent 名称、下一节点、分支条件、模板参数和重试策略。共享状态让下游节点可以读取上游产出，消息历史则保留通信轨迹。

一次典型消息流如下：

```text
executor 发送 task 消息给 analysis_agent
analysis_agent 返回 result 消息给 executor
executor 发送 task 消息给 doc_agent，消息中包含代码、分析和上游结果
doc_agent 返回 result 消息给 executor
executor 返回状态给 main.py
```

每跳消息都带同一个 trace_id，消息历史保存在 state.messages。

十四、扩展方法

新增或调整流程节点时，只修改 workflow/workflow_def.py 中的 WORKFLOW_DEF。例如在分析后插入一个安全审查节点，可以写成：

```python
"security_review": NodeDefinition(
    name="security_review",
    agent="security_agent",
    next_node="generate_python_docs",
)
```

然后把 analyze_code 的 next_node 或分支目标指向它。执行器不需要修改。

新增 Agent 时，先创建一个继承 BaseAgent 的类，设置唯一的 name，实现 run 方法，然后在 build_agent_registry 中注册，最后在 WORKFLOW_DEF 的节点里填写对应的 agent 名称。只要遵守接口，执行器的调度、重试、日志和状态管理都会自动复用。

新增语言模板时，在 templates 目录增加一个 Markdown 文件，使用已有的占位符，再在 AnalysisAgent 中补充识别规则，在 WORKFLOW_DEF 中增加一个文档节点和对应分支。

调整节点顺序时修改 next_node。调整分支时修改 branch。调整重试次数时修改 max_retries，全局默认在 WorkflowDefinition.max_retries 中设置，单个节点可以用 NodeDefinition.max_retries 覆盖，负一表示继承全局。这些都是配置修改，不需要改 executor.py。

十五、核心数据结构

Message 的定义如下：

```python
@dataclass
class Message:
    sender: str
    receiver: str
    msg_type: str
    payload: dict
    trace_id: str
    timestamp: str
    message_id: str
```

WorkflowState 的定义如下：

```python
@dataclass
class WorkflowState:
    workflow_id: str
    code: str
    language: str
    analysis: dict
    document: str
    status: str
    current_node: str
    logs: list
    error: str
    messages: list
    started_at: str
    finished_at: str
    duration_ms: int
```

状态值包括 pending、running、done 和 failed。current_node 在节点开始前更新，成功完成后变为 END，失败时保留失败节点。

十六、设计取舍

消息和共享状态同时存在，看起来有一点重复，但两者用途不同。消息用于说明 Agent 之间传了什么，状态用于把一次运行的上下文集中起来。只保留消息的话，日志和最终结果要反复遍历消息历史；只保留状态的话，又看不出 Agent 之间的任务边界。MVP 选择两者并存，代码稍多，但演示和排查更方便。

语言识别使用正则打分，没有引入 AST 或编译器前端。这样做符合零第三方依赖的要求，也方便解释识别依据。代价是复杂语法可能识别不完整，因此文档中保留了人工复核的提示。

模板放在独立文件中，不写死在 DocAgent 里。这样新增模板不需要改 Agent 代码，文档格式也可以单独调整。模板使用固定占位符，未知占位符会触发异常，再交给执行器重试，避免生成一半占位符一半内容的文档。

流程使用配置数据描述，执行器只负责通用调度。这样新增节点或改变顺序不需要改执行器，代价是分支表达能力有限，复杂条件需要扩展配置模型。

失败处理选择重试、快照恢复和状态收敛。节点失败不会直接中断程序，而是先尽可能恢复，再把最终结果交给调用方。这个选择比较适合课程演示，也方便在日志中观察完整过程。

十七、已知限制

语言识别和结构分析都基于正则表达式，不是完整的语法解析器。多行导入、复杂的装饰器参数、内部类以及动态生成的代码可能识别不完整。Java 部分只覆盖常见的类、接口、枚举、方法和导入写法，复杂泛型或跨行方法签名需要人工复核。

通用模板只做基础的结构提取，适合无法判断语言时使用，不能替代完整的代码分析工具。重试没有退避和超时控制，max_steps 只用于防止流程配置成环。run.log 每次运行会覆盖写，只保留最近一次运行的记录。

当前版本没有并行调度、分布式执行和持久化队列，也没有提供 Web 界面。可视化通过 Mermaid 图和生成的 Markdown 文档呈现。

十八、独立完成声明

这个项目的代码、模板和文档均为独立编写，没有复用已有项目的源码或资源。运行时只使用 Python 标准库，不访问网络，也不依赖外部服务。
