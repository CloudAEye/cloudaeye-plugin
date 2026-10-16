[CmdletBinding()]
param(
    [string]$PluginRoot = '',
    [string]$DestinationRoot = (Join-Path $HOME '.cursor\plugins\local'),
    [string]$DirectoryName = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $PluginRoot) {
    $PluginRoot = Split-Path -Parent $PSScriptRoot
}
$source = (Resolve-Path -LiteralPath $PluginRoot).ProviderPath
$manifestPath = Join-Path $source '.cursor-plugin\plugin.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.name -notmatch '^[a-z0-9]+(?:[.-][a-z0-9]+)*$') {
    throw 'The Cursor plugin name must be a valid lowercase identifier.'
}
$components = @(
    '.cursor-plugin', '.mcp.json', 'cursor', 'README.md',
    'scripts/repository_preflight.py', 'scripts/owners_file.py'
)
# Do not install unreleased skills or generated files from a developer checkout.
$components += Get-ChildItem -LiteralPath (Join-Path $source 'skills') -Directory |
    Where-Object { $_.Name -ne 'assign-reviewer' -and (Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md')) } |
    ForEach-Object { "skills/$($_.Name)" }
foreach ($relativePath in $components) {
    if (-not (Test-Path -LiteralPath (Join-Path $source $relativePath))) {
        throw "Plugin component is missing: $relativePath"
    }
}

$destinationRootPath = [System.IO.Path]::GetFullPath($DestinationRoot)
if (-not $DirectoryName) {
    $DirectoryName = $manifest.name
}
if ($DirectoryName -notmatch '^[a-z0-9]+(?:[.-][a-z0-9]+)*$') {
    throw 'The destination directory name must be a valid lowercase identifier.'
}
$destination = Join-Path $destinationRootPath $DirectoryName
$existing = Get-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
if ($existing) {
    throw "Existing Cursor plugin was not modified: $destination. Choose an unused -DirectoryName; external junctions are not supported by Cursor."
}

New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($component in $components) {
    $target = Join-Path $destination $component
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $component) -Destination $target -Recurse -Force
}
Write-Output "Cursor plugin installed: $destination"
Write-Output 'Restart Cursor, enable CloudAEye, and authenticate its MCP connection.'
