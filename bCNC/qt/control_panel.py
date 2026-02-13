# Qt Control Panel - DRO, connection, jog controls
#
# Replaces parts of ControlPage with a compact QWidget providing
# digital readout (DRO), connection controls, and jog buttons.

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QComboBox, QDoubleSpinBox,
)

import Utils
from CNC import CNC
from Sender import NOT_CONNECTED, STATECOLOR


# Jog step sizes (mm)
JOG_STEPS = [0.001, 0.01, 0.1, 1.0, 5.0, 10.0, 50.0, 100.0]

DRO_FONT = QFont("Monospace", 14, QFont.Weight.Bold)


class DROWidget(QWidget):
    """Digital Readout showing work and machine positions."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        headers = ["", "Work", "Machine"]
        for col, text in enumerate(headers):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl, 0, col)

        self._work_labels = {}
        self._mach_labels = {}
        axes = ["X", "Y", "Z"]
        colors = {"X": "red", "Y": "green", "Z": "blue"}

        for row, axis in enumerate(axes, start=1):
            # Axis name
            name_lbl = QLabel(axis)
            name_lbl.setFont(DRO_FONT)
            name_lbl.setStyleSheet(f"color: {colors[axis]};")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(name_lbl, row, 0)

            # Work position
            w_lbl = QLabel("0.000")
            w_lbl.setFont(DRO_FONT)
            w_lbl.setAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
            w_lbl.setMinimumWidth(100)
            layout.addWidget(w_lbl, row, 1)
            self._work_labels[axis] = w_lbl

            # Machine position
            m_lbl = QLabel("0.000")
            m_lbl.setFont(DRO_FONT)
            m_lbl.setStyleSheet("color: gray;")
            m_lbl.setAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
            m_lbl.setMinimumWidth(100)
            layout.addWidget(m_lbl, row, 2)
            self._mach_labels[axis] = m_lbl

    def update_position(self, wx, wy, wz, mx, my, mz):
        """Update displayed coordinates."""
        fmt = "%.3f" if not CNC.inch else "%.4f"
        self._work_labels["X"].setText(fmt % wx)
        self._work_labels["Y"].setText(fmt % wy)
        self._work_labels["Z"].setText(fmt % wz)
        self._mach_labels["X"].setText(fmt % mx)
        self._mach_labels["Y"].setText(fmt % my)
        self._mach_labels["Z"].setText(fmt % mz)


class ConnectionWidget(QWidget):
    """Serial connection controls."""

    connect_clicked = Signal()

    def __init__(self, sender, parent=None):
        super().__init__(parent)
        self.sender = sender

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._port_combo.setMinimumWidth(150)
        self._populate_ports()
        layout.addWidget(QLabel("Port:"))
        layout.addWidget(self._port_combo, 1)

        self._baud_combo = QComboBox()
        for rate in [9600, 19200, 38400, 57600, 115200, 230400]:
            self._baud_combo.addItem(str(rate))
        self._baud_combo.setCurrentText(
            str(Utils.getInt("Connection", "baud", 115200)))
        layout.addWidget(QLabel("Baud:"))
        layout.addWidget(self._baud_combo)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(self._connect_btn)

        self._state_label = QLabel(NOT_CONNECTED)
        self._state_label.setMinimumWidth(100)
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_label.setStyleSheet(
            f"background-color: {STATECOLOR[NOT_CONNECTED]}; padding: 2px;")
        layout.addWidget(self._state_label)

    def _populate_ports(self):
        """Scan for available serial ports."""
        self._port_combo.clear()
        try:
            import serial.tools.list_ports
            for port in serial.tools.list_ports.comports():
                self._port_combo.addItem(port.device)
        except ImportError:
            pass
        # Add saved port
        saved = Utils.getStr("Connection", "port", "")
        if saved and self._port_combo.findText(saved) < 0:
            self._port_combo.addItem(saved)
        if saved:
            self._port_combo.setCurrentText(saved)

    def _on_connect(self):
        if self.sender.serial is None:
            device = self._port_combo.currentText()
            baud = int(self._baud_combo.currentText())
            try:
                self.sender.open(device, baud)
            except Exception as e:
                self._state_label.setText(f"Error: {e}")
                return
        else:
            self.sender.close()
        self.connect_clicked.emit()

    def update_state(self, state, color):
        """Update connection state display."""
        self._state_label.setText(state)
        self._state_label.setStyleSheet(
            f"background-color: {color}; padding: 2px;")
        if self.sender.serial is not None:
            self._connect_btn.setText("Disconnect")
        else:
            self._connect_btn.setText("Connect")


class JogWidget(QWidget):
    """Jog control buttons and step size selector."""

    def __init__(self, sender, parent=None):
        super().__init__(parent)
        self.sender = sender

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Step size selector
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step:"))
        self._step_spin = QDoubleSpinBox()
        self._step_spin.setRange(0.001, 1000.0)
        self._step_spin.setDecimals(3)
        self._step_spin.setValue(1.0)
        self._step_spin.setSuffix(" mm")
        step_layout.addWidget(self._step_spin)

        # Quick step buttons
        for step in [0.1, 1.0, 10.0]:
            btn = QPushButton(f"{step}")
            btn.setMaximumWidth(50)
            btn.clicked.connect(
                lambda checked, s=step: self._step_spin.setValue(s))
            step_layout.addWidget(btn)
        layout.addLayout(step_layout)

        # Jog buttons grid
        grid = QGridLayout()
        grid.setSpacing(2)

        buttons = {
            (0, 1): ("Y+", self._jog_yp),
            (2, 1): ("Y-", self._jog_yn),
            (1, 0): ("X-", self._jog_xn),
            (1, 2): ("X+", self._jog_xp),
            (0, 3): ("Z+", self._jog_zp),
            (2, 3): ("Z-", self._jog_zn),
            (1, 1): ("Home", self._home),
        }

        for (r, c), (label, callback) in buttons.items():
            btn = QPushButton(label)
            btn.setMinimumSize(50, 35)
            btn.clicked.connect(callback)
            grid.addWidget(btn, r, c)

        layout.addLayout(grid)

        # Action buttons
        action_layout = QHBoxLayout()
        for label, callback in [
            ("Unlock", lambda: sender.unlock()),
            ("Reset", lambda: sender.softReset()),
            ("Home All", lambda: sender.home()),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(callback)
            action_layout.addWidget(btn)
        layout.addLayout(action_layout)

    def _jog(self, axis, direction):
        step = self._step_spin.value() * direction
        cmd = f"$J=G91 {axis}{step:.3f} F{self._feed_rate()}"
        self.sender.sendGCode(cmd)

    def _feed_rate(self):
        return max(100.0, self._step_spin.value() * 60.0)

    def _jog_xp(self): self._jog("X", 1)
    def _jog_xn(self): self._jog("X", -1)
    def _jog_yp(self): self._jog("Y", 1)
    def _jog_yn(self): self._jog("Y", -1)
    def _jog_zp(self): self._jog("Z", 1)
    def _jog_zn(self): self._jog("Z", -1)
    def _home(self): self.sender.home()


class ControlPanel(QWidget):
    """Combined control panel with DRO, connection, and jog widgets."""

    def __init__(self, sender, signals, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.signals = signals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # Connection group
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.setContentsMargins(2, 2, 2, 2)
        self.connection = ConnectionWidget(sender)
        conn_layout.addWidget(self.connection)
        layout.addWidget(conn_group)

        # DRO group
        dro_group = QGroupBox("Position")
        dro_layout = QVBoxLayout(dro_group)
        dro_layout.setContentsMargins(2, 2, 2, 2)
        self.dro = DROWidget()
        dro_layout.addWidget(self.dro)
        layout.addWidget(dro_group)

        # Jog group
        jog_group = QGroupBox("Jog")
        jog_layout = QVBoxLayout(jog_group)
        jog_layout.setContentsMargins(2, 2, 2, 2)
        self.jog = JogWidget(sender)
        jog_layout.addWidget(self.jog)
        layout.addWidget(jog_group)

        # Run controls
        run_group = QGroupBox("Execution")
        run_layout = QHBoxLayout(run_group)
        run_layout.setContentsMargins(2, 2, 2, 2)
        for label, signal in [
            ("Run", signals.run_requested),
            ("Pause", signals.pause_requested),
            ("Stop", signals.stop_requested),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(signal.emit)
            run_layout.addWidget(btn)
        layout.addWidget(run_group)

        layout.addStretch()

        # Wire signals
        signals.state_changed.connect(self.connection.update_state)
        signals.position_updated.connect(self.dro.update_position)
