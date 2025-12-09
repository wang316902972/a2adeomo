"""
FastAPI 服务：SQL 优化审核系统 API (单 Agent + SSH 架构)
基于单 Agent 架构和 SSH 认证的 SQL 优化和审核功能

启动服务:
uvicorn fastapi_service:app --host 0.0.0.0 --port 8000 --reload

API 文档:
http://localhost:8000/docs

架构特点:
- 单一综合 SQL 专家 Agent
- SSH 方式访问 GitHub，更安全的认证
- 简化的工作流程，高效执行
- 集成分析、优化、报告于一体

环境变量配置:
GITHUB_SSH_KEY_PATH      - SSH 私钥文件路径
GITHUB_SSH_KEY_CONTENT   - SSH 私钥内容 (可选)
GITHUB_USER              - Git 用户名
GITHUB_EMAIL             - Git 邮箱地址
GITHUB_WEBHOOK_SECRET    - Webhook 密钥
OPENAI_API_KEY           - LLM API 密钥
OPENAI_BASE_URL          - LLM 基础 URL
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import asyncio
import json
import logging
from datetime import datetime
import uuid
import hmac
import hashlib
import httpx
import os
import re
import subprocess
import tempfile
import shutil
from pathlib import Path

# 导入单 Agent SQL 优化组件
from optimize_sql import SQLOptimizerSingle

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="SQL 优化审核系统 API",
    description="基于单 Agent 架构的 SQL 优化和审核服务",
    version="2.0.0",
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

# 全局变量存储 SQL 优化器实例
sql_optimizer_instance = None

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

class GitHubWebhookRequest(BaseModel):
    """GitHub Webhook 请求模型"""
    ref: Optional[str] = None
    repository: Optional[Dict[str, Any]] = None
    commits: Optional[List[Dict[str, Any]]] = None
    pusher: Optional[Dict[str, Any]] = None
    head_commit: Optional[Dict[str, Any]] = None
    sender: Optional[Dict[str, Any]] = None

class SQLReviewResult(BaseModel):
    """SQL 审核结果模型"""
    file_path: str
    status: str
    issues: List[str]
    optimizations: Optional[List[str]] = None
    optimized_sql: Optional[str] = None
    severity: str  # 'low', 'medium', 'high', 'critical'

class WebhookResponse(BaseModel):
    """Webhook 响应模型"""
    webhook_id: str
    status: str
    message: str
    timestamp: str
    repository: Optional[str] = None
    commit: Optional[str] = None
    sql_files_found: int
    reviews: Optional[List[SQLReviewResult]] = None

# 内存存储任务状态（生产环境应使用 Redis）
task_store: Dict[str, TaskStatus] = {}

# GitHub webhook 配置（从环境变量读取）
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
# SSH 配置
GITHUB_SSH_KEY_PATH = os.getenv("GITHUB_SSH_KEY_PATH", "")  # SSH 私钥文件路径
GITHUB_SSH_KEY_CONTENT = os.getenv("GITHUB_SSH_KEY_CONTENT", "")  # SSH 私钥内容（可选，优先使用文件路径）
GITHUB_KNOWN_HOSTS_PATH = os.getenv("GITHUB_KNOWN_HOSTS_PATH", "/tmp/known_hosts")  # SSH known_hosts 文件路径
GITHUB_USER = os.getenv("GITHUB_USER", "git")  # Git 用户名
GITHUB_EMAIL = os.getenv("GITHUB_EMAIL", "")  # Git 邮箱（用于 commit 签名）

# 存储 webhook 处理历史
webhook_history: Dict[str, WebhookResponse] = {}

# SSH 配置全局变量
ssh_configured = False

async def setup_ssh_config():
    """设置 SSH 配置"""
    global ssh_configured
    try:
        # 检查 SSH 密钥配置
        ssh_key_path = GITHUB_SSH_KEY_PATH or ""
        ssh_key_content = GITHUB_SSH_KEY_CONTENT or ""

        if not ssh_key_path and not ssh_key_content:
            logger.warning("❌ 未配置 GitHub SSH 密钥，请设置 GITHUB_SSH_KEY_PATH 或 GITHUB_SSH_KEY_CONTENT 环境变量")
            return False

        ssh_configured = True
        logger.info("✅ SSH 配置初始化成功")
        return True

    except Exception as e:
        logger.error(f"❌ SSH 配置初始化失败: {e}")
        ssh_configured = False
        return False

# 启动时初始化
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化单 Agent SQL 优化器和 SSH 配置"""
    global sql_optimizer_instance
    try:
        # 初始化 SSH 配置
        await setup_ssh_config()

        # 初始化单 Agent SQL 优化器
        logger.info("正在初始化单 Agent SQL 优化器...")
        sql_optimizer_instance = SQLOptimizerSingle()
        logger.info("✅ 单 Agent SQL 优化器初始化成功")
    except Exception as e:
        logger.error(f"❌ 单 Agent SQL 优化器初始化失败: {e}")
        sql_optimizer_instance = None

