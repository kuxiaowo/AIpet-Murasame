param(
    [string]$EnvironmentName = "aipet_build_whisper",
    [string]$CudaDllDirectory = "",
    [string]$CudnnDllDirectory = "",
    [string]$CudaNvrtcDllDirectory = "",
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
$cublasDllNames = @(
    "cublas64_12.dll",
    "cublasLt64_12.dll"
)
$cudnnDllNames = @(
    "cudnn64_9.dll",
    "cudnn_adv64_9.dll",
    "cudnn_cnn64_9.dll",
    "cudnn_engines_precompiled64_9.dll",
    "cudnn_engines_runtime_compiled64_9.dll",
    "cudnn_graph64_9.dll",
    "cudnn_heuristic64_9.dll",
    "cudnn_ops64_9.dll"
)
$nvrtcDllNames = @("nvrtc64_120_0.dll")

function Resolve-CondaExecutable {
    $command = Get-Command conda.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $legacyCommand = Get-Command conda -ErrorAction SilentlyContinue
    if ($legacyCommand -and $legacyCommand.Source) {
        $legacyDirectory = Split-Path -Parent $legacyCommand.Source
        $candidateRoots = @(
            $legacyDirectory
            Split-Path -Parent $legacyDirectory
            Split-Path -Parent (
                Split-Path -Parent $legacyDirectory
            )
        )
        foreach ($root in $candidateRoots) {
            $candidate = Join-Path $root "Scripts\conda.exe"
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return $candidate
            }
        }
    }

    throw "conda.exe was not found on PATH or beside the Conda installation."
}

$condaExecutable = Resolve-CondaExecutable

function Get-CondaEnvironmentPath {
    param([string]$Name)

    $environmentList = (
        & $condaExecutable env list --json | ConvertFrom-Json
    ).envs
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to list Conda environments."
    }
    return $environmentList | Where-Object {
        (Split-Path $_ -Leaf) -ieq $Name
    } | Select-Object -First 1
}

$buildEnvironmentPath = Get-CondaEnvironmentPath $EnvironmentName
if ($LASTEXITCODE -ne 0) {
    throw "Unable to list Conda environments."
}

if (-not $buildEnvironmentPath) {
    Write-Host "Creating Conda environment: $EnvironmentName"
    & $condaExecutable create -n $EnvironmentName python=3.10 pip -y
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create Conda environment: $EnvironmentName"
    }
    $buildEnvironmentPath = Get-CondaEnvironmentPath $EnvironmentName
    if (-not $buildEnvironmentPath) {
        throw "The newly created Conda environment could not be located."
    }
}

