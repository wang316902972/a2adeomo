"""
需求分析系统使用示例
演示如何使用各个Agent和工作流
"""

import asyncio
import json
from workflow import RequirementAnalysisWorkflow
from agents import RequirementAnalysisAgents


# ============================================================================
# 示例1：完整的需求分析流程
# ============================================================================

async def example_full_analysis():
    """示例：完整的需求分析流程"""
    
    print("=" * 80)
    print("示例1：完整的需求分析流程")
    print("=" * 80)
    
    # 需求文档示例
    requirement_doc = """
# 数据分析需求：用户行为分析看板

## 一、需求背景
运营团队需要实时了解用户在APP上的行为数据，以便优化产品功能和运营策略。
当前只能通过数据库查询获取数据，效率低且无法实时监控。

## 二、核心目标
1. 实时监控用户活跃情况
2. 分析用户留存和流失原因
3. 发现用户行为规律，指导产品迭代

## 三、核心指标
1. DAU（日活跃用户数）
2. MAU（月活跃用户数）
3. 用户留存率（次日、7日、30日）
4. 用户行为路径分析
5. 功能使用热力图
6. 用户画像分析

## 四、分析维度
- 时间维度：按天、周、月
- 地域维度：省份、城市
- 用户维度：新用户、老用户、付费用户、免费用户
- 渠道维度：iOS、Android、Web

## 五、数据源
1. 用户行为日志（埋点数据）- 日增量约500万条
2. 用户基础信息表 - 总量约1000万用户
3. 订单交易数据 - 日增量约10万条

## 六、展示需求
- 需要一个Web看板，支持PC和移动端
- 实时更新（延迟不超过5分钟）
- 支持按多维度筛选和下钻
- 支持数据导出（Excel、CSV）
- 需要数据权限控制

## 七、性能要求
- 页面加载时间 < 3秒
- 支持1000+并发用户
- 数据查询响应 < 1秒

## 八、时间要求
希望在1个月内完成开发并上线
"""
    
    # 创建工作流
    workflow = RequirementAnalysisWorkflow(
        model="gpt-4o-mini-2024-07-18"  # 使用环境变量中的API配置
    )
    
    # 执行完整分析
    result = await workflow.analyze_requirement(requirement_doc)
    
    # 打印结果
    print("\n分析结果摘要：")
    print("-" * 80)
    summary = result.get("summary", {})
    print(f"审批状态: {summary.get('approval_status', '未知')}")
    print(f"工作量预估: {summary.get('total_effort_days', 0)} 人日")
    print(f"项目周期: {summary.get('project_duration', '未知')}")
    print(f"风险等级: {summary.get('risk_level', '未知')}")
    print(f"\n关键建议:")
    for rec in summary.get('key_recommendations', []):
        print(f"  - {rec}")
    
    # 保存完整结果到文件
    with open("analysis_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n完整分析结果已保存到: analysis_result.json")


# ============================================================================
# 示例2：单独使用某个Agent
# ============================================================================

async def example_single_agent():
    """示例：单独使用技术可行性评估Agent"""
    
    print("\n" + "=" * 80)
    print("示例2：单独使用技术可行性评估Agent")
    print("=" * 80)
    
    # 创建Agent工厂
    agent_factory = RequirementAnalysisAgents(model="gpt-4o-mini")
    
    # 创建技术可行性评估Agent
    tech_agent = agent_factory.create_tech_feasibility_agent()
    
    # 简单需求
    simple_requirement = """
需求：开发一个简单的博客系统
功能：文章发布、评论、用户注册登录
技术栈：不限
用户量：预计1000用户以内
"""
    
    print(f"\n需求内容:\n{simple_requirement}")
    print("\n正在评估技术可行性...")
    
    # 这里演示如何单独调用Agent
    # 实际使用中可以通过RoundRobinGroupChat来运行
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
    
    termination = TextMentionTermination("评估完成") | MaxMessageTermination(3)
    team = RoundRobinGroupChat(
        participants=[tech_agent],
        termination_condition=termination
    )
    
    task = f"""请对以下需求进行技术可行性评估：

{simple_requirement}

请给出技术栈建议、可行性评分和实现建议。
评估完成后回复：评估完成
"""
    
    result = await team.run(task=task)
    
    print("\n评估结果:")
    print("-" * 80)
    for msg in result.messages:
        if hasattr(msg, 'content'):
            print(msg.content)


