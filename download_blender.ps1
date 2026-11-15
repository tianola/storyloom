$url = 'https://download.blender.org/release/Blender4.5/blender-4.5.15-windows-x64.zip'
$dest = 'tools/blender-4.5.15-windows-x64.zip'

Write-Host 'Downloading Blender 4.5.15...'
try {
    Invoke-WebRequest -Uri $url -OutFile $dest
    Write-Host 'Download complete. Extracting...'
    Expand-Archive -Path $dest -DestinationPath 'tools/' -Force
    Write-Host 'Extracting complete. Verifying...'
    $exe = 'tools/blender-4.5.15-windows-x64/blender.exe'
    if (Test-Path $exe) { 
        Write-Host 'SUCCESS: Blender installed at ' $exe 
    } else { 
        Write-Host 'ERROR: Blender not found at ' $exe 
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    exit 1
}