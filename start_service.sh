#!/bin/bash

# SQL 优化审核系统 FastAPI 服务启动脚本

echo "🚀 启动 SQL 优化审核系统 FastAPI 服务"
echo "=================================="

# 检查 Python 版本
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ 错误: 未找到 Python 解释器"
    exit 1
fi

echo "📋 使用 Python: $(${PYTHON_CMD} --version)"

# 检查依赖
echo ""
echo "📦 检查依赖..."
if ! $PYTHON_CMD -c "import fastapi" 2>/dev/null; then
    echo "⚠️  FastAPI 未安装，正在安装..."
    $PYTHON_CMD -m pip install fastapi uvicorn pydantic python-multipart
fi

if ! $PYTHON_CMD -c "import crewai" 2>/dev/null; then
    echo "⚠️  CrewAI 未安装，正在安装..."
    $PYTHON_CMD -m pip install crewai crewai-tools
fi

if ! $PYTHON_CMD -c "import autogen_agentchat" 2>/dev/null; then
    echo "⚠️  AutoGen 未安装，正在安装..."
    $PYTHON_CMD -m pip install autogen-agentchat autogen-core autogen-ext
fi

if ! $PYTHON_CMD -c "import openai" 2>/dev/null; then
    echo "⚠️  OpenAI 未安装，正在安装..."
    $PYTHON_CMD -m pip install openai python-dotenv
fi

# 检查环境变量
echo ""
echo "🔧 检查环境变量..."
if [ ! -f ".env" ]; then
    echo "⚠️  .env 文件不存在，创建示例文件..."
    cat > .env << 'EOF'
# OpenAI API 配置
  OPENAI_BASE_URL=https://yunwu.ai/v1
  OPENAI_API_KEY=sk-tEWaHDG6MWf1UENkaanThDQ3Ej4Dai39LS5XC5UXSuTlEu8n
EOF
    echo "✅ 已创建 .env 文件，请编辑并设置正确的 API Key"
fi

# 启动服务
echo ""
echo "🌟 启动 FastAPI 服务..."
echo "服务将在以下地址可用:"
echo "  - API 服务: http://localhost:8003"
echo "  - API 文档: http://localhost:8003/docs"
echo "  - ReDoc 文档: http://localhost:8003/redoc"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=================================="

# 启动 uvicorn
$PYTHON_CMD -m uvicorn fastapi_service:app --host 0.0.0.0 --port 8003 --reload