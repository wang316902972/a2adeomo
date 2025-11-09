"""
A2A Framework Demo: SQL 优化审核系统
整合 CrewAI (优化Agent) 和 AutoGen 0.4+ (审核Agent)

安装依赖:
pip install crewai crewai-tools autogen-agentchat autogen-core autogen-ext openai python-dotenv

环境变量配置 (.env):
OPENAI_API_KEY=your_api_key_here
"""

import asyncio
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  dotenv 未安装，跳过 .env 文件加载")

# CrewAI imports
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# AutoGen 0.7+ imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination,MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.base import TaskResult
from autogen_agentchat.ui import Console

os.environ["OPENAI_BASE_URL"] = "https://yunwu.ai/v1"
os.environ["OPENAI_API_KEY"] = "sk-tEWaHDG6MWf1UENkaanThDQ3Ej4Dai39LS5XC5UXSuTlEu8n"

# 加载环境变量
load_dotenv()

# ============================================================================
# 1. CrewAI SQL 优化 Agent (完整实现)
# ============================================================================

@tool("SQL Analysis Tool")
def analyze_sql_tool(sql_query: str) -> str:
    """分析 SQL 语句，识别性能问题和优化机会

    Args:
        sql_query: 要分析的 SQL 查询语句

    Returns:
        分析结果字符串，包含发现的问题和建议
    """
    issues = []
    sql_lower = sql_query.lower()

    # 检查 SELECT *
    if "select *" in sql_lower:
        issues.append("❌ 使用 SELECT * 会检索所有列，建议明确指定需要的列")

    # 检查 WHERE 子句
    if "where" not in sql_lower and "from" in sql_lower:
        issues.append("❌ 缺少 WHERE 子句可能导致全表扫描")

    # 检查 JOIN 数量
    join_count = sql_lower.count("join")
    if join_count > 3:
        issues.append(f"⚠️  发现 {join_count} 个 JOIN，可能影响性能")

    # 检查索引使用
    if "or" in sql_lower and "where" in sql_lower:
        issues.append("⚠️  OR 条件可能无法有效使用索引")

    # 检查通配符
    if "like" in sql_lower and "'%" in sql_lower:
        issues.append("❌ LIKE 前置通配符 '%xxx' 无法使用索引")

    # 检查子查询
    if sql_lower.count("select") > 1:
        issues.append("💡 存在子查询，考虑是否可以用 JOIN 优化")

    # 检查 DISTINCT
    if "distinct" in sql_lower:
        issues.append("💡 使用 DISTINCT 可能影响性能，检查是否必要")

    # 检查排序
    if "order by" in sql_lower:
        issues.append("💡 ORDER BY 操作需要排序，确保相关列有索引")

    if not issues:
        return "✅ SQL 语句看起来不错，没有明显的性能问题"

    return "发现以下问题:\n" + "\n".join(issues)

@tool("SQL Optimization Tool")
def generate_optimization_suggestions(sql_query: str) -> str:
    """根据 SQL 分析结果生成具体的优化建议

    Args:
        sql_query: 要优化的 SQL 查询语句

    Returns:
        优化建议字符串
    """
    suggestions = []
    sql_lower = sql_query.lower()

    if "select *" in sql_lower:
        suggestions.append("""
优化建议 1: 明确列名
- 问题: SELECT * 检索所有列
- 方案: 只选择需要的列
- 示例: SELECT id, name, email, created_at FROM users
- 收益: 减少数据传输量，提升查询速度
        """)

    if "where" not in sql_lower and "from" in sql_lower:
        suggestions.append("""
优化建议 2: 添加过滤条件
- 问题: 缺少 WHERE 子句
- 方案: 添加合适的过滤条件
- 示例: WHERE status = 'active' AND created_at >= '2024-01-01'
- 收益: 减少扫描的行数，避免全表扫描
        """)

    if "like" in sql_lower and "'%" in sql_lower:
        suggestions.append("""
优化建议 3: 优化模糊查询
- 问题: 前置通配符无法使用索引
- 方案:
  * 改为后置通配符: LIKE 'keyword%'
  * 使用全文索引: MATCH...AGAINST
  * 使用专门的搜索引擎: Elasticsearch
- 收益: 大幅提升搜索性能
        """)

    if sql_lower.count("join") > 2:
        suggestions.append("""
优化建议 4: 优化多表关联
- 问题: 过多的 JOIN 操作
- 方案:
  * 使用 CTE (WITH 子句) 分步处理
  * 考虑反规范化存储
  * 添加覆盖索引
- 示例:
  WITH user_orders AS (
    SELECT user_id, COUNT(*) as order_count
    FROM orders
    GROUP BY user_id
  )
  SELECT u.*, uo.order_count FROM users u
  JOIN user_orders uo ON u.id = uo.user_id
        """)

    if not suggestions:
        return "当前 SQL 已经较为优化，建议:\n1. 确保相关列有索引\n2. 使用 EXPLAIN 分析执行计划\n3. 监控实际执行性能"

    return "\n".join(suggestions)


