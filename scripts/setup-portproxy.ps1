# Set port variable (default 9192, can override with argument)
param(
    [int]$Port = 9192
)

# Detect WSL IP address (only first IP)
$wslIp = (wsl hostname -I).Split(" ")[0].Trim()

# Check if WSL IP was detected
if ([string]::IsNullOrWhiteSpace($wslIp)) {
    Write-Host "ERROR: Could not detect WSL IP. Is WSL running?" -ForegroundColor Red
    exit 1
}

Write-Host ("Detected WSL IP: {0}" -f $wslIp) -ForegroundColor Green

# Clean previous portproxy rule if exists
try {
    netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0
    Write-Host ("Previous portproxy rule deleted.") -ForegroundColor Yellow
} catch {
    Write-Host ("No previous portproxy rule found.") -ForegroundColor Gray
}

# Add new portproxy rule
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=$Port connectaddress=$wslIp connectport=$Port
Write-Host ("Port forwarding configured: 0.0.0.0:{0} -> {1}:{0}" -f $Port, $wslIp) -ForegroundColor Green

# Clean previous firewall rule if exists
$fwRule = Get-NetFirewallRule -DisplayName ("Allow {0} for WSL" -f $Port) -ErrorAction SilentlyContinue
if ($fwRule) {
    Remove-NetFirewallRule -DisplayName ("Allow {0} for WSL" -f $Port)
    Write-Host ("Previous firewall rule deleted.") -ForegroundColor Yellow
} else {
    Write-Host ("No previous firewall rule found.") -ForegroundColor Gray
}

# Add new firewall rule
New-NetFirewallRule -DisplayName ("Allow {0} for WSL" -f $Port) `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port
Write-Host ("Firewall rule created to allow TCP {0} inbound." -f $Port) -ForegroundColor Green

# Show current portproxy rules (optional)
netsh interface portproxy show all
