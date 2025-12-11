"""
需求分析系统 - FastAPI 服务
基于AutoGen 0.7.0框架的需求分析REST API服务

启动服务:
uvicorn api_service:app --host 0.0.0.0 --port 8001 --reload

API 文档:
http://localhost:8001/docs
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
import os
from dotenv import load_dotenv

from workflow import RequirementAnalysisWorkflow

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="需求分析系统",
    description="基于AutoGen 0.7.0的智能需求分析服务",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局存储（生产环境应使用数据库）
analysis_tasks = {}


# ============================================================================
# 请求/响应模型
# ============================================================================

class RequirementAnalysisRequest(BaseModel):
    """需求分析请求"""
    requirement_doc: str = Field(..., description="需求文档内容")
    api_key: Optional[str] = Field(None, description="OpenAI API密钥（可选）")
    base_url: Optional[str] = Field(None, description="API基础URL（可选）")
    model: Optional[str] = Field("gpt-4o-mini", description="使用的模型")
    
    class Config:
        json_schema_extra = {
            "example": {
                "requirement_doc": "# 需求：用户行为分析看板\n\n需要开发一个实时的用户行为分析看板...",
                "model": "gpt-4o-mini"
            }
        }


class AnalysisTaskResponse(BaseModel):
    """分析任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态: pending/running/completed/failed")
    message: str = Field(..., description="状态消息")
    created_at: str = Field(..., description="创建时间")


class AnalysisResultResponse(BaseModel):
    """分析结果响应"""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


# ============================================================================
# API 路由
# ============================================================================

@app.get("/")
async def root():
    """根路径 - API信息"""
    return {
        "service": "需求分析系统",
        "version": "1.0.0",
        "framework": "AutoGen 0.4.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/v1/analyze", response_model=AnalysisTaskResponse)
async def create_analysis_task(
    request: RequirementAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    创建需求分析任务
    
    该接口异步执行需求分析，立即返回任务ID
    """
    try:
        # 生成任务ID
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        # 初始化任务状态
        analysis_tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "result": None,
            "error": None
        }
        
        # 添加后台任务
        background_tasks.add_task(
            run_analysis_task,
            task_id,
            request.requirement_doc,
            request.api_key,
            request.base_url,
            request.model
        )
        
        logger.info(f"创建分析任务: {task_id}")
        
        return AnalysisTaskResponse(
            task_id=task_id,
            status="pending",
            message="任务已创建，正在排队处理",
            created_at=analysis_tasks[task_id]["created_at"]
        )
        
    except Exception as e:
        logger.error(f"创建分析任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@app.get("/api/v1/analyze/{task_id}", response_model=AnalysisResultResponse)
async def get_analysis_result(task_id: str):
    """
    获取需求分析结果
    
    根据任务ID查询分析结果
    """
    if task_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    
    task = analysis_tasks[task_id]
    
    return AnalysisResultResponse(
        task_id=task_id,
        status=task["status"],
        result=task.get("result"),
        error=task.get("error"),
        created_at=task["created_at"],
        completed_at=task.get("completed_at")
    )


@app.get("/api/v1/tasks", response_model=List[AnalysisTaskResponse])
async def list_analysis_tasks(limit: int = 10):
    """
    列出所有分析任务
    
    返回最近的分析任务列表
    """
    tasks = sorted(
        analysis_tasks.values(),
        key=lambda x: x["created_at"],
        reverse=True
    )[:limit]
    
    return [
        AnalysisTaskResponse(
            task_id=task["task_id"],
            status=task["status"],
            message=_get_status_message(task["status"]),
            created_at=task["created_at"]
        )
        for task in tasks
    ]


@app.delete("/api/v1/analyze/{task_id}")
async def delete_analysis_task(task_id: str):
    """删除分析任务"""
    if task_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    
    del analysis_tasks[task_id]
    logger.info(f"删除任务: {task_id}")
    
    return {"message": f"任务 {task_id} 已删除"}


@app.post("/api/v1/analyze/sync")
async def analyze_sync(request: RequirementAnalysisRequest):
    """
    同步执行需求分析
    
    该接口同步执行分析并返回结果（适用于简单需求）
    """
    try:
        logger.info("开始同步需求分析")
        
        # 创建工作流
        workflow = RequirementAnalysisWorkflow(
            api_key=request.api_key,
            base_url=request.base_url,
            model=request.model
        )
        
        # 执行分析
        result = await workflow.analyze_requirement(request.requirement_doc)
        
        logger.info("同步需求分析完成")
        
        return {
            "status": "completed",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"同步分析失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


# ============================================================================
# 后台任务处理
# ============================================================================

async def run_analysis_task(
    task_id: str,
    requirement_doc: str,
    api_key: Optional[str],
    base_url: Optional[str],
    model: str
):
    """后台运行分析任务"""
    try:
        logger.info(f"开始执行分析任务: {task_id}")
        
        # 更新状态为运行中
        analysis_tasks[task_id]["status"] = "running"
        
        # 创建工作流
        workflow = RequirementAnalysisWorkflow(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        
        # 执行分析
        result = await workflow.analyze_requirement(requirement_doc)
        
        # 更新任务状态
        analysis_tasks[task_id]["status"] = "completed"
        analysis_tasks[task_id]["result"] = result
        analysis_tasks[task_id]["completed_at"] = datetime.now().isoformat()
        
        logger.info(f"分析任务完成: {task_id}")
        
    except Exception as e:
        logger.error(f"分析任务失败: {task_id}, 错误: {str(e)}", exc_info=True)
        
        analysis_tasks[task_id]["status"] = "failed"
        analysis_tasks[task_id]["error"] = str(e)
        analysis_tasks[task_id]["completed_at"] = datetime.now().isoformat()


def _get_status_message(status: str) -> str:
    """获取状态消息"""
    messages = {
        "pending": "任务等待处理",
        "running": "任务正在执行",
        "completed": "任务已完成",
        "failed": "任务执行失败"
    }
    return messages.get(status, "未知状态")


# ============================================================================
# 启动配置
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("SERVICE_HOST", "0.0.0.0")
    port = int(os.getenv("SERVICE_PORT", 8001))
    
    logger.info(f"启动需求分析服务: {host}:{port}")
    
    uvicorn.run(
        "api_service:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
