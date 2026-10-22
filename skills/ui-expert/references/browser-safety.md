# Browser Safety

How to run a browser automation server without risking the operator's
machine. The rules are written per capability, so they hold for any open
browser MCP server; each server gets one row with its concrete flags.

## Capabilities every launch must have

| Capability | Why |
| --- | --- |
| **Launches its own browser** | Attaching drives the operator's real tabs, cookies and sessions; one bad call there breaks the browser they work in. |
| **Dedicated browser binary** | The daily browser carries extensions, sync and a profile that automation must never touch. |
| **Throwaway profile** | State from one run never leaks into the next, and nothing persists after the browser closes. |
| **Headless** | No window to steal focus, nothing the operator can click into by accident. |
| **No telemetry or data egress** | Usage statistics, field-data lookups and update checks send data out of the machine; verification needs none of them. |
| **Pinned version, 7 days old or more** | An unpinned server changes under you; a release younger than a week has had no time to be pulled for a regression or a compromise. |

## Server table

| Server | Launch flags (all required) | Forbidden flags | Environment |
| --- | --- | --- | --- |
| `chrome-devtools-mcp` | `--executablePath <chromium>` `--isolated` `--headless` `--no-usage-statistics` `--no-performance-crux` | `--browserUrl` / `--browser-url` / `-u`, `--wsEndpoint` / `--ws-endpoint` / `-w`, `--autoConnect` / `--auto-connect`, `--userDataDir` pointing at a real profile | `CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS=1` |

Reference command shape (version and path are examples, not the rule):

```bash
npx -y chrome-devtools-mcp@<pinned> \
  --executablePath <dedicated-chromium> \
  --isolated --headless --no-usage-statistics --no-performance-crux
```

`--isolated` deletes the profile when the browser closes; without it the
server keeps a persistent profile under the user's cache directory.
`--no-performance-crux` stops performance tools from sending page URLs to
an external field-data API. A `--config` file can set any flag, including
attach mode: the agent must not be able to write it.

To add a server, add a row: the flags that give it each capability above
and the flags that break one. The rules do not change.

## Picking the pin

Choose the version when the configuration is written, not at run time:
look up the release date on the package registry
(`npm view <package> time --json`), take the newest release at least 7
days old, and write that exact version into the command. Re-pin
deliberately, never by letting `@latest` float.

## The dedicated browser

Install a Chromium used only for automation and pass its path. Common
locations (examples):

| System | Typical path |
| --- | --- |
| Linux | `/usr/bin/chromium`, `/usr/bin/chromium-browser` |
| macOS | `/Applications/Chromium.app/Contents/MacOS/Chromium` |
| Windows | `%LOCALAPPDATA%\Chromium\Application\chrome.exe` |

Never point `--executablePath` at the browser the operator uses every
day, and never at a binary whose profile directory is the operator's.

## Auditing what is running

`jacazul ui doctor` reports running servers with their parent and age,
orphans, attach mode, unpinned versions, missing launch flags, telemetry
watchdogs, remote-debugging ports and whether a dedicated Chromium is
installed, on Linux, macOS and Windows. It never writes and never kills;
it prints the commands to run after you confirm. Exit status: 0 clean,
1 something needs the operator, 2 the doctor could not look. It cannot
see another process's environment, so `CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS`
stays a configuration check.

Without the launcher, the same audit by hand:

| System | Server processes | Remote-debugging listeners |
| --- | --- | --- |
| Linux | `pgrep -af chrome-devtools-mcp` | `ss -ltnp \| grep -E ':922[0-9]'` |
| macOS | `ps -axo pid,ppid,etime,command \| grep [c]hrome-devtools-mcp` | `lsof -nP -iTCP -sTCP:LISTEN \| grep -E ':922[0-9]'` |
| Windows | `Get-CimInstance Win32_Process \| Where-Object CommandLine -match 'chrome-devtools-mcp'` | `Get-NetTCPConnection -State Listen \| Where-Object LocalPort -in 9222..9229` |

Read each command line for the forbidden flags and the missing launch
flags. A server whose parent is gone (parent PID 1, or a parent that no
longer exists) is an orphan left by a session that ended.

## Cleaning up

Report and wait. Print the exact command for the operator (`kill <pid>`
on Linux and macOS, `Stop-Process -Id <pid>` on Windows) and run it only
after an explicit yes. Then fix the configuration that started the
process, or it comes back with the next session.
