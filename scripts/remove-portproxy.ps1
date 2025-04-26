# Detect WSL IP address (only first IP)
$wslIp = (wsl hostname -I).Split(" ")[0].Trim()

# Check if WSL IP was detected
if ([string]::IsNullOrWhiteSpace($wslIp)) {
    Write-Host "❌ Could not detect WSL IP. Is WSL running?" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Detected WSL IP: $wslIp" -ForegroundColor Green

# Remove portproxy rule
try {
    netsh interface portproxy delete v4tov4 listenport=9192 listenaddress=0.0.0.0
    Write-Host "🧹 Portproxy rule deleted: 0.0.0.0:9192" -ForegroundColor Yellow
} catch {
    Write-Host "ℹ️ No portproxy rule to delete." -ForegroundColor Gray
}

# Remove firewall rule
$fwRule = Get-NetFirewallRule -DisplayName "Allow 9192 for WSL" -ErrorAction SilentlyContinue
if ($fwRule) {
    Remove-NetFirewallRule -DisplayName "Allow 9192 for WSL"
    Write-Host "🧹 Firewall rule 'Allow 9192 for WSL' deleted." -ForegroundColor Yellow
} else {
    Write-Host "ℹ️ No firewall rule 'Allow 9192 for WSL' found." -ForegroundColor Gray
}

# Show remaining portproxy rules (optional)
netsh interface portproxy show all