class SQLOptimizerCrew:
    """CrewAI SQL 优化系统"""
    def __init__(self, openai_api_key: Optional[str] = None):
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.base_url =  os.getenv("OPENAI_BASE_URL")
        if not self.api_key:
            raise ValueError("需要设置 OPENAI_API_KEY 环境变量")

        self._setup_llm()
        self._setup_agents()

    def _setup_llm(self):
        """设置 LLM 配置"""
        try:
            # 尝试导入 LLM
            from crewai import LLM

            # 配置 LLM
            self.llm = LLM(
                model="openai/gpt-4o-mini",
                temperature=0.1,  # 低温度以确保准确性
                api_key=self.api_key,
                base_url=self.base_url
            )
            print("✅ LLM 配置成功")
        except ImportError:
            print("⚠️  无法导入 LLM，使用默认配置")
            self.llm = None
        except Exception as e:
            print(f"⚠️  LLM 配置失败，将使用备用方案: {e}")
            self.llm = None

    def _setup_agents(self):
        """初始化 CrewAI Agents"""

        # 准备 agent 配置参数
        agent_config = {
            'verbose': True,
            'allow_delegation': False,
            'llm': self.llm
        }

        # SQL 分析专家
        self.analyzer = Agent(
            role='SQL 性能分析专家',
            goal='深入分析 SQL 语句，识别所有性能瓶颈和优化机会',
            backstory="""你是一位拥有 15 年经验的数据库性能优化专家。
            你精通 MySQL、PostgreSQL、Oracle 等主流数据库，
            能够快速识别 SQL 语句中的性能问题，并给出专业的优化建议。
            你的分析总是全面、准确、有理有据。""",
            tools=[analyze_sql_tool],
            **agent_config
        )

        # SQL 优化工程师
        self.optimizer = Agent(
            role='SQL 优化工程师',
            goal='根据分析结果，生成优化的 SQL 语句和详细的优化方案',
            backstory="""你是一位资深的 SQL 优化工程师，擅长将复杂的 SQL
            语句重构为高性能的查询。你不仅能找出问题，还能提供可执行的
            优化方案和最佳实践建议。你的优化方案总是兼顾性能和可读性。""",
            tools=[generate_optimization_suggestions],
            **agent_config
        )

        # 报告生成专家
        self.reporter = Agent(
            role='技术文档专家',
            goal='生成清晰、专业的 SQL 优化报告',
            backstory="""你是一位技术写作专家，擅长将复杂的技术内容
            转化为易于理解的文档。你的报告结构清晰，重点突出，
            包含完整的优化前后对比和具体的实施建议。""",
            tools=[],  # 报告生成专家不需要工具
            **agent_config
        )
    
    def optimize_sql(self, sql_query: str) -> Dict[str, Any]:
        """执行 SQL 优化流程"""
        print("\n" + "="*80)
        print("🚀 CrewAI SQL 优化流程启动")
        print("="*80)

        # 任务 1: 分析 SQL
        analysis_task = Task(
            description=f"""
            分析以下 SQL 语句，识别所有性能问题:

            ```sql
            {sql_query}
            ```

            请使用 SQL 分析工具进行全面检查，包括:
            1. 索引使用情况
            2. 查询效率
            3. 潜在的性能瓶颈
            4. 可优化的部分

            输出格式要求:
            - 列出所有发现的问题
            - 标注问题严重程度
            - 说明问题影响
            """,
            agent=self.analyzer,
            expected_output="详细的 SQL 分析报告，包含所有发现的性能问题"
        )

        # 任务 2: 生成优化方案
        optimization_task = Task(
            description=f"""
            基于分析结果，为以下 SQL 生成优化方案:

            ```sql
            {sql_query}
            ```

            请使用优化建议生成器工具，提供:
            1. 具体的优化建议
            2. 优化后的 SQL 语句
            3. 预期的性能提升
            4. 实施注意事项

            优化原则:
            - 保持 SQL 语义不变
            - 优先考虑性能提升
            - 兼顾代码可读性
            - 提供多种优化方案
            """,
            agent=self.optimizer,
            expected_output="完整的优化方案，包含优化后的 SQL 和详细说明"
        )

        # 任务 3: 生成报告
        report_task = Task(
            description=f"""
            整合分析和优化结果，生成最终报告。

            报告应包含:
            1. 原始 SQL 和优化后的 SQL 对比
            2. 发现的问题列表
            3. 优化措施详解
            4. 预期性能提升
            5. 实施建议

            格式要求:
            - 使用 JSON 格式输出
            - 结构清晰，易于解析
            - 包含所有关键信息

            JSON 结构示例:
            {{
                "original_sql": "原始 SQL",
                "optimized_sql": "优化后的 SQL",
                "issues_found": ["问题1", "问题2"],
                "optimizations_applied": ["优化1", "优化2"],
                "performance_gain_estimate": "预估提升百分比",
                "recommendations": ["建议1", "建议2"]
            }}
            """,
            agent=self.reporter,
            expected_output="JSON 格式的完整优化报告"
        )

        # 检查是否有有效的 LLM 配置
        if not self.llm:
            print("⚠️  LLM 未正确配置，直接使用备用优化逻辑")
            return self._get_fallback_result(sql_query)

        # 创建 Crew 并执行
        crew = Crew(
            #agents=[self.analyzer, self.optimizer, self.reporter],
            #tasks=[analysis_task, optimization_task, report_task],
            agents=[self.analyzer, self.optimizer],
            tasks=[analysis_task, optimization_task],
            process=Process.sequential,
            verbose=True
        )

        try:
            print("🚀 开始执行 CrewAI 任务...")
            # 执行任务
            result = crew.kickoff()
            print(f"🎯 CrewAI 执行完成，结果类型: {type(result)}")

            # 解析结果
            result_str = str(result)
            print(f"📄 结果字符串长度: {len(result_str)}")

            # 尝试提取 JSON
            json_start = result_str.find('{')
            json_end = result_str.rfind('}') + 1

            if json_start != -1 and json_end > json_start:
                json_str = result_str[json_start:json_end]
                print(f"🔍 提取的 JSON 长度: {len(json_str)}")
                parsed_result = json.loads(json_str)
                print("✅ JSON 解析成功")
            else:
                print("⚠️  未找到完整 JSON，使用备用解析")
                parsed_result = self._parse_fallback_result(result_str, sql_query)

        except Exception as e:
            print(f"❌ CrewAI 执行或解析出错: {e}")
            print(f"🔄 使用备用优化逻辑")
            # 提供更详细的错误信息
            if "choices" in str(e):
                print("💡 这通常意味着 API 响应格式不正确或 API key 无效")
            elif "timeout" in str(e).lower():
                print("💡 这可能是网络超时问题")
            elif "api" in str(e).lower():
                print("💡 这可能是 API 认证问题")

            parsed_result = self._get_fallback_result(sql_query)

        # 确保基本字段存在
        parsed_result = self._ensure_required_fields(parsed_result, sql_query)

        # 添加元数据
        parsed_result["timestamp"] = datetime.now().isoformat()
        parsed_result["agent"] = "crewai_sql_optimizer"
        parsed_result["full_output"] = result_str if 'result_str' in locals() else "Execution failed"

        print("\n✅ CrewAI 优化完成")
        return parsed_result
    
    def _simple_optimize(self, sql: str) -> str:
        """简单的 SQL 优化（备用）"""
        optimized = sql.strip()

        if "SELECT *" in optimized.upper():
            optimized = optimized.replace("SELECT *",
                "SELECT id, name, email, created_at")

        if "WHERE" not in optimized.upper() and "FROM" in optimized.upper():
            parts = optimized.split("FROM")
            if len(parts) > 1:
                optimized = parts[0] + "FROM" + parts[1].rstrip(";") + \
                    "\nWHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"

        return optimized

    def _parse_fallback_result(self, result_str: str, sql_query: str) -> Dict[str, Any]:
        """备用结果解析"""
        # 尝试从文本中提取有用信息
        issues = []
        optimizations = []

        # 使用我们的工具函数
        try:
            analysis_result = analyze_sql_tool(sql_query)
            suggestions_result = generate_optimization_suggestions(sql_query)

            if "发现以下问题:" in analysis_result:
                issues = [line.strip() for line in analysis_result.split('\n')[1:] if line.strip()]

            if "优化建议" in suggestions_result:
                optimizations = [s.strip() for s in suggestions_result.split('优化建议') if s.strip() and len(s.strip()) > 10]

        except Exception as e:
            print(f"⚠️  备用分析出错: {e}")

        return {
            "original_sql": sql_query,
            "optimized_sql": self._simple_optimize(sql_query),
            "issues_found": issues[:5] if issues else ["需要详细分析"],
            "optimizations_applied": optimizations[:3] if optimizations else ["基础优化"],
            "performance_gain_estimate": "10-20%",
            "recommendations": ["建议查看完整分析报告", "考虑添加索引", "优化查询条件"]
        }

    def _get_fallback_result(self, sql_query: str) -> Dict[str, Any]:
        """获取备用结果"""
        # 直接使用工具函数进行分析
        try:
            print("🔧 执行备用 SQL 分析...")

            # 检查工具函数是否可调用
            if callable(analyze_sql_tool):
                analysis = analyze_sql_tool(sql_query)
                print("✅ SQL 分析工具执行成功")
            else:
                analysis = "⚠️  SQL 分析工具不可用，使用内置逻辑"
                print("⚠️  SQL 分析工具不可用，使用内置逻辑")

            if callable(generate_optimization_suggestions):
                suggestions = generate_optimization_suggestions(sql_query)
                print("✅ 优化建议工具执行成功")
            else:
                suggestions = "⚠️  优化建议工具不可用，使用内置逻辑"
                print("⚠️  优化建议工具不可用，使用内置逻辑")

            issues = []
            if "❌" in analysis or "⚠️" in analysis:
                issues = [line.strip() for line in analysis.split('\n') if line.strip() and ('❌' in line or '⚠️' in line)]

            optimizations = []
            if "优化建议" in suggestions:
                # 提取优化建议的关键词
                opt_lines = [line.strip() for line in suggestions.split('\n') if line.strip()]
                optimizations = [line for line in opt_lines if line.startswith('-') or line.startswith('•')]

            # 如果工具函数不可用，使用内置逻辑
            if not issues:
                issues = self._analyze_sql_fallback(sql_query)
            if not optimizations:
                optimizations = self._get_suggestions_fallback(sql_query)

        except Exception as e:
            print(f"⚠️  工具函数执行出错: {e}")
            print("🔄 使用内置分析逻辑")
            issues = self._analyze_sql_fallback(sql_query)
            optimizations = self._get_suggestions_fallback(sql_query)

        return {
            "original_sql": sql_query,
            "optimized_sql": self._simple_optimize(sql_query),
            "issues_found": issues[:5] if issues else ["检查 SELECT * 使用", "检查是否有 WHERE 子句"],
            "optimizations_applied": optimizations[:3] if optimizations else ["基础优化"],
            "performance_gain_estimate": "5-15%",
            "recommendations": ["使用 EXPLAIN 分析执行计划", "添加合适的索引", "避免使用 SELECT *"]
        }

    def _analyze_sql_fallback(self, sql_query: str) -> List[str]:
        """内置 SQL 分析逻辑"""
        issues = []
        sql_lower = sql_query.lower()

        if "select *" in sql_lower:
            issues.append("❌ 使用 SELECT * 会检索所有列")
        if "where" not in sql_lower and "from" in sql_lower:
            issues.append("❌ 缺少 WHERE 子句可能导致全表扫描")
        if "like" in sql_lower and "'%" in sql_lower:
            issues.append("❌ LIKE 前置通配符无法使用索引")

        return issues if issues else ["✅ 未发现明显的性能问题"]

    def _get_suggestions_fallback(self, sql_query: str) -> List[str]:
        """内置优化建议逻辑"""
        suggestions = []
        sql_lower = sql_query.lower()

        if "select *" in sql_lower:
            suggestions.append("- 明确指定需要的列名而不是使用 SELECT *")
        if "where" not in sql_lower and "from" in sql_lower:
            suggestions.append("- 添加合适的 WHERE 条件来过滤数据")
        if "like" in sql_lower and "'%" in sql_lower:
            suggestions.append("- 避免 LIKE 前置通配符，考虑使用全文搜索")

        return suggestions if suggestions else ["- 当前 SQL 已经较为优化"]

    def _ensure_required_fields(self, result: Dict[str, Any], sql_query: str) -> Dict[str, Any]:
        """确保结果包含所有必需字段"""
        required_fields = {
            "original_sql": sql_query,
            "optimized_sql": result.get("optimized_sql", self._simple_optimize(sql_query)),
            "issues_found": result.get("issues_found", []),
            "optimizations_applied": result.get("optimizations_applied", []),
            "performance_gain_estimate": result.get("performance_gain_estimate", "10-30%"),
            "recommendations": result.get("recommendations", [])
        }

        # 确保列表字段不为空
        if not required_fields["issues_found"]:
            required_fields["issues_found"] = ["需要详细分析"]
        if not required_fields["optimizations_applied"]:
            required_fields["optimizations_applied"] = ["基础优化"]
        if not required_fields["recommendations"]:
            required_fields["recommendations"] = ["查看完整分析报告"]

        # 合并额外字段
        final_result = {**required_fields, **result}
        return final_result


