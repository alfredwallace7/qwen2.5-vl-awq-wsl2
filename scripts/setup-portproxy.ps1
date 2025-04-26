# Detect WSL IP address (only first IP)
$wslIp = (wsl hostname -I).Split(" ")[0].Trim()

# Check if WSL IP was detected
if ([string]::IsNullOrWhiteSpace($wslIp)) {
    Write-Host "❌ Could not detect WSL IP. Is WSL running?" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Detected WSL IP: $wslIp" -ForegroundColor Green

# Clean previous portproxy rule if exists
try {
    netsh interface portproxy delete v4tov4 listenport=9192 listenaddress=0.0.0.0
    Write-Host "🧹 Previous portproxy rule deleted." -ForegroundColor Yellow
} catch {
    Write-Host "ℹ️ No previous portproxy rule found." -ForegroundColor Gray
}

# Add new portproxy rule
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=9192 connectaddress=$wslIp connectport=9192
Write-Host "✅ Port forwarding configured: 0.0.0.0:9192 -> $wslIp:9192" -ForegroundColor Green

# Clean previous firewall rule if exists
$fwRule = Get-NetFirewallRule -DisplayName "Allow 9192 for WSL" -ErrorAction SilentlyContinue
if ($fwRule) {
    Remove-NetFirewallRule -DisplayName "Allow 9192 for WSL"
    Write-Host "🧹 Previous firewall rule deleted." -ForegroundColor Yellow
} else {
    Write-Host "ℹ️ No previous firewall rule found." -ForegroundColor Gray
}

# Add new firewall rule
New-NetFirewallRule -DisplayName "Allow 9192 for WSL" `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort 9192
Write-Host "✅ Firewall rule created to allow TCP 9192 inbound." -ForegroundColor Green

# Show current portproxy rules (optional)
netsh interface portproxy show all
