# bCNC — Project Instructions for Claude

## Project Overview

CNC controller GUI app (Python 3.8+). Originally Tkinter, actively migrating to Qt (PySide6).
Forked from [vlachoudis/bCNC](https://github.com/vlachoudis/bCNC).

- **Tkinter entry:** `bCNC/bmain.py` — `Application(Tk, Sender)` (inheritance)
- **Qt entry:** `bCNC/qt/app.py` — `MainWindow` owns `Sender` (composition)
- **Launch Qt:** `python -m bCNC.qt.app`

## Critical Import Order

`Helpers.py` **must** be imported before `Utils.py` — it installs the `_()` builtin via `gettext.install()`. Every Qt file that uses `_()` relies on this.

```python
import Helpers  # FIRST — installs _() builtin
import Utils
from CNC import CNC
```

`Utils` → `Ribbon` → `tkExtra` → `bFileDialog` chain still requires tkinter at import time. Qt modules avoid importing Utils at module level where possible.

## Architecture

### Composition Pattern (Qt)

```
QApplication
  └─ MainWindow(QMainWindow)
       ├─ self.sender = Sender()        # backend (serial, G-code queue)
       ├─ self.signals = AppSignals()    # central signal hub (45+ signals)
       ├─ self.serial_monitor            # QTimer → polls Sender → emits signals
       ├─ self.canvas_panel              # central widget (QGraphicsView)
       ├─ self.control_panel             # left dock (DRO, connection, jog)
       ├─ self.probe_panel               # right dock (5 tabs: Probe/Autolevel/Camera/Orient/Tool)
       ├─ self.editor_panel              # right dock (QTreeView block/line editor)
       ├─ self.tools_panel               # right dock (plugins, CAM ops)
       └─ self.terminal_panel            # bottom dock (serial log, command entry)
```

### CNC.vars — Global State Bus

`CNC.vars` is a class-level dict on `CNC` (CNC.py ~line 681). All machine state flows through it:
- Sender's serial thread **writes** (from GRBL responses)
- SerialMonitor **reads** and emits Qt signals
- UI panels **read** in signal handlers, **write** before sending commands

Key vars: `wx/wy/wz` (work pos), `mx/my/mz` (machine pos), `state`, `prbx/prby/prbz`, `prbfeed`, `prbcmd`, `TLO`, `safe`

### Signal Flow

No direct panel-to-panel communication. Everything goes through `AppSignals`:

```
Sender (backend thread) → SerialMonitor._poll() (QTimer 200ms) → Qt signals → panels
```

## Key File Locations

| Layer | Files |
|-------|-------|
| Backend (toolkit-independent) | `Sender.py`, `CNC.py`, `EventBus.py`, `MachineState.py`, `CommandDispatcher.py`, `FileManager.py` |
| Canvas math (toolkit-independent) | `ViewTransform.py`, `PathGeometry.py`, `SceneGraph.py` |
| Qt UI | `qt/{app,signals,main_window,canvas_widget,control_panel,terminal_panel,serial_monitor,editor_panel,editor_model,probe_panel,autolevel_panel,camera_overlay,camera_tab,orient_overlay,orient_tab,tools_manager,tools_panel}.py` |
| Tkinter UI (original) | `bmain.py`, `ControlPage.py`, `EditorPage.py`, `ProbePage.py`, `FilePage.py`, `TerminalPage.py`, `ToolsPage.py`, `CNCCanvas.py` |
| Controllers | `controllers/{GRBL0,GRBL1,SMOOTHIE,G2Core}.py` |
| Plugins | `plugins/` (42+ CAM/utility plugins) |

## Conventions

### Adding a New Panel/Tab

1. Create `bCNC/qt/my_panel.py`
2. Constructor: `__init__(self, sender, signals, parent=None)`
3. Connect to signals in constructor
4. Add `loadConfig()` / `saveConfig()` using `Utils.getFloat/setFloat` etc.
5. In `main_window.py`: create dock, add to View menu, wire signals, save on close

### Adding a New Signal

1. Add to `AppSignals` in `signals.py` with a comment
2. Emit from the appropriate source (usually `serial_monitor.py` or a panel)
3. Connect in the consuming panel's constructor

### Naming

- Files: `snake_case.py`
- Classes: `PascalCase` — panels end with `Panel` or `Tab`
- Signals: `snake_case` matching the Tkinter event they replace
- Handlers: `_on_<action>` for signal/button slots
- Config keys: match existing Tkinter keys in `[Section]` for compatibility

### Sending G-code

```python
self.sender.sendGCode("G0 X10 Y20")             # single command
self.sender.runLines(["G91", "G38.2 Z-10 F50"])  # multi-line sequence
```

Special prefixes in runLines: `%wait`, `%global var; var=expr`, `%update var`, `[var]` substitution.

## Testing

### Syntax check
```bash
python -c "import py_compile; py_compile.compile('bCNC/qt/my_file.py', doraise=True)"
```

### Import check
```bash
PYTHONPATH=bCNC:bCNC/lib python -c "import Helpers; from bCNC.qt.my_module import MyClass; print('OK')"
```

### Full integration test
```bash
PYTHONPATH=bCNC:bCNC/lib:bCNC/controllers:bCNC/plugins python -c "
import os; os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import Helpers, Utils
# Patch config for missing sections:
_orig = Utils.config.items
Utils.config.items = lambda s='DEFAULT', **kw: [] if s != 'DEFAULT' and not Utils.config.has_section(s) else _orig(s, **kw)
_og = Utils.config.get
Utils.config.get = lambda s, o, **kw: (_og(s, o, **kw) if Utils.config.has_section(s) else (Utils.config.add_section(s) or _og(s, o, **kw)))
from PySide6.QtWidgets import QApplication; import sys
app = QApplication(sys.argv)
from Sender import Sender; sender = Sender()
from qt.main_window import MainWindow; w = MainWindow(sender)
print('OK')
"
```

### Launch the app
```bash
python -m bCNC.qt.app
```

## Remaining Gaps (Tkinter → Qt)

All major UI features have been ported. The advanced toolbar/ribbon system
(CNCRibbon with configurable groups) is a lower-priority gap tracked in DEV-GUIDE.md.

## Documentation Files

- `CHANGELOG.md` — feature changelog (update when adding Qt features)
- `USER-GUIDE.md` — end-user guide for the Qt interface
- `DEV-GUIDE.md` — developer guide with architecture and conventions
- `README.md` — project overview (has Qt section near bottom)

Update all four when adding significant new features.
