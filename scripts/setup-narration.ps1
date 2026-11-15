#Requires -Version 5.1
<#
.SYNOPSIS
    Prepares the local English narration runtime: project venv, pinned CPU-only
    Python dependencies and the official Kokoro ONNX model assets.

.DESCRIPTION
    Network access is used ONLY here. python/narrate.py itself synthesizes
    offline. Re-running is cheap: an existing venv and hash-verified assets are
    left alone. Nothing outside this project is modified and no environment
    variable is persisted.
#>
[CmdletBinding()]
param(
    [string]$PythonExe = 'C:\Users\thana\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe',
    [switch]$SkipDependencies,
    [switch]$SkipAssets
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$VenvDir = Join-Path $Root '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$Requirements = Join-Path $Root 'python\requirements.txt'
$ModelDir = Join-Path $Root 'models\kokoro'
$AssetsManifest = Join-Path $ModelDir 'assets.json'

$Release = 'model-files-v1.1'
$ReleaseApi = "https://api.github.com/repos/thewh1teagle/kokoro-onnx/releases/tags/$Release"
# Digests and sizes are the values the GitHub release asset API reports for $Release.
$Assets = @(
    [pscustomobject]@{
        FileName  = 'kokoro-v1.0.onnx'
        Source    = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/$Release/kokoro-v1.0.onnx"
        Size      = 325505369
        Sha256    = 'beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a'
        Purpose   = 'Kokoro v1.0 English speech model, full precision, ONNX CPU inference'
        License   = 'Apache-2.0'
        LicenseNote = 'Weights originate from hexgrad/Kokoro-82M (Apache-2.0); this ONNX export is published by the MIT-licensed thewh1teagle/kokoro-onnx project.'
    },
    [pscustomobject]@{
        FileName  = 'voices-v1.0.bin'
        Source    = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/$Release/voices-v1.0.bin"
        Size      = 28214398
        Sha256    = 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'
        Purpose   = 'Voice style bundle for the v1.0 models (54 voices, English IDs af_/am_/bf_/bm_)'
        License   = 'Apache-2.0'
        LicenseNote = 'Same source as the model export. No voice cloning is performed; only bundled voices are used.'
    }
)

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments, [string]$What)
    Write-Host ">> $Exe $($Arguments -join ' ')"
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$What failed with exit code $LASTEXITCODE"
    }
}

function Get-Sha256 {
    param([string]$Path)
    (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

function Test-Asset {
    param([object]$Asset)
    $path = Join-Path $ModelDir $Asset.FileName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $false }
    if ((Get-Item -LiteralPath $path).Length -ne $Asset.Size) { return $false }
    return (Get-Sha256 -Path $path) -eq $Asset.Sha256
}

function Save-Asset {
    param([object]$Asset)
    $destination = Join-Path $ModelDir $Asset.FileName
    $partial = "$destination.partial"
    Write-Host "<< downloading $($Asset.FileName) ($([math]::Round($Asset.Size / 1MB, 1)) MB)"
    if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    Invoke-WebRequest -Uri $Asset.Source -OutFile $partial -UseBasicParsing
    $size = (Get-Item -LiteralPath $partial).Length
    if ($size -ne $Asset.Size) {
        throw "$($Asset.FileName) downloaded $size bytes, expected $($Asset.Size)"
    }
    $hash = Get-Sha256 -Path $partial
    if ($hash -ne $Asset.Sha256) {
        throw "$($Asset.FileName) sha256 $hash does not match pinned $($Asset.Sha256)"
    }
    Move-Item -LiteralPath $partial -Destination $destination -Force
    Write-Host "   verified sha256 $hash"
}

if (-not (Test-Path -LiteralPath $Requirements -PathType Leaf)) {
    throw "Missing requirements file: $Requirements"
}
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
        throw "Python 3.12 not found at $PythonExe. Pass -PythonExe <path>; this script never installs Python."
    }
    Invoke-Checked -Exe $PythonExe -Arguments @('-m', 'venv', $VenvDir) -What 'python -m venv'
}

$pythonVersion = & $VenvPython --version
Write-Host "venv python: $pythonVersion ($VenvPython)"

if (-not $SkipDependencies) {
    Invoke-Checked -Exe $VenvPython -Arguments @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', $Requirements) -What 'dependency install'
}

$records = @()
foreach ($asset in $Assets) {
    if ($SkipAssets) {
        Write-Host "!! -SkipAssets: not verifying $($asset.FileName)"
        continue
    }
    if (Test-Asset -Asset $asset) {
        Write-Host "ok $($asset.FileName) already verified"
    }
    else {
        Save-Asset -Asset $asset
    }
    $records += [ordered]@{
        file        = $asset.FileName
        source      = $asset.Source
        releaseTag  = $Release
        releaseApi  = $ReleaseApi
        sizeBytes   = $asset.Size
        sha256      = $asset.Sha256
        purpose     = $asset.Purpose
        license     = $asset.License
        licenseNote = $asset.LicenseNote
        verifiedAt  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss'Z'")
    }
}

if ($records.Count -gt 0) {
    $payload = [ordered]@{
        owner        = 'scripts/setup-narration.ps1'
        consumer     = 'python/narrate.py'
        modelDir     = 'models/kokoro'
        assets       = $records
        dependencies = [ordered]@{
            requirements = 'python/requirements.txt'
            pinnedAndHashed = $true
            runtime       = 'onnxruntime CPUExecutionProvider (no CUDA/ROCm)'
        }
    }
    $tmp = "$AssetsManifest.tmp"
    # PowerShell 5.1 'Set-Content -Encoding UTF8' writes a BOM; json.loads would choke on it.
    [IO.File]::WriteAllText($tmp, ($payload | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding $false))
    Move-Item -LiteralPath $tmp -Destination $AssetsManifest -Force
    Write-Host "wrote $AssetsManifest"
}

Write-Host ""
Write-Host "Narration runtime ready. Offline synthesis:"
Write-Host "  .venv\Scripts\python.exe python\narrate.py --input request.json --output OUT ``"
Write-Host "    --model models\kokoro\kokoro-v1.0.onnx --voices models\kokoro\voices-v1.0.bin"
