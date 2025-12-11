# 需求分析系统

基于 **AutoGen 0.7.0** 框架的智能需求分析多Agent系统，可以自动完成需求的技术可行性评估、风险识别、难度评估、任务拆解、工作量估算、排期规划和需求复核。

## 📋 功能特性

### 7个专业Agent

1. **技术可行性评估Agent** - 评估需求的技术实现方案和可行性
2. **需求风险识别Agent** - 识别需求中的各类风险点
3. **需求难度评估Agent** - 评估需求的实现难度等级
4. **需求拆解Agent** - 将需求拆分为可执行的任务
5. **工作量评估Agent** - 估算各任务的工作量（人日）
6. **需求排期Agent** - 制定项目时间表和里程碑
7. **需求复核Agent** - 对整个分析过程进行质量把关

### 核心能力

- ✅ 自动化需求分析全流程
- ✅ 多维度评估（技术、风险、难度、工作量）
- ✅ 结构化输出（JSON格式）
- ✅ RESTful API 接口
- ✅ 异步任务处理
- ✅ 支持自定义LLM配置

## 🏗️ 系统架构

```
需求文档输入
    ↓
技术可行性评估 → 评估技术栈和数据源
    ↓
需求风险识别 → 识别各类风险
    ↓
需求难度评估 → 评估实现难度
    ↓
需求拆解 → 拆分为任务列表
    ↓
工作量评估 → 估算人日
    ↓
需求排期 → 制定时间表
    ↓
需求复核 → 最终审查
    ↓
生成分析报告
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- pip 或 conda
- 虚拟环境（推荐）

### 2. 创建并激活虚拟环境

```bash
cd /usr/local/src/a2ademo/requirement_analysis
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 Windows: venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# OpenAI API Configuration
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1

# LLM Model Configuration
LLM_MODEL=gpt-4o-mini

# Service Configuration
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8001
```

### 5. 启动服务

**重要：所有命令执行前请先激活虚拟环境**

```bash
source venv/bin/activate  # 每次使用前都需要激活
```

#### 方式1：直接启动API服务

```bash
source venv/bin/activate
python api_service.py
```

或使用 uvicorn：

```bash
source venv/bin/activate
uvicorn api_service:app --host 0.0.0.0 --port 8001 --reload
```

#### 方式2：运行命令行演示

```bash
source venv/bin/activate
python workflow.py
```

### 6. 访问API文档

服务启动后访问：

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## 📖 使用示例

### API调用示例

#### 1. 创建分析任务（异步）

```bash
curl -X POST "http://localhost:8001/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "requirement_doc": "# 需求：用户行为分析看板\n\n需要开发一个实时的用户行为分析看板，包括DAU、留存率等指标。\n\n## 数据源\n- 用户行为日志\n- 订单数据\n\n## 时间要求\n1个月内上线",
    "model": "gpt-4o-mini"
  }'
```

响应：
```json
{
  "task_id": "task_abc123def456",
  "status": "pending",
  "message": "任务已创建，正在排队处理",
  "created_at": "2025-12-10T10:00:00"
}
```

#### 2. 查询分析结果

```bash
curl -X GET "http://localhost:8001/api/v1/analyze/task_abc123def456"
```

响应：
```json
{
  "task_id": "task_abc123def456",
  "status": "completed",
  "result": {
    "analysis_date": "2025-12-10 10:05:00",
    "tech_feasibility": { ... },
    "risk_analysis": { ... },
    "difficulty_assessment": { ... },
    "requirement_decomposition": { ... },
    "workload_estimation": { ... },
    "project_schedule": { ... },
    "final_review": { ... },
    "summary": {
      "approval_status": "通过",
      "total_effort_days": 36,
      "project_duration": "42天",
      "risk_level": "中",
      "key_recommendations": [ ... ]
    }
  },
  "created_at": "2025-12-10T10:00:00",
  "completed_at": "2025-12-10T10:05:00"
}
```

#### 3. 同步执行分析

```bash
curl -X POST "http://localhost:8001/api/v1/analyze/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "requirement_doc": "您的需求文档内容...",
    "model": "gpt-4o-mini"
  }'
```

#### 4. 列出所有任务

```bash
curl -X GET "http://localhost:8001/api/v1/tasks?limit=10"
```

### Python SDK示例

```python
import asyncio
from workflow import RequirementAnalysisWorkflow

# 需求文档
requirement_doc = """
# 数据分析需求：用户行为分析看板

## 需求背景
运营团队需要实时了解用户在APP上的行为数据。

## 核心指标
1. DAU（日活跃用户数）
2. 用户留存率（次日、7日、30日）
3. 用户行为路径分析

## 数据源
- 用户行为日志
- 用户基础信息表

## 时间要求
1个月内上线
"""