if (-not $SkipDependencyInstall) {
    Write-Host "Installing build and Whisper dependencies..."
    & $condaExecutable run -n $EnvironmentName python -m pip install `
        --disable-pip-version-check `
        --no-input `
        -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed."
    }

    if (
        -not $CudaDllDirectory -or
        -not $CudnnDllDirectory -or
        -not $CudaNvrtcDllDirectory
    ) {
        Write-Host "Installing the CUDA 12 cuBLAS/cuDNN 9 runtime..."
        & $condaExecutable install -n $EnvironmentName -c conda-forge `
            "libcublas>=12,<13" `
            "cudnn>=9,<10" `
            "cuda-nvrtc>=12,<13" `
            -y
        if ($LASTEXITCODE -ne 0) {
            throw "CUDA runtime installation failed."
        }
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

& $condaExecutable run -n $EnvironmentName python -c $dependencyCheck
if ($LASTEXITCODE -ne 0) {
    throw "The build environment is incomplete or contains heavyweight extras."
}

if (-not $CudaDllDirectory) {
    $CudaDllDirectory = Join-Path $buildEnvironmentPath "Library\bin"
}
if (-not $CudnnDllDirectory) {
    $CudnnDllDirectory = Join-Path $buildEnvironmentPath "Library\bin"
}
if (-not $CudaNvrtcDllDirectory) {
    $CudaNvrtcDllDirectory = Join-Path $buildEnvironmentPath "Library\bin"
}
$CudaDllDirectory = [System.IO.Path]::GetFullPath($CudaDllDirectory)
$CudnnDllDirectory = [System.IO.Path]::GetFullPath($CudnnDllDirectory)
$CudaNvrtcDllDirectory = [System.IO.Path]::GetFullPath(
    $CudaNvrtcDllDirectory
)

function Assert-DllSet {
    param(
        [string]$Directory,
        [string[]]$Names,
        [string]$ParameterName
    )

    $missingDlls = @(
        $Names | Where-Object {
            -not (Test-Path -LiteralPath (
                Join-Path $Directory $_
            ) -PathType Leaf)
        }
    )
    if ($missingDlls.Count -gt 0) {
        throw (
            "CUDA runtime directory is incomplete: $Directory. Missing: " +
            ($missingDlls -join ", ") +
            ". Run without -SkipDependencyInstall or pass -$ParameterName."
        )
    }
}

Assert-DllSet `
    -Directory $CudaDllDirectory `
    -Names $cublasDllNames `
    -ParameterName "CudaDllDirectory"
Assert-DllSet `
    -Directory $CudnnDllDirectory `
    -Names $cudnnDllNames `
    -ParameterName "CudnnDllDirectory"
Assert-DllSet `
    -Directory $CudaNvrtcDllDirectory `
    -Names $nvrtcDllNames `
    -ParameterName "CudaNvrtcDllDirectory"

$nvrtcBuiltins = @(
    Get-ChildItem -LiteralPath $CudaNvrtcDllDirectory `
        -Filter "nvrtc-builtins64_*.dll" `
        -File
)
if ($nvrtcBuiltins.Count -eq 0) {
    throw (
        "CUDA NVRTC directory is incomplete: $CudaNvrtcDllDirectory. " +
        "Missing: nvrtc-builtins64_*.dll. Run without " +
        "-SkipDependencyInstall or pass -CudaNvrtcDllDirectory."
    )
}

$allCudaDlls = @(
    $cublasDllNames | ForEach-Object {
        Join-Path $CudaDllDirectory $_
    }
    $cudnnDllNames | ForEach-Object {
        Join-Path $CudnnDllDirectory $_
    }
    $nvrtcDllNames | ForEach-Object {
        Join-Path $CudaNvrtcDllDirectory $_
    }
    $nvrtcBuiltins | ForEach-Object {
        $_.FullName
    }
)
$duplicateCudaDlls = @(
    $allCudaDlls |
        Group-Object { Split-Path $_ -Leaf } |
        Where-Object Count -gt 1
)
if ($duplicateCudaDlls.Count -gt 0) {
    throw (
        "CUDA runtime contains duplicate DLL names: " +
        (($duplicateCudaDlls | ForEach-Object Name) -join ", ")
    )
}

$missingCudaDlls = @(
    $allCudaDlls | Where-Object {
        -not (Test-Path -LiteralPath (
            $_
        ) -PathType Leaf)
    }
)
if ($missingCudaDlls.Count -gt 0) {
    throw (
        "CUDA runtime is incomplete. Missing: " +
        ($missingCudaDlls -join ", ") +
        "."
    )
}

function Invoke-AIpetBuild {
    param(
        [string]$Variant,
        [string]$ArtifactName,
        [string]$VariantWorkPath
    )

    Write-Host "Building $ArtifactName..."
    $previousVariant = $env:AIPET_BUILD_VARIANT
    $previousCudaDirectory = $env:AIPET_CUDA_DLL_DIR
    $previousCudnnDirectory = $env:AIPET_CUDNN_DLL_DIR
    $previousNvrtcDirectory = $env:AIPET_CUDA_NVRTC_DLL_DIR
    try {
        $env:AIPET_BUILD_VARIANT = $Variant
        $env:AIPET_CUDA_DLL_DIR = $CudaDllDirectory
        $env:AIPET_CUDNN_DLL_DIR = $CudnnDllDirectory
        $env:AIPET_CUDA_NVRTC_DLL_DIR = $CudaNvrtcDllDirectory
        Push-Location $projectRoot
        try {
            & $condaExecutable run -n $EnvironmentName `
                python -m PyInstaller `
                --noconfirm `
                --clean `
                --distpath $distPath `
                --workpath $VariantWorkPath `
                $specPath | Out-Host
            if ($LASTEXITCODE -ne 0) {
                throw "PyInstaller failed for build variant: $Variant"
            }
        }
        finally {
            Pop-Location
        }
    }
    finally {
        $env:AIPET_BUILD_VARIANT = $previousVariant
        $env:AIPET_CUDA_DLL_DIR = $previousCudaDirectory
        $env:AIPET_CUDNN_DLL_DIR = $previousCudnnDirectory
        $env:AIPET_CUDA_NVRTC_DLL_DIR = $previousNvrtcDirectory
    }

    return Get-Item (Join-Path $distPath $ArtifactName)
}

$artifacts = @(
    Invoke-AIpetBuild `
        -Variant "standard" `
        -ArtifactName "AIpet.exe" `
        -VariantWorkPath (Join-Path $workPath "standard")
    Invoke-AIpetBuild `
        -Variant "with-cuda" `
        -ArtifactName "AIpet-with-cuda.exe" `
        -VariantWorkPath (Join-Path $workPath "with-cuda")
)

Write-Host ""
Write-Host "Build complete:"
foreach ($artifact in $artifacts) {
    $hash = Get-FileHash -Algorithm SHA256 $artifact.FullName
    Write-Host "  File:   $($artifact.FullName)"
    Write-Host "  Size:   $([math]::Round($artifact.Length / 1MB, 1)) MiB"
    Write-Host "  SHA256: $($hash.Hash)"
    Write-Host ""
}
