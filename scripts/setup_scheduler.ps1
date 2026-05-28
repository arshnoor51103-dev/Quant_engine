<#
.SYNOPSIS
    Register the Quant Engine daily run as a Windows Scheduled Task.

.DESCRIPTION
    Creates task 'QuantEngine-DailyRun' with two triggers:
      1. Daily at $RunTime (configurable at top of script)
      2. At logon (fallback for missed runs)
    Requires admin rights or matching user credentials.

.NOTES
    Microsoft account users may need an app password for "run whether logged on or not".
    Alternative: configure "run only when logged on" in Task Scheduler GUI after running this script.
#>

# --- CONFIGURE TRIGGER TIME ---
# TSX closes 1:00 PM PT. Pick one:
$RunTime = "06:00"   # morning pre-market — catches overnight data, runs before market open
# $RunTime = "13:30" # post-close — data settled 30 min after TSX close

$TaskName = "QuantEngine-DailyRun"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$BatPath = Join-Path $ProjectRoot "scripts\daily_run.bat"

# Action
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatPath`"" `
    -WorkingDirectory $ProjectRoot

# Triggers
$TriggerDaily = New-ScheduledTaskTrigger -Daily -At $RunTime
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

# Credentials
$Cred = Get-Credential -Message "Enter Windows credentials for the scheduled task (Microsoft account users: use app password)"

# Register
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger @($TriggerDaily, $TriggerLogon) `
    -Settings $Settings `
    -RunLevel Highest `
    -Credential $Cred `
    -Force

Write-Host ""
Write-Host "Task registered. Verification commands:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'   # manual trigger / smoke test"
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName'  # removal"
