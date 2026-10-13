# MacroDroid + Termux:Tasker

Create two macros with an Android home-screen shortcut as trigger.

## Activate

1. In **Actions**, choose **Locale/Tasker Plugin** > **Termux:Tasker**.
2. Executable: `activate_imou` (the executable in `~/.termux/tasker/`).
3. Arguments: empty. **Execute in a terminal session**: unchecked.
4. **Wait for result for commands**: checked. Configure a nonzero timeout (e.g. 60 s) if available.
5. On the MacroDroid result-variable screen, enable **Block next actions until complete** and save **Exit Code** as a local integer variable `imou_exit_code`.
6. Add **If `imou_exit_code == 0`** > show notification: `Monitoring successfully activated.`.
7. **Else** > show notification: `Error activating monitoring`.

## Deactivate

Repeat with `deactivate_imou` and change notification texts to `Monitoring successfully deactivated.` / `Error disabling monitoring`.

You may use the same notification ID in both macros to replace the previous status notification. Make sure MacroDroid has permission to post notifications.

> Important: notifications represent the Python script's exit code and API verification, not an independent physical security guarantee. Test both macros with Imou Life before relying on them.

If the plugin cannot run, check that Termux and Termux:Tasker are installed from compatible sources, and grant MacroDroid the Android permission to run commands in the Termux environment when offered.
