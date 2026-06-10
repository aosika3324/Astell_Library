param(
    [string]$PublicHost = $env:PUBLIC_HOST,
    [string]$User = $env:BASIC_AUTH_USER,
    [string]$Password = $env:BASIC_AUTH_PASSWORD,
    [string]$AcmeEmail = $env:ACME_EMAIL,
    [string]$PublishedPort = $env:ASTELL_PUBLISHED_PORT
)

$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RootDir

if (-not $PublicHost) { $PublicHost = "localhost" }
if (-not $User) { $User = "astell" }
if (-not $AcmeEmail) { $AcmeEmail = "admin@example.com" }
if (-not $PublishedPort) { $PublishedPort = "8080" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required."
}

$generatedPassword = $false
if (-not $Password) {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $Password = [Convert]::ToBase64String($bytes)
    $generatedPassword = $true
}

$BasicAuthHash = docker run --rm caddy:2 caddy hash-password --plaintext $Password
if ($LASTEXITCODE -ne 0) {
    throw "Failed to generate Caddy Basic Auth hash."
}

$sha = [System.Security.Cryptography.SHA256]::Create()
$hashBytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Password))
$AstellPasswordSha256 = -join ($hashBytes | ForEach-Object { $_.ToString("x2") })

if ($PublicHost -eq "localhost" -or $PublicHost -eq "127.0.0.1") {
    $CorsOrigins = "http://localhost:$PublishedPort,http://127.0.0.1:$PublishedPort"
} else {
    $CorsOrigins = "https://$PublicHost"
}

@"
PUBLIC_HOST=$PublicHost
ACME_EMAIL=$AcmeEmail
BASIC_AUTH_USER=$User
BASIC_AUTH_HASH='$BasicAuthHash'
ASTELL_AUTH_ENABLED=1
ASTELL_AUTH_USER=$User
ASTELL_AUTH_PASSWORD_SHA256=$AstellPasswordSha256
ASTELL_AUTH_REALM=Astell Library
ASTELL_CORS_ORIGINS=$CorsOrigins
ASTELL_UI_HOST=0.0.0.0
ASTELL_UI_PORT=8080
ASTELL_OPEN_BROWSER=0
ASTELL_PUBLISHED_PORT=$PublishedPort
"@ | Set-Content -Path ".env" -Encoding ascii

New-Item -ItemType Directory -Force -Path "deploy/container/projects" | Out-Null

docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "docker compose failed."
}

Write-Host "Astell service is starting."
Write-Host "URL: http://localhost:$PublishedPort/"
Write-Host "Username: $User"
if ($generatedPassword) {
    Write-Host "Generated password: $Password"
    Write-Host "Store this password now; it is not written in plaintext."
}
