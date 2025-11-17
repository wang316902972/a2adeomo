# SQL 优化审核系统 FastAPI 服务

基于 A2A 框架的 SQL 优化和审核功能的 FastAPI Web 服务。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_fastapi.txt
```

### 2. 启动服务

```bash
# 开发模式
uvicorn fastapi_service:app --host 0.0.0.0 --port 8003 --reload

# 生产模式
uvicorn fastapi_service:app --host 0.0.0.0 --port 8003 --workers 4
```

### 3. 访问 API 文档

- Swagger UI: http://localhost:8003/docs
- ReDoc: http://localhost:8003/redoc

## 📡 API 端点

### 1. 健康检查

```http
GET /api/health
```

返回服务状态和 A2A 编排器初始化状态。

### 2. 同步 SQL 优化

```http
POST /api/optimize
```

**请求体:**
```json
{
    "sql_query": "SELECT * FROM users WHERE status = 'active'",
    "optimization_level": "standard",
    "include_review": true
}
```

**响应:**
```json
{
    "request_id": "uuid",
    "status": "success",
    "message": "SQL 优化完成",
    "timestamp": "2024-01-01T00:00:00",
    "optimization_result": {...},
    "review_result": {...},
    "final_status": "APPROVED",
    "processing_time": 2.5
}
```

### 3. 异步 SQL 优化

```http
POST /api/optimize-async
```

返回任务 ID，可后续查询状态。

**响应:**
```json
{
    "task_id": "uuid",
    "status": "submitted",
    "message": "优化任务已提交",
    "timestamp": "2024-01-01T00:00:00"
}
```

### 4. 查询任务状态

```http
GET /api/task/{task_id}
```

**响应:**
```json
{
    "task_id": "uuid",
    "status": "completed",
    "message": "任务完成",
    "progress": 100.0,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:01:00",
    "result": {...}
}
```

### 5. 批量 SQL 优化

```http
POST /api/batch-optimize
```

**请求体:**
```json
[
    {
        "sql_query": "SELECT * FROM table1",
        "optimization_level": "standard",
        "include_review": true
    },
    {
        "sql_query": "SELECT * FROM table2",
        "optimization_level": "standard",
        "include_review": true
    }
]
```

## 🧪 测试客户端

使用提供的测试客户端来验证服务功能：

```bash
python test_fastapi_client.py
```

测试客户端将执行以下测试：
1. 健康检查
2. 同步 SQL 优化
3. 异步 SQL 优化
4. 批量 SQL 优化

## 🔧 配置

### 环境变量

在 `.env` 文件中设置：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
```

### 优化级别

- `basic`: 基础优化（快速）
- `standard`: 标准优化（平衡）
- `aggressive`: 激进优化（深入分析）

## 📊 响应结构

### 优化结果

```json
{
    "original_sql": "原始 SQL",
    "optimized_sql": "优化后的 SQL",
    "issues_found": ["问题1", "问题2"],
    "optimizations_applied": ["优化1", "优化2"],
    "performance_gain_estimate": "10-30%",
    "recommendations": ["建议1", "建议2"],
    "timestamp": "2024-01-01T00:00:00",
    "agent": "crewai_sql_optimizer"
}
```

### 审核结果

```json
{
    "approved": true,
    "score": 85,
    "syntax_check": {
        "passed": true,
        "issues": []
    },
    "security_check": {
        "passed": true,
        "issues": []
    },
    "performance_check": {
        "passed": true,
        "score": 85
    },
    "best_practices": {
        "score": 85,
        "suggestions": ["建议1", "建议2"]
    },
    "summary": "审核总结",
    "recommendations": ["建议1", "建议2"],
    "timestamp": "2024-01-01T00:00:00",
    "agent": "autogen_sql_reviewer",
    "comparison": {
        "length_change": "100 → 80 字符",
        "complexity": "简化",
        "readability": "提升"
    }
}
```

## 🚨 错误处理

API 使用标准 HTTP 状态码：

- `200`: 成功
- `400`: 请求参数错误
- `404`: 资源不存在
- `500`: 服务器内部错误
- `503`: 服务不可用（A2A 编排器未初始化）

错误响应格式：
```json
{
    "detail": "错误描述"
}
```

## 🔒 安全考虑

1. **输入验证**: 所有 SQL 输入都经过验证
2. **长度限制**: SQL 查询最大 10,000 字符
3. **速率限制**: 可根据需要添加（建议在生产环境中）
4. **CORS 配置**: 在生产环境中应设置具体的允许域名

## 📈 性能优化

1. **异步处理**: 对于长时间运行的优化任务使用异步端点
2. **批处理**: 支持批量优化多个 SQL 语句
3. **缓存**: 可考虑添加 Redis 缓存重复的优化结果
4. **负载均衡**: 生产环境可使用多个 worker 进程

## 🐳 Docker 部署

创建 `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements_fastapi.txt .
RUN pip install --no-cache-dir -r requirements_fastapi.txt

COPY . .

EXPOSE 8003

CMD ["uvicorn", "fastapi_service:app", "--host", "0.0.0.0", "--port", "8003"]
```

构建和运行：

```bash
docker build -t sql-optimizer-api .
docker run -p 8003:8003 --env-file .env sql-optimizer-api
```

## 🔄 监控和日志

- 使用 FastAPI 内置的日志记录
- 可集成 Prometheus 进行指标监控
- 建议在生产环境中使用结构化日志

## 📝 使用示例

### Python 客户端

```python
import requests

# 提交优化任务
response = requests.post("http://localhost:8003/api/optimize", json={
    "sql_query": "SELECT * FROM users WHERE created_at > '2024-01-01'",
    "include_review": True
})

result = response.json()
print(f"优化结果: {result['optimization_result']}")
print(f"审核评分: {result['review_result']['score']}/100")
```

### cURL 客户端

```bash
curl -X POST "http://localhost:8003/api/optimize" \
  -H "Content-Type: application/json" \
  -d '{
    "sql_query": "SELECT * FROM orders WHERE status LIKE \"%pending%\"",
    "include_review": true
  }'
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进这个服务。

## 📄 许可证

本项目采用 MIT 许可证。