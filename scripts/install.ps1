# VESK — installe les 20 skills de montage vidéo (Windows PowerShell).
#
#   .\scripts\install.ps1
#   .\scripts\install.ps1 -Mode link -Target C:\skills
#   .\scripts\install.ps1 -Only animated-captions-generator,viral-hooks-library
#   .\scripts\install.ps1 -Force
#   .\scripts\install.ps1 -Uninstall
#
param(
    [string]$Target = "$HOME\.claude\skills",
    [ValidateSet("copy", "link")][string]$Mode = "copy",
    [string]$Only = "",
    [switch]$Force,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$SkillsDir = Join-Path $Root "skills"

function Copy-Skill {
    param([string]$Source, [string]$Destination)
    Copy-Item -Recurse -Path $Source -Destination $Destination
    Get-ChildItem -Recurse -Path $Destination -Include "__pycache__", "*.pyc" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    $sharedDest = Join-Path $Destination "_shared"
    New-Item -ItemType Directory -Force -Path $sharedDest | Out-Null
    Copy-Item -Recurse -Path (Join-Path $Root "shared\vesk") -Destination $sharedDest
    # données de tous les skills : les appels croisés (styles, hooks…) restent possibles
    foreach ($dataDir in (Get-ChildItem -Path $SkillsDir -Directory)) {
        $dataFiles = Get-ChildItem -Path $dataDir.FullName -Filter "*.json" -File
        if ($dataFiles) {
            $dataTarget = Join-Path $sharedDest "data\$($dataDir.Name)"
            New-Item -ItemType Directory -Force -Path $dataTarget | Out-Null
            $dataFiles | Copy-Item -Destination $dataTarget
        }
    }
}

if (-not (Test-Path $SkillsDir)) { throw "Dossier skills/ introuvable : $SkillsDir" }

if ($Uninstall) {
    if (-not (Test-Path $Target)) { Write-Host "Rien à désinstaller dans $Target" -ForegroundColor Yellow; exit 0 }
    $removed = 0
    foreach ($dir in (Get-ChildItem -Path $SkillsDir -Directory)) {
        $dest = Join-Path $Target $dir.Name
        if (Test-Path $dest) {
            Remove-Item -Recurse -Force $dest
            Write-Host "✓ retiré : $($dir.Name)" -ForegroundColor Green
            $removed++
        }
    }
    Write-Host "$removed skill(s) retiré(s) de $Target" -ForegroundColor Green
    exit 0
}

Write-Host "VESK — installation" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $Root "shared\vesk"))) { throw "Dossier shared/vesk introuvable." }

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python 3.9+ est requis (winget install Python.Python.3.12)." }

if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "✓ FFmpeg détecté" -ForegroundColor Green
} else {
    Write-Host "! FFmpeg introuvable : winget install Gyan.FFmpeg" -ForegroundColor Yellow
}

New-Item -ItemType Directory -Force -Path $Target | Out-Null

$skills = @(Get-ChildItem -Path $SkillsDir -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName "SKILL.md") })

if ($Only) {
    $wanted = $Only.Split(",") | ForEach-Object { $_.Trim() }
    foreach ($name in $wanted) {
        if (-not ($skills | Where-Object { $_.Name -eq $name })) { throw "Skill inconnu : $name" }
    }
    $skills = @($skills | Where-Object { $wanted -contains $_.Name })
}

$installed = 0
foreach ($skill in $skills) {
    $name = $skill.Name
    $dest = Join-Path $Target $name
    $existing = Get-Item -Force -LiteralPath $dest -ErrorAction SilentlyContinue
    if ($existing) {
        if ($Force) { Remove-Item -Recurse -Force $dest }
        else { Write-Host "! déjà présent, ignoré : $name (-Force pour écraser)" -ForegroundColor Yellow; continue }
    }
    if ($Mode -eq "link") {
        try {
            New-Item -ItemType SymbolicLink -Path $dest -Target $skill.FullName | Out-Null
        } catch {
            Write-Host "! lien symbolique impossible (mode développeur requis) — copie utilisée pour $name" -ForegroundColor Yellow
            Copy-Skill -Source $skill.FullName -Destination $dest
        }
    } else {
        Copy-Skill -Source $skill.FullName -Destination $dest
    }
    $installed++
    Write-Host "✓ $name" -ForegroundColor Green
}

Write-Host ""
Write-Host "$installed skill(s) installé(s) dans $Target" -ForegroundColor Green
Write-Host @"

Utilisation depuis un agent (Claude Code, Cursor, etc.) :
  « Utilise le skill animated-captions-generator sur clip.mp4 avec le style hormozi »

Test rapide :
  python "$Target\animated-captions-generator\scripts\generate.py" --list-styles
  python "$Target\speech-to-text-whisper\scripts\transcribe.py" --doctor

Dépendances optionnelles :
  pip install faster-whisper            # transcription locale
  pip install opencv-python-headless    # suivi de visage
  pip install torch transformers pillow # recherche CLIP

Désinstaller : .\scripts\install.ps1 -Uninstall
"@