# ============================================================================
# 示例3：比较不同难度的需求
# ============================================================================

async def example_compare_requirements():
    """示例：比较不同难度需求的分析结果"""
    
    print("\n" + "=" * 80)
    print("示例3：比较不同难度需求的分析结果")
    print("=" * 80)
    
    # 简单需求
    simple_req = "开发一个静态博客网站，支持Markdown文章发布"
    
    # 中等需求
    medium_req = "开发一个电商系统的订单管理模块，包括订单创建、支付、发货、退款等功能"
    
    # 复杂需求
    complex_req = "开发一个大数据实时分析平台，支持PB级数据的实时查询和多维分析，要求秒级响应"
    
    workflow = RequirementAnalysisWorkflow(model="gpt-4o-mini")
    
    requirements = {
        "简单需求": simple_req,
        "中等需求": medium_req,
        "复杂需求": complex_req
    }
    
    results = {}
    
    for name, req in requirements.items():
        print(f"\n分析【{name}】...")
        result = await workflow.analyze_requirement(req)
        results[name] = result.get("summary", {})
    
    # 对比结果
    print("\n" + "=" * 80)
    print("对比结果:")
    print("=" * 80)
    print(f"\n{'需求类型':<15} {'工作量(人日)':<15} {'项目周期':<15} {'风险等级':<10}")
    print("-" * 80)
    
    for name, summary in results.items():
        effort = summary.get('total_effort_days', 0)
        duration = summary.get('project_duration', '未知')
        risk = summary.get('risk_level', '未知')
        print(f"{name:<15} {effort:<15} {duration:<15} {risk:<10}")


# ============================================================================
# 示例4：API客户端调用示例
# ============================================================================

async def example_api_client():
    """示例：使用HTTP客户端调用API"""
    
    print("\n" + "=" * 80)
    print("示例4：API客户端调用")
    print("=" * 80)
    
    import httpx
    
    api_base_url = "http://localhost:8001"
    
    # 准备请求数据
    requirement = {
        "requirement_doc": "开发一个用户反馈管理系统，支持用户提交反馈、管理员处理反馈、数据统计分析等功能。",
        "model": "gpt-4o-mini"
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1. 创建分析任务
        print("\n1. 创建分析任务...")
        response = await client.post(
            f"{api_base_url}/api/v1/analyze",
            json=requirement
        )
        task_data = response.json()
        task_id = task_data["task_id"]
        print(f"   任务ID: {task_id}")
        print(f"   状态: {task_data['status']}")
        
        # 2. 轮询查询结果
        print("\n2. 查询分析结果...")
        max_attempts = 30
        for i in range(max_attempts):
            await asyncio.sleep(10)  # 等待10秒
            
            response = await client.get(
                f"{api_base_url}/api/v1/analyze/{task_id}"
            )
            result_data = response.json()
            status = result_data["status"]
            
            print(f"   第{i+1}次查询 - 状态: {status}")
            
            if status == "completed":
                print("\n✓ 分析完成！")
                result = result_data["result"]
                summary = result.get("summary", {})
                print(f"\n分析摘要:")
                print(f"  - 审批状态: {summary.get('approval_status')}")
                print(f"  - 工作量: {summary.get('total_effort_days')}人日")
                print(f"  - 项目周期: {summary.get('project_duration')}")
                break
            elif status == "failed":
                print(f"\n✗ 分析失败: {result_data.get('error')}")
                break
        else:
            print("\n⚠ 查询超时")


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """运行所有示例"""
    
    # 示例1：完整分析流程
    await example_full_analysis()
    
    # 示例2：单独使用Agent
    # await example_single_agent()
    
    # 示例3：比较不同需求
    # await example_compare_requirements()
    
    # 示例4：API客户端（需要先启动API服务）
    # await example_api_client()


if __name__ == "__main__":
    print("""
需求分析系统 - 使用示例

本文件包含多个使用示例：
1. example_full_analysis()      - 完整的需求分析流程
2. example_single_agent()        - 单独使用某个Agent
3. example_compare_requirements() - 比较不同难度需求
4. example_api_client()          - API客户端调用示例

默认运行示例1，如需运行其他示例，请修改main()函数。
""")
    
    asyncio.run(main())
