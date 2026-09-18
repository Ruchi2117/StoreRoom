param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$downloadDirectory = Join-Path $projectRoot 'data/downloads'
$reportDirectory = Join-Path $projectRoot 'reports'
New-Item -ItemType Directory -Force -Path $downloadDirectory, $reportDirectory | Out-Null
$headers = @{Accept='application/vnd.mendeley-public-dataset.1+json'}
$folderIds = @('828b6a7d-5cea-4eae-b1a1-0dfe22c5ac34', 'e1918a28-2219-4374-bc6b-4ce7680d2354')
$files = foreach ($folderId in $folderIds) {
    Invoke-RestMethod -Uri "https://data.mendeley.com/public-api/datasets/gz39ggf35n/files?folder_id=$folderId&version=1" -Headers $headers
}
$manifest = [ordered]@{
    source = 'https://data.mendeley.com/datasets/gz39ggf35n/1'
    doi = '10.17632/gz39ggf35n.1'
    license = 'CC BY 4.0'
    retrieved_at = (Get-Date).ToUniversalTime().ToString('o')
    files = @()
}
foreach ($file in $files) {
    if ([IO.Path]::GetFileName($file.filename) -cne $file.filename) { throw 'Unsafe remote filename' }
    $destination = Join-Path $downloadDirectory $file.filename
    $partial = "$destination.part"
    if (-not (Test-Path -LiteralPath $destination)) {
        Write-Host "Downloading $($file.filename) ($($file.size) bytes); interrupted downloads can resume."
        & curl.exe --fail --location --silent --show-error --retry 3 --continue-at - --output $partial $file.content_details.download_url
        if ($LASTEXITCODE -ne 0) { throw "Download failed; rerun this script to resume: $partial" }
        $candidate = $partial
    } else { $candidate = $destination }
    $hash = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-Item -LiteralPath $candidate).Length -ne $file.size -or $hash -ne $file.content_details.sha256_hash) {
        throw "Size or SHA-256 mismatch: $candidate. File not accepted."
    }
    if ($candidate -eq $partial) { Move-Item -LiteralPath $partial -Destination $destination }
    $manifest.files += [ordered]@{
        filename = $file.filename; bytes = $file.size; sha256 = $hash
        url = $file.content_details.download_url; verified = $true
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $reportDirectory 'download_manifest.json') -Encoding utf8
    Write-Host "Verified SHA-256: $hash"
}