@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "SQL 优化审核系统 API (单 Agent 架构)",
        "version": "2.0.0",
        "status": "running",
        "architecture": "single_agent",
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
        "sql_optimizer": "initialized" if sql_optimizer_instance else "not_initialized",
        "architecture": "single_agent",
        "ssh_configured": ssh_configured,
        "github_auth_method": get_github_auth_method()
    }

def get_github_auth_method() -> str:
    """获取 GitHub 认证方法"""
    if os.getenv("GITHUB_TOKEN"):
        return "token"
    elif ssh_configured:
        return "ssh"
    else:
        return "not_configured"

@app.post("/api/optimize", response_model=SQLOptimizationResponse)
async def optimize_sql_endpoint(request: SQLOptimizationRequest, background_tasks: BackgroundTasks):
    """
    优化 SQL 查询 (单 Agent 架构)

    - **sql_query**: 要优化的 SQL 语句
    - **optimization_level**: 优化级别 (basic/standard/aggressive) - 当前版本忽略，使用统一优化策略
    - **include_review**: 是否包含审核步骤 - 当前版本单 Agent 已包含综合分析
    """
    if not sql_optimizer_instance:
        raise HTTPException(
            status_code=503,
            detail="SQL 优化器未初始化，服务暂时不可用"
        )

    # 生成请求 ID
    request_id = str(uuid.uuid4())
    start_time = datetime.now()

    try:
        logger.info(f"收到 SQL 优化请求: {request_id}")

        # 单 Agent 执行完整优化分析
        optimization_result = sql_optimizer_instance.optimize_sql(request.sql_query)

        # 单 Agent 已经包含完整的分析和优化，无需额外的审核步骤
        review_result = None
        final_status = "OPTIMIZED_BY_SINGLE_AGENT"

        # 计算处理时间
        processing_time = (datetime.now() - start_time).total_seconds()

        response = SQLOptimizationResponse(
            request_id=request_id,
            status="success",
            message="SQL 优化完成 (单 Agent 综合分析)",
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
    异步优化 SQL 查询（适用于长时间运行的优化任务）- 单 Agent 架构

    返回任务 ID，可以通过 /api/task/{task_id} 查询状态
    """
    if not sql_optimizer_instance:
        raise HTTPException(
            status_code=503,
            detail="SQL 优化器未初始化，服务暂时不可用"
        )

    # 生成任务 ID
    task_id = str(uuid.uuid4())

    # 创建任务状态
    task_status = TaskStatus(
        task_id=task_id,
        status="pending",
        message="任务已提交，等待单 Agent 处理",
        progress=0.0,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    task_store[task_id] = task_status

    # 添加后台任务
    background_tasks.add_task(process_optimization_task_single_agent, task_id, request)

    return {
        "task_id": task_id,
        "status": "submitted",
        "message": "优化任务已提交 (单 Agent 处理)",
        "timestamp": datetime.now().isoformat()
    }

async def process_optimization_task_single_agent(task_id: str, request: SQLOptimizationRequest):
    """后台处理优化任务 - 单 Agent 架构"""
    try:
        # 更新状态为处理中
        task_status = task_store[task_id]
        task_status.status = "processing"
        task_status.message = "单 Agent 正在执行 SQL 优化分析..."
        task_status.progress = 50.0
        task_status.updated_at = datetime.now().isoformat()

        # 单 Agent 执行完整优化分析
        optimization_result = sql_optimizer_instance.optimize_sql(request.sql_query)

        # 更新为完成状态
        task_status.status = "completed"
        task_status.message = "单 Agent 优化分析完成"
        task_status.progress = 100.0
        task_status.updated_at = datetime.now().isoformat()
        task_status.result = {
            "optimization": optimization_result,
            "review": None,  # 单 Agent 已包含综合分析，无需单独审核
            "final_status": "OPTIMIZED_BY_SINGLE_AGENT"
        }

    except Exception as e:
        logger.error(f"单 Agent 后台任务失败: {task_id}, 错误: {str(e)}")
        # 更新为失败状态
        task_status = task_store[task_id]
        task_status.status = "failed"
        task_status.message = f"单 Agent 任务失败: {str(e)}"
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

# ============================================================================
# GitLab Webhook 相关功能
# ============================================================================

def verify_gitlab_signature(payload_body: bytes, signature_header: str, token_header: str = None) -> bool:
    """验证 GitLab webhook 签名"""
    if not GITHUB_WEBHOOK_SECRET:  # 重用相同的环境变量，但用于 GitLab
        logger.warning("⚠️ 未设置 GITHUB_WEBHOOK_SECRET，跳过签名验证 (仅用于测试环境)")
        logger.info("💡 生产环境请设置 GITHUB_WEBHOOK_SECRET 环境变量以确保安全性")
        return True

    try:
        # GitLab 支持多种验证方式
        # 1. Token 验证 (推荐)
        if token_header:
            expected_token = GITHUB_WEBHOOK_SECRET
            if token_header == expected_token:
                logger.info("✅ GitLab Token 验证成功")
                return True
            else:
                logger.error("❌ GitLab Token 验证失败")
                logger.error(f"Expected: {expected_token}")
                logger.error(f"Received: {token_header}")
                return False

        # 2. X-Gitlab-Token header 验证
        gitlab_token_header = None  # 需要从请求头中获取

        # 3. Signature 验证 (如果使用 secret)
        if signature_header:
            # GitLab 的签名格式可能是: sha256=xxxxx
            if signature_header.startswith('sha256='):
                hash_algorithm, gitlab_signature = signature_header.split('=', 1)

                if hash_algorithm == 'sha256':
                    # 计算预期的签名
                    mac = hmac.new(
                        GITHUB_WEBHOOK_SECRET.encode('utf-8'),
                        msg=payload_body,
                        digestmod=hashlib.sha256
                    )
                    expected_signature = mac.hexdigest()

                    # 使用恒定时间比较防止时序攻击
                    is_valid = hmac.compare_digest(expected_signature, gitlab_signature)

                    if not is_valid:
                        logger.error("❌ GitLab Webhook 签名验证失败")
                        logger.error(f"Expected: sha256={expected_signature}")
                        logger.error(f"Received: {signature_header}")
                    else:
                        logger.info("✅ GitLab Webhook 签名验证成功")

                    return is_valid
                else:
                    logger.error(f"❌ 不支持的哈希算法: {hash_algorithm}")
                    return False
            else:
                logger.error("❌ GitLab 签名格式错误，应以 'sha256=' 开头")
                return False

        # 如果没有提供任何验证信息
        logger.warning("⚠️ 未提供 GitLab webhook 验证信息")
        return True  # 测试环境下允许通过

    except Exception as e:
        logger.error(f"❌ GitLab 签名验证过程中发生错误: {e}")
        return False

def extract_sql_files(commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从提交中提取 SQL 文件 (支持 GitLab webhook 格式)"""
    sql_files = []

    logger.info(f"开始处理 {len(commits)} 个提交")

    for commit in commits:
        # 检查 commit 是否为字典类型
        if not isinstance(commit, dict):
            logger.error(f"Commit 不是字典类型: {type(commit)}")
            continue

        commit_id = commit.get('id', '')
        commit_message = commit.get('message', '')

        logger.info(f"处理 commit: {commit_id[:8]} - {commit_message[:50]}")

        # GitLab webhook 中文件变更信息
        # GitLab 使用 'added', 'modified', 'removed' 字段
        added = commit.get('added', [])
        modified = commit.get('modified', [])
        removed = commit.get('removed', [])

        logger.info(f"文件变更统计 - 新增: {len(added)}, 修改: {len(modified)}, 删除: {len(removed)}")

        # 合并所有变更的文件
        all_changed_files = []

        # 处理添加的文件
        for file_info in added:
            if isinstance(file_info, dict):
                # GitLab 可能返回文件对象而不是字符串
                file_path = file_info.get('path', '')
                all_changed_files.append({'path': file_path, 'action': 'added'})
            else:
                all_changed_files.append({'path': file_info, 'action': 'added'})

        # 处理修改的文件
        for file_info in modified:
            if isinstance(file_info, dict):
                file_path = file_info.get('path', '')
                all_changed_files.append({'path': file_path, 'action': 'modified'})
            else:
                all_changed_files.append({'path': file_info, 'action': 'modified'})

        # 提取 SQL 文件
        for file_info in all_changed_files:
            file_path = file_info.get('path', file_info if isinstance(file_info, str) else '')

            if file_path.lower().endswith('.sql'):
                sql_files.append({
                    'file_path': file_path,
                    'commit_id': commit_id,
                    'commit_message': commit_message,
                    'action': file_info.get('action', 'modified')
                })
                logger.info(f"发现 SQL 文件: {file_path}")

    logger.info(f"总共发现 {len(sql_files)} 个 SQL 文件")
    return sql_files

async def fetch_file_content(repo_full_name: str, file_path: str, commit_sha: str) -> Optional[str]:
    """通过 SSH 从 GitLab 获取文件内容"""
    if not ssh_configured:
        logger.warning("SSH 配置未完成，无法获取文件内容")
        return None

    # 创建临时目录
    try:
        # 设置 SSH 环境
        env = os.environ.copy()
        ssh_command_parts = []

        # 优先使用环境变量中的密钥内容
        ssh_key_content = GITHUB_SSH_KEY_CONTENT
            # 使用默认的 SSH 配置 (~/.ssh/id_rsa)
        default_key = Path.home() / ".ssh" / "id_rsa"
        if default_key.exists():
            ssh_command_parts.append(f"-i {default_key}")
            logger.info(f"使用默认 SSH 密钥: {default_key}")
        else:
            logger.warning("未找到 SSH 密钥，使用默认 SSH 配置")
                

        # 添加 SSH 配置选项
        ssh_command_parts.extend([
            "-o StrictHostKeyChecking=no",
            "-o UserKnownHostsFile=/dev/null",
            "-o LogLevel=ERROR"
        ])

        # 构建 SSH 命令
        if ssh_command_parts:
            ssh_command = f"ssh {' '.join(ssh_command_parts)}"
            env['GIT_SSH_COMMAND'] = ssh_command
            logger.info(f"SSH 命令: {ssh_command}")

        # 设置 Git 用户信息
        env['GIT_AUTHOR_NAME'] = GITHUB_USER
        env['GIT_AUTHOR_EMAIL'] = GITHUB_EMAIL or "sql-optimizer@example.com"
        env['GIT_COMMITTER_NAME'] = GITHUB_USER
        env['GIT_COMMITTER_EMAIL'] = GITHUB_EMAIL or "sql-optimizer@example.com"

        repo_url = f"ssh://git@git.nd.com.cn:10022/data-tech/monitor/{repo_full_name}.git"
      
        logger.info(f"尝试克隆仓库: {repo_url}")
        logger.info(f"仓库完整名称: {repo_full_name}")

        # 使用临时目录，避免路径冲突
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp(prefix="git_clone_")
        clone_path = Path(temp_dir) / "repo"
        logger.info(f"使用临时目录: {clone_path}")

        try:
            # 克隆特定 commit
            clone_cmd = [
                'git', 'clone', '--depth', '1',
                '--no-checkout', repo_url, str(clone_path)
            ]

            logger.info(f"执行克隆命令: {' '.join(clone_cmd)}")
            result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=60
            )

            if result.returncode != 0:
                logger.error(f"Git 克隆失败: {result.stderr}")
                logger.error(f"克隆命令输出: {result.stdout}")
                # 清理临时目录
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

            logger.info("仓库克隆成功")

            # 切换到指定 commit 并检出文件
            original_cwd = os.getcwd()
            try:
                os.chdir(clone_path)

                # 检出特定 commit
                checkout_cmd = ['git', 'checkout', commit_sha, '--', file_path]
                logger.info(f"执行检出命令: {' '.join(checkout_cmd)}")

                result = subprocess.run(
                    checkout_cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30
                )

                if result.returncode != 0:
                    logger.error(f"Git 检出失败: {file_path}, 错误: {result.stderr}")
                    return None

                logger.info("文件检出成功")

                # 读取文件内容
                file_full_path = clone_path / file_path
                if file_full_path.exists():
                    content = file_full_path.read_text(encoding='utf-8', errors='ignore')
                    logger.info(f"成功读取文件内容，长度: {len(content)} 字符")
                    return content
                else:
                    logger.error(f"文件不存在: {file_path}")
                    return None

            finally:
                # 恢复原始工作目录
                os.chdir(original_cwd)
                
        except subprocess.TimeoutExpired:
            logger.error(f"Git 操作超时: {file_path}")
            return None
        except Exception as e:
            logger.error(f"通过 SSH 获取文件内容失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return None
        finally:
            # 清理临时目录
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"已清理临时目录: {temp_dir}")
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")

    except Exception as e:
        logger.error(f"创建临时目录或克隆仓库失败: {e}")
        return None

