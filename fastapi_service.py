"""
FastAPI 服务：SQL 优化审核系统 API
基于 A2A 框架的 SQL 优化和审核功能

启动服务:
uvicorn fastapi_service:app --host 0.0.0.0 --port 8000 --reload

API 文档:
http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import asyncio
import json
import logging
from datetime import datetime
import uuid

# 导入现有的 A2A 框架组件
from a2atest1 import SQLOptimizerCrew, SQLReviewerAutoGen, A2AOrchestrator

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="SQL 优化审核系统 API",
    description="基于 A2A 框架的 SQL 优化和审核服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量存储 orchestrator 实例
orchestrator_instance = None

# Pydantic 模型定义
class SQLOptimizationRequest(BaseModel):
    """SQL 优化请求模型"""
    sql_query: str = Field(..., description="要优化的 SQL 查询语句", min_length=10, max_length=10000)
    optimization_level: Optional[str] = Field("standard", description="优化级别", pattern="^(basic|standard|aggressive)$")
    include_review: Optional[bool] = Field(True, description="是否包含审核步骤")

class SQLOptimizationResponse(BaseModel):
    """SQL 优化响应模型"""
    request_id: str
    status: str
    message: str
    timestamp: str
    optimization_result: Optional[Dict[str, Any]] = None
    review_result: Optional[Dict[str, Any]] = None
    final_status: Optional[str] = None
    processing_time: Optional[float] = None

class TaskStatus(BaseModel):
    """任务状态模型"""
    task_id: str
    status: str
    message: str
    progress: Optional[float] = None
    created_at: str
    updated_at: str
    result: Optional[Dict[str, Any]] = None

# 内存存储任务状态（生产环境应使用 Redis）
task_store: Dict[str, TaskStatus] = {}

# 启动时初始化
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global orchestrator_instance
    try:
        logger.info("正在初始化 A2A 编排器...")
        orchestrator_instance = A2AOrchestrator()

        # 创建 Agents
        sql_optimizer = SQLOptimizerCrew()
        sql_reviewer = SQLReviewerAutoGen()

        # 注册到 A2A
        orchestrator_instance.register_agent("crewai_sql_optimizer", sql_optimizer)
        orchestrator_instance.register_agent("autogen_sql_reviewer", sql_reviewer)

        logger.info("✅ A2A 编排器初始化成功")
    except Exception as e:
        logger.error(f"❌ A2A 编排器初始化失败: {e}")
        orchestrator_instance = None

@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "SQL 优化审核系统 API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "optimize_sql": "/api/optimize",
            "task_status": "/api/task/{task_id}",
            "health": "/api/health",
            "docs": "/docs"
        }
    }

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "orchestrator": "initialized" if orchestrator_instance else "not_initialized"
    }

@app.post("/api/optimize", response_model=SQLOptimizationResponse)
async def optimize_sql(request: SQLOptimizationRequest, background_tasks: BackgroundTasks):
    """
    优化 SQL 查询

    - **sql_query**: 要优化的 SQL 语句
    - **optimization_level**: 优化级别 (basic/standard/aggressive)
    - **include_review**: 是否包含审核步骤
    """
    if not orchestrator_instance:
        raise HTTPException(
            status_code=503,
            detail="A2A 编排器未初始化，服务暂时不可用"
        )

    # 生成请求 ID
    request_id = str(uuid.uuid4())
    start_time = datetime.now()

    try:
        logger.info(f"收到 SQL 优化请求: {request_id}")

        # 执行优化（同步方式，也可以改为异步）
        if request.include_review:
            # 完整流程：优化 + 审核
            result = await orchestrator_instance.optimize_and_review_sql(request.sql_query)

            content = result.get("content", {})
            optimization_result = content.get("optimization", {})
            review_result = content.get("review", {})
            final_status = content.get("final_status")

        else:
            # 仅优化，不审核
            optimizer = orchestrator_instance.agents.get("crewai_sql_optimizer")
            if not optimizer:
                raise HTTPException(status_code=503, detail="SQL 优化器不可用")

            optimization_result = optimizer.optimize_sql(request.sql_query)
            review_result = None
            final_status = "OPTIMIZED_ONLY"

        # 计算处理时间
        processing_time = (datetime.now() - start_time).total_seconds()

        response = SQLOptimizationResponse(
            request_id=request_id,
            status="success",
            message="SQL 优化完成",
            timestamp=datetime.now().isoformat(),
            optimization_result=optimization_result,
            review_result=review_result,
            final_status=final_status,
            processing_time=processing_time
        )

        logger.info(f"SQL 优化完成: {request_id}, 耗时: {processing_time:.2f}s")
        return response

    except Exception as e:
        logger.error(f"SQL 优化失败: {request_id}, 错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"SQL 优化失败: {str(e)}"
        )

@app.post("/api/optimize-async")
async def optimize_sql_async(request: SQLOptimizationRequest, background_tasks: BackgroundTasks):
    """
    异步优化 SQL 查询（适用于长时间运行的优化任务）

    返回任务 ID，可以通过 /api/task/{task_id} 查询状态
    """
    if not orchestrator_instance:
        raise HTTPException(
            status_code=503,
            detail="A2A 编排器未初始化，服务暂时不可用"
        )

    # 生成任务 ID
    task_id = str(uuid.uuid4())

    # 创建任务状态
    task_status = TaskStatus(
        task_id=task_id,
        status="pending",
        message="任务已提交，等待处理",
        progress=0.0,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    task_store[task_id] = task_status

    # 添加后台任务
    background_tasks.add_task(process_optimization_task, task_id, request)

    return {
        "task_id": task_id,
        "status": "submitted",
        "message": "优化任务已提交",
        "timestamp": datetime.now().isoformat()
    }

async def process_optimization_task(task_id: str, request: SQLOptimizationRequest):
    """后台处理优化任务"""
    try:
        # 更新状态为处理中
        task_status = task_store[task_id]
        task_status.status = "processing"
        task_status.message = "正在执行 SQL 优化..."
        task_status.progress = 25.0
        task_status.updated_at = datetime.now().isoformat()

        if request.include_review:
            # 完整流程：优化 + 审核
            task_status.progress = 50.0
            task_status.message = "正在执行 SQL 优化..."
            task_status.updated_at = datetime.now().isoformat()

            result = await orchestrator_instance.optimize_and_review_sql(request.sql_query)

            task_status.progress = 75.0
            task_status.message = "正在执行 SQL 审核..."
            task_status.updated_at = datetime.now().isoformat()

            content = result.get("content", {})
            optimization_result = content.get("optimization", {})
            review_result = content.get("review", {})
            final_status = content.get("final_status")

        else:
            # 仅优化
            optimizer = orchestrator_instance.agents.get("crewai_sql_optimizer")
            optimization_result = optimizer.optimize_sql(request.sql_query)
            review_result = None
            final_status = "OPTIMIZED_ONLY"

        # 更新为完成状态
        task_status.status = "completed"
        task_status.message = "任务完成"
        task_status.progress = 100.0
        task_status.updated_at = datetime.now().isoformat()
        task_status.result = {
            "optimization": optimization_result,
            "review": review_result,
            "final_status": final_status
        }

    except Exception as e:
        logger.error(f"后台任务失败: {task_id}, 错误: {str(e)}")
        # 更新为失败状态
        task_status.status = "failed"
        task_status.message = f"任务失败: {str(e)}"
        task_status.updated_at = datetime.now().isoformat()

@app.get("/api/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task_store[task_id]

@app.get("/api/tasks")
async def list_tasks():
    """列出所有任务"""
    return {
        "tasks": list(task_store.values()),
        "total": len(task_store)
    }

@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="任务不存在")

    del task_store[task_id]
    return {"message": "任务已删除"}

@app.post("/api/batch-optimize")
async def batch_optimize_sql(requests: List[SQLOptimizationRequest]):
    """
    批量优化 SQL 查询

    最多支持 10 个 SQL 语句的批量优化
    """
    if len(requests) > 10:
        raise HTTPException(status_code=400, detail="批量请求最多支持 10 个 SQL 语句")

    if not orchestrator_instance:
        raise HTTPException(
            status_code=503,
            detail="A2A 编排器未初始化，服务暂时不可用"
        )

    results = []
    start_time = datetime.now()

    for i, request in enumerate(requests):
        try:
            logger.info(f"处理批量优化 {i+1}/{len(requests)}")

            if request.include_review:
                result = await orchestrator_instance.optimize_and_review_sql(request.sql_query)
                content = result.get("content", {})
                optimization_result = content.get("optimization", {})
                review_result = content.get("review", {})
                final_status = content.get("final_status")
            else:
                optimizer = orchestrator_instance.agents.get("crewai_sql_optimizer")
                optimization_result = optimizer.optimize_sql(request.sql_query)
                review_result = None
                final_status = "OPTIMIZED_ONLY"

            results.append({
                "index": i,
                "status": "success",
                "optimization_result": optimization_result,
                "review_result": review_result,
                "final_status": final_status
            })

        except Exception as e:
            logger.error(f"批量优化第 {i+1} 个失败: {str(e)}")
            results.append({
                "index": i,
                "status": "failed",
                "error": str(e)
            })

    processing_time = (datetime.now() - start_time).total_seconds()

    return {
        "batch_id": str(uuid.uuid4()),
        "total": len(requests),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "processing_time": processing_time,
        "results": results,
        "timestamp": datetime.now().isoformat()
    }

# 错误处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"全局异常: {str(exc)}")
    return HTTPException(
        status_code=500,
        detail=f"服务器内部错误: {str(exc)}"
    )

# 启动命令提示
if __name__ == "__main__":
    import uvicorn

    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║              SQL 优化审核系统 FastAPI 服务                         ║
    ║                                                                  ║
    ║  启动命令:                                                        ║
    ║    uvicorn fastapi_service:app --host 0.0.0.0 --port 8004       ║
    ║                                                                  ║
    ║  API 文档:                                                        ║
    ║    http://localhost:8004/docs                                     ║
    ║                                                                  ║
    ║  主要端点:                                                        ║
    ║    POST /api/optimize          - 同步 SQL 优化                   ║
    ║    POST /api/optimize-async    - 异步 SQL 优化                   ║
    ║    GET  /api/task/{task_id}    - 查询任务状态                     ║
    ║    POST /api/batch-optimize    - 批量 SQL 优化                   ║
    ║    GET  /api/health            - 健康检查                         ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "fastapi_service:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info"
    )