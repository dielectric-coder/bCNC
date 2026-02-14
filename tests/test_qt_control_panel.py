"""Tests for Qt control panel: macro buttons and DRO font customization."""

import os
import sys
import unittest

# Offscreen rendering — must be set before QApplication import
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# bCNC import path setup
_root = os.path.join(os.path.dirname(__file__), "..")
for sub in ("bCNC", "bCNC/lib", "bCNC/controllers", "bCNC/plugins"):
    p = os.path.join(_root, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import Helpers  # noqa: E402  — must be first (installs _() builtin)
import Utils  # noqa: E402

# Patch config.get so missing sections don't raise
_orig_get = Utils.config.get
def _safe_get(section, option, **kw):
    if not Utils.config.has_section(section):
        Utils.config.add_section(section)
    return _orig_get(section, option, **kw)
Utils.config.get = _safe_get

_orig_items = Utils.config.items
Utils.config.items = lambda s="DEFAULT", **kw: (
    [] if s != "DEFAULT" and not Utils.config.has_section(s)
    else _orig_items(s, **kw)
)

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402

# Single QApplication for all tests
app = QApplication.instance() or QApplication(sys.argv)

from Sender import Sender  # noqa: E402
from qt.control_panel import (  # noqa: E402
    _config_font,
    MacroButtonsWidget,
    MacroEditDialog,
    ControlPanel,
    DROWidget,
)
from qt.signals import AppSignals  # noqa: E402


class TestConfigFont(unittest.TestCase):
    """Test _config_font() helper that loads QFont from [Font] config."""

    def test_defaults_when_no_config(self):
        """Returns default font when config key is missing."""
        font = _config_font("nonexistent.key", "Courier", 16, True)
        self.assertEqual(font.family(), "Courier")
        self.assertEqual(font.pointSize(), 16)
        self.assertTrue(font.bold())

    def test_parses_config_string(self):
        """Parses 'Family,size,bold' format from config."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.font", "Monospace,18,bold")
        font = _config_font("test.font")
        self.assertEqual(font.family(), "Monospace")
        self.assertEqual(font.pointSize(), 18)
        self.assertTrue(font.bold())
        Utils.config.remove_option("Font", "test.font")

    def test_parses_italic(self):
        """Parses italic flag from config string."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.italic", "Arial,10,italic")
        font = _config_font("test.italic")
        self.assertEqual(font.family(), "Arial")
        self.assertEqual(font.pointSize(), 10)
        self.assertFalse(font.bold())
        self.assertTrue(font.italic())
        Utils.config.remove_option("Font", "test.italic")

    def test_parses_bold_italic(self):
        """Parses both bold and italic."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.bi", "Helvetica,14,bold,italic")
        font = _config_font("test.bi")
        self.assertTrue(font.bold())
        self.assertTrue(font.italic())
        Utils.config.remove_option("Font", "test.bi")

    def test_negative_size_uses_absolute(self):
        """Negative sizes (Tkinter convention) are converted to positive."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.neg", "Sans,-11")
        font = _config_font("test.neg")
        self.assertEqual(font.pointSize(), 11)
        Utils.config.remove_option("Font", "test.neg")

    def test_family_only(self):
        """Config with only family name uses defaults for size/weight."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "test.fam", "Times")
        font = _config_font("test.fam", default_size=20)
        self.assertEqual(font.family(), "Times")
        self.assertEqual(font.pointSize(), 20)
        Utils.config.remove_option("Font", "test.fam")


class TestDROWidget(unittest.TestCase):
    """Test DROWidget uses configurable fonts."""

    def test_work_and_machine_fonts_differ(self):
        """Work position labels should use wpos font, machine labels use mpos."""
        if not Utils.config.has_section("Font"):
            Utils.config.add_section("Font")
        Utils.config.set("Font", "dro.wpos", "Sans,14,bold")
        Utils.config.set("Font", "dro.mpos", "Sans,10")

        dro = DROWidget()
        w_font = dro._work_labels["X"].font()
        m_font = dro._mach_labels["X"].font()

        self.assertEqual(w_font.pointSize(), 14)
        self.assertTrue(w_font.bold())
        self.assertEqual(m_font.pointSize(), 10)
        self.assertFalse(m_font.bold())

        # Cleanup
        Utils.config.remove_option("Font", "dro.wpos")
        Utils.config.remove_option("Font", "dro.mpos")

    def test_all_axes_have_labels(self):
        """DRO has work and machine labels for X, Y, Z."""
        dro = DROWidget()
        for axis in ("X", "Y", "Z"):
            self.assertIn(axis, dro._work_labels)
            self.assertIn(axis, dro._mach_labels)


class TestMacroButtonsWidget(unittest.TestCase):
    """Test MacroButtonsWidget loads buttons from [Buttons] config."""

    def setUp(self):
        self.sender = Sender()
        if not Utils.config.has_section("Buttons"):
            Utils.config.add_section("Buttons")

    def test_builds_correct_button_count(self):
        """Button count = n-1 (skipping button 0)."""
        Utils.config.set("Buttons", "n", "4")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(len(widget._buttons), 3)  # buttons 1, 2, 3

    def test_button_names_from_config(self):
        """Buttons get their names from config."""
        Utils.config.set("Buttons", "n", "3")
        Utils.config.set("Buttons", "name.1", "Home XY")
        Utils.config.set("Buttons", "name.2", "Probe Z")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(widget._buttons[0].text(), "Home XY")
        self.assertEqual(widget._buttons[1].text(), "Probe Z")

    def test_button_tooltip_from_config(self):
        """Buttons get tooltips from config, fallback to default."""
        Utils.config.set("Buttons", "n", "3")
        Utils.config.set("Buttons", "name.1", "B1")
        Utils.config.set("Buttons", "tooltip.1", "Go to origin")
        Utils.config.set("Buttons", "name.2", "B2")
        # No tooltip for button 2
        if Utils.config.has_option("Buttons", "tooltip.2"):
            Utils.config.remove_option("Buttons", "tooltip.2")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(widget._buttons[0].toolTip(), "Go to origin")
        self.assertEqual(widget._buttons[1].toolTip(), "Right-click to configure")

    def test_execute_queues_to_pendant(self):
        """Clicking a configured button queues commands via pendant."""
        Utils.config.set("Buttons", "n", "2")
        Utils.config.set("Buttons", "name.1", "Test")
        Utils.config.set("Buttons", "command.1", "G0 X0 Y0\nG0 Z5")
        widget = MacroButtonsWidget(self.sender)
        widget._execute(1)
        # Drain the pendant queue
        lines = []
        while not self.sender.pendant.empty():
            lines.append(self.sender.pendant.get())
        self.assertEqual(lines, ["G0 X0 Y0", "G0 Z5"])

    def test_execute_empty_command_does_not_queue(self):
        """Empty command does not put anything on pendant queue."""
        from unittest.mock import patch
        Utils.config.set("Buttons", "n", "2")
        Utils.config.set("Buttons", "name.1", "Empty")
        Utils.config.set("Buttons", "command.1", "")
        widget = MacroButtonsWidget(self.sender)
        # Patch _edit to prevent modal dialog from blocking
        with patch.object(widget, "_edit"):
            widget._execute(1)
        self.assertTrue(self.sender.pendant.empty())

    def test_rebuild_after_config_change(self):
        """_build_buttons() refreshes from config."""
        Utils.config.set("Buttons", "n", "2")
        Utils.config.set("Buttons", "name.1", "Old")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(widget._buttons[0].text(), "Old")

        Utils.config.set("Buttons", "name.1", "New")
        widget._build_buttons()
        self.assertEqual(widget._buttons[0].text(), "New")

    def test_default_button_count(self):
        """Default n=6 gives 5 buttons."""
        # Remove n if set
        if Utils.config.has_option("Buttons", "n"):
            Utils.config.remove_option("Buttons", "n")
        widget = MacroButtonsWidget(self.sender)
        self.assertEqual(len(widget._buttons), 5)


class TestMacroEditDialog(unittest.TestCase):
    """Test MacroEditDialog saves to config on accept."""

    def setUp(self):
        if not Utils.config.has_section("Buttons"):
            Utils.config.add_section("Buttons")

    def test_dialog_loads_config_values(self):
        """Dialog fields are populated from config."""
        Utils.config.set("Buttons", "name.5", "MyMacro")
        Utils.config.set("Buttons", "tooltip.5", "Does stuff")
        Utils.config.set("Buttons", "command.5", "G28")

        dlg = MacroEditDialog(5)
        self.assertEqual(dlg._name.text(), "MyMacro")
        self.assertEqual(dlg._tooltip.text(), "Does stuff")
        self.assertEqual(dlg._command.toPlainText(), "G28")

    def test_accept_saves_to_config(self):
        """Accepting the dialog writes values back to config."""
        dlg = MacroEditDialog(7)
        dlg._name.setText("Saved")
        dlg._tooltip.setText("A tooltip")
        dlg._command.setPlainText("G0 X10\nG0 Y20")
        dlg.accept()

        self.assertEqual(Utils.config.get("Buttons", "name.7"), "Saved")
        self.assertEqual(Utils.config.get("Buttons", "tooltip.7"), "A tooltip")
        self.assertEqual(Utils.config.get("Buttons", "command.7"), "G0 X10\nG0 Y20")


class TestControlPanelIntegration(unittest.TestCase):
    """Integration test: ControlPanel has macro_buttons widget."""

    def test_macro_buttons_present(self):
        """ControlPanel has a macro_buttons attribute."""
        sender = Sender()
        signals = AppSignals()
        panel = ControlPanel(sender, signals)
        self.assertTrue(hasattr(panel, "macro_buttons"))
        self.assertIsInstance(panel.macro_buttons, MacroButtonsWidget)

    def test_macro_buttons_has_buttons(self):
        """macro_buttons widget contains QPushButtons."""
        sender = Sender()
        signals = AppSignals()
        panel = ControlPanel(sender, signals)
        self.assertGreater(len(panel.macro_buttons._buttons), 0)


if __name__ == "__main__":
    unittest.main()