async def post_github_comment(repo_full_name: str, commit_sha: str, comment: str) -> bool:
    """在 Git commit 上发布评论 (支持 SSH 方式，适用于 git.nd.com.cn)"""

    # 注意：由于使用 git.nd.com.cn 而非 GitHub.com，GitHub API 不可用
    # 直接使用 SSH 方式创建带评论的 tag
    logger.info("使用 SSH 方式创建评论 tag (适用于 git.nd.com.cn)")

    # 使用 SSH 方式创建带评论的 tag
    if not ssh_configured:
        logger.warning("SSH 配置未完成且无 Token，无法发布评论")
        return False

    try:
        # 设置 SSH 环境
        env = os.environ.copy()

        # 设置 SSH 密钥
        ssh_key_path = GITHUB_SSH_KEY_PATH
        if ssh_key_path and Path(ssh_key_path).exists():
            env['GIT_SSH_COMMAND'] = f'ssh -i {ssh_key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile={GITHUB_KNOWN_HOSTS_PATH}'
      
        # 设置 Git 用户信息
        env['GIT_AUTHOR_NAME'] = GITHUB_USER
        env['GIT_AUTHOR_EMAIL'] = GITHUB_EMAIL or "sql-optimizer@example.com"
        env['GIT_COMMITTER_NAME'] = GITHUB_USER
        env['GIT_COMMITTER_EMAIL'] = GITHUB_EMAIL or "sql-optimizer@example.com"

        repo_url = f"ssh://git@git.nd.com.cn:10022/data-tech/monitor/{repo_full_name}.git"
        clone_path = "/data/optimize_sql/repo"

        # 克隆仓库
        clone_cmd = ['git', 'clone', repo_url, str(clone_path)]
        result = subprocess.run(
            clone_cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=60
        )

        if result.returncode != 0:
            logger.error(f"Git 克隆失败: {result.stderr}")
            return False

        os.chdir(clone_path)

        # 创建带评论的 tag 作为备选方案
        tag_name = f"sql-review-{commit_sha[:8]}"
        tag_message = f"SQL 优化审核报告\n\n{comment[:500]}"  # 限制长度

        # 创建 annotated tag
        tag_cmd = ['git', 'tag', '-a', tag_name, commit_sha, '-m', tag_message]
        result = subprocess.run(
            tag_cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"Git tag 创建失败: {result.stderr}")
            return False

        # 推送 tag
        push_cmd = ['git', 'push', 'origin', tag_name]
        result = subprocess.run(
            push_cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        if result.returncode == 0:
            logger.info(f"✅ 通过 SSH 创建评论 tag: {tag_name}")
            return True
        else:
            logger.error(f"Git push 失败: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Git 操作超时")
        return False
    except Exception as e:
        logger.error(f"SSH 方式发布评论失败: {e}")
        return False

def format_review_comment(reviews: List[SQLReviewResult]) -> str:
    """格式化审核结果为 Markdown 评论"""
    comment_parts = ["## 🔍 SQL 代码审核报告\n"]
    
    # 统计
    total_files = len(reviews)
    critical_count = sum(1 for r in reviews if r.severity == 'critical')
    high_count = sum(1 for r in reviews if r.severity == 'high')
    medium_count = sum(1 for r in reviews if r.severity == 'medium')
    
    comment_parts.append(f"**总计**: {total_files} 个 SQL 文件\n")
    
    if critical_count > 0:
        comment_parts.append(f"🚨 **严重问题**: {critical_count}\n")
    if high_count > 0:
        comment_parts.append(f"⚠️ **高优先级**: {high_count}\n")
    if medium_count > 0:
        comment_parts.append(f"💡 **中等优先级**: {medium_count}\n")
    
    comment_parts.append("\n---\n\n")
    
    # 每个文件的详细信息
    for review in reviews:
        severity_emoji = {
            'critical': '🚨',
            'high': '⚠️',
            'medium': '💡',
            'low': '✅'
        }.get(review.severity, '📝')
        
        comment_parts.append(f"### {severity_emoji} {review.file_path}\n\n")
        comment_parts.append(f"**状态**: {review.status}\n\n")
        
        if review.issues:
            comment_parts.append("**发现的问题**:\n")
            for i, issue in enumerate(review.issues[:5], 1):  # 限制显示前5个
                comment_parts.append(f"{i}. {issue}\n")
            comment_parts.append("\n")
        
        if review.optimizations:
            comment_parts.append("**优化建议**:\n")
            for i, opt in enumerate(review.optimizations[:3], 1):  # 限制显示前3个
                comment_parts.append(f"{i}. {opt}\n")
            comment_parts.append("\n")
        
        if review.optimized_sql:
            comment_parts.append("<details>\n")
            comment_parts.append("<summary>查看优化后的 SQL</summary>\n\n")
            comment_parts.append("```sql\n")
            comment_parts.append(review.optimized_sql[:500])  # 限制长度
            if len(review.optimized_sql) > 500:
                comment_parts.append("\n... (已截断)")
            comment_parts.append("\n```\n")
            comment_parts.append("</details>\n\n")
        
        comment_parts.append("---\n\n")
    
    comment_parts.append("\n🤖 *此报告由 SQL 优化审核系统自动生成*")
    
    return "".join(comment_parts)

@app.post("/api/webhook/gitlab", response_model=WebhookResponse)
async def gitlab_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    GitLab Webhook 接口

    配置说明:
    1. 在 GitLab 项目设置中添加 Webhook
    2. URL: http://your-server:8004/api/webhook/gitlab
    3. Secret Token: 设置一个密钥（与 GITHUB_WEBHOOK_SECRET 环境变量一致）
    4. 触发事件: Push events

    环境变量:
    - GITHUB_WEBHOOK_SECRET: webhook 密钥（用于验证请求）
    """
    webhook_id = str(uuid.uuid4())

    try:
        # 读取请求体
        payload_body = await request.body()

        # 手动获取 GitLab headers
        headers = dict(request.headers)
        x_gitlab_token = headers.get("x-gitlab-token") or headers.get("X-Gitlab-Token")
        x_gitlab_event = headers.get("x-gitlab-event") or headers.get("X-Gitlab-Event")
        x_gitlab_signature = headers.get("x-gitlab-signature") or headers.get("X-Gitlab-Signature")

        logger.info(f"收到 GitLab webhook 请求，事件: {x_gitlab_event}")
        logger.info(f"Token: {x_gitlab_token is not None}, Signature: {x_gitlab_signature is not None}")

        # 验证签名或token
        if not verify_gitlab_signature(payload_body, x_gitlab_signature, x_gitlab_token):
            logger.warning("GitLab webhook 验证失败")
            raise HTTPException(status_code=401, detail="Webhook 验证失败")

        # 只处理 push 事件
        if x_gitlab_event != "Push Hook":
            logger.info(f"忽略非 push 事件: {x_gitlab_event}")
            return WebhookResponse(
                webhook_id=webhook_id,
                status="ignored",
                message=f"仅处理 Push Hook 事件，当前事件: {x_gitlab_event}",
                timestamp=datetime.now().isoformat(),
                sql_files_found=0
            )
        
        # 解析 payload
        try:
            payload = json.loads(payload_body)
            logger.info(f"Payload type: {type(payload)}")
            logger.info(f"Payload keys: {payload.keys() if isinstance(payload, dict) else 'Not a dict'}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.error(f"Payload body: {payload_body[:500]}...")  # 显示前500个字符
            raise

        # 提取 GitLab 特有信息
        if not isinstance(payload, dict):
            logger.error(f"Payload 不是字典类型: {type(payload)}")
            raise HTTPException(status_code=400, detail="无效的 webhook payload 格式")

        project = payload.get('project', {})
        if not isinstance(project, dict):
            logger.error(f"Project 字段不是字典类型: {type(project)}")
            project = {}

        repo_name = project.get('name', '')  # GitLab 项目名称
        namespace = project.get('namespace', {})
        if isinstance(namespace, dict):
            namespace_name = namespace.get('name', '')
            repo_full_name = f"{namespace_name}/{repo_name}" if namespace_name else repo_name
        else:
            repo_full_name = repo_name

        # GitLab 的 commits 结构与 GitHub 略有不同
        commits = payload.get('commits', [])
        if not isinstance(commits, list):
            logger.error(f"Commits 字段不是列表类型: {type(commits)}")
            commits = []

        if not commits:
            logger.info("没有提交信息")
            return WebhookResponse(
                webhook_id=webhook_id,
                status="no_commits",
                message="没有找到提交信息",
                timestamp=datetime.now().isoformat(),
                repository=repo_full_name,
                sql_files_found=0
            )
        
        # 提取 SQL 文件
        sql_files = extract_sql_files(commits)

        if not sql_files:
            logger.info("没有发现 SQL 文件变更")
            return WebhookResponse(
                webhook_id=webhook_id,
                status="no_sql_files",
                message="没有发现 SQL 文件变更",
                timestamp=datetime.now().isoformat(),
                repository=repo_full_name,
                commit=commits[0].get('id', '') if commits else '',
                sql_files_found=0
            )

        logger.info(f"发现 {len(sql_files)} 个 SQL 文件需要审核")

        # 提交后台任务进行审核
        background_tasks.add_task(
            process_sql_reviews_single_agent,
            webhook_id,
            repo_full_name,
            sql_files,
            commits[0].get('id', '') if commits else ''
        )

        response = WebhookResponse(
            webhook_id=webhook_id,
            status="processing",
            message=f"发现 {len(sql_files)} 个 SQL 文件，正在进行审核",
            timestamp=datetime.now().isoformat(),
            repository=repo_full_name,
            commit=commits[0].get('id', '') if commits else '',
            sql_files_found=len(sql_files)
        )

        # 保存到历史记录
        webhook_history[webhook_id] = response

        return response

    except json.JSONDecodeError:
        logger.error("无法解析 JSON payload")
        raise HTTPException(status_code=400, detail="无效的 JSON payload")
    except Exception as e:
        logger.error(f"处理 GitLab webhook 失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理 webhook 失败: {str(e)}")

# 保留 GitHub webhook 端点作为备用，但重定向到 GitLab 处理
@app.post("/api/webhook/github", response_model=WebhookResponse)
async def github_webhook_fallback(request: Request, background_tasks: BackgroundTasks):
    """GitHub Webhook 备用端点，重定向到 GitLab 处理"""
    logger.info("收到 GitHub webhook 请求，使用 GitLab 处理逻辑")
    return await gitlab_webhook(request, background_tasks)

async def process_sql_reviews_single_agent(webhook_id: str, repo_full_name: str, sql_files: List[Dict[str, Any]], commit_sha: str):
    """后台处理 SQL 文件审核 - 单 Agent 架构"""
    try:
        reviews = []

        for sql_file in sql_files:
            file_path = sql_file['file_path']
            logger.info(f"单 Agent 审核文件: {file_path}")

            # 获取文件内容
            sql_content = await fetch_file_content(repo_full_name, file_path, commit_sha)

            if not sql_content:
                reviews.append(SQLReviewResult(
                    file_path=file_path,
                    status="error",
                    issues=["无法获取文件内容"],
                    severity="medium"
                ))
                continue

            # 调用单 Agent SQL 优化服务
            try:
                if sql_optimizer_instance:
                    optimization_result = sql_optimizer_instance.optimize_sql(sql_content)

                    # 提取问题和优化建议
                    issues = optimization_result.get("issues_found", [])
                    optimizations = optimization_result.get("optimizations_applied", [])
                    optimized_sql = optimization_result.get("optimized_sql", "")

                    # 确定严重程度
                    severity = "low"
                    if any(keyword in str(issues).lower() for keyword in ['critical', '严重', 'error']):
                        severity = "critical"
                    elif any(keyword in str(issues).lower() for keyword in ['warning', '警告', 'high']):
                        severity = "high"
                    elif len(issues) > 3:
                        severity = "medium"

                    reviews.append(SQLReviewResult(
                        file_path=file_path,
                        status="reviewed",
                        issues=issues if isinstance(issues, list) else [str(issues)],
                        optimizations=optimizations if isinstance(optimizations, list) else [str(optimizations)],
                        optimized_sql=optimized_sql,
                        severity=severity
                    ))
                else:
                    reviews.append(SQLReviewResult(
                        file_path=file_path,
                        status="error",
                        issues=["单 Agent 优化服务未初始化"],
                        severity="medium"
                    ))

            except Exception as e:
                logger.error(f"单 Agent 审核文件 {file_path} 失败: {e}")
                reviews.append(SQLReviewResult(
                    file_path=file_path,
                    status="error",
                    issues=[f"单 Agent 审核失败: {str(e)}"],
                    severity="high"
                ))

        # 更新 webhook 历史记录
        if webhook_id in webhook_history:
            webhook_history[webhook_id].status = "completed"
            webhook_history[webhook_id].reviews = reviews
            webhook_history[webhook_id].message = f"单 Agent 已完成 {len(reviews)} 个文件的审核"

        # 在 GitHub 上发布评论
        comment = format_review_comment(reviews)
        await post_github_comment(repo_full_name, commit_sha, comment)

        logger.info(f"单 Agent Webhook {webhook_id} 处理完成")

    except Exception as e:
        logger.error(f"单 Agent 处理 SQL 审核失败: {e}")
        if webhook_id in webhook_history:
            webhook_history[webhook_id].status = "failed"
            webhook_history[webhook_id].message = f"单 Agent 处理失败: {str(e)}"

@app.get("/api/webhook/{webhook_id}", response_model=WebhookResponse)
async def get_webhook_status(webhook_id: str):
    """获取 webhook 处理状态"""
    if webhook_id not in webhook_history:
        raise HTTPException(status_code=404, detail="Webhook 记录不存在")
    
    return webhook_history[webhook_id]

@app.get("/api/webhooks")
async def list_webhooks():
    """列出所有 webhook 处理记录"""
    return {
        "webhooks": list(webhook_history.values()),
        "total": len(webhook_history)
    }

@app.post("/api/batch-optimize")
async def batch_optimize_sql(requests: List[SQLOptimizationRequest]):
    """
    批量优化 SQL 查询 - 单 Agent 架构

    最多支持 10 个 SQL 语句的批量优化
    """
    if len(requests) > 10:
        raise HTTPException(status_code=400, detail="批量请求最多支持 10 个 SQL 语句")

    if not sql_optimizer_instance:
        raise HTTPException(
            status_code=503,
            detail="SQL 优化器未初始化，服务暂时不可用"
        )

    results = []
    start_time = datetime.now()

    for i, request in enumerate(requests):
        try:
            logger.info(f"单 Agent 处理批量优化 {i+1}/{len(requests)}")

            # 单 Agent 执行完整优化分析
            optimization_result = sql_optimizer_instance.optimize_sql(request.sql_query)
            review_result = None  # 单 Agent 已包含综合分析
            final_status = "OPTIMIZED_BY_SINGLE_AGENT"

            results.append({
                "index": i,
                "status": "success",
                "optimization_result": optimization_result,
                "review_result": review_result,
                "final_status": final_status
            })

        except Exception as e:
            logger.error(f"单 Agent 批量优化第 {i+1} 个失败: {str(e)}")
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
    ║      SQL 优化审核系统 FastAPI 服务 (单 Agent + SSH 架构)         ║
    ║                                                                  ║
    ║  架构特点:                                                       ║
    ║    • 单一综合 SQL 专家 Agent                                      ║
    ║    • SSH 方式访问 GitHub (更安全的认证)                           ║
    ║    • 简化的工作流程，高效执行                                     ║
    ║    • 集成分析、优化、报告于一体                                   ║
    ║                                                                  ║
    ║  启动命令:                                                        ║
    ║    uvicorn fastapi_service:app --host 0.0.0.0 --port 8004       ║
    ║                                                                  ║
    ║  API 文档:                                                        ║
    ║    http://localhost:8004/docs                                     ║
    ║                                                                  ║
    ║  主要端点:                                                        ║
    ║    POST /api/optimize          - 同步 SQL 优化 (单 Agent)        ║
    ║    POST /api/optimize-async    - 异步 SQL 优化 (单 Agent)        ║
    ║    GET  /api/task/{task_id}    - 查询任务状态                     ║
    ║    POST /api/batch-optimize    - 批量 SQL 优化 (单 Agent)        ║
    ║    POST /api/webhook/gitlab    - GitLab Webhook (SSH 审核)        ║
    ║    POST /api/webhook/github    - GitHub Webhook 备用端点          ║
    ║    GET  /api/webhook/{id}      - 查询 webhook 状态               ║
    ║    GET  /api/health            - 健康检查 (含 SSH 状态)           ║
    ║                                                                  ║
    ║  环境变量配置:                                                    ║
    ║    GITHUB_SSH_KEY_PATH      - SSH 私钥文件路径                    ║
    ║    GITHUB_SSH_KEY_CONTENT   - SSH 私钥内容 (可选)                 ║
    ║    GITHUB_USER              - Git 用户名                          ║
    ║    GITHUB_EMAIL             - Git 邮箱地址                        ║
    ║    GITHUB_WEBHOOK_SECRET    - GitLab Webhook 密钥 (Token)          ║
    ║    OPENAI_API_KEY           - LLM API 密钥                        ║
    ║    OPENAI_BASE_URL          - LLM 基础 URL                        ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "fastapi_service:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info"
    )