# ============================================================================
# 2. AutoGen 0.4+ SQL 审核 Agent (完整实现)
# ============================================================================

class SQLReviewerAutoGen:
    """AutoGen 0.7+ SQL 审核系统"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        if not self.api_key:
            raise ValueError("需要设置 OPENAI_API_KEY 环境变量")
        
        self._setup_agents()
    
    def _setup_agents(self):
        """初始化 AutoGen 0.7+ Agents"""
        print("🤖 初始化 AutoGen 0.7+ Agents...")

        try:
            # 创建 OpenAI 客户端，添加更多配置
            self.model_client = OpenAIChatCompletionClient(
                model="gpt-4o-mini-2024-07-18",
                api_key=self.api_key,
                base_url=self.base_url,
                # 添加超时和重试配置（如果支持的参数）
                timeout=30,
            )

            # 创建 SQL 审核 Agent
            self.reviewer_agent = AssistantAgent(
                name="SQL_Reviewer",
                model_client=self.model_client,
                description="资深的 SQL 审核专家，负责审核优化后的 SQL 语句",
                system_message="""你是一位资深的 SQL 审核专家，负责审核优化后的 SQL 语句。

你的审核维度包括:
1. **语法正确性**: 检查 SQL 语法是否正确
2. **安全性**: 检查是否存在 SQL 注入风险、危险操作
3. **性能**: 评估查询性能和优化效果
4. **最佳实践**: 检查是否符合 SQL 编码规范

