$zipPath = 'F:\AI-PROJECTS\longform-explainer-code-package.zip'
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Add-Type -AssemblyName System.IO.Compression.FileSystem

$sourceDir = 'F:\AI-PROJECTS\longform-explainer'
$zipFile = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)

$excludePatterns = @(
    '.venv', '.venv-xpu', 'node_modules', '__pycache__', '.pytest_cache',
    '_scratch', 'models', 'media', 'dist',
    'tools/blender-*', 'models', 'media',
    'work/episode-*', 'work/*/renders', 'work/*/dist', 'work/*/segments',
    'work/*/qc', 'work/*/vo', 'work/*/renders', 'work/*/segments',
    'work/*/edit', 'work/*/music', 'work/*/motion', 'work/*/assets',
    '.venv', '.venv-xpu', 'node_modules', '__pycache__', '.pytest_cache',
    '.superpowers', '.git', '.github', '*.log', '*.tmp', '*.tmp.*',
    '*.mp4', '*.wav', '*.png', '*.jpg', '*.jpeg', '*.webp', '*.gif',
    '*.zip', '*.tar', '*.gz', '*.rar', '*.7z',
    '.vs', '.vscode', '.idea', '*.swp', '*.swo', '*~',
    'Thumbs.db', 'ehthumbs.db', 'Desktop.ini'
)

function ShouldExclude($path) {
    $relPath = $path.Substring($sourceDir.Length + 1).Replace('\', '/')
    foreach ($pattern in $global:excludePatterns) {
        if ($relPath -like $pattern) { return $true }
        if ($relPath -like "$pattern/*") { return $true }
    }
    return $false
}

$global:excludePatterns = @(
    '.venv', '.venv-xpu', 'node_modules', '__pycache__', '.pytest_cache',
    '_scratch', 'models', 'media', 'dist',
    'tools/blender-*', 'models', 'media',
    'work/episode-*', 'work/*/renders', 'work/*/dist', 'work/*/segments',
    'work/*/qc', 'work/*/vo', 'work/*/renders', 'work/*/segments',
    'work/*/edit', 'work/*/music', 'work/*/motion', 'work/*/assets',
    '.venv', '.venv-xpu', 'node_modules', '__pycache__', '.pytest_cache',
    '.superpowers', '.git', '.github', '*.log', '*.tmp', '*.tmp.*',
    '*.mp4', '*.wav', '*.png', '*.jpg', '*.jpeg', '*.webp', '*.gif',
    '*.zip', '*.tar', '*.gz', '*.rar', '*.7z',
    '.vs', '.vscode', '.idea', '*.swp', '*.swo', '*~',
    'Thumbs.db', 'ehthumbs.db', 'Desktop.ini'
)

$files = Get-ChildItem -Path $sourceDir -Recurse -File
$count = 0
foreach ($file in $files) {
    $relPath = $file.FullName.Substring($sourceDir.Length + 1).Replace('\', '/')
    $excluded = $false
    foreach ($pattern in $global:excludePatterns) {
        if ($relPath -like $pattern -or $relPath -like "$pattern/*") {
            $excluded = $true
            break
        }
    }
    if (-not $excluded) {
        $entryName = $relPath
        $entry = $zipFile.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
        $stream = $entry.Open()
        $fileStream = [System.IO.File]::OpenRead($file.FullName)
        $fileStream.CopyTo($stream)
        $stream.Close()
        $fileStream.Close()
        $count++
    }
}

$zipFile.Dispose()
Write-Host "ZIP created successfully! Files included: $count"