# Ultron-inspired capabilities ported to HOMER

This branch imports and adapts selected ideas and modules from [AbuZar-Ansarii/Ultron](https://github.com/AbuZar-Ansarii/Ultron) into HOMER's existing architecture.

## Source inventory
The upstream repository tree contains the standalone application (main.py/ui.py), 51 action modules, core services, dashboard assets, memory modules, plugin loader, presets, and dependency/setup files. The upstream README declares MIT, but a root LICENSE file was not present at the inspected main ref. Keep original source attribution on imported files and verify licensing with upstream owner before redistribution or shipping.

## Imported reference files
Selected source modules are preserved under `ultron_compat/` with per-file source URLs. These are not auto-discovered or executed by HOMER; Ultron's standalone action loader and callbacks are not compatible with HOMER's API.

## HOMER-native integrations
The new `app/tools/ultron_compat.py` adapter adds bounded utilities and is registered through HOMER's JSON-schema tool registry and MCP:
- Countdown timers (maximum 24 hours; in-process timer state only).
- Workspace preset suggestions (coding, study, creative, focus); URL opening requires explicit confirmation.
- Weather lookup through Open-Meteo.
- Search page opening with DuckDuckGo / Google.
- Read-only Git status for repositories under HOMER project or Documents.
- Text-file reading limited to HOMER project/Documents and fixed text extensions.
- Code-draft prompt creation only; no generated code is written or executed.

## Intentionally excluded / not ported as executable actions
- Self-modifying code, dynamic unreviewed code hot-loading, arbitrary PowerShell/cmd/bash execution.
- Biometric identification, webcam sentry, facial surveillance, or background screen/audio monitoring.
- Automatic locking, shutdown/reboot, destructive purge/cleanup, arbitrary process termination.
- Unrestricted file operations, auto-submitting forms, messaging/Telegram/Android commands.
- Drone/sub-agent swarm, crypto/price tracking, and unattended network scanning.
- Voice avatar/HUD replacement and Ultron assets; HOMER's original `homer_core.png` interface remains intact.
- God's Eye, ASCII face, and job-search features remain excluded.

These limitations are deliberate security, privacy, maintainability, and 4 GB RAM compatibility decisions.

## Validation status
Unit tests have been added. Full CI and runtime validation must pass before merge. Timer notifications, UI buttons for new actions, physical Windows integration, and low-memory performance are not claimed as verified by source import alone.
