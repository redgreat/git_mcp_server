# ==========================================
# Git MCP Server - Docker 清理 & 重建脚本
# 用法: .\script\dockerrebuid.ps1
# ==========================================

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
$ProjectRoot = Get-Location

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Git MCP Server - Docker 重建脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ==========================================
# 1. 停止运行中的容器
# ==========================================
Write-Host "[1/6] 停止运行中的容器..." -ForegroundColor Yellow

$containers = @(
    "git_mcp_server"
)

foreach ($name in $containers) {
    $running = docker ps -q -f "name=$name" 2>$null
    if ($running) {
        docker stop $name 2>$null
        Write-Host "  已停止: $name" -ForegroundColor Green
    } else {
        Write-Host "  未运行: $name" -ForegroundColor Gray
    }
}

# ==========================================
# 2. 删除旧容器 & 旧镜像
# ==========================================
Write-Host ""
Write-Host "[2/6] 删除旧容器和镜像..." -ForegroundColor Yellow

# 删除 git_mcp 相关的容器（包括已停止的）
$oldContainers = docker ps -a -q -f "name=git_mcp" 2>$null
if ($oldContainers) {
    docker rm -f $oldContainers 2>$null
    Write-Host "  已删除旧容器" -ForegroundColor Green
} else {
    Write-Host "  无旧容器" -ForegroundColor Gray
}

# 删除 git_mcp 相关的旧镜像
$oldImages = docker images -q "git_mcp_server" 2>$null
if ($oldImages) {
    docker rmi -f $oldImages 2>$null
    Write-Host "  已删除旧镜像: git_mcp_server" -ForegroundColor Green
} else {
    Write-Host "  无旧镜像" -ForegroundColor Gray
}

# 清理悬挂镜像 (dangling images)
$dangling = docker images -q -f "dangling=true" 2>$null
if ($dangling) {
    docker rmi -f $dangling 2>$null
    Write-Host "  已清理悬挂镜像" -ForegroundColor Green
}

# ==========================================
# 3. 清理 Docker Volume (保留 PG 数据)
# ==========================================
Write-Host ""
Write-Host "[3/6] 清理 Docker Volume (跳过 PostgreSQL)..." -ForegroundColor Yellow

# 列出所有 git_mcp 相关的 volume
$volumes = docker volume ls -q -f "name=git_mcp" 2>$null
if ($volumes) {
    foreach ($vol in $volumes) {
        # 跳过 PostgreSQL 数据卷
        if ($vol -match "pgdata") {
            Write-Host "  保留: $vol (PostgreSQL 数据)" -ForegroundColor Green
            continue
        }
        docker volume rm $vol 2>$null
        Write-Host "  已删除: $vol" -ForegroundColor Green
    }
} else {
    Write-Host "  无相关 volume" -ForegroundColor Gray
}

# 清理 builder cache
Write-Host "  清理 build cache..."
docker builder prune -f 2>$null

# ==========================================
# 4. 清理历史日志
# ==========================================
Write-Host ""
Write-Host "[4/6] 清理历史日志..." -ForegroundColor Yellow

$logDir = Join-Path $ProjectRoot "logs"
if (Test-Path $logDir) {
    Remove-Item -Path "$logDir\*.log*" -Force -ErrorAction SilentlyContinue
    Write-Host "  已清理: $logDir" -ForegroundColor Green
} else {
    Write-Host "  日志目录不存在，跳过" -ForegroundColor Gray
}

# 清理本地 frontend 构建缓存
$buildDir = Join-Path $ProjectRoot "frontend\build"
if (Test-Path $buildDir) {
    Remove-Item -Path $buildDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  已清理: frontend/build" -ForegroundColor Green
}
$svelteDir = Join-Path $ProjectRoot "frontend\.svelte-kit"
if (Test-Path $svelteDir) {
    Remove-Item -Path $svelteDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  已清理: frontend/.svelte-kit" -ForegroundColor Green
}

# 清理 src/static 前端缓存
$staticDir = Join-Path $ProjectRoot "src\static"
if (Test-Path $staticDir) {
    Remove-Item -Path $staticDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  已清理: src/static" -ForegroundColor Green
}

# ==========================================
# 5. 检查配置文件
# ==========================================
Write-Host ""
Write-Host "[5/6] 检查配置文件..." -ForegroundColor Yellow

$configFile = Join-Path $ProjectRoot "config\config.yml"
if (-not (Test-Path $configFile)) {
    $exampleFile = Join-Path $ProjectRoot "config\config.yml.example"
    if (Test-Path $exampleFile) {
        Copy-Item $exampleFile $configFile
        Write-Host "  已创建 config.yml (从 example)" -ForegroundColor Green
        Write-Host "  ⚠️ 请编辑 config/config.yml 修改密钥和数据库密码!" -ForegroundColor Red
    } else {
        Write-Host "  ❌ 配置模板不存在!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  配置文件已存在" -ForegroundColor Green
}

# ==========================================
# 6. 重新构建 & 启动
# ==========================================
Write-Host ""
Write-Host "[6/6] Docker 构建 & 启动..." -ForegroundColor Yellow

# 使用 docker compose 构建本地镜像
Write-Host ""
Write-Host "  >>> docker compose build ..." -ForegroundColor Cyan

docker compose -f docker/docker-compose-local.yml build --no-cache 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Docker 构建失败!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  >>> docker compose up ..." -ForegroundColor Cyan

docker compose -f docker/docker-compose-local.yml up -d 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Docker 启动失败!" -ForegroundColor Red
    exit 1
}

# ==========================================
# 等待服务启动 & 健康检查
# ==========================================
Write-Host ""
Write-Host "  等待服务启动..." -ForegroundColor Yellow

$maxAttempts = 30
$attempt = 0
$healthy = $false

while ($attempt -lt $maxAttempts) {
    $attempt++
    Start-Sleep -Seconds 2

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3001/health" -TimeoutSec 3 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {
        # 服务尚未就绪
    }

    if ($attempt % 5 -eq 0) {
        Write-Host "    等待中... ($attempt/$maxAttempts)" -ForegroundColor Gray
    }
}

if ($healthy) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host " ✅ 构建成功！服务已启动" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  管理后台: http://localhost:3001/admin" -ForegroundColor Cyan
    Write-Host "  MCP 端点: http://localhost:3001/mcp/query" -ForegroundColor Cyan
    Write-Host "  默认账号: admin / admin123" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  查看日志: docker compose -f docker/docker-compose-local.yml logs -f" -ForegroundColor Gray
    Write-Host "  停止服务: docker compose -f docker/docker-compose-local.yml down" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "⚠️ 容器已启动但健康检查未通过，请查看日志:" -ForegroundColor Yellow
    Write-Host "  docker compose -f docker/docker-compose-local.yml logs git-mcp-server" -ForegroundColor Gray
}