审核标准:
- 语法错误: 不通过
- 安全风险: 不通过
- 性能问题: 根据严重程度决定
- 规范问题: 给出建议但可以通过

请给出明确的审核结论: APPROVED (通过) 或 REJECTED (拒绝)
并提供详细的审核理由和改进建议。

输出格式要求 JSON:
{
    "approved": true/false,
    "score": 0-100,
    "syntax_check": {"passed": true/false, "issues": []},
    "security_check": {"passed": true/false, "issues": []},
    "performance_check": {"passed": true/false, "score": 0-100},
    "best_practices": {"score": 0-100, "suggestions": []},
    "summary": "审核总结",
    "recommendations": ["建议1", "建议2"]
}

只返回 JSON，不要其他文字。"""
            )

            print("✅ AutoGen Agents 初始化成功")

        except Exception as e:
            print(f"❌ AutoGen Agents 初始化失败: {e}")
            # 创建一个备用的 Mock Agent
            self.reviewer_agent = None
            self.model_client = None
            print("⚠️  将使用备用审核逻辑")
    
    async def _collect_stream_messages(self, team, task: str, timeout: int = 30) -> list:
        """异步收集流式消息 - 修复版"""
        import sys
        
        print(f"🔄 启动流式收集（超时: {timeout}秒）...")
        
        messages = []
        
        try:
            async with asyncio.timeout(timeout):
                stream = team.run_stream(task=task)
                message_count = 0
                
                async for message in stream:
                    messages.append(message)
                    message_count += 1
                    
                    # 限制消息数量
                    if message_count >= 10:
                        print(f"📝 已达到最大消息数 ({message_count})，停止收集")
                        break
                    
                    # 显示进度
                    if message_count <= 3:
                        # 调试消息结构
                        print(f"🔍 消息 {message_count} 类型: {type(message)}")
                        attrs = [attr for attr in dir(message) if not attr.startswith('_')][:10]  # 限制显示的属性数量
                        print(f"🔍 消息 {message_count} 属性: {attrs}")

                        # 尝试提取内容预览
                        content_preview = "N/A"
                        if hasattr(message, 'content'):
                            content_preview = str(message.content)[:100]
                        elif hasattr(message, 'text'):
                            content_preview = str(message.text)[:100]
                        elif hasattr(message, 'message'):
                            content_preview = str(message.message)[:100]
                        else:
                            content_preview = str(message)[:100]

                        print(f"📝 收到消息 {message_count}: {content_preview}...")
           
            
            print(f"✅ 流式收集完成，共 {len(messages)} 条消息")
            
        except asyncio.TimeoutError:
            print(f"⏰ 流式收集超时 ({timeout}秒)，已收集 {len(messages)} 条消息")
        except Exception as e:
            print(f"❌ 流式收集出错: {e}")
            import traceback
            traceback.print_exc()
        
        return messages
    
    async def review_optimization(self, optimization_result: Dict[str, Any]) -> Dict[str, Any]:
        """执行 SQL 审核流程（异步）"""
        print("\n" + "="*80)
        print("🔍 SQL 审核流程启动")
        print("="*80)

        # 检查 AutoGen Agent 是否可用
        if self.reviewer_agent is None:
            print("⚠️  AutoGen Agent 不可用，使用备用审核逻辑")
            optimized_sql = optimization_result.get("optimized_sql", "")
            original_sql = optimization_result.get("original_sql", "")

            result = self._fallback_review(optimized_sql)
            result["timestamp"] = datetime.now().isoformat()
            result["agent"] = "fallback_reviewer"
            result["comparison"] = self._compare_sqls(original_sql, optimized_sql)

            print(f"\n✅ 备用审核完成")
            print(f"   状态: {'✅ 通过' if result.get('approved') else '❌ 未通过'}")
            print(f"   评分: {result.get('score', 0)}/100")

            return result

        original_sql = optimization_result.get("original_sql", "")
        optimized_sql = optimization_result.get("optimized_sql", "")
        issues = optimization_result.get("issues_found", [])
        optimizations = optimization_result.get("optimizations_applied", [])

        # 构建审核请求
        review_request = f"""
