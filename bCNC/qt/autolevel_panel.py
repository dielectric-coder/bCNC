# Qt Autolevel Panel - port of ProbePage.py ProbeCommonFrame + AutolevelFrame
#
# Single panel combining probe settings, grid configuration,
# and autolevel action buttons.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QDoubleSpinBox,
    QSpinBox, QComboBox, QMessageBox,
)

import Utils
from CNC import CNC


PROBE_CMD = [
    "G38.2 stop on contact else error",
    "G38.3 stop on contact",
    "G38.4 stop on loss contact else error",
    "G38.5 stop on loss contact",
]


class AutolevelPanel(QWidget):
    """Autolevel configuration and control panel.

    Combines probe settings (feed, TLO, command), grid configuration
    (X/Y min/max/N, Z min/max), and action buttons (scan, autolevel, etc.).
    """

    def __init__(self, sender, signals, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.signals = signals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Probe Settings group ---
        probe_group = QGroupBox("Probe Settings")
        pg = QGridLayout(probe_group)

        pg.addWidget(QLabel("Fast Probe Feed:"), 0, 0)
        self.fast_probe_feed = QDoubleSpinBox()
        self.fast_probe_feed.setRange(0.1, 10000)
        self.fast_probe_feed.setDecimals(1)
        pg.addWidget(self.fast_probe_feed, 0, 1)

        pg.addWidget(QLabel("Probe Feed:"), 1, 0)
        self.probe_feed = QDoubleSpinBox()
        self.probe_feed.setRange(0.1, 10000)
        self.probe_feed.setDecimals(1)
        pg.addWidget(self.probe_feed, 1, 1)

        pg.addWidget(QLabel("TLO:"), 2, 0)
        tlo_row = QHBoxLayout()
        self.tlo = QDoubleSpinBox()
        self.tlo.setRange(-1000, 1000)
        self.tlo.setDecimals(3)
        tlo_row.addWidget(self.tlo)
        self.tlo_set_btn = QPushButton("Set")
        self.tlo_set_btn.clicked.connect(self._on_tlo_set)
        tlo_row.addWidget(self.tlo_set_btn)
        pg.addLayout(tlo_row, 2, 1)

        pg.addWidget(QLabel("Probe Command:"), 3, 0)
        self.probe_cmd = QComboBox()
        self.probe_cmd.addItems(PROBE_CMD)
        pg.addWidget(self.probe_cmd, 3, 1)

        pg.setColumnStretch(1, 1)
        layout.addWidget(probe_group)

        # --- Grid Configuration group ---
        grid_group = QGroupBox("Grid Configuration")
        gg = QGridLayout(grid_group)

        # Header
        for col, label in enumerate(["", "Min", "Max", "Step", "N"], 0):
            gg.addWidget(QLabel(label), 0, col)

        # X row
        gg.addWidget(QLabel("X:"), 1, 0)
        self.x_min = QDoubleSpinBox()
        self.x_min.setRange(-10000, 10000)
        self.x_min.setDecimals(3)
        gg.addWidget(self.x_min, 1, 1)
        self.x_max = QDoubleSpinBox()
        self.x_max.setRange(-10000, 10000)
        self.x_max.setDecimals(3)
        gg.addWidget(self.x_max, 1, 2)
        self.x_step = QLabel("")
        self.x_step.setStyleSheet("color: darkblue; background: #e8e8e8;")
        gg.addWidget(self.x_step, 1, 3)
        self.x_n = QSpinBox()
        self.x_n.setRange(2, 1000)
        self.x_n.valueChanged.connect(self._on_grid_changed)
        gg.addWidget(self.x_n, 1, 4)

        # Y row
        gg.addWidget(QLabel("Y:"), 2, 0)
        self.y_min = QDoubleSpinBox()
        self.y_min.setRange(-10000, 10000)
        self.y_min.setDecimals(3)
        gg.addWidget(self.y_min, 2, 1)
        self.y_max = QDoubleSpinBox()
        self.y_max.setRange(-10000, 10000)
        self.y_max.setDecimals(3)
        gg.addWidget(self.y_max, 2, 2)
        self.y_step = QLabel("")
        self.y_step.setStyleSheet("color: darkblue; background: #e8e8e8;")
        gg.addWidget(self.y_step, 2, 3)
        self.y_n = QSpinBox()
        self.y_n.setRange(2, 1000)
        self.y_n.valueChanged.connect(self._on_grid_changed)
        gg.addWidget(self.y_n, 2, 4)

        # Z row (only min/max)
        gg.addWidget(QLabel("Z:"), 3, 0)
        self.z_min = QDoubleSpinBox()
        self.z_min.setRange(-10000, 10000)
        self.z_min.setDecimals(3)
        gg.addWidget(self.z_min, 3, 1)
        self.z_max = QDoubleSpinBox()
        self.z_max.setRange(-10000, 10000)
        self.z_max.setDecimals(3)
        gg.addWidget(self.z_max, 3, 2)

        gg.setColumnStretch(1, 2)
        gg.setColumnStretch(2, 2)
        gg.setColumnStretch(3, 1)
        layout.addWidget(grid_group)

        # --- Action Buttons group ---
        action_group = QGroupBox("Actions")
        ag = QGridLayout(action_group)

        self.btn_get_margins = QPushButton("Get Margins")
        self.btn_get_margins.setToolTip("Get margins from gcode file")
        self.btn_get_margins.clicked.connect(self._on_get_margins)
        ag.addWidget(self.btn_get_margins, 0, 0)

        self.btn_scan_margins = QPushButton("Scan Margins")
        self.btn_scan_margins.setToolTip("Scan autolevel margins")
        self.btn_scan_margins.clicked.connect(self._on_scan_margins)
        ag.addWidget(self.btn_scan_margins, 0, 1)

        self.btn_set_zero = QPushButton("Set Zero")
        self.btn_set_zero.setToolTip(
            "Set current XY location as autoleveling Z-zero")
        self.btn_set_zero.clicked.connect(self._on_set_zero)
        ag.addWidget(self.btn_set_zero, 1, 0)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setToolTip("Clear probe data")
        self.btn_clear.clicked.connect(self._on_clear)
        ag.addWidget(self.btn_clear, 1, 1)

        self.btn_autolevel = QPushButton("Autolevel")
        self.btn_autolevel.setToolTip(
            "Modify G-Code to match autolevel")
        self.btn_autolevel.clicked.connect(self._on_autolevel)
        ag.addWidget(self.btn_autolevel, 2, 0)

        self.btn_scan = QPushButton("Scan")
        self.btn_scan.setToolTip(
            "Scan probed area for level information on Z plane")
        self.btn_scan.clicked.connect(self._on_scan)
        ag.addWidget(self.btn_scan, 2, 1)

        layout.addWidget(action_group)

        # --- Info label ---
        self.info_label = QLabel("No probe data")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        layout.addStretch()

        # Wire signals
        self.signals.probe_updated.connect(self._on_probe_updated)

        # Connect spinbox changes for step recalc
        self.x_min.valueChanged.connect(self._on_grid_changed)
        self.x_max.valueChanged.connect(self._on_grid_changed)
        self.y_min.valueChanged.connect(self._on_grid_changed)
        self.y_max.valueChanged.connect(self._on_grid_changed)

        self.loadConfig()

    # ------------------------------------------------------------------
    # Config persistence (matches Tkinter [Probe] section keys)
    # ------------------------------------------------------------------
    def loadConfig(self):
        self.fast_probe_feed.setValue(
            Utils.getFloat("Probe", "fastfeed", 100.0))
        self.probe_feed.setValue(
            Utils.getFloat("Probe", "feed", 10.0))
        self.tlo.setValue(
            Utils.getFloat("Probe", "tlo", 0.0))

        cmd = Utils.getStr("Probe", "cmd")
        for i, p in enumerate(PROBE_CMD):
            if p.split()[0] == cmd:
                self.probe_cmd.setCurrentIndex(i)
                break

        self.x_min.setValue(Utils.getFloat("Probe", "xmin", 0.0))
        self.x_max.setValue(Utils.getFloat("Probe", "xmax", 10.0))
        self.y_min.setValue(Utils.getFloat("Probe", "ymin", 0.0))
        self.y_max.setValue(Utils.getFloat("Probe", "ymax", 10.0))
        self.z_min.setValue(Utils.getFloat("Probe", "zmin", -10.0))
        self.z_max.setValue(Utils.getFloat("Probe", "zmax", 3.0))
        self.x_n.setValue(max(2, Utils.getInt("Probe", "xn", 5)))
        self.y_n.setValue(max(2, Utils.getInt("Probe", "yn", 5)))

        self._update_steps()

    def saveConfig(self):
        Utils.setFloat("Probe", "fastfeed", self.fast_probe_feed.value())
        Utils.setFloat("Probe", "feed", self.probe_feed.value())
        Utils.setFloat("Probe", "tlo", self.tlo.value())
        Utils.setFloat("Probe", "cmd",
                        self.probe_cmd.currentText().split()[0])
        Utils.setFloat("Probe", "xmin", self.x_min.value())
        Utils.setFloat("Probe", "xmax", self.x_max.value())
        Utils.setInt("Probe", "xn", self.x_n.value())
        Utils.setFloat("Probe", "ymin", self.y_min.value())
        Utils.setFloat("Probe", "ymax", self.y_max.value())
        Utils.setInt("Probe", "yn", self.y_n.value())
        Utils.setFloat("Probe", "zmin", self.z_min.value())
        Utils.setFloat("Probe", "zmax", self.z_max.value())

    # ------------------------------------------------------------------
    # Push UI values into CNC.vars and Probe object
    # ------------------------------------------------------------------
    def _apply_to_probe(self):
        """Push current UI values into CNC.vars and the Probe object.

        Returns an error string or None on success.
        """
        probe = self.sender.gcode.probe

        CNC.vars["fastprbfeed"] = self.fast_probe_feed.value()
        CNC.vars["prbfeed"] = self.probe_feed.value()
        CNC.vars["prbcmd"] = self.probe_cmd.currentText().split()[0]

        try:
            probe.xmin = self.x_min.value()
            probe.xmax = self.x_max.value()
            probe.xn = max(2, self.x_n.value())
            probe.xstep()
        except Exception:
            return "Invalid X probing region"

        if probe.xmin >= probe.xmax:
            return "Invalid X range [xmin >= xmax]"

        try:
            probe.ymin = self.y_min.value()
            probe.ymax = self.y_max.value()
            probe.yn = max(2, self.y_n.value())
            probe.ystep()
        except Exception:
            return "Invalid Y probing region"

        if probe.ymin >= probe.ymax:
            return "Invalid Y range [ymin >= ymax]"

        try:
            probe.zmin = self.z_min.value()
            probe.zmax = self.z_max.value()
        except Exception:
            return "Invalid Z probing region"

        if probe.zmin >= probe.zmax:
            return "Invalid Z range [zmin >= zmax]"

        return None

    def _update_steps(self):
        """Recalculate and display step sizes."""
        try:
            xrange = self.x_max.value() - self.x_min.value()
            xn = max(2, self.x_n.value())
            self.x_step.setText(f"{xrange / (xn - 1):.5g}")
        except Exception:
            self.x_step.setText("")

        try:
            yrange = self.y_max.value() - self.y_min.value()
            yn = max(2, self.y_n.value())
            self.y_step.setText(f"{yrange / (yn - 1):.5g}")
        except Exception:
            self.y_step.setText("")

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------
    def _on_grid_changed(self):
        self._update_steps()

    def _on_tlo_set(self):
        try:
            CNC.vars["TLO"] = self.tlo.value()
            cmd = f"G43.1Z{self.tlo.value()}"
            self.sender.sendGCode(cmd)
        except Exception:
            pass

    def _on_get_margins(self):
        self.x_min.setValue(CNC.vars.get("xmin", 0.0))
        self.x_max.setValue(CNC.vars.get("xmax", 10.0))
        self.y_min.setValue(CNC.vars.get("ymin", 0.0))
        self.y_max.setValue(CNC.vars.get("ymax", 10.0))
        self._update_steps()
        self._request_draw_probe()

    def _on_scan_margins(self):
        err = self._apply_to_probe()
        if err:
            QMessageBox.critical(self, "Probe Error", err)
            return
        lines = self.sender.gcode.probe.scanMargins()
        if not self.sender.runLines(lines):
            QMessageBox.warning(self, "Cannot Run",
                                "Not connected or already running.")

    def _on_set_zero(self):
        x = CNC.vars.get("wx", 0.0)
        y = CNC.vars.get("wy", 0.0)
        self.sender.gcode.probe.setZero(x, y)
        self._request_draw_probe()

    def _on_clear(self):
        ans = QMessageBox.question(
            self, "Clear Autolevel",
            "Delete all autolevel information?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.sender.gcode.probe.clear()
        self._request_draw_probe()

    def _on_autolevel(self):
        probe = self.sender.gcode.probe
        if probe.isEmpty():
            QMessageBox.warning(self, "No Probe Data",
                                "Run a probe scan first.")
            return
        # Apply to all enabled blocks
        items = [i for i, b in enumerate(self.sender.gcode.blocks)
                 if b.enable]
        if not items:
            QMessageBox.warning(self, "No Blocks",
                                "No enabled gcode blocks found.")
            return
        self.sender.gcode.autolevel(items)
        self.signals.draw_requested.emit()

    def _on_scan(self):
        err = self._apply_to_probe()
        if err:
            QMessageBox.critical(self, "Probe Error", err)
            return
        self._request_draw_probe()
        lines = self.sender.gcode.probe.scan()
        if not self.sender.runLines(lines):
            QMessageBox.warning(self, "Cannot Run",
                                "Not connected or already running.")

    def _on_probe_updated(self):
        """Called when the serial monitor detects new probe data."""
        probe = self.sender.gcode.probe
        total = probe.xn * probe.yn
        got = len(probe.points)
        self.info_label.setText(f"{got} / {total} points")
        self._request_draw_probe()

    def _request_draw_probe(self):
        self.signals.draw_probe.emit()
