# Imou Ranger Dual API Control

Control motion and human detection for **both lenses** of an Imou Ranger Dual camera through the Imou Open Platform IoT API. Run it from Python or from Android using Termux + MacroDroid; no Home Assistant or always-on server required.

**Tested with:** Imou Ranger Dual 6MP, model `IPC-S2X-6M0WED`, channels `0` (PT/mobile lens) and `1` (fixed lens). Compatibility with other models/firmware is **not established**.

## What it controls

| Channel | IoT property ref | Function |
|---|---|---|
| 0 and 1 | `108800` | Motion detection |
| 0 and 1 | `18200` | Human detection |

These property references were verified by comparing the API values against the switches in Imou Life, and by checking that a write was reflected in Imou Life. The script re-reads all four states after writes and exits nonzero when verification fails.

**Out of scope:** Imou Life notification preferences, siren, recording settings, privacy mode, animal detection and smart tracking. Leave Imou Life notifications enabled if you want alerts when detection is enabled.

## Requirements

- Python 3 (standard library only)
- Imou Open Platform application with `AppId` / `AppSecret`, authorized camera and available API quota
- Internet access
- The API host configured for your own data center. The script currently defaults to **Central Europe**: `https://openapi-fk.easy4ip.com`. For other regions verify and change `HOST` in `imou_control.py` before running.

## Setup (Windows, Linux or macOS)

1. Clone/download this repository.
2. Copy `.env.example` to `.env` in the same directory as `imou_control.py`.
3. Fill in `IMOU_APP_ID`, `IMOU_APP_SECRET`, `IMOU_DEVICE_ID` with your own credentials and device serial number.
4. Run:

```sh
python imou_control.py state
python imou_control.py activate
python imou_control.py deactivate
```

Commands:

- `state`: reads motion/human states on both channels.
- `activate`: sets all four to `1` and verifies.
- `deactivate`: sets all four to `0` and verifies.

The script does not prompt for confirmation or credentials; this is intentional for automation. An error results in a nonzero exit status. A successful API response **alone** is not treated as proof: the script also checks returned property values.

## Android: Termux and MacroDroid

1. Install Termux and the compatible **Termux:Tasker** add-on (e.g., both from F-Droid), plus MacroDroid.
2. In Termux install Python: `pkg update && pkg install python`.
3. Copy `imou_control.py` and your private `.env` to `~/imou/`. Run `chmod 600 ~/imou/.env`.
4. Create the executable directory: `mkdir -p ~/.termux/tasker`.
5. Copy `termux/activate_imou` and `termux/deactivate_imou` to `~/.termux/tasker/`, and run `chmod 700 ~/.termux/tasker/*`.
6. Test in Termux: `~/.termux/tasker/activate_imou` and `~/.termux/tasker/deactivate_imou`.
7. Configure MacroDroid actions with Termux:Tasker using the instructions in [`macrodroid/README.md`](macrodroid/README.md).

The tasker scripts work in the background; no Imou Life UI automation is needed. Android may restrict background work through battery optimization policies, so test from a locked screen and after idle time.

## Security

- **Never commit `.env`, `AppSecret`, access tokens, or real camera serial numbers.** `.gitignore` excludes `.env` but cannot protect secrets already committed.
- Keep the private `.env` in Termux's app-private storage rather than the public Downloads folder.
- Treat the AppSecret as a sensitive credential; rotate it if ever exposed.
- Do not publish MacroDroid exports containing private variables, device IDs or credentials without inspecting them.
- Avoid running or advertising this as a certified security system. Network/API outages can interrupt commands or verification.

## API operations used

- `accessToken`
- `listDeviceDetailsByPage`
- `getIotDeviceProperties`
- `setIotDeviceProperties`

Imou Open Platform: https://open.imoulife.com/  
SDK reference: https://github.com/Imou-OpenPlatform/Py-Imou-Open-Api
