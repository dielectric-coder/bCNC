# Qt Main Window - QMainWindow replacing Application(Tk, Sender)
#
# Provides menu bar, toolbar, dock panels (control, terminal),
# central canvas, and status bar.

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QStatusBar,
    QLabel, QProgressBar, QMenuBar, QToolBar,
    QFileDialog, QMessageBox,
)

import Utils
from CNC import CNC

from .signals import AppSignals
from .canvas_widget import CanvasPanel
from .control_panel import ControlPanel
from .terminal_panel import TerminalPanel
from .serial_monitor import SerialMonitor
from .autolevel_panel import AutolevelPanel
from .editor_panel import EditorPanel


FILETYPES_FILTER = (
    "All accepted (*.ngc *.cnc *.nc *.tap *.gcode *.dxf *.probe "
    "*.orient *.stl *.svg);;"
    "G-Code (*.ngc *.cnc *.nc *.tap *.gcode);;"
    "DXF (*.dxf);;"
    "SVG (*.svg);;"
    "Probe (*.probe *.xyz);;"
    "Orient (*.orient);;"
    "STL (*.stl);;"
    "All files (*)"
)


class MainWindow(QMainWindow):
    """Main application window.

    Owns the Sender, wires Qt signals, and manages layout.
    Does NOT inherit from Sender — uses composition instead.
    """

    def __init__(self, sender):
        super().__init__()
        self.sender = sender
        self.signals = AppSignals()

        self.setWindowTitle(
            f"{Utils.__prg__} {Utils.__version__} [Qt]")
        self.resize(1200, 800)

        # Wire Sender UI callbacks
        sender._ui_set_status = lambda msg: self.signals.status_message.emit(msg)
        sender._ui_disable = lambda: self._set_widgets_enabled(False)
        sender._ui_enable = lambda: self._set_widgets_enabled(True)
        sender._ui_show_info = lambda title, msg: QMessageBox.information(
            self, title, msg)

        # --- Central widget: Canvas ---
        self.canvas_panel = CanvasPanel(self.signals)
        self.setCentralWidget(self.canvas_panel)

        # --- Dock: Control panel (left) ---
        self.control_dock = QDockWidget("Control", self)
        self.control_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)
        self.control_panel = ControlPanel(sender, self.signals)
        self.control_dock.setWidget(self.control_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.control_dock)

        # --- Dock: Terminal panel (bottom) ---
        self.terminal_dock = QDockWidget("Terminal", self)
        self.terminal_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.TopDockWidgetArea)
        self.terminal_panel = TerminalPanel(sender, self.signals)
        self.terminal_dock.setWidget(self.terminal_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,
                           self.terminal_dock)

        # --- Dock: Autolevel panel (right) ---
        self.autolevel_dock = QDockWidget("Autolevel", self)
        self.autolevel_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)
        self.autolevel_panel = AutolevelPanel(sender, self.signals)
        self.autolevel_dock.setWidget(self.autolevel_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,
                           self.autolevel_dock)

        # --- Dock: Editor panel (right, tabified with autolevel) ---
        self.editor_dock = QDockWidget("Editor", self)
        self.editor_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea)
        self.editor_panel = EditorPanel(sender.gcode, self.signals)
        self.editor_dock.setWidget(self.editor_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,
                           self.editor_dock)
        self.tabifyDockWidget(self.autolevel_dock, self.editor_dock)
        self.editor_dock.raise_()

        # --- Status bar ---
        self._setup_statusbar()

        # --- Menu bar ---
        self._setup_menubar()

        # --- Toolbar ---
        self._setup_toolbar()

        # --- Serial monitor ---
        self.serial_monitor = SerialMonitor(sender, self.signals)
        self.serial_monitor.start()

        # --- Wire signals ---
        self.signals.status_message.connect(self._on_status_message)
        self.signals.canvas_coords.connect(self._on_canvas_coords)
        self.signals.run_progress.connect(self._on_run_progress)
        self.signals.buffer_fill.connect(self._on_buffer_fill)
        self.signals.draw_requested.connect(self._on_draw)
        self.signals.position_updated.connect(
            self.canvas_panel.update_gantry)

        # Execution signals
        self.signals.run_requested.connect(self._on_run)
        self.signals.stop_requested.connect(self._on_stop)
        self.signals.pause_requested.connect(self._on_pause)

        # Editor signals
        self.signals.file_loaded.connect(self.editor_panel.fill)

        # Selection sync: editor → canvas, canvas → editor
        self.signals.selection_changed.connect(
            self._on_editor_selection_changed)
        self.signals.canvas_block_clicked.connect(
            self._on_canvas_block_clicked)

        # Probe / autolevel signals
        self.signals.draw_probe.connect(self._on_draw_probe)
        self.signals.serial_run_end.connect(self._on_run_end)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self._status_label = QLabel("Ready")
        self.statusbar.addWidget(self._status_label, 1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setMaximumHeight(16)
        self._progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self._progress_bar)

        self._buffer_bar = QProgressBar()
        self._buffer_bar.setMaximumWidth(80)
        self._buffer_bar.setMaximumHeight(16)
        self._buffer_bar.setRange(0, 100)
        self._buffer_bar.setFormat("%v%")
        self._buffer_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self._buffer_bar)

        self._coord_x = QLabel("X: 0.000")
        self._coord_x.setMinimumWidth(80)
        self._coord_x.setStyleSheet("color: darkred;")
        self._coord_y = QLabel("Y: 0.000")
        self._coord_y.setMinimumWidth(80)
        self._coord_y.setStyleSheet("color: darkred;")
        self._coord_z = QLabel("Z: 0.000")
        self._coord_z.setMinimumWidth(80)
        self._coord_z.setStyleSheet("color: darkred;")
        self.statusbar.addPermanentWidget(self._coord_x)
        self.statusbar.addPermanentWidget(self._coord_y)
        self.statusbar.addPermanentWidget(self._coord_z)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def _setup_menubar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Machine menu
        machine_menu = menubar.addMenu("&Machine")

        connect_action = QAction("&Connect/Disconnect", self)
        connect_action.triggered.connect(
            self.control_panel.connection._on_connect)
        machine_menu.addAction(connect_action)

        machine_menu.addSeparator()

        home_action = QAction("&Home", self)
        home_action.triggered.connect(lambda: self.sender.home())
        machine_menu.addAction(home_action)

        unlock_action = QAction("&Unlock", self)
        unlock_action.triggered.connect(lambda: self.sender.unlock())
        machine_menu.addAction(unlock_action)

        reset_action = QAction("Soft &Reset", self)
        reset_action.triggered.connect(lambda: self.sender.softReset())
        machine_menu.addAction(reset_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        view_menu.addAction(self.control_dock.toggleViewAction())
        view_menu.addAction(self.terminal_dock.toggleViewAction())
        view_menu.addAction(self.autolevel_dock.toggleViewAction())
        view_menu.addAction(self.editor_dock.toggleViewAction())

        view_menu.addSeparator()

        fit_action = QAction("&Fit to Content", self)
        fit_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_action.triggered.connect(self.canvas_panel.view.fit_to_content)
        view_menu.addAction(fit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        undo_action = QAction("&Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._on_undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("&Redo", self)
        redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        redo_action.triggered.connect(self._on_redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        cut_action = QAction("Cu&t", self)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        cut_action.triggered.connect(self.editor_panel.cut)
        edit_menu.addAction(cut_action)

        copy_action = QAction("&Copy", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.editor_panel.copy)
        edit_menu.addAction(copy_action)

        paste_action = QAction("&Paste", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self.editor_panel.paste)
        edit_menu.addAction(paste_action)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def _setup_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open", self)
        open_action.triggered.connect(self._on_open_file)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        run_action = QAction("Run", self)
        run_action.triggered.connect(self.signals.run_requested.emit)
        toolbar.addAction(run_action)

        pause_action = QAction("Pause", self)
        pause_action.triggered.connect(self.signals.pause_requested.emit)
        toolbar.addAction(pause_action)

        stop_action = QAction("Stop", self)
        stop_action.triggered.connect(self.signals.stop_requested.emit)
        toolbar.addAction(stop_action)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def _on_open_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open G-Code File", "", FILETYPES_FILTER)
        if filename:
            self.sender.load(filename)
            self.signals.file_loaded.emit(filename)
            self._on_draw()

    def _on_save_file(self):
        if self.sender.gcode.filename:
            self.sender.save(self.sender.gcode.filename)
        else:
            self._on_save_as()

    def _on_save_as(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save G-Code File", "", FILETYPES_FILTER)
        if filename:
            self.sender.save(filename)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _on_run(self):
        if self.sender.serial is None:
            QMessageBox.warning(self, "Not Connected",
                                "Please connect to a machine first.")
            return
        self.sender.run()

    def _on_stop(self):
        self.sender.stopRun()

    def _on_pause(self):
        self.sender.pause()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------
    def _on_status_message(self, msg):
        self._status_label.setText(msg)

    def _on_canvas_coords(self, x, y, z):
        fmt = "%.3f" if not CNC.inch else "%.4f"
        self._coord_x.setText(f"X: {fmt % x}")
        self._coord_y.setText(f"Y: {fmt % y}")
        self._coord_z.setText(f"Z: {fmt % z}")

    def _on_run_progress(self, completed, total):
        if total > 0:
            self._progress_bar.setVisible(True)
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(completed)
        else:
            self._progress_bar.setVisible(False)

    def _on_buffer_fill(self, percent):
        self._buffer_bar.setVisible(True)
        self._buffer_bar.setValue(int(percent))

    def _on_undo(self):
        self.sender.gcode.undo()
        self.editor_panel.fill()
        self._on_draw()

    def _on_redo(self):
        self.sender.gcode.redo()
        self.editor_panel.fill()
        self._on_draw()

    def _on_editor_selection_changed(self):
        """Editor selection changed → highlight on canvas."""
        blocks = self.editor_panel.get_selected_blocks()
        self.canvas_panel.highlight_selection(blocks)

    def _on_canvas_block_clicked(self, bid, ctrl):
        """Canvas path clicked → select in editor."""
        if ctrl:
            self.editor_panel.add_to_selection([bid])
        else:
            self.editor_panel.select_blocks([bid])

    def _on_draw(self):
        """Rebuild the canvas from current gcode."""
        self.canvas_panel.rebuild(self.sender.gcode, self.sender.cnc)
        # Re-apply selection highlight (rebuild clears all scene state)
        blocks = self.editor_panel.get_selected_blocks()
        if blocks:
            self.canvas_panel.highlight_selection(blocks)

    def _on_draw_probe(self):
        """Draw probe overlay on canvas."""
        self.canvas_panel.draw_probe(self.sender.gcode.probe)

    def _on_run_end(self, msg):
        """Re-enable UI when a run (including probe scan) ends."""
        self._set_widgets_enabled(True)
        self._progress_bar.setVisible(False)
        self._buffer_bar.setVisible(False)

    # ------------------------------------------------------------------
    # Widget enable/disable for run mode
    # ------------------------------------------------------------------
    def _set_widgets_enabled(self, enabled):
        self.control_panel.setEnabled(enabled)
        self.autolevel_panel.setEnabled(enabled)
        self.editor_panel.setEnabled(enabled)
        self.menuBar().setEnabled(enabled)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        """Clean shutdown: save config, stop serial monitor, close connection."""
        self.autolevel_panel.saveConfig()
        self.serial_monitor.stop()
        self.sender.quit()
        if self.sender.serial is not None:
            self.sender.close()
        event.accept()
