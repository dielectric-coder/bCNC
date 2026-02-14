# $Id$
#
# Author:       vvlachoudis@gmail.com
# Date: 24-Aug-2014
#
# Toolkit-independent tool classes are defined in tools_base.py and
# re-exported here so that ``from ToolsPage import Plugin`` (used by
# 43+ plugins) still works without any code changes.
#
# Tkinter UI classes (Tools, InPlaceText, DataBaseGroup, CAMGroup,
# ConfigGroup, ToolsFrame, ToolsPage) are loaded lazily via module
# __getattr__ the first time they are accessed — typically only from
# the Tkinter application entry point (bmain.py).

from tools_base import (  # noqa: F401 — re-exported for plugins
    _Base,
    DataBase,
    Plugin,
    Ini,
    Font,
    Color,
    Events,
    Shortcut,
    Camera,
    Config,
    Material,
    EndMill,
    Stock,
    Cut,
    Drill,
    Profile,
    Pocket,
    Tabs,
    Controller,
)

__author__ = "Vasilis Vlachoudis"
__email__ = "Vasilis.Vlachoudis@cern.ch"

# Names that require tkinter — loaded on demand
_TK_NAMES = frozenset({
    "InPlaceText", "Tools",
    "DataBaseGroup", "CAMGroup", "ConfigGroup",
    "ToolsFrame", "ToolsPage",
})

_tk_loaded = False


