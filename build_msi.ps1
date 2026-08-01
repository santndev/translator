param(
    [string]$Version = "1.0.2",
    [switch]$SkipApplicationBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$toolsRoot = Join-Path $projectRoot ".build-tools"
$wixRoot = Join-Path $toolsRoot "wix314"
$wixZip = Join-Path $toolsRoot "wix314-binaries.zip"
$distRoot = Join-Path $projectRoot "dist\Translator"
$installerRoot = Join-Path $projectRoot "installer"
$generatedRoot = Join-Path $installerRoot "generated"
$objectRoot = Join-Path $installerRoot "obj"
$releaseRoot = Join-Path $projectRoot "release"

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must use major.minor.patch format."
}

New-Item -ItemType Directory -Force -Path $toolsRoot, $generatedRoot, $objectRoot, $releaseRoot | Out-Null

# The release directory is dedicated to final installer artifacts. Resolve and
# validate it before deletion so a future path edit cannot broaden the cleanup
# beyond this project's release folder.
$resolvedProjectRoot = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
$resolvedReleaseRoot = [System.IO.Path]::GetFullPath($releaseRoot).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
)
$requiredPrefix = $resolvedProjectRoot + [System.IO.Path]::DirectorySeparatorChar
if (-not $resolvedReleaseRoot.StartsWith(
    $requiredPrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Refusing to clean MSI files outside the project: $resolvedReleaseRoot"
}

$previousMsiFiles = @(
    Get-ChildItem -LiteralPath $resolvedReleaseRoot -Filter "*.msi" -File -Recurse
)
foreach ($previousMsiFile in $previousMsiFiles) {
    Remove-Item -LiteralPath $previousMsiFile.FullName -Force
}
if ($previousMsiFiles.Count -gt 0) {
    Write-Output (
        "Removed {0} previous MSI build(s) from {1}" -f
        $previousMsiFiles.Count,
        $resolvedReleaseRoot
    )
}

if (-not $SkipApplicationBuild) {
    $versionParts = $Version.Split('.')
    $fileVersion = "$($versionParts[0]), $($versionParts[1]), $($versionParts[2]), 0"
    $versionInfo = Get-Content -Raw -LiteralPath (Join-Path $installerRoot "version_info.txt")
    $versionInfo = $versionInfo -replace 'filevers=\([^\)]*\)', "filevers=($fileVersion)"
    $versionInfo = $versionInfo -replace 'prodvers=\([^\)]*\)', "prodvers=($fileVersion)"
    $versionInfo = $versionInfo -replace "StringStruct\('FileVersion', '[^']*'\)", "StringStruct('FileVersion', '$Version')"
    $versionInfo = $versionInfo -replace "StringStruct\('ProductVersion', '[^']*'\)", "StringStruct('ProductVersion', '$Version')"
    $generatedVersionInfo = Join-Path $generatedRoot "version_info.txt"
    Set-Content -LiteralPath $generatedVersionInfo -Value $versionInfo -Encoding UTF8

    $previousVersionInfo = $env:TRANSLATOR_VERSION_INFO
    try {
        $env:TRANSLATOR_VERSION_INFO = $generatedVersionInfo
        python -m PyInstaller --noconfirm --clean (Join-Path $projectRoot "Translator.spec")
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $distRoot "Translator.exe"))) {
            throw "PyInstaller did not produce Translator.exe."
        }
    } finally {
        $env:TRANSLATOR_VERSION_INFO = $previousVersionInfo
    }
} elseif (-not (Test-Path (Join-Path $distRoot "Translator.exe"))) {
    throw "-SkipApplicationBuild requires an existing dist\Translator\Translator.exe."
}

if (-not (Test-Path (Join-Path $wixRoot "heat.exe"))) {
    $downloadUrl = "https://github.com/wixtoolset/wix3/releases/download/wix3141rtm/wix314-binaries.zip"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $wixZip
    New-Item -ItemType Directory -Force -Path $wixRoot | Out-Null
    Expand-Archive -LiteralPath $wixZip -DestinationPath $wixRoot -Force
}

$heat = Join-Path $wixRoot "heat.exe"
$candle = Join-Path $wixRoot "candle.exe"
$light = Join-Path $wixRoot "light.exe"
$filesWxs = Join-Path $generatedRoot "Files.wxs"

& $heat dir $distRoot `
    -nologo -cg ApplicationFiles -dr INSTALLFOLDER -srd -sfrag -sreg -scom `
    -ag -var var.SourceDir -out $filesWxs
if ($LASTEXITCODE -ne 0) { throw "WiX Heat failed." }

Get-ChildItem -LiteralPath $objectRoot -File -ErrorAction SilentlyContinue |
    Remove-Item -Force

& $candle -nologo -arch x64 `
    "-dSourceDir=$distRoot" `
    "-dProductVersion=$Version" `
    "-dProjectRoot=$projectRoot" `
    -out "$objectRoot\" `
    (Join-Path $installerRoot "Product.wxs") `
    $filesWxs
if ($LASTEXITCODE -ne 0) { throw "WiX Candle failed." }

$msiPath = Join-Path $releaseRoot "Translator-$Version-x64.msi"
& $light -nologo `
    -ext WixUIExtension `
    -cultures:en-us `
    -out $msiPath `
    (Join-Path $objectRoot "Product.wixobj") `
    (Join-Path $objectRoot "Files.wixobj")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $msiPath)) {
    throw "WiX Light did not produce the MSI."
}

$sha256 = [System.Security.Cryptography.SHA256]::Create()
$stream = [System.IO.File]::OpenRead($msiPath)
try {
    $hashBytes = $sha256.ComputeHash($stream)
    $hashValue = -join ($hashBytes | ForEach-Object { $_.ToString("x2") })
} finally {
    $stream.Dispose()
    $sha256.Dispose()
}
Write-Output "MSI=$msiPath"
Write-Output "SHA256=$hashValue"
