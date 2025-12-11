#!/bin/bash

# 需求分析系统启动脚本

echo "=========================================="
echo "需求分析系统 - 启动脚本"
echo "=========================================="

# 检查是否在正确的目录
if [ ! -f "api_service.py" ]; then
    echo "错误: 请在 requirement_analysis 目录下运行此脚本"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "错误: 虚拟环境不存在，请先创建虚拟环境"
    echo "运行: python3 -m venv venv"
    exit 1
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "警告: 未找到 .env 文件"
    echo "正在从 .env.example 复制..."
    cp .env.example .env
    echo "请编辑 .env 文件，配置您的API密钥"
    echo ""
fi

# 检查依赖
echo "检查Python依赖..."
python -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "依赖未安装，正在安装..."
    pip install -r requirements.txt
fi

echo ""
echo "=========================================="
echo "选择启动模式:"
echo "1. 启动API服务 (默认)"
echo "2. 运行命令行演示"
echo "3. 运行使用示例"
echo "=========================================="
read -p "请选择 (1/2/3) [1]: " choice
choice=${choice:-1}

case $choice in
    1)
        echo ""
        echo "启动API服务..."
        echo "API文档: http://localhost:8001/docs"
        echo ""
        python api_service.py
        ;;
    2)
        echo ""
        echo "运行命令行演示..."
        python workflow.py
        ;;
    3)
        echo ""
        echo "运行使用示例..."
        python example_usage.py
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac
