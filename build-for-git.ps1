<#
.SYNOPSIS
    Build, version, and release the trend-rider-lib Python package for GitHub pip consumption.

.DESCRIPTION
    Automates the release workflow:
    - Pre-flight validation (branch, git status, up-to-date, tool availability)
    - Version bump (major/minor/patch) across pyproject.toml, trend_rider_lib/__init__.py, setup.py
    - Build validation in a temporary venv via python -m build
    - Unit tests via pytest (skippable)
    - Git commit, annotated tag, and push to origin
    - Post-release summary with pip install instructions

.PARAMETER BumpType
    The semantic version part to increment: major, minor, or patch. Defaults to patch.

.PARAMETER SkipGitChecks
    If set, skips branch name validation, dirty-tree check, and remote-sync check.

.PARAMETER SkipTests
    If set, skips running pytest entirely.

.EXAMPLE
    .\build-for-git.ps1
    Patch bump (0.3.1 to 0.3.2).

.EXAMPLE
    .\build-for-git.ps1 -BumpType minor
    Minor bump (0.3.1 to 0.4.0).

.EXAMPLE
    .\build-for-git.ps1 -BumpType major -SkipTests
    Major bump (0.3.1 to 1.0.0), skip tests.
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('major', 'minor', 'patch')]
    [string]$BumpType = 'patch',

    [Parameter()]
    [switch]$SkipGitChecks,

    [Parameter()]
    [switch]$SkipTests
)

Set-StrictMode -Version Latest

# NOTE: $ErrorActionPreference is deliberately NOT set to 'Stop'.
# With 'Stop', any stderr output from native commands (pip, git, python)
# captured via 2>&1 becomes a terminating error. Native commands routinely
# write informational messages to stderr, which would break the script.
# We handle all errors explicitly via $LASTEXITCODE checks and Write-ErrorExit.

# ------------------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------------------
function Write-Step([string]$Message) {
    Write-Host "`n--- $Message ---" -ForegroundColor Cyan
}

function Write-ErrorExit([string]$Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Write-Warn([string]$Message) {
    Write-Host "WARNING: $Message" -ForegroundColor Yellow
}

function Assert-Executable([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-ErrorExit "'$Name' is not available in PATH. Aborting."
    }
}

# ------------------------------------------------------------------------------
# 0 -- Tool availability
# ------------------------------------------------------------------------------
Write-Step "0/7 -- Checking tool availability"

Assert-Executable 'git'
Assert-Executable 'python'
Assert-Executable 'pip'

$RepoRoot = (Get-Item $PSScriptRoot).FullName
Set-Location $RepoRoot

Write-Host "Repository root: $RepoRoot" -ForegroundColor Gray

# ------------------------------------------------------------------------------
# 1 -- Pre-flight validation
# ------------------------------------------------------------------------------
if (-not $SkipGitChecks) {
    Write-Step "1/7 -- Pre-flight validation"

    # 1a -- On main branch
    $branch = git rev-parse --abbrev-ref HEAD
    if ($branch -ne 'main') {
        Write-ErrorExit "Current branch is '$branch'. Must be on 'main'."
    }
    Write-Host "[PASS] On main branch" -ForegroundColor Green

    # 1b -- Clean working tree
    $status = git status --porcelain
    if ($status) {
        Write-Host "Uncommitted changes detected:" -ForegroundColor Red
        Write-Host $status
        Write-ErrorExit "Working tree is dirty. Commit or stash changes before releasing."
    }
    Write-Host "[PASS] Working tree is clean" -ForegroundColor Green

    # 1c -- Up to date with origin/main
    git fetch origin main 2>&1
    if ($LASTEXITCODE -ne 0) { Write-ErrorExit "git fetch failed." }
    $behind = git rev-list --count HEAD..origin/main 2>&1
    if ($LASTEXITCODE -ne 0) { Write-ErrorExit "git rev-list failed." }
    if ([int]$behind -gt 0) {
        Write-ErrorExit "Local main is $behind commit(s) behind origin/main. Pull first."
    }
    Write-Host "[PASS] Local main is up to date with origin/main" -ForegroundColor Green
} else {
    Write-Step "1/7 -- Pre-flight validation (skipped via -SkipGitChecks)"
}

# 1d -- Required files exist
Write-Host "`nChecking required files exist..." -ForegroundColor Gray
$requiredFiles = @(
    'pyproject.toml',
    'trend_rider_lib/__init__.py',
    'setup.py'
)
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-ErrorExit "Required file '$file' not found."
    }
    Write-Host "[PASS] $file exists" -ForegroundColor Green
}

# 1e -- Verify __init__.py contains __version__
$initContent = Get-Content 'trend_rider_lib/__init__.py' -Raw
if ($initContent -notmatch '__version__\s*=') {
    Write-ErrorExit "trend_rider_lib/__init__.py does not contain __version__."
}
Write-Host "[PASS] __version__ found in trend_rider_lib/__init__.py" -ForegroundColor Green

# 1f -- .gitignore validation
$expectedGitIgnore = @('dist/', 'build/', '*.egg-info/', '__pycache__/')
$gitignoreContent = Get-Content '.gitignore' -ErrorAction SilentlyContinue
$missingInGitIgnore = $expectedGitIgnore | Where-Object { $gitignoreContent -notcontains $_ }
if ($missingInGitIgnore) {
    Write-Warn ".gitignore is missing entries: $($missingInGitIgnore -join ', ')"
} else {
    Write-Host "[PASS] .gitignore contains all expected entries (dist/, build/, *.egg-info/, __pycache__/)" -ForegroundColor Green
}

# 1g -- Additional file warnings
if (-not (Test-Path 'README.md')) {
    Write-Warn "README.md not found -- consider adding one."
} else {
    Write-Host "[PASS] README.md exists" -ForegroundColor Green
}
if (-not (Test-Path 'LICENSE')) {
    Write-Warn "LICENSE file not found -- consider adding one."
} else {
    Write-Host "[PASS] LICENSE exists" -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 2 -- Version bump
# ------------------------------------------------------------------------------
Write-Step "2/7 -- Version bump ($BumpType)"

# Read current version from pyproject.toml (authoritative source)
$pyproject = Get-Content 'pyproject.toml' -Raw
$versionMatch = [regex]::Match($pyproject, 'version\s*=\s*"(\d+)\.(\d+)\.(\d+)"')
if (-not $versionMatch.Success) {
    Write-ErrorExit "Could not parse version from pyproject.toml."
}

$major = [int]$versionMatch.Groups[1].Value
$minor = [int]$versionMatch.Groups[2].Value
$patch = [int]$versionMatch.Groups[3].Value

Write-Host "Current version: $major.$minor.$patch" -ForegroundColor Gray

# Increment per semver
switch ($BumpType) {
    'major' { $major += 1; $minor = 0; $patch = 0 }
    'minor' { $minor += 1; $patch = 0 }
    'patch' { $patch += 1 }
}

$newVersion = "$major.$minor.$patch"
Write-Host "New version: $newVersion" -ForegroundColor Green

# Check that tag doesn't already exist locally
$tagName = "v$newVersion"
$tagExistsLocally = git tag --list "$tagName" 2>&1
if ($tagExistsLocally) {
    Write-ErrorExit "Tag '$tagName' already exists locally."
}
Write-Host "[PASS] Tag '$tagName' does not exist locally" -ForegroundColor Green

# Check remote tag existence (warn on failure — non-interactive git may not have credentials)
git fetch origin --tags 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Could not fetch remote tags (non-interactive git may lack credentials). Remote tag check skipped."
} else {
    $tagExistsRemotely = git tag --list "$tagName" 2>&1
    if ($tagExistsRemotely) {
        Write-ErrorExit "Tag '$tagName' already exists on remote."
    }
    Write-Host "[PASS] Tag '$tagName' does not exist on remote" -ForegroundColor Green
}

    # -- Update pyproject.toml --
    $pyprojectNew = $pyproject -replace 'version\s*=\s*"\d+\.\d+\.\d+"', "version = `"$newVersion`""
    # WriteAllText writes UTF-8 without BOM (Set-Content -Encoding UTF8 adds BOM, breaking TOML)
    [System.IO.File]::WriteAllText((Resolve-Path 'pyproject.toml'), $pyprojectNew)
    Write-Host "[PASS] Updated pyproject.toml" -ForegroundColor Green

    # -- Update trend_rider_lib/__init__.py (match __version__ = "..." or __version__ = '...') --
    $initNew = $initContent -replace '__version__\s*=\s*["''].*?["'']', "__version__ = `"$newVersion`""
    [System.IO.File]::WriteAllText((Resolve-Path 'trend_rider_lib/__init__.py'), $initNew)
    Write-Host "[PASS] Updated trend_rider_lib/__init__.py" -ForegroundColor Green

    # -- Update setup.py (match version="..." or version='...') --
    $setupContent = Get-Content 'setup.py' -Raw
    $setupNew = $setupContent -replace 'version\s*=\s*["''].*?["'']', "version=`"$newVersion`""
    [System.IO.File]::WriteAllText((Resolve-Path 'setup.py'), $setupNew)
    Write-Host "[PASS] Updated setup.py" -ForegroundColor Green

# ------------------------------------------------------------------------------
# 3 -- Build validation
# ------------------------------------------------------------------------------
Write-Step "3/7 -- Build validation"

$tempVenv = Join-Path $env:TEMP "trend-rider-build-$([System.IO.Path]::GetRandomFileName())"
try {
    # Create temp venv
    Write-Host "Creating temporary venv at: $tempVenv" -ForegroundColor Gray
    python -m venv $tempVenv
    if ($LASTEXITCODE -ne 0) { Write-ErrorExit "Failed to create temp venv." }

    # Join-Path in Windows PowerShell only accepts 2 segments; chain calls
    $pipPath = Join-Path (Join-Path $tempVenv 'Scripts') 'pip.exe'
    $pythonPath = Join-Path (Join-Path $tempVenv 'Scripts') 'python.exe'

    # Upgrade pip (may fail on Windows due to file locking; non-critical)
    Write-Host "Attempting pip upgrade..." -ForegroundColor Gray
    & $pipPath install --upgrade pip 2>&1 | Out-Null
    Write-Host "[PASS] pip upgraded (or skipped)" -ForegroundColor Green

    # Install build dependencies (critical)
    Write-Host "Installing build/setuptools/wheel..." -ForegroundColor Gray
    & $pipPath install build setuptools wheel 2>&1 | Out-Null
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-ErrorExit "Failed to install build dependencies (exit code $LASTEXITCODE)."
    }
    Write-Host "[PASS] build, setuptools, wheel installed" -ForegroundColor Green

    # Build (use setup.py directly — more reliable than python -m build which creates an
    # isolated environment and can fail with custom build backends)
    Write-Host "Running python setup.py sdist bdist_wheel ..." -ForegroundColor Gray
    & $pythonPath setup.py sdist bdist_wheel 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorExit "Build failed (exit code $LASTEXITCODE)."
    }
    Write-Host "[PASS] Build succeeded" -ForegroundColor Green

    # Smoke test: verify dist/ artifacts exist
    $whlFiles = Get-ChildItem -Path 'dist' -Filter '*.whl' -ErrorAction SilentlyContinue
    $tarFiles = Get-ChildItem -Path 'dist' -Filter '*.tar.gz' -ErrorAction SilentlyContinue
    if (-not $whlFiles -or -not $tarFiles) {
        Write-ErrorExit "Build did not produce expected dist/*.whl or dist/*.tar.gz."
    }
    Write-Host "[PASS] Found: $($whlFiles.Name) and $($tarFiles.Name)" -ForegroundColor Green

    # Smoke test: pip install the wheel in the temp venv
    Write-Host "Smoke-testing pip install dist/*.whl ..." -ForegroundColor Gray
    & $pipPath install "$($whlFiles.FullName)" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "pip install of the built wheel failed -- the build may still be usable."
    } else {
        Write-Host "[PASS] Wheel installable" -ForegroundColor Green
    }

    # Clean up build artifacts (dist/ and build/ should NOT be committed)
    Write-Host "Cleaning up dist/ and build/ ..." -ForegroundColor Gray
    if (Test-Path 'dist') { Remove-Item -Recurse -Force 'dist' }
    if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
    if (Test-Path '*.egg-info') { Get-ChildItem '*.egg-info' | Remove-Item -Recurse -Force }
    Write-Host "[PASS] Build artifacts cleaned" -ForegroundColor Green

} finally {
    # Remove temp venv
    if (Test-Path $tempVenv) {
        Remove-Item -Recurse -Force $tempVenv -ErrorAction SilentlyContinue
        Write-Host "[PASS] Temporary venv removed" -ForegroundColor Green
    }
}

# ------------------------------------------------------------------------------
# 4 -- Run tests
# ------------------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Step "4/7 -- Running tests"

    if (Test-Path 'tests') {
        Write-Host "Running pytest (tests/ only)..." -ForegroundColor Gray
        python -m pytest tests/ -v 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-ErrorExit "Tests failed (exit code $LASTEXITCODE)."
        }
        Write-Host "[PASS] All tests passed" -ForegroundColor Green
    } else {
        Write-Warn "No tests/ directory found -- skipping tests."
    }
} else {
    Write-Step "4/7 -- Running tests (skipped via -SkipTests)"
}

# ------------------------------------------------------------------------------
# 5 -- Git commit, tag, and push
# ------------------------------------------------------------------------------
Write-Step "5/7 -- Git commit, tag, and push"

$commitMessage = "chore: bump version to $newVersion"
$tagMessage = "Release v$newVersion"

# Stage files
git add pyproject.toml trend_rider_lib/__init__.py setup.py
if ($LASTEXITCODE -ne 0) { Write-ErrorExit "git add failed." }
Write-Host "[PASS] Files staged" -ForegroundColor Green

# Commit
git commit -m $commitMessage
if ($LASTEXITCODE -ne 0) { Write-ErrorExit "git commit failed." }
Write-Host "[PASS] Committed: $commitMessage" -ForegroundColor Green

# Annotated tag
git tag -a $tagName -m $tagMessage
if ($LASTEXITCODE -ne 0) { Write-ErrorExit "git tag failed." }
Write-Host "[PASS] Tagged: $tagName" -ForegroundColor Green

# Push commits
Write-Host "Pushing commits to origin main..." -ForegroundColor Gray
git push origin main 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-ErrorExit "Failed to push commits to origin/main."
}
Write-Host "[PASS] Commits pushed to origin/main" -ForegroundColor Green

# Push tag
Write-Host "Pushing tag $tagName to origin..." -ForegroundColor Gray
git push origin $tagName 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-ErrorExit "Failed to push tag $tagName to origin."
}
Write-Host "[PASS] Tag $tagName pushed to origin" -ForegroundColor Green

# ------------------------------------------------------------------------------
# 6 -- Post-release output
# ------------------------------------------------------------------------------
Write-Step "6/7 -- Release summary"

$installUrl = "git+https://github.com/nanduahmed/trend-rider-lib.git@$tagName"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  [OK] Released version $newVersion" -ForegroundColor Green
Write-Host "  [TAG] $tagName" -ForegroundColor Green
Write-Host "  [INSTALL] pip install $installUrl" -ForegroundColor Green
Write-Host "" -ForegroundColor Green
Write-Host "  or in requirements.txt:" -ForegroundColor Green
Write-Host "  trend @ $installUrl" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

Write-Step "7/7 -- Done"
Write-Host "Release completed successfully." -ForegroundColor Green

exit 0