# 创建工作流
workflow = RequirementAnalysisWorkflow(
    api_key="your_api_key",
    base_url="https://api.openai.com/v1",
    model="gpt-4o-mini"
)

# 执行分析
result = asyncio.run(workflow.analyze_requirement(requirement_doc))

# 输出结果
print(result)
```

## 📊 输出结果结构

完整的分析报告包含以下部分：

```json
{
  "analysis_date": "2025-12-10 10:05:00",
  "tech_feasibility": {
    "feasibility_score": "可行",
    "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Redis", "React"],
    "data_sources": ["用户行为日志表", "订单数据表"],
    "technical_challenges": ["实时数据处理", "高并发查询"],
    "recommendations": ["使用Redis缓存", "数据预聚合"]
  },
  "risk_analysis": {
    "risks": [
      {
        "category": "技术风险",
        "description": "实时计算性能瓶颈",
        "probability": "中",
        "impact": "高",
        "mitigation": "采用流式计算框架"
      }
    ],
    "overall_risk_level": "中"
  },
  "difficulty_assessment": {
    "difficulty_score": 6,
    "difficulty_level": "中等",
    "dimensions": {
      "technical": 7,
      "business": 5,
      "data": 6,
      "integration": 5,
      "interaction": 6
    },
    "key_challenges": ["实时数据处理", "大数据量查询优化"]
  },
  "requirement_decomposition": {
    "tasks": [
      {
        "task_id": "T001",
        "task_name": "数据模型设计",
        "category": "数据层任务",
        "description": "设计用户行为数据模型",
        "dependencies": [],
        "priority": "高",
        "acceptance_criteria": "完成ER图和表结构文档"
      }
    ]
  },
  "workload_estimation": {
    "total_effort": {
      "optimistic": 20,
      "most_likely": 35,
      "pessimistic": 50,
      "expected": 36,
      "unit": "person-days"
    },
    "resource_requirements": {
      "backend_developers": 2,
      "frontend_developers": 1,
      "data_engineers": 1,
      "qa_engineers": 1
    }
  },
  "project_schedule": {
    "project_timeline": {
      "start_date": "2025-12-10",
      "end_date": "2026-01-20",
      "total_duration": "42天",
      "buffer_days": 6
    },
    "milestones": [
      {
        "milestone": "技术方案评审",
        "date": "2025-12-15",
        "deliverables": ["技术方案文档", "架构设计图"]
      }
    ]
  },
  "final_review": {
    "review_result": "通过",
    "completeness_check": {
      "score": "良好",
      "issues": []
    },
    "final_decision": {
      "approve": true,
      "conditions": ["需要数据源确认"],
      "next_steps": ["启动技术方案设计"]
    }
  },
  "summary": {
    "approval_status": "通过",
    "total_effort_days": 36,
    "project_duration": "42天",
    "risk_level": "中",
    "key_recommendations": ["建议采用增量开发", "关注性能优化"]
  }
}
```

## 🔧 技术栈

- **AutoGen 0.7.0** - 多Agent框架
- **FastAPI** - Web框架
- **Pydantic** - 数据验证
- **Uvicorn** - ASGI服务器
- **OpenAI API** - LLM接口

## 📝 项目结构

```
requirement_analysis/
├── agents.py              # Agent定义
├── workflow.py            # 工作流编排
├── api_service.py         # FastAPI服务
├── requirements.txt       # 依赖列表
├── .env.example          # 环境变量示例
├── README.md             # 项目文档
└── example_usage.py      # 使用示例
```

## 🎯 适用场景

- 产品经理进行需求评审前的预分析
- 技术Leader评估项目可行性
- 项目经理制定项目计划
- 研发团队评估工作量
- 需求变更影响分析

## ⚠️ 注意事项

1. **API密钥安全**：请妥善保管OpenAI API密钥，不要提交到版本控制
2. **成本控制**：每次完整分析会调用多次LLM，注意API使用成本
3. **结果参考**：AI生成的分析结果仅供参考，需要结合实际情况判断
4. **数据隐私**：避免在需求文档中包含敏感信息

## 🔄 版本历史

- **v1.1.0** (2025-12-10)
  - 升级到AutoGen 0.7.0
  - 支持最新API和功能
  - 添加虚拟环境管理

- **v1.0.0** (2025-12-10)
  - 初始版本基于AutoGen 0.4.0实现
  - 7个专业Agent
  - FastAPI服务
  - 完整工作流

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📧 联系方式

如有问题或建议，请联系项目维护者。
