# Memory Tree System 依赖安装脚本（统一走国内镜像源）
# 用法：pwsh -File install-deps.ps1
# 或：.\install-deps.ps1
#
# 镜像源顺序：清华 TUNA 优先，失败则回退阿里云。
# 若需强制指定：.\install-deps.ps1 -IndexUrl https://mirrors.aliyun.com/pypi/simple/

param(
    [string]$IndexUrl = "https://pypi.tuna.tsinghua.edu.cn/simple"
)

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

Write-Host "==> 使用镜像源: $IndexUrl"
python -m pip install --index-url $IndexUrl -r requirements.txt

if ($LASTEXITCODE -ne 0 -and $IndexUrl -like "*tuna*") {
    Write-Host "==> 清华源失败，回退阿里云"
    python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "==> 依赖安装完成，验证："
    python -c "import sqlite3, jieba, pytest; print('sqlite3', sqlite3.sqlite_version, '| jieba', jieba.__version__, '| pytest', pytest.__version__)"
} else {
    Write-Host "==> 安装失败（exit $LASTEXITCODE）。若环境无外网，请在有网环境执行本脚本。"
    exit $LASTEXITCODE
}
