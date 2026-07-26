param(
    [string]$EnvironmentName = "aipet_build_whisper",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$packagingRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $packagingRoot
$requirementsPath = Join-Path $packagingRoot "requirements-build.txt"
$specPath = Join-Path $packagingRoot "AIpet.spec"
$distPath = Join-Path $projectRoot "dist"
$workPath = Join-Path $projectRoot "build"

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    throw "Conda was not found on PATH."
}

$environmentList = (& conda env list --json | ConvertFrom-Json).envs
if ($LASTEXITCODE -ne 0) {
    throw "Unable to list Conda environments."
}

$environmentExists = @(
    $environmentList | Where-Object {
        (Split-Path $_ -Leaf) -ieq $EnvironmentName
    }
).Count -gt 0

if (-not $environmentExists) {
    Write-Host "Creating Conda environment: $EnvironmentName"
    & conda create -n $EnvironmentName python=3.10 pip -y
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create Conda environment: $EnvironmentName"
    }
}

if (-not $SkipDependencyInstall) {
    Write-Host "Installing build and Whisper dependencies..."
    & conda run -n $EnvironmentName python -m pip install `
        --disable-pip-version-check `
        --no-input `
        -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed."
    }
}

$dependencyCheck = @"
import importlib.util
import sys

required = [
    "PyInstaller",
    "PyQt5",
    "av",
    "ctranslate2",
    "cv2",
    "faster_whisper",
    "numpy",
    "onnxruntime",
    "paramiko",
    "pydantic",
    "pynput",
    "requests",
    "sounddevice",
]
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    print("Missing build dependencies: " + ", ".join(missing))
    sys.exit(1)

forbidden = [
    "accelerate",
    "bitsandbytes",
    "torch",
    "torchaudio",
    "torchvision",
    "transformers",
]
installed = [
    name for name in forbidden if importlib.util.find_spec(name) is not None
]
if installed:
    print("Refusing a polluted build environment: " + ", ".join(installed))
    sys.exit(2)
"@

& conda run -n $EnvironmentName python -c $dependencyCheck
if ($LASTEXITCODE -ne 0) {
    throw "The build environment is incomplete or contains heavyweight extras."
}

Write-Host "Building AIpet.exe..."
Push-Location $projectRoot
try {
    & conda run -n $EnvironmentName python -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $distPath `
        --workpath $workPath `
        $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }
}
finally {
    Pop-Location
}

$artifact = Get-Item (Join-Path $distPath "AIpet.exe")
$hash = Get-FileHash -Algorithm SHA256 $artifact.FullName

Write-Host ""
Write-Host "Build complete:"
Write-Host "  File:   $($artifact.FullName)"
Write-Host "  Size:   $([math]::Round($artifact.Length / 1MB, 1)) MiB"
Write-Host "  SHA256: $($hash.Hash)"
