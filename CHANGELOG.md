# bCNC changelog

There are too much commits, so i've created this brief overview of new features in bCNC.

## Qt Migration (in progress)

Backend decoupling and experimental Qt (PySide6) interface.

- Phase 1 — Decouple backend from Tkinter
  - EventBus: toolkit-independent pub/sub signal system
  - MachineState: observable wrapper around CNC.vars with thread-safe batch updates
  - CommandDispatcher: extracted GCode operation routing from bmain.py
  - FileManager: file I/O with EventBus notifications
  - Clean Sender: removed tkinter imports, replaced widget refs with UI callbacks

- Phase 2 — Extract portable canvas math
  - ViewTransform: 3D projection, coordinate transforms, zoom/fit
  - PathGeometry: grid, margins, axes, gantry geometry generation
  - SceneGraph: drawing primitives, scene layers, toolkit-independent renderer

- Phase 3 — Qt UI shell
  - Application entry point (`python -m bCNC.qt.app`)
  - Main window with dockable panels, menus, toolbar, status bar
  - Canvas: QGraphicsView-based CNC visualization with zoom/pan
  - Control panel: DRO, connection widget, jog controls, per-axis zero buttons
  - 6-axis (ABC) support: conditional DRO rows, jog buttons, and zero buttons
    when `enable6axisopt` is enabled in config (matches Tkinter 6-axis mode)
  - Terminal: serial log with command entry and history
  - Serial monitor: QTimer-based polling replacing Tk.after() loop
  - Editor: QTreeView with block/line hierarchy, context menu, clipboard, undo/redo
  - Probe panel: tabbed Probe/Autolevel/Tool with shared probe settings
  - Bidirectional selection sync between canvas and editor
  - Tools panel: full plugin system, tool database (Material/EndMill/Stock),
    CAM operations (Cut/Profile/Pocket/Drill/Tabs), and all 42+ external plugins
    with dynamic form builder and AppProxy for plugin compatibility
  - Camera tab: live OpenCV video overlay on canvas with cyan crosshair/circles,
    10 anchor modes (gantry-following + 9 viewport positions), camera-to-spindle
    offset registration, edge detection, frame freeze/save, coordinate switching
  - Orient tab: marker-based workpiece alignment — place marker pairs mapping
    machine positions to G-code design positions, least-squares solve for
    rotation + translation, canvas overlay with green/red crosses and error
    circles, apply orientation transform to selected blocks
  - Help menu: Documentation link (F1), Check for Updates (queries PyPI),
    About dialog
  - Pendant controls: Start/Stop Pendant in Machine menu with status messages

## 0.9.16
- Breaking changes:
  - Python3.8 is the lowest supported version. Starting bCNC with any prior version will fail. [#1719](https://github.com/vlachoudis/bCNC/issues/1719)
  - tkinter-gl is now required

## 0.9.15

- New features
  - Python 3 is (mostly) supported now #228
  - 6 axis support #1384
  - Can load SVG files (~only paths without transformations~ improved by tatarize, see
    wiki) #902 #1312
  - Can slice 3D meshes in STL and PLY formats (with minor limitations) #901
  - Can export 3D scan (autolevel probe) data in XYZ format suitable for meshlab poisson
    surface reconstruction
  - Support for helical and ramp cutting #590
  - New style of tabs implemented using "islands" with support for arbitrary shapes and
    pockets #220
  - Interactive value entry is now possible in g-code scripting #1256
  - DRO entry can now handle math formulas like: `sqrt(safe)+1`, `sin(pi**2)` or
    `3.175/2` #789
  - Drag Knife postprocessor and simulator plugin #975
  - Jog digitizer to create drawing by recording points while jogging #929
  - ArcFit plugin can interpolate lots of small segments using one long line/arc #921
  - DrillMark plugin to laser engrave markers for manual drilling #1128
  - More plugins: find center of path, close path, flatten path, scaling, randomize...
  - Start cycle can now be triggered by hardware button connected to arduino #885
- Improvements
  - Restructured UI #1057 and more
  - Better autodetection of serial ports (with device names, ids and without restarting
    bCNC)
  - Disabled blocks are commented-out in exported g-code #767
  - Lots of small improvements and experimental/development features like "trochoidal"
    (see git)
  - Added button to activate GRBL sleep mode (= disable motors) #1099
  - Added button to trigger GRBL door alarm
  - Added button to scan autoleveling margins (to see what will be probed)
  - Added some useful jog buttons
  - Added framework to show help text and images for each plugin #806
- Bug Fixes
  - Proper path direction detection and climb/conventional support #881
  - Proper handling of G91 when moving/rotating g-code #915
- Development and release engineering
  - Created PyPI package for bCNC #964
    - This means bCNC now installs as `pip install bCNC` and launches as
      `python -m bCNC` (see wiki!)
  - Added .bat script to build .exe package of bCNC #437
  - Support for individual motion controllers is now in form of separate plugins #1020
  - Added some basic Travis-CI tests #1117
- New bugs
  - We've hidden few secret bugs in our code as a challenge for you to find and report
    :-)

## 0.9.14

- Currently there is no changelog for 0.9.14 and older releases
- You can still find some info in github issues and history
  https://github.com/vlachoudis/bCNC/commits/master