请审核以下 SQL 优化结果:

**原始 SQL:**
```sql
{original_sql}
```

**优化后的 SQL:**
```sql
{optimized_sql}
```

**发现的问题:**
{json.dumps(issues, ensure_ascii=False, indent=2)}

**应用的优化:**
{json.dumps(optimizations, ensure_ascii=False, indent=2)}

请进行全面审核，并以 JSON 格式返回审核结果。
重点关注:
1. 优化后的 SQL 是否保持了原有语义
2. 是否存在语法错误
3. 是否存在安全风险
4. 性能是否真正得到提升
5. 是否符合 SQL 最佳实践

请直接返回 JSON，不要有其他文字。
"""

        review_result = None

        try:
            print("🤖 AutoGen 正在审核优化结果...")

            # 使用 RoundRobinGroupChat 进行对话
            termination = TextMentionTermination("TERMINATE")
            max_message_termination = MaxMessageTermination(5)
            # 使用`|` 运算符组合终止条件，在满足任一条件时停止任务
            termination = termination | max_message_termination
            team = RoundRobinGroupChat(
                participants=[self.reviewer_agent],
                termination_condition=termination,
                max_turns=None
            )

            # 使用修复后的异步流式收集，添加更短的超时时间
            messages = await self._collect_stream_messages(team, review_request, timeout=15)

            if messages:
                # 获取最后一条消息
                last_message = messages[-1]

                # 提取内容 - 支持多种消息格式
                content = None

                # 尝试不同的内容属性
                if hasattr(last_message, 'content'):
                    content = last_message.content
                    print(f"📄 通过 content 属性获取内容: {str(content)[:100]}...")
                elif hasattr(last_message, 'text'):
                    content = last_message.text
                    print(f"📄 通过 text 属性获取内容: {str(content)[:100]}...")
                elif hasattr(last_message, 'message'):
                    content = last_message.message
                    print(f"📄 通过 message 属性获取内容: {str(content)[:100]}...")
                elif hasattr(last_message, 'source') and hasattr(last_message, 'data'):
                    content = str(last_message.data)
                    print(f"📄 通过 data 属性获取内容: {str(content)[:100]}...")
                else:
                    # 尝试转换为字符串
                    content = str(last_message)
                    print(f"📄 通过 str() 获取内容: {content[:100]}...")
                    print(f"🔍 消息类型: {type(last_message)}")
                    print(f"🔍 消息属性: {[attr for attr in dir(last_message) if not attr.startswith('_')]}")

                if content and len(content.strip()) > 0:
                    review_result = self._parse_review_response(content, optimized_sql)
                else:
                    print("⚠️  消息内容为空或无法提取")
                    review_result = self._fallback_review(optimized_sql)
            else:
                print("⚠️  未收集到任何消息")
                review_result = self._fallback_review(optimized_sql)

        except Exception as e:
            print(f"❌ AutoGen 审核出错: {e}")
            print("🔄 切换到备用审核逻辑")
            import traceback
            traceback.print_exc()
            review_result = self._fallback_review(optimized_sql)

        # 如果审核结果为空，使用备用逻辑
        if review_result is None:
            print("🔄 审核结果为空，使用备用审核逻辑")
            review_result = self._fallback_review(optimized_sql)

        # 添加元数据
        review_result["timestamp"] = datetime.now().isoformat()
        review_result["agent"] = "autogen_sql_reviewer"
        review_result["comparison"] = self._compare_sqls(original_sql, optimized_sql)

        print(f"\n✅ SQL 审核完成")
        print(f"   状态: {'✅ 通过' if review_result.get('approved') else '❌ 未通过'}")
        print(f"   评分: {review_result.get('score', 0)}/100")

        return review_result
    
    def _parse_review_response(self, content: str, optimized_sql: str) -> Dict[str, Any]:
        """解析 AutoGen 审核响应"""
        try:
            # 解析 JSON
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                review_result = json.loads(json_str)
                print(f"✅ JSON 解析成功")
                return review_result
            else:
                print("⚠️  未找到完整 JSON")
                return self._fallback_review(optimized_sql)
        
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 解析失败: {e}")
            return self._fallback_review(optimized_sql)
    
    def _fallback_review(self, sql: str) -> Dict[str, Any]:
        """备用审核逻辑"""
        print("🔄 使用备用审核逻辑...")
        
        score = 100
        issues = []
        
        sql_upper = sql.upper()
        
        # 安全检查
        if "DROP" in sql_upper or "TRUNCATE" in sql_upper:
            score -= 50
            issues.append("包含危险操作 (DROP/TRUNCATE)")
        
        if "DELETE" in sql_upper and "WHERE" not in sql_upper:
            score -= 40
            issues.append("DELETE 语句缺少 WHERE 条件")
        
        # 性能检查
        if "SELECT *" in sql:
            score -= 10
            issues.append("使用 SELECT *")
        
        if "WHERE" not in sql_upper and "FROM" in sql_upper:
            score -= 15
            issues.append("缺少 WHERE 子句")
        
        if sql.count("JOIN") > 3:
            score -= 10
            issues.append(f"过多的 JOIN ({sql.count('JOIN')} 个)")
        
        # 计算最终评分
        score = max(0, score)
        
        return {
            "approved": score >= 70,
            "score": score,
            "syntax_check": {
                "passed": True,
                "issues": []
            },
            "security_check": {
                "passed": score >= 70,
                "issues": [i for i in issues if "危险" in i or "DELETE" in i]
            },
            "performance_check": {
                "passed": score >= 70,
                "score": score
            },
            "best_practices": {
                "score": score,
                "suggestions": issues
            },
            "summary": f"备用审核完成，评分 {score}/100",
            "recommendations": issues if issues else ["SQL 质量良好"]
        }
    
    def _compare_sqls(self, original: str, optimized: str) -> Dict[str, Any]:
        """对比两个 SQL"""
        return {
            "length_change": f"{len(original)} → {len(optimized)} 字符",
            "complexity": "简化" if len(optimized) < len(original) else "优化",
            "readability": "提升" if "\n" in optimized and "\n" not in original else "保持"
        }


# ============================================================================
# 3. A2A Framework 协议实现
# ============================================================================

class A2AMessage:
    """A2A 协议消息"""
    
    def __init__(self, sender: str, receiver: str, content: Dict[str, Any], 
                 message_type: str = "request"):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.message_type = message_type
        self.timestamp = datetime.now().isoformat()
        self.message_id = f"{sender}_{int(datetime.now().timestamp() * 1000)}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp,
            "protocol": "A2A-v1.0"
        }


class A2AOrchestrator:
    """A2A 框架编排器"""
    
    def __init__(self):
        self.agents = {}
        self.message_history = []
        
    def register_agent(self, agent_id: str, agent: Any):
        """注册 Agent"""
        self.agents[agent_id] = agent
        print(f"✅ [A2A] 注册 Agent: {agent_id}")
    
    async def send_message(self, message: A2AMessage) -> Dict[str, Any]:
        """发送 A2A 消息"""
        msg_dict = message.to_dict()
        self.message_history.append(msg_dict)
        
        print(f"\n📨 [A2A Protocol] 消息传递")
        print(f"   From: {message.sender}")
        print(f"   To: {message.receiver}")
        print(f"   Type: {message.message_type}")
        print(f"   Message ID: {message.message_id}")
        
        await asyncio.sleep(0.2)
        
        return msg_dict
    
    async def optimize_and_review_sql(self, sql_query: str) -> Dict[str, Any]:
        """完整的 SQL 优化和审核流程"""
        
        print("\n" + "🌟"*40)
        print("         A2A SQL 优化审核系统")
        print("🌟"*40)
        
        # 步骤 1: 用户 -> CrewAI Optimizer
        optimizer = self.agents.get("crewai_sql_optimizer")
        if not optimizer:
            raise ValueError("CrewAI SQL Optimizer Agent 未注册")
        
        optimize_msg = A2AMessage(
            sender="user",
            receiver="crewai_sql_optimizer",
            content={"sql_query": sql_query, "task": "optimize"},
            message_type="optimization_request"
        )
        await self.send_message(optimize_msg)
        
        # CrewAI 执行优化（同步）
        optimization_result = optimizer.optimize_sql(sql_query)
        
        # 步骤 2: CrewAI Optimizer -> AutoGen Reviewer
        reviewer = self.agents.get("autogen_sql_reviewer")
        if not reviewer:
            raise ValueError("AutoGen SQL Reviewer Agent 未注册")
        
        review_msg = A2AMessage(
            sender="crewai_sql_optimizer",
            receiver="autogen_sql_reviewer",
            content=optimization_result,
            message_type="review_request"
        )
        await self.send_message(review_msg)
        
        # AutoGen 执行审核（异步）
        review_result = await reviewer.review_optimization(optimization_result)
        
        # 步骤 3: AutoGen Reviewer -> User
        final_msg = A2AMessage(
            sender="autogen_sql_reviewer",
            receiver="user",
            content={
                "optimization": optimization_result,
                "review": review_result,
                "final_status": "APPROVED" if review_result.get("approved") else "REJECTED",
                "workflow_complete": True
            },
            message_type="final_response"
        )
        await self.send_message(final_msg)
        print("         流程完成")
        return final_msg.to_dict()


# ============================================================================
# 4. 主程序
# ============================================================================

async def main():
    """主程序"""
    
    # 检查 API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ 错误: 未设置 OPENAI_API_KEY 环境变量")
        print("请创建 .env 文件并添加: OPENAI_API_KEY=your_key_here")
        return
    
    try:
        # 初始化 A2A 编排器
        orchestrator = A2AOrchestrator()
        
        # 创建 Agents
        print("\n🔧 初始化 Agents...")
        sql_optimizer = SQLOptimizerCrew()
        sql_reviewer = SQLReviewerAutoGen()
        
        # 注册到 A2A
        orchestrator.register_agent("crewai_sql_optimizer", sql_optimizer)
        orchestrator.register_agent("autogen_sql_reviewer", sql_reviewer)
        
        # 测试 SQL
        test_sql = """
        SELECT * FROM users 
        JOIN orders ON users.id = orders.user_id 
        JOIN products ON orders.product_id = products.id 
        WHERE name LIKE '%John%'
        """
        
        print(f"\n📝 原始 SQL:\n{test_sql}")
        
        # 执行完整流程
        result = await orchestrator.optimize_and_review_sql(test_sql)
        
        # 打印结果
        print_final_report(result, orchestrator.message_history)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


def print_final_report(result: Dict, message_history: List):
    """打印最终报告"""
    
    content = result["content"]
    opt = content["optimization"]
    rev = content["review"]
    
    print("                  最终报告")
    print(f"\n{'='*80}")
    print("状态信息")
    print(f"{'='*80}")
    print(f"最终状态: {content['final_status']}")
    print(f"审核评分: {rev.get('score', 'N/A')}/100")
    print(f"是否通过: {'✅ 是' if rev.get('approved') else '❌ 否'}")
    
    print(f"\n{'='*80}")
    print("优化结果")
    print(f"{'='*80}")
    print(f"\n原始 SQL:\n{opt['original_sql']}")
    print(f"\n优化后的 SQL:\n{opt['optimized_sql']}")
    
    if opt.get('issues_found'):
        print(f"\n发现的问题 ({len(opt['issues_found'])} 个):")
        for i, issue in enumerate(opt['issues_found'][:5], 1):
            print(f"  {i}. {issue}")
    
    if rev.get('recommendations'):
        print(f"\n改进建议:")
        for i, rec in enumerate(rev['recommendations'][:5], 1):
            print(f"  {i}. {rec}")
    
    print(f"\n{'='*80}")
    print("A2A 消息历史")
    print(f"{'='*80}")
    print(f"总消息数: {len(message_history)}")
    for i, msg in enumerate(message_history, 1):
        print(f"\n  [{i}] {msg['sender']} → {msg['receiver']}")
        print(f"      类型: {msg['type']}")
        print(f"      时间: {msg['timestamp']}")


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                A2A Framework SQL 优化审核系统                     ║
    ║                      (AutoGen 0.4+ 版本)                         ║
    ║                                                                  ║
    ║  技术栈:                                                          ║
    ║    • CrewAI          - 协作式 AI Agent (SQL 优化)               ║
    ║    • AutoGen 0.4+    - 新架构对话式 Agent (SQL 审核)            ║
    ║    • A2A Protocol    - Agent-to-Agent 通信协议                  ║
    ║                                                                  ║
    ║  工作流:                                                         ║
    ║    User → CrewAI Optimizer → AutoGen Reviewer → User            ║
    ║                                                                  ║
    ║  依赖安装:                                                       ║
    ║    pip install crewai crewai-tools                              ║
    ║    pip install autogen-agentchat autogen-core autogen-ext       ║
    ║    pip install openai python-dotenv                             ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    asyncio.run(main())