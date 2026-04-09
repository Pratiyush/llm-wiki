# Scheduled sync

Run `llmwiki sync` automatically so your wiki stays up to date overnight.
Templates are provided for macOS, Linux, and Windows.

> **Privacy note**: scheduled runs use the same `config.json` and
> redaction rules as manual runs. No new data paths are introduced.
> The sync process only reads local `.jsonl` session files and writes
> to your local `raw/` and `site/` directories.

## macOS (launchd)

1. Copy the plist and edit the paths:

```bash
cp docs/scheduled-sync/launchd.plist ~/Library/LaunchAgents/com.llmwiki.sync.plist
```

2. Edit `~/Library/LaunchAgents/com.llmwiki.sync.plist`:
   - Set `WorkingDirectory` to your llm-wiki repo root
   - Set the `llmwiki` path in `ProgramArguments` (find it with `which llmwiki`)

3. Load the agent:

```bash
launchctl load ~/Library/LaunchAgents/com.llmwiki.sync.plist
```

4. Verify it's registered:

```bash
launchctl list | grep llmwiki
```

5. Check logs after the first run:

```bash
cat /tmp/llmwiki-sync.log
```

**Uninstall:**

```bash
launchctl unload ~/Library/LaunchAgents/com.llmwiki.sync.plist
rm ~/Library/LaunchAgents/com.llmwiki.sync.plist
```

## Linux (systemd)

1. Copy both unit files:

```bash
sudo cp docs/scheduled-sync/llmwiki-sync.service /etc/systemd/system/
sudo cp docs/scheduled-sync/llmwiki-sync.timer /etc/systemd/system/
```

2. Edit `/etc/systemd/system/llmwiki-sync.service`:
   - Set `ExecStart` to the path of your `llmwiki` binary
   - Set `WorkingDirectory` to your llm-wiki repo root
   - Set `User` to your username

3. Enable and start the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now llmwiki-sync.timer
```

4. Verify:

```bash
systemctl list-timers | grep llmwiki
```

5. Check logs:

```bash
journalctl -u llmwiki-sync.service --no-pager -n 20
```

**Run manually (test):**

```bash
sudo systemctl start llmwiki-sync.service
```

**Uninstall:**

```bash
sudo systemctl disable --now llmwiki-sync.timer
sudo rm /etc/systemd/system/llmwiki-sync.{service,timer}
sudo systemctl daemon-reload
```

## Windows (Task Scheduler)

1. Open Task Scheduler (`taskschd.msc`) or use PowerShell.

2. **Import the XML template:**

```powershell
Register-ScheduledTask -TaskName "llmwiki-sync" -Xml (Get-Content docs\scheduled-sync\llmwiki-sync-task.xml | Out-String)
```

3. Edit the task to fix paths:
   - Open Task Scheduler > find "llmwiki-sync"
   - Under **Actions**, update the `llmwiki` command path and working directory
   - Under **General**, confirm it runs under your user account

4. **Or create from scratch via PowerShell:**

```powershell
$action = New-ScheduledTaskAction `
  -Execute "llmwiki" `
  -Argument "sync" `
  -WorkingDirectory "C:\Users\YOU\llm-wiki"

$trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM

Register-ScheduledTask `
  -TaskName "llmwiki-sync" `
  -Action $action `
  -Trigger $trigger `
  -Description "llmwiki nightly sync"
```

5. Verify:

```powershell
Get-ScheduledTask -TaskName "llmwiki-sync"
```

**Uninstall:**

```powershell
Unregister-ScheduledTask -TaskName "llmwiki-sync" -Confirm:$false
```

## Customization

All templates default to **03:00 daily**. To change the schedule:

| OS | Where to edit |
|---|---|
| macOS | `StartCalendarInterval` dict in the plist |
| Linux | `OnCalendar` in the `.timer` file |
| Windows | `StartBoundary` in the XML or `-At` in PowerShell |

To also rebuild the HTML site after sync, change the command to:

```bash
llmwiki sync && llmwiki build
```
