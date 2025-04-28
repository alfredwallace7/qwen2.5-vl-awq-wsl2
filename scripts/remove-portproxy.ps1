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

# Remove portproxy rule
try {
    netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0
    Write-Host ("Portproxy rule deleted: 0.0.0.0:{0}" -f $Port) -ForegroundColor Yellow
} catch {
    Write-Host ("No portproxy rule to delete.") -ForegroundColor Gray
}

# Remove firewall rule
$fwRule = Get-NetFirewallRule -DisplayName ("Allow {0} for WSL" -f $Port) -ErrorAction SilentlyContinue
if ($fwRule) {
    Remove-NetFirewallRule -DisplayName ("Allow {0} for WSL" -f $Port)
    Write-Host ("Firewall rule 'Allow {0} for WSL' deleted." -f $Port) -ForegroundColor Yellow
} else {
    Write-Host ("No firewall rule 'Allow {0} for WSL' found." -f $Port) -ForegroundColor Gray
}

# Show remaining portproxy rules (optional)
netsh interface portproxy show all