def __getattr__(name):
    """Lazily load tkinter UI classes on first access."""
    global _tk_loaded
    if name in _TK_NAMES:
        if not _tk_loaded:
            _load_tk_ui()
            _tk_loaded = True
        if name in globals():
            return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _load_tk_ui():
    """Import tkinter and define all Tkinter-only classes.

    Also monkey-patches _Base.populate, _Base.edit, _Base._sendReturn,
    _Base._editPrev, _Base._editNext, and DataBase.rename with their
    Tkinter implementations so tool instances work correctly in the
    Tkinter app.
    """
    import glob
    import os
    import sys
    import traceback
    from operator import attrgetter
    from tkinter import (
        TclError,
        YES,
        W,
        NSEW,
        X,
        Y,
        BOTH,
        LEFT,
        TOP,
        RIGHT,
        VERTICAL,
        END,
        NORMAL,
        DISABLED,
        ACTIVE,
        StringVar,
        Button,
        Frame,
        Label,
        Menu,
        Scrollbar,
        Text,
        PanedWindow,
        messagebox,
    )

    import CNCRibbon
    import Ribbon
    import tkExtra
    import Unicode
    import Utils
    from Helpers import N_

    _EXE_FONT = ("Helvetica", 12, "bold")

    # -----------------------------------------------------------------
    # Monkey-patch _Base methods with Tkinter implementations
    # -----------------------------------------------------------------
    def _tk_populate(self):
        self.master.listbox.delete(0, END)
        for var in self.variables:
            n, t, d, lp = var[:4]
            value = self[n]
            if t == "bool":
                if value:
                    value = Unicode.BALLOT_BOX_WITH_X
                else:
                    value = Unicode.BALLOT_BOX
            elif t == "mm" and self.master.inches:
                try:
                    value /= 25.4
                    value = round(value, self.master.digits)
                except Exception:
                    value = ""
            elif t == "float":
                try:
                    value = round(value, self.master.digits)
                except Exception:
                    value = ""
            self.master.listbox.insert(END, (lp, value))

            if t == "color":
                try:
                    self.master.listbox.listbox(1).itemconfig(
                        END, background=value)
                except TclError:
                    pass

        # Load help
        varhelp = ""
        if hasattr(self, "help") and self.help is not None:
            varhelp += self.help

        varhelpheader = True
        for var in self.variables:
            if len(var) > 4:
                if varhelpheader:
                    varhelp += "\n=== Module options ===\n\n"
                    varhelpheader = False
                varhelp += (
                    "* " + var[0].upper() + ": "
                    + var[3] + "\n" + var[4] + "\n\n"
                )

        self.master.widget["paned"].remove(self.master.widget["toolHelpFrame"])
        self.master.widget["toolHelp"].config(state=NORMAL)
        self.master.widget["toolHelp"].delete(1.0, END)
        if len(varhelp) > 0:
            for line in varhelp.splitlines():
                if (len(line) > 0
                        and line[0] == "#"
                        and line[1:] in Utils.images.keys()):
                    self.master.widget["toolHelp"].image_create(
                        END, image=Utils.images[line[1:]]
                    )
                    self.master.widget["toolHelp"].insert(END, "\n")
                else:
                    self.master.widget["toolHelp"].insert(END, line + "\n")
            self.master.widget["paned"].add(self.master.widget[
                "toolHelpFrame"])
        self.master.widget["toolHelp"].config(state=DISABLED)

    _Base.populate = _tk_populate

    def _tk_sendReturn(self, active):
        self.master.listbox.selection_clear(0, END)
        self.master.listbox.selection_set(active)
        self.master.listbox.activate(active)
        self.master.listbox.see(active)
        n, t, d, lp = self.variables[active][:4]
        if t == "bool":
            return  # Forbid changing value of bool
        self.master.listbox.event_generate("<Return>")

    _Base._sendReturn = _tk_sendReturn

    def _tk_editPrev(self):
        active = self.master.listbox.index(ACTIVE) - 1
        if active < 0:
            return
        self._sendReturn(active)

    _Base._editPrev = _tk_editPrev

    def _tk_editNext(self):
        active = self.master.listbox.index(ACTIVE) + 1
        if active >= self.master.listbox.size():
            return
        self._sendReturn(active)

    _Base._editNext = _tk_editNext

    # --- InPlaceText (needed by _tk_edit) ---
    class _InPlaceText(tkExtra.InPlaceText):
        def defaultBinds(self):
            tkExtra.InPlaceText.defaultBinds(self)
            self.edit.bind("<Escape>", self.ok)

    globals()["InPlaceText"] = _InPlaceText

    def _tk_edit(self, event=None, rename=False):
        lb = self.master.listbox.listbox(1)
        if event is None or event.type == "2":
            keyboard = True
        else:
            keyboard = False
        if keyboard:
            active = lb.index(ACTIVE)
        else:
            active = lb.nearest(event.y)
            self.master.listbox.activate(active)

        ypos = lb.yview()[0]
        save = lb.get(ACTIVE)

        n, t, d, lp = self.variables[active][:4]

        if t == "int":
            edit = tkExtra.InPlaceInteger(lb)
        elif t in ("float", "mm"):
            edit = tkExtra.InPlaceFloat(lb)
        elif t == "bool":
            edit = None
            value = int(lb.get(active) == Unicode.BALLOT_BOX)
            if value:
                lb.set(active, Unicode.BALLOT_BOX_WITH_X)
            else:
                lb.set(active, Unicode.BALLOT_BOX)
        elif t == "list":
            edit = tkExtra.InPlaceList(lb, values=self.listdb[n])
        elif t == "db":
            if n == "name":
                if rename:
                    edit = tkExtra.InPlaceEdit(lb)
                else:
                    edit = tkExtra.InPlaceList(lb, values=self.names())
            else:
                tool = self.master[n]
                names = tool.names()
                names.insert(0, "")
                edit = tkExtra.InPlaceList(lb, values=names)
        elif t == "text":
            edit = _InPlaceText(lb)
        elif "," in t:
            choices = [""]
            choices.extend(t.split(","))
            edit = tkExtra.InPlaceList(lb, values=choices)
        elif t == "file":
            edit = tkExtra.InPlaceFile(lb, save=False)
        elif t == "output":
            edit = tkExtra.InPlaceFile(lb, save=True)
        elif t == "color":
            edit = tkExtra.InPlaceColor(lb)
            if edit.value is not None:
                try:
                    lb.itemconfig(ACTIVE, background=edit.value)
                except TclError:
                    pass
        else:
            edit = tkExtra.InPlaceEdit(lb)

        if edit is not None:
            value = edit.value
            if value is None:
                return

        if value == save:
            if edit.lastkey == "Up":
                self._editPrev()
            elif edit.lastkey in ("Return", "KP_Enter", "Down"):
                self._editNext()
            return

        if t == "int":
            try:
                value = int(value)
            except ValueError:
                value = ""
        elif t in ("float", "mm"):
            try:
                value = float(value)
                if t == "mm" and self.master.inches:
                    value *= 25.4
            except ValueError:
                value = ""

        if n == "name" and not rename:
            if self.makeCurrent(value):
                self.populate()
        else:
            self[n] = value
            if self.update():
                self.populate()

        self.master.listbox.selection_set(active)
        self.master.listbox.activate(active)
        self.master.listbox.yview_moveto(ypos)
        if edit is not None and not rename:
            if edit.lastkey == "Up":
                self._editPrev()
            elif edit.lastkey in ("Return", "KP_Enter", "Down") and active > 0:
                self._editNext()

    _Base.edit = _tk_edit

    def _tk_rename(self):
        self.master.listbox.selection_clear(0, END)
        self.master.listbox.selection_set(0)
        self.master.listbox.activate(0)
        self.master.listbox.see(0)
        self.edit(None, True)

    DataBase.rename = _tk_rename

    # -----------------------------------------------------------------
    # Tkinter-only classes
    # -----------------------------------------------------------------

    class _Tools:
        def __init__(self, gcode):
            self.gcode = gcode
            self.inches = False
            self.digits = 4
            self.active = StringVar()

            self.tools = {}
            self.buttons = {}
            self.widget = {}
            self.listbox = None

            for cls in [
                Camera, Config, Font, Color, Controller,
                Cut, Drill, EndMill, Events, Material,
                Pocket, Profile, Shortcut, Stock, Tabs,
            ]:
                tool = cls(self)
                self.addTool(tool)

            for f in glob.glob(f"{Utils.prgpath}/plugins/*.py"):
                name, ext = os.path.splitext(os.path.basename(f))
                try:
                    package = __import__(name, globals(), locals(), [], 0)
                    tool = package.Tool(self)
                    self.addTool(tool)
                except (ImportError, AttributeError):
                    typ, val, tb = sys.exc_info()
                    traceback.print_exception(typ, val, tb)

        def addTool(self, tool):
            self.tools[tool.name.upper()] = tool

        def pluginList(self):
            plugins = [x for x in self.tools.values() if x.plugin]
            return sorted(plugins, key=attrgetter("name"))

        def setListbox(self, listbox):
            self.listbox = listbox

        def setWidget(self, name, widget):
            self.widget[name] = widget

        def __getitem__(self, name):
            return self.tools[name.upper()]

        def getActive(self):
            try:
                return self.tools[self.active.get().upper()]
            except Exception:
                self.active.set("CNC")
                return self.tools["CNC"]

        def setActive(self, value):
            self.active.set(value)

        def toMm(self, value):
            if self.inches:
                return value * 25.4
            else:
                return value

        def fromMm(self, value):
            if self.inches:
                return value / 25.4
            else:
                return value

        def names(self):
            lst = [x.name for x in self.tools.values()]
            lst.sort()
            return lst

        def loadConfig(self):
            self.active.set(Utils.getStr(Utils.__prg__, "tool", "CNC"))
            for tool in self.tools.values():
                tool.load()

        def saveConfig(self):
            Utils.setStr(Utils.__prg__, "tool", self.active.get())
            for tool in self.tools.values():
                tool.save()

        def cnc(self):
            return self.gcode.cnc

        def addButton(self, name, button):
            self.buttons[name] = button

        def activateButtons(self, tool):
            for btn in self.buttons.values():
                btn.config(state=DISABLED)
            for name in tool.buttons:
                self.buttons[name].config(state=NORMAL)
            self.buttons["exe"].config(text=self.active.get())

            icon = self.tools[self.active.get().upper()].icon
            if icon is None:
                icon = "gear"
            self.buttons["exe"].config(image=Utils.icons[icon])

    globals()["Tools"] = _Tools

    # -----------------------------------------------------------------
    class _DataBaseGroup(CNCRibbon.ButtonGroup):
        def __init__(self, master, app):
            CNCRibbon.ButtonGroup.__init__(self, master, N_("Database"), app)
            self.grid3rows()

            col, row = 0, 0
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["stock32"],
                text=_("Stock"),
                compound=TOP,
                anchor=W,
                variable=app.tools.active,
                value="Stock",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, rowspan=3, padx=2, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(b, _("Stock material currently on machine"))
            self.addWidget(b)

            col, row = 1, 0
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["material"],
                text=_("Material"),
                compound=LEFT,
                anchor=W,
                variable=app.tools.active,
                value="Material",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(
                b, _("Editable database of material properties"))
            self.addWidget(b)

            row += 1
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["endmill"],
                text=_("End Mill"),
                compound=LEFT,
                anchor=W,
                variable=app.tools.active,
                value="EndMill",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(
                b, _("Editable database of EndMills properties"))
            self.addWidget(b)

            row += 1
            b = Ribbon.LabelButton(
                self.frame,
                app,
                "<<ToolRename>>",
                image=Utils.icons["rename"],
                text=_("Rename"),
                compound=LEFT,
                anchor=W,
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(
                b, _("Edit name of current operation/object"))
            self.addWidget(b)
            app.tools.addButton("rename", b)

            col, row = 2, 0
            b = Ribbon.LabelButton(
                self.frame,
                app,
                "<<ToolAdd>>",
                image=Utils.icons["add"],
                text=_("Add"),
                compound=LEFT,
                anchor=W,
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(b, _("Add a new operation/object"))
            self.addWidget(b)
            app.tools.addButton("add", b)

            row += 1
            b = Ribbon.LabelButton(
                self.frame,
                app,
                "<<ToolClone>>",
                image=Utils.icons["clone"],
                text=_("Clone"),
                compound=LEFT,
                anchor=W,
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(b, _("Clone selected operation/object"))
            self.addWidget(b)
            app.tools.addButton("clone", b)

            row += 1
            b = Ribbon.LabelButton(
                self.frame,
                app,
                "<<ToolDelete>>",
                image=Utils.icons["x"],
                text=_("Delete"),
                compound=LEFT,
                anchor=W,
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=0, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(
                b, _("Delete selected operation/object"))
            self.addWidget(b)
            app.tools.addButton("delete", b)

    globals()["DataBaseGroup"] = _DataBaseGroup

    # -----------------------------------------------------------------
    class _CAMGroup(CNCRibbon.ButtonMenuGroup):
        def __init__(self, master, app):
            CNCRibbon.ButtonMenuGroup.__init__(
                self, master, N_("CAM"), app)
            self.grid3rows()

            col, row = 0, 0
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["cut32"],
                text=_("Cut"),
                compound=TOP,
                anchor=W,
                variable=app.tools.active,
                value="Cut",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, rowspan=3,
                   padx=1, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(
                b, _("Cut for the full stock thickness selected code"))
            self.addWidget(b)

            col += 1
            for group in ["CAM_Core+"]:
                for tool in app.tools.pluginList():
                    if tool.group != group:
                        continue
                    if tool.oneshot:
                        b = Ribbon.LabelButton(
                            self.frame,
                            image=Utils.icons[tool.icon + "32"],
                            text=_(tool.name),
                            compound=TOP,
                            anchor=W,
                            command=lambda s=self, a=app, t=tool: a.tools[
                                t.name.upper()
                            ].execute(a),
                            background=Ribbon._BACKGROUND,
                        )
                    else:
                        b = Ribbon.LabelRadiobutton(
                            self.frame,
                            image=Utils.icons[tool.icon + "32"],
                            text=tool.name,
                            compound=TOP,
                            anchor=W,
                            variable=app.tools.active,
                            value=tool.name,
                            background=Ribbon._BACKGROUND,
                        )

                    b.grid(row=row, column=col, rowspan=3,
                           padx=1, pady=0, sticky=NSEW)
                    tkExtra.Balloon.set(b, tool.__doc__)
                    self.addWidget(b)

                    col += 1

            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["profile32"],
                text=_("Profile"),
                compound=TOP,
                anchor=W,
                variable=app.tools.active,
                value="Profile",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, rowspan=3,
                   padx=1, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(
                b, _("Perform a profile operation on selected code"))
            self.addWidget(b)

            col += 1
            row = 0
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["pocket"],
                text=_("Pocket"),
                compound=LEFT,
                anchor=W,
                variable=app.tools.active,
                value="Pocket",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=2, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(
                b, _("Perform a pocket operation on selected code"))
            self.addWidget(b)

            row += 1
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["drill"],
                text=_("Drill"),
                compound=LEFT,
                anchor=W,
                variable=app.tools.active,
                value="Drill",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=2, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(
                b,
                _("Insert a drill cycle on current objects/location"))
            self.addWidget(b)

            row += 1
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["tab"],
                text=_("Tabs"),
                compound=LEFT,
                anchor=W,
                variable=app.tools.active,
                value="Tabs",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=2, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(b, _("Insert holding tabs"))
            self.addWidget(b)

            col += 1
            row = 0
            b = Ribbon.LabelButton(
                self.frame,
                image=Utils.icons["island"],
                text=_("Island"),
                compound=LEFT,
                anchor=W,
                command=lambda s=app: s.insertCommand("ISLAND", True),
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=2, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(b, _("Toggle island"))
            self.addWidget(b)

            row += 1

            for group in ["CAM_Core", "CAM"]:
                for tool in app.tools.pluginList():
                    if tool.group != group:
                        continue
                    if tool.oneshot:
                        b = Ribbon.LabelButton(
                            self.frame,
                            image=Utils.icons[tool.icon],
                            text=_(tool.name),
                            compound=LEFT,
                            anchor=W,
                            command=lambda s=self, a=app, t=tool: a.tools[
                                t.name.upper()
                            ].execute(a),
                            background=Ribbon._BACKGROUND,
                        )
                    else:
                        b = Ribbon.LabelRadiobutton(
                            self.frame,
                            image=Utils.icons[tool.icon],
                            text=tool.name,
                            compound=LEFT,
                            anchor=W,
                            variable=app.tools.active,
                            value=tool.name,
                            background=Ribbon._BACKGROUND,
                        )

                    b.grid(row=row, column=col,
                           padx=2, pady=0, sticky=NSEW)
                    tkExtra.Balloon.set(b, tool.__doc__)
                    self.addWidget(b)

                    row += 1
                    if row == 3:
                        col += 1
                        row = 0

        def createMenu(self):
            menu = Menu(self, tearoff=0)
            for group in ("Artistic", "Generator", "Development"):
                submenu = Menu(menu, tearoff=0)
                menu.add_cascade(label=group, menu=submenu)
                for tool in self.app.tools.pluginList():
                    if tool.group != group:
                        continue
                    if tool.oneshot:
                        submenu.add_command(
                            label=_(tool.name),
                            image=Utils.icons[tool.icon],
                            compound=LEFT,
                            command=lambda s=self, a=self.app, t=tool:
                                a.tools[t.name.upper()].execute(a),
                        )
                    else:
                        submenu.add_radiobutton(
                            label=_(tool.name),
                            image=Utils.icons[tool.icon],
                            compound=LEFT,
                            variable=self.app.tools.active,
                            value=tool.name,
                        )
            return menu

    globals()["CAMGroup"] = _CAMGroup

    # -----------------------------------------------------------------
    class _ConfigGroup(CNCRibbon.ButtonMenuGroup):
        def __init__(self, master, app):
            CNCRibbon.ButtonMenuGroup.__init__(
                self, master, N_("Config"), app)
            self.grid3rows()

            col, row = 0, 0
            f = Frame(self.frame)
            f.grid(row=row, column=col, columnspan=2,
                   padx=0, pady=0, sticky=NSEW)

            b = Label(
                f, image=Utils.icons["globe"],
                background=Ribbon._BACKGROUND)
            b.pack(side=LEFT)

            self.language = Ribbon.LabelCombobox(
                f, command=self.languageChange, width=16)
            self.language.pack(side=RIGHT, fill=X, expand=YES)
            tkExtra.Balloon.set(
                self.language,
                _("Change program language restart is required"))
            self.addWidget(self.language)

            self.fillLanguage()

            row += 1
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["config"],
                text=_("Config"),
                compound=LEFT,
                anchor=W,
                variable=app.tools.active,
                value="CNC",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=1, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(b, _("Machine configuration for bCNC"))
            self.addWidget(b)

            col += 1
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["shortcut"],
                text=_("Shortcuts"),
                compound=LEFT,
                anchor=W,
                variable=app.tools.active,
                value="Shortcut",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=1, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(b, _("Shortcuts configuration"))
            self.addWidget(b)

            row += 1
            col = 0
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["arduino"],
                text=_("Controller"),
                compound=LEFT,
                anchor=W,
                variable=app.tools.active,
                value="Controller",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=1, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(
                b, _("Controller (GRBL) configuration"))
            self.addWidget(b)

            col += 1
            b = Ribbon.LabelRadiobutton(
                self.frame,
                image=Utils.icons["camera"],
                text=_("Camera"),
                compound=LEFT,
                anchor=W,
                variable=app.tools.active,
                value="Camera",
                background=Ribbon._BACKGROUND,
            )
            b.grid(row=row, column=col, padx=1, pady=0, sticky=NSEW)
            tkExtra.Balloon.set(b, _("Camera Configuration"))
            self.addWidget(b)

        def fillLanguage(self):
            self.language.set(Utils.LANGUAGES.get(Utils.language, ""))
            self.language.fill(list(sorted(Utils.LANGUAGES.values())))

        def languageChange(self):
            lang = self.language.get()
            for a, b in Utils.LANGUAGES.items():
                if b == lang:
                    if Utils.language == a:
                        return
                    Utils.language = a
                    Utils.setStr(
                        Utils.__prg__, "language", Utils.language)
                    messagebox.showinfo(
                        _("Language change"),
                        _("Please restart the program."),
                        parent=self.winfo_toplevel(),
                    )
                    return

        def createMenu(self):
            menu = Menu(self, tearoff=0)
            menu.add_command(
                label=_("User File"),
                image=Utils.icons["about"],
                compound=LEFT,
                command=self.app.showUserFile,
            )
            menu.add_radiobutton(
                label=_("Events"),
                image=Utils.icons["event"],
                compound=LEFT,
                variable=self.app.tools.active,
                value="Events",
            )
            menu.add_radiobutton(
                label=_("Colors"),
                image=Utils.icons["color"],
                compound=LEFT,
                variable=self.app.tools.active,
                value="Color",
            )
            menu.add_radiobutton(
                label=_("Fonts"),
                image=Utils.icons["font"],
                compound=LEFT,
                variable=self.app.tools.active,
                value="Font",
            )
            return menu

    globals()["ConfigGroup"] = _ConfigGroup

    # -----------------------------------------------------------------
    class _ToolsFrame(CNCRibbon.PageFrame):
        def __init__(self, master, app):
            CNCRibbon.PageFrame.__init__(self, master, "CAM", app)
            self.tools = app.tools

            paned = PanedWindow(self, orient=VERTICAL)
            paned.pack(expand=YES, fill=BOTH)

            frame = Frame(paned)
            paned.add(frame)

            b = Button(
                frame,
                text=_("Execute"),
                image=Utils.icons["gear"],
                compound=LEFT,
                foreground="DarkRed",
                activeforeground="DarkRed",
                activebackground="LightYellow",
                font=_EXE_FONT,
                command=self.execute,
            )
            b.pack(side=TOP, fill=X)
            self.tools.addButton("exe", b)

            self.toolList = tkExtra.MultiListbox(
                frame,
                ((_("Name"), 24, None), (_("Value"), 12, None)),
                height=20,
                header=False,
                stretch="last",
                background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
            )
            self.toolList.sortAssist = None
            self.toolList.pack(fill=BOTH, expand=YES)
            self.toolList.bindList("<Double-1>", self.help)
            self.toolList.bindList("<Return>", self.edit)
            self.toolList.bindList("<Key-space>", self.edit)
            self.toolList.listbox(1).bind(
                "<ButtonRelease-1>", self.edit)
            self.tools.setListbox(self.toolList)
            self.addWidget(self.toolList)

            frame = Frame(paned)
            paned.add(frame)

            toolHelp = Text(frame, width=20, height=5)
            toolHelp.pack(side=LEFT, expand=YES, fill=BOTH)
            scroll = Scrollbar(frame, command=toolHelp.yview)
            scroll.pack(side=RIGHT, fill=Y)
            toolHelp.configure(yscrollcommand=scroll.set)
            self.addWidget(toolHelp)
            toolHelp.config(state=DISABLED)

            self.tools.setWidget("paned", paned)
            self.tools.setWidget("toolHelpFrame", frame)
            self.tools.setWidget("toolHelp", toolHelp)

            app.tools.active.trace("w", self.change)
            self.change()

        def change(self, a=None, b=None, c=None):
            tool = self.tools.getActive()
            tool.beforeChange(self.app)
            tool.populate()
            tool.update()
            self.tools.activateButtons(tool)

        populate = change

        def help(self, event=None, rename=False):
            item = self.toolList.get(
                self.toolList.curselection())[0]
            for var in self.tools.getActive().variables:
                if var[3] == item or _(var[3]) == item:
                    varname = var[0]
                    helpname = f"Help for ({varname}) {item}"
                    if len(var) > 4 and var[4] is not None:
                        helptext = var[4]
                    else:
                        helptext = (
                            f"{helpname}:\nnot available yet!")
                    messagebox.showinfo(helpname, helptext)

        def edit(self, event=None):
            sel = self.toolList.curselection()
            if not sel:
                return
            if sel[0] == 0 and (
                    event is None or event.keysym == 0):
                self.tools.getActive().rename()
            else:
                self.tools.getActive().edit(event)

        def execute(self, event=None):
            self.tools.getActive().execute(self.app)

        def add(self, event=None):
            self.tools.getActive().add()

        def delete(self, event=None):
            self.tools.getActive().delete()

        def clone(self, event=None):
            self.tools.getActive().clone()

        def rename(self, event=None):
            self.tools.getActive().rename()

    globals()["ToolsFrame"] = _ToolsFrame

    # -----------------------------------------------------------------
    class _ToolsPage(CNCRibbon.Page):
        __doc__ = _("GCode manipulation tools and user plugins")
        _name_ = N_("CAM")
        _icon_ = "tools"

        def register(self):
            self._register(
                (
                    _ConfigGroup,
                    _DataBaseGroup,
                    _CAMGroup,
                ),
                (_ToolsFrame,),
            )

        def edit(self, event=None):
            CNCRibbon.Page.frames["CAM"].edit()

        def add(self, event=None):
            CNCRibbon.Page.frames["CAM"].add()

        def clone(self, event=None):
            CNCRibbon.Page.frames["CAM"].clone()

        def delete(self, event=None):
            CNCRibbon.Page.frames["CAM"].delete()

        def rename(self, event=None):
            CNCRibbon.Page.frames["CAM"].rename()

    globals()["ToolsPage"] = _ToolsPage
