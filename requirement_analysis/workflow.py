"""
需求分析工作流模块
基于AutoGen 0.7.0框架实现需求分析的完整工作流
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import ChatMessage

from agents import RequirementAnalysisAgents


class RequirementAnalysisWorkflow:
    """需求分析工作流管理器"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        """
        初始化工作流管理器
        
        Args:
            api_key: OpenAI API密钥
            base_url: API基础URL
            model: 使用的模型名称
        """
        self.agent_factory = RequirementAnalysisAgents(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        self.results = {}
        
    async def analyze_requirement(
        self,
        requirement_doc: str,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        执行完整的需求分析流程
        
        Args:
            requirement_doc: 需求文档内容
            stream: 是否流式输出
            
        Returns:
            完整的分析结果
        """
        print("=" * 80)
        print("开始需求分析流程...")
        print("=" * 80)
        
        # 1. 技术可行性评估
        print("\n[阶段 1/7] 技术可行性评估...")
        tech_feasibility = await self._run_tech_feasibility_analysis(requirement_doc)
        self.results["tech_feasibility"] = tech_feasibility
        
        # 2. 风险识别
        print("\n[阶段 2/7] 需求风险识别...")
        risk_analysis = await self._run_risk_identification(requirement_doc, tech_feasibility)
        self.results["risk_analysis"] = risk_analysis
        
        # 3. 难度评估
        print("\n[阶段 3/7] 需求难度评估...")
        difficulty = await self._run_difficulty_assessment(
            requirement_doc, 
            tech_feasibility,
            risk_analysis
        )
        self.results["difficulty"] = difficulty
        
        # 4. 需求拆解
        print("\n[阶段 4/7] 需求拆解...")
        decomposition = await self._run_requirement_decomposition(
            requirement_doc,
            tech_feasibility,
            difficulty
        )
        self.results["decomposition"] = decomposition
        
        # 5. 工作量评估
        print("\n[阶段 5/7] 工作量评估...")
        workload = await self._run_workload_estimation(
            decomposition,
            difficulty
        )
        self.results["workload"] = workload
        
        # 6. 排期规划
        print("\n[阶段 6/7] 需求排期...")
        schedule = await self._run_scheduling(
            decomposition,
            workload,
            risk_analysis
        )
        self.results["schedule"] = schedule
        
        # 7. 需求复核
        print("\n[阶段 7/7] 需求复核...")
        review = await self._run_review(self.results)
        self.results["review"] = review
        
        # 生成最终报告
        final_report = self._generate_final_report()
        
        print("\n" + "=" * 80)
        print("需求分析流程完成！")
        print("=" * 80)
        
        return final_report
    
    async def _run_tech_feasibility_analysis(self, requirement_doc: str) -> Dict[str, Any]:
        """运行技术可行性评估"""
        agent = self.agent_factory.create_tech_feasibility_agent()
        
        task = f"""请对以下需求进行技术可行性评估：

{requirement_doc}

请严格按照以下JSON格式输出评估结果，不要包含任何其他文字，只输出JSON对象：
{{
  "feasibility_score": "可行/有风险/不可行",
  "tech_stack": ["所需技术栈列表"],
  "data_sources": ["数据源评估"],
  "technical_challenges": ["技术挑战列表"],
  "recommendations": ["技术建议"]
}}
"""
        
        # 创建简单的对话
        termination = MaxMessageTermination(2)
        team = RoundRobinGroupChat(
            participants=[agent],
            termination_condition=termination
        )
        
        result = await team.run(task=task)
        return self._extract_json_from_messages(result.messages)
    
    async def _run_risk_identification(
        self,
        requirement_doc: str,
        tech_feasibility: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行风险识别"""
        agent = self.agent_factory.create_risk_identification_agent()
        
        task = f"""请对以下需求进行风险识别：

需求文档：
{requirement_doc}

技术可行性评估结果：
{json.dumps(tech_feasibility, ensure_ascii=False, indent=2)}

请严格按照以下JSON格式输出风险识别结果，不要包含任何其他文字，只输出JSON对象：
{{
  "risks": [
    {{
      "category": "风险类别",
      "description": "风险描述",
      "probability": "高/中/低",
      "impact": "高/中/低",
      "mitigation": "应对措施"
    }}
  ],
  "overall_risk_level": "高/中/低"
}}
"""
        
        termination = MaxMessageTermination(2)
        team = RoundRobinGroupChat(
            participants=[agent],
            termination_condition=termination
        )
        
        result = await team.run(task=task)
        return self._extract_json_from_messages(result.messages)
    
    async def _run_difficulty_assessment(
        self,
        requirement_doc: str,
        tech_feasibility: Dict[str, Any],
        risk_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行难度评估"""
        agent = self.agent_factory.create_difficulty_assessment_agent()
        
        task = f"""请对以下需求进行难度评估：

需求文档：
{requirement_doc}

技术可行性：
{json.dumps(tech_feasibility, ensure_ascii=False, indent=2)}

风险分析：
{json.dumps(risk_analysis, ensure_ascii=False, indent=2)}

请严格按照以下JSON格式输出，不要包含任何其他文字，只输出JSON对象：难度评估结果：
{{
  "difficulty_score": 1-10,
  "difficulty_level": "简单/中等/困难/极难",
  "dimensions": {{
    "technical": 1-10,
    "business": 1-10,
    "data": 1-10,
    "integration": 1-10,
    "interaction": 1-10
  }},
  "analysis": "详细分析",
  "key_challenges": ["关键挑战列表"]
}}


"""
        
        termination = MaxMessageTermination(2)
        team = RoundRobinGroupChat(
            participants=[agent],
            termination_condition=termination
        )
        
        result = await team.run(task=task)
        return self._extract_json_from_messages(result.messages)
    
    async def _run_requirement_decomposition(
        self,
        requirement_doc: str,
        tech_feasibility: Dict[str, Any],
        difficulty: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行需求拆解"""
        agent = self.agent_factory.create_requirement_decomposition_agent()
        
        task = f"""请对以下需求进行任务拆解：

需求文档：
{requirement_doc}

技术可行性：
{json.dumps(tech_feasibility, ensure_ascii=False, indent=2)}

难度评估：
{json.dumps(difficulty, ensure_ascii=False, indent=2)}

请严格按照以下JSON格式输出，不要包含任何其他文字，只输出JSON对象：任务拆解结果：
{{
  "tasks": [
    {{
      "task_id": "T001",
      "task_name": "任务名称",
      "category": "任务分类",
      "description": "详细描述",
      "dependencies": ["依赖的任务ID"],
      "priority": "高/中/低",
      "acceptance_criteria": "验收标准"
    }}
  ],
  "task_graph": "任务依赖关系图描述"
}}


"""
        
        termination = MaxMessageTermination(2)
        team = RoundRobinGroupChat(
            participants=[agent],
            termination_condition=termination
        )
        
        result = await team.run(task=task)
        return self._extract_json_from_messages(result.messages)
    
    async def _run_workload_estimation(
        self,
        decomposition: Dict[str, Any],
        difficulty: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行工作量评估"""
        agent = self.agent_factory.create_workload_estimation_agent()
        
        task = f"""请对以下任务进行工作量评估：

任务拆解结果：
{json.dumps(decomposition, ensure_ascii=False, indent=2)}

难度评估：
{json.dumps(difficulty, ensure_ascii=False, indent=2)}

请严格按照以下JSON格式输出，不要包含任何其他文字，只输出JSON对象：工作量评估结果：
{{
  "task_estimates": [
    {{
      "task_id": "T001",
      "task_name": "任务名称",
      "optimistic": 2,
      "most_likely": 3,
      "pessimistic": 5,
      "expected": 3.2,
      "confidence": "高/中/低"
    }}
  ],
  "total_effort": {{
    "optimistic": 20,
    "most_likely": 35,
    "pessimistic": 50,
    "expected": 36,
    "unit": "person-days"
  }},
  "critical_path": ["关键路径任务列表"],
  "resource_requirements": {{
    "backend_developers": 2,
    "frontend_developers": 1,
    "data_engineers": 1,
    "qa_engineers": 1
  }}
}}


"""
        
        termination = MaxMessageTermination(2)
        team = RoundRobinGroupChat(
            participants=[agent],
            termination_condition=termination
        )
        
        result = await team.run(task=task)
        return self._extract_json_from_messages(result.messages)
    
    async def _run_scheduling(
        self,
        decomposition: Dict[str, Any],
        workload: Dict[str, Any],
        risk_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行排期规划"""
        agent = self.agent_factory.create_scheduling_agent()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        task = f"""请基于以下信息制定项目排期计划：

当前日期：{today}

任务拆解：
{json.dumps(decomposition, ensure_ascii=False, indent=2)}

工作量评估：
{json.dumps(workload, ensure_ascii=False, indent=2)}

风险分析：
{json.dumps(risk_analysis, ensure_ascii=False, indent=2)}

请严格按照以下JSON格式输出，不要包含任何其他文字，只输出JSON对象：排期计划：
{{
  "project_timeline": {{
    "start_date": "2025-12-10",
    "end_date": "2026-01-20",
    "total_duration": "42天",
    "buffer_days": 6
  }},
  "milestones": [
    {{
      "milestone": "里程碑名称",
      "date": "2025-12-15",
      "deliverables": ["交付物列表"]
    }}
  ],
  "schedule": [
    {{
      "task_id": "T001",
      "task_name": "任务名称",
      "start_date": "2025-12-10",
      "end_date": "2025-12-13",
      "duration": 3,
      "assigned_to": "角色",
      "status": "未开始"
    }}
  ],
  "resource_allocation": "资源分配计划",
  "risks": ["排期风险列表"]
}}


"""
        
        termination = MaxMessageTermination(2)
        team = RoundRobinGroupChat(
            participants=[agent],
            termination_condition=termination
        )
        
        result = await team.run(task=task)
        return self._extract_json_from_messages(result.messages)
    
    async def _run_review(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """运行需求复核"""
        agent = self.agent_factory.create_review_agent()
        
        task = f"""请对整个需求分析过程进行复核：

完整分析结果：
{json.dumps(all_results, ensure_ascii=False, indent=2)}

请严格按照以下JSON格式输出，不要包含任何其他文字，只输出JSON对象：复核结果：
{{
  "review_result": "通过/有条件通过/不通过",
  "completeness_check": {{
    "score": "优秀/良好/一般/差",
    "issues": ["发现的问题"]
  }},
  "consistency_check": {{
    "score": "优秀/良好/一般/差",
    "conflicts": ["发现的矛盾"]
  }},
  "feasibility_check": {{
    "score": "优秀/良好/一般/差",
    "concerns": ["关注点"]
  }},
  "recommendations": ["建议列表"],
  "action_items": ["待办事项"],
  "final_decision": {{
    "approve": true/false,
    "conditions": ["通过条件"],
    "next_steps": ["下一步行动"]
  }}
}}


"""
        
        termination = MaxMessageTermination(2)
        team = RoundRobinGroupChat(
            participants=[agent],
            termination_condition=termination
        )
        
        result = await team.run(task=task)
        return self._extract_json_from_messages(result.messages)
    
    def _extract_json_from_messages(self, messages: List[ChatMessage]) -> Dict[str, Any]:
        """从消息中提取JSON结果"""
        import re
        
        for msg in reversed(messages):
            if hasattr(msg, 'content') and isinstance(msg.content, str):
                content = msg.content
                
                # 尝试查找JSON代码块（支持多种格式）
                json_block_patterns = [
                    r'```json\s*([\s\S]*?)```',
                    r'```\s*([\s\S]*?)```',
                ]
                
                for pattern in json_block_patterns:
                    matches = re.findall(pattern, content, re.DOTALL)
                    if matches:
                        for match in matches:
                            try:
                                json_str = match.strip()
                                result = json.loads(json_str)
                                print(f"✓ 成功从代码块中解析JSON")
                                return result
                            except Exception as e:
                                print(f"✗ 代码块JSON解析失败: {str(e)[:100]}")
                                continue
                
                # 尝试直接解析为JSON（查找完整的JSON对象）
                try:
                    start = content.find('{')
                    end = content.rfind('}')
                    if start != -1 and end != -1 and start < end:
                        json_str = content[start:end+1]
                        result = json.loads(json_str)
                        print(f"✓ 成功从文本中解析JSON")
                        return result
                except Exception as e:
                    print(f"✗ 直接JSON解析失败: {str(e)[:100]}")
        
        # 如果没有找到JSON，返回文本内容
        last_content = messages[-1].content if messages else "无输出"
        print(f"✗ 未能解析JSON，内容前200字符: {last_content[:200]}")
        return {
            "raw_output": last_content,
            "note": "未能解析为结构化JSON"
        }
    
    def _generate_final_report(self) -> Dict[str, Any]:
        """生成最终分析报告"""
        return {
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tech_feasibility": self.results.get("tech_feasibility", {}),
            "risk_analysis": self.results.get("risk_analysis", {}),
            "difficulty_assessment": self.results.get("difficulty", {}),
            "requirement_decomposition": self.results.get("decomposition", {}),
            "workload_estimation": self.results.get("workload", {}),
            "project_schedule": self.results.get("schedule", {}),
            "final_review": self.results.get("review", {}),
            "summary": self._generate_summary()
        }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """生成摘要信息"""
        review = self.results.get("review", {})
        workload = self.results.get("workload", {})
        schedule = self.results.get("schedule", {})
        risk = self.results.get("risk_analysis", {})
        
        return {
            "approval_status": review.get("review_result", "未知"),
            "total_effort_days": workload.get("total_effort", {}).get("expected", 0),
            "project_duration": schedule.get("project_timeline", {}).get("total_duration", "未知"),
            "risk_level": risk.get("overall_risk_level", "未知"),
            "key_recommendations": review.get("recommendations", [])
        }


async def demo_analysis():
    """演示需求分析流程"""
    
    # 示例需求文档
    requirement_doc = """
# 数据分析需求：用户行为分析看板

## 需求背景
运营团队需要实时了解用户在APP上的行为数据，以便优化产品功能和运营策略。

## 核心指标
1. DAU（日活跃用户数）
2. 用户留存率（次日、7日、30日）
3. 用户行为路径分析
4. 功能使用热力图

## 数据源
- 用户行为日志（埋点数据）
- 用户基础信息表
- 订单交易数据

## 展示需求
- 需要一个实时更新的Web看板
- 支持按时间、地域、用户类型等维度筛选
- 支持数据导出功能

## 时间要求
希望在1个月内上线
"""
    
    # 创建工作流
    workflow = RequirementAnalysisWorkflow()
    
    # 执行分析
    result = await workflow.analyze_requirement(requirement_doc)
    
    # 输出结果
    print("\n" + "=" * 80)
    print("最终分析报告")
    print("=" * 80)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    return result


if __name__ == "__main__":
    asyncio.run(demo_analysis())
