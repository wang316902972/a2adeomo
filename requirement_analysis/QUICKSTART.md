# 🚀 快速启动指南

## ✅ 系统已就绪

所有测试已通过，系统已准备好使用！

## 📦 已安装组件

- ✅ Python虚拟环境 (venv)
- ✅ AutoGen 0.7.0 框架
- ✅ FastAPI 服务框架
- ✅ 7个专业分析Agent
- ✅ 完整工作流系统
- ✅ REST API接口

## 🎯 三种使用方式

### 方式1：启动API服务（推荐）

```bash
cd /usr/local/src/a2ademo/requirement_analysis
source venv/bin/activate
python api_service.py
```

然后访问：http://localhost:8001/docs

### 方式2：使用启动脚本

```bash
cd /usr/local/src/a2ademo/requirement_analysis
./start.sh
```

### 方式3：命令行演示

```bash
cd /usr/local/src/a2ademo/requirement_analysis
source venv/bin/activate
python workflow.py
```

## 📝 API调用示例

### 创建分析任务

```bash
curl -X POST "http://localhost:8001/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "requirement_doc": "# 需求：用户行为分析看板\n\n需要开发一个实时的用户行为分析看板...",
    "model": "gpt-4o-mini"
  }'
```

### 查询任务结果

```bash
curl -X GET "http://localhost:8001/api/v1/analyze/{task_id}"
```

## 🔧 7个专业Agent

1. **技术可行性评估Agent** - 评估技术方案和数据源
2. **需求风险识别Agent** - 识别各类风险
3. **需求难度评估Agent** - 评估实现难度（1-10分）
4. **需求拆解Agent** - 拆分为可执行任务
5. **工作量评估Agent** - 估算工作量（人日）
6. **需求排期Agent** - 制定项目时间表
7. **需求复核Agent** - 最终质量审查

## 📊 完整分析流程

```
需求输入 → 技术评估 → 风险识别 → 难度评估 → 
任务拆解 → 工作量评估 → 排期规划 → 需求复核 → 生成报告
```

## 🌟 核心特性

- ✅ 自动化需求分析全流程
- ✅ 多维度评估（技术/风险/难度/工作量）
- ✅ 结构化JSON输出
- ✅ 支持异步任务处理
- ✅ 支持自定义LLM模型

## 📚 详细文档

- `README.md` - 完整使用文档
- `example_usage.py` - 代码示例
- `API文档` - http://localhost:8001/docs

## 🎉 开始使用

```bash
# 1. 进入项目目录
cd /usr/local/src/a2ademo/requirement_analysis

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 启动服务
python api_service.py

# 4. 在浏览器中打开
open http://localhost:8001/docs
```

## 💡 提示

- 所有依赖已安装在虚拟环境中
- .env配置已设置好API密钥
- 测试全部通过，系统运行正常
- 支持同步和异步两种分析模式

---

**项目位置**: `/usr/local/src/a2ademo/requirement_analysis`

**创建时间**: 2025年12月10日

**框架版本**: AutoGen 0.7.0 (最新版本)
