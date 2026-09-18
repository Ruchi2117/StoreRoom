$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) { $pythonExecutable = 'python' }
$pythonInfo = & $pythonExecutable -c 'import json,sys,platform,importlib.metadata; print(json.dumps(dict(executable=sys.executable,version=sys.version,platform=platform.platform(),packages={d.metadata["Name"]:d.version for d in importlib.metadata.distributions()})))' | ConvertFrom-Json
$gpuInfo = @(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion)
$cudaCommands = @(Get-Command nvidia-smi,nvcc -ErrorAction SilentlyContinue | Select-Object Name,Source)
$environmentReport = [ordered]@{
    checked_at = (Get-Date).ToUniversalTime().ToString('o')
    python = $pythonInfo
    pip = (& $pythonExecutable -m pip --version)
    venv_available = (& $pythonExecutable -c 'import venv; print(True)')
    git = (& git --version)
    gpus = $gpuInfo
    cuda_tools = $cudaCommands
    memory_bytes = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
    disk = (Get-PSDrive C | Select-Object Name,Used,Free)
    training_packages_installed = [bool]($pythonInfo.packages.torch -or $pythonInfo.packages.ultralytics)
}
New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot 'reports') | Out-Null
$environmentReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $projectRoot 'reports/environment.json') -Encoding utf8
$environmentReport | ConvertTo-Json -Depth 8

