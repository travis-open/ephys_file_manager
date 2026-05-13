"""
Fluorescence Imaging Control GUI
Controls Lumencore Spectra light engine and camera via PyCroManager/MicroManager.

Channels:
  DAPI   -> UV/Violet: State=0, intensity via White_Level
  FITC   -> Cyan:  State=1, Cyan_Enable=1,  Cyan_Level
  TXRED  -> Green: State=1, Green_Enable=1, Green_Level
  DIC    -> no software light control; exposure only
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime

import umanager

# --- Channel configuration ---
# spectra_name=None means no software light control (DIC)
# uv=True: channel uses State=0 + White_Level (DAPI/Violet)
# uv=False (visible): State=1 + {spectra_name}_Enable + {spectra_name}_Level
CHANNELS = {
    "DAPI":  {"spectra_name": "Violet", "color": "#a78bfa", "uv": True},
    "FITC":  {"spectra_name": "Cyan",   "color": "#34d399", "uv": False},
    "TXRED": {"spectra_name": "Green",  "color": "#f87171", "uv": False},
    "DIC":   {"spectra_name": None,     "color": "#94a3b8", "uv": False},
}

DEVICE  = "Spectra"
BG      = "#0f172a"
CARD_BG = "#1e293b"
DIM     = "#475569"

OBJ_LIST = ["5X", "40X"]


class FluorescenceGUI:
    def __init__(self, root, parent=None):
        self.root = root
        self.parent = parent  # ExpControlGUI instance, or None in standalone mode
        self.root.title("Fluorescence Imaging Control")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # Use the shared umanager core (may be None if MM not running)
        self.core = umanager.core

        # Per-channel state: enabled (BooleanVar), level (IntVar), exposure (DoubleVar)
        self.channel_vars = {}

        # Objective selection — metadata/logging only (turret not motorized)
        self.objective_var = tk.StringVar(value="5X")

        # Standalone save directory (used when parent is None)
        self.save_dir_var = tk.StringVar(value=r"C:\Data")

        self._build_ui()
        self._init_safe_state()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = self.root

        # Title bar
        title_frame = tk.Frame(root, bg=BG, pady=12)
        title_frame.pack(fill="x", padx=24)

        tk.Label(
            title_frame,
            text="FLUORESCENCE CONTROL",
            font=("Courier New", 13, "bold"),
            fg="#94a3b8",
            bg=BG,
        ).pack(side="left")

        status_color = "#22c55e" if self.core else "#ef4444"
        status_text  = "CONNECTED" if self.core else "DEMO MODE"
        self._status_label = tk.Label(
            title_frame,
            text=f"● {status_text}",
            font=("Courier New", 10),
            fg=status_color,
            bg=BG,
        )
        self._status_label.pack(side="right", pady=4)

        ttk.Separator(root, orient="horizontal").pack(fill="x", padx=16)

        # Scope settings row (objective + optional save dir)
        self._build_scope_row(root)

        ttk.Separator(root, orient="horizontal").pack(fill="x", padx=16)

        # Channel cards
        channels_frame = tk.Frame(root, bg=BG, padx=16, pady=16)
        channels_frame.pack(fill="x")

        tk.Label(
            channels_frame,
            text="LIGHT ENGINE  ·  Lumencore Spectra",
            font=("Courier New", 9),
            fg=DIM,
            bg=BG,
        ).pack(anchor="w", pady=(0, 8))

        for ch_name, ch_cfg in CHANNELS.items():
            self._build_channel_card(channels_frame, ch_name, ch_cfg)

        ttk.Separator(root, orient="horizontal").pack(fill="x", padx=16)

        self._build_action_buttons(root)

    def _build_scope_row(self, parent):
        scope_frame = tk.Frame(parent, bg=BG, padx=16, pady=10)
        scope_frame.pack(fill="x")

        # Objective selector
        tk.Label(
            scope_frame,
            text="OBJECTIVE",
            font=("Courier New", 8),
            fg=DIM,
            bg=BG,
        ).pack(side="left")

        obj_menu = tk.OptionMenu(scope_frame, self.objective_var, *OBJ_LIST,
                                 command=self._on_objective_change)
        obj_menu.config(
            font=("Courier New", 10),
            bg=CARD_BG,
            fg="#94a3b8",
            activebackground=CARD_BG,
            activeforeground="#94a3b8",
            highlightthickness=0,
            relief="flat",
            cursor="hand2",
            width=4,
        )
        obj_menu["menu"].config(bg=CARD_BG, fg="#94a3b8")
        obj_menu.pack(side="left", padx=(6, 24))

        # Save directory (standalone only)
        if self.parent is None:
            tk.Label(
                scope_frame,
                text="SAVE TO",
                font=("Courier New", 8),
                fg=DIM,
                bg=BG,
            ).pack(side="left")

            save_entry = tk.Entry(
                scope_frame,
                textvariable=self.save_dir_var,
                font=("Courier New", 9),
                bg=CARD_BG,
                fg="#94a3b8",
                insertbackground="#94a3b8",
                relief="flat",
                width=28,
                state="readonly",
            )
            save_entry.pack(side="left", padx=(6, 4))

            tk.Button(
                scope_frame,
                text="…",
                command=self._pick_save_dir,
                font=("Courier New", 9),
                bg=CARD_BG,
                fg="#94a3b8",
                activebackground=CARD_BG,
                activeforeground="#94a3b8",
                relief="flat",
                cursor="hand2",
                padx=4,
            ).pack(side="left")

    def _build_channel_card(self, parent, ch_name, ch_cfg):
        accent       = ch_cfg["color"]
        spectra_name = ch_cfg["spectra_name"]
        has_light    = spectra_name is not None

        enabled_var  = tk.BooleanVar(value=False)
        level_var    = tk.IntVar(value=50)
        exposure_var = tk.DoubleVar(value=100.0)

        self.channel_vars[ch_name] = {
            "enabled":  enabled_var,
            "level":    level_var,
            "exposure": exposure_var,
        }

        card = tk.Frame(parent, bg=CARD_BG, bd=0)
        card.pack(fill="x", pady=5)

        tk.Frame(card, bg=accent, width=5).pack(side="left", fill="y")

        inner = tk.Frame(card, bg=CARD_BG, padx=14, pady=10)
        inner.pack(side="left", fill="both", expand=True)

        # Row 1: name | spectra tag | ENABLE checkbox
        row1 = tk.Frame(inner, bg=CARD_BG)
        row1.pack(fill="x")

        tk.Label(
            row1,
            text=ch_name,
            font=("Courier New", 14, "bold"),
            fg=accent,
            bg=CARD_BG,
            width=7,
            anchor="w",
        ).pack(side="left")

        tag_text = f"→ {spectra_name}" if has_light else "→ manual"
        tk.Label(
            row1,
            text=tag_text,
            font=("Courier New", 9),
            fg=DIM,
            bg=CARD_BG,
        ).pack(side="left", padx=(0, 12))

        tk.Checkbutton(
            row1,
            text=" ENABLE",
            variable=enabled_var,
            font=("Courier New", 9, "bold"),
            fg="#94a3b8",
            bg=CARD_BG,
            selectcolor=BG,
            activebackground=CARD_BG,
            activeforeground=accent,
            cursor="hand2",
            command=lambda n=ch_name: self._on_toggle(n),
        ).pack(side="right")

        # Row 2: intensity spinbox (fluorescence only) + exposure spinbox
        row2 = tk.Frame(inner, bg=CARD_BG)
        row2.pack(fill="x", pady=(8, 0))

        if has_light:
            tk.Label(
                row2,
                text="INTENSITY",
                font=("Courier New", 8),
                fg=DIM,
                bg=CARD_BG,
                width=9,
                anchor="w",
            ).pack(side="left")

            tk.Spinbox(
                row2,
                from_=0,
                to=100,
                textvariable=level_var,
                width=5,
                font=("Courier New", 11),
                bg=BG,
                fg=accent,
                insertbackground=accent,
                buttonbackground=CARD_BG,
                relief="flat",
                highlightthickness=1,
                highlightcolor=accent,
                highlightbackground="#334155",
            ).pack(side="left", padx=(4, 2))

            tk.Label(
                row2,
                text="%",
                font=("Courier New", 10),
                fg=DIM,
                bg=CARD_BG,
            ).pack(side="left", padx=(0, 20))
        else:
            tk.Label(
                row2,
                text="(no software light control)",
                font=("Courier New", 8, "italic"),
                fg=DIM,
                bg=CARD_BG,
            ).pack(side="left", padx=(0, 20))

        tk.Label(
            row2,
            text="EXPOSURE",
            font=("Courier New", 8),
            fg=DIM,
            bg=CARD_BG,
            anchor="w",
        ).pack(side="left")

        tk.Spinbox(
            row2,
            from_=1,
            to=60000,
            increment=1,
            textvariable=exposure_var,
            width=7,
            font=("Courier New", 11),
            bg=BG,
            fg=accent,
            insertbackground=accent,
            buttonbackground=CARD_BG,
            relief="flat",
            highlightthickness=1,
            highlightcolor=accent,
            highlightbackground="#334155",
        ).pack(side="left", padx=(4, 2))

        tk.Label(
            row2,
            text="ms",
            font=("Courier New", 10),
            fg=DIM,
            bg=CARD_BG,
        ).pack(side="left")

    def _build_action_buttons(self, parent):
        frame = tk.Frame(parent, bg=BG, padx=16, pady=14)
        frame.pack(fill="x")

        def btn(text, cmd, color, width=14):
            return tk.Button(
                frame,
                text=text,
                command=cmd,
                font=("Courier New", 10, "bold"),
                bg=color,
                fg=BG,
                activebackground=color,
                activeforeground=BG,
                relief="flat",
                cursor="hand2",
                width=width,
                pady=6,
            )

        btn("APPLY SETTINGS", self.apply_settings, "#94a3b8").pack(side="left", padx=(0, 8))
        btn("SNAP IMAGE",     self.snap_image,     "#22c55e").pack(side="left", padx=(0, 8))
        btn("ALL OFF",        self.all_off,         "#ef4444", width=10).pack(side="right")

    # ------------------------------------------------------------------
    # Hardware interaction
    # ------------------------------------------------------------------

    def _on_objective_change(self, value):
        """Send objective change to MicroManager."""
        if self.core:
            self.core.set_property("DObjective", "Label", value)
        else:
            print(f"[DEMO] core.set_property('DObjective', 'Label', '{value}')")

    def _init_safe_state(self):
        """Zero all light output on startup to prevent UV-on-at-boot."""
        if self.core:
            self.core.set_property(DEVICE, "White_Level", 0)
            self.core.set_property(DEVICE, "State", 1)
            for cfg in CHANNELS.values():
                if cfg["spectra_name"] and not cfg["uv"]:
                    self.core.set_property(DEVICE, f"{cfg['spectra_name']}_Enable", "0")
                    self.core.set_property(DEVICE, f"{cfg['spectra_name']}_Level", 0)
        else:
            print("[DEMO] Hardware initialized to safe all-off state")

    def _set_state(self, state: int):
        """Set Spectra State (0 = UV mode, 1 = visible mode)."""
        if self.core:
            self.core.set_property(DEVICE, "State", state)
        else:
            print(f"[DEMO] core.set_property('{DEVICE}', 'State', {state})")

    def _set_spectra_level(self, ch_name, level):
        cfg = CHANNELS[ch_name]
        if cfg["spectra_name"] is None:
            return
        prop = "White_Level" if cfg["uv"] else f"{cfg['spectra_name']}_Level"
        if self.core:
            self.core.set_property(DEVICE, prop, int(level))
        else:
            print(f"[DEMO] core.set_property('{DEVICE}', '{prop}', {int(level)})")

    def _set_spectra_enable(self, ch_name, enabled: bool):
        cfg = CHANNELS[ch_name]
        if cfg["spectra_name"] is None:
            return
        if cfg["uv"]:
            # UV channel: toggle via White_Level; State is handled in _activate_channel
            if not enabled:
                self._set_spectra_level(ch_name, 0)
        else:
            prop  = f"{cfg['spectra_name']}_Enable"
            value = "1" if enabled else "0"
            if self.core:
                self.core.set_property(DEVICE, prop, value)
            else:
                print(f"[DEMO] core.set_property('{DEVICE}', '{prop}', '{value}')")

    def _set_exposure(self, exposure_ms: float):
        if self.core:
            self.core.set_exposure(exposure_ms)
        else:
            print(f"[DEMO] core.set_exposure({exposure_ms})")

    def _activate_channel(self, ch_name):
        """Switch State and turn on a single channel."""
        cfg = CHANNELS[ch_name]
        if cfg["uv"]:
            self._set_state(0)
            self._set_spectra_level(ch_name, self.channel_vars[ch_name]["level"].get())
        else:
            self._set_state(1)
            self._set_spectra_enable(ch_name, True)
            self._set_spectra_level(ch_name, self.channel_vars[ch_name]["level"].get())
        self._set_exposure(self.channel_vars[ch_name]["exposure"].get())

    def _deactivate_all(self):
        """Zero all light output without touching UI variables."""
        if self.core:
            self.core.set_property(DEVICE, "White_Level", 0)
            self.core.set_property(DEVICE, "State", 1)
            for ch_name, cfg in CHANNELS.items():
                if cfg["spectra_name"] and not cfg["uv"]:
                    self.core.set_property(DEVICE, f"{cfg['spectra_name']}_Enable", "0")
        else:
            print("[DEMO] All lights off (White_Level=0, State=1, all _Enable=0)")

    def _on_toggle(self, ch_name):
        """When a channel is enabled, disable all others first."""
        enabled = self.channel_vars[ch_name]["enabled"].get()

        if enabled:
            for other, vars_ in self.channel_vars.items():
                if other != ch_name and vars_["enabled"].get():
                    vars_["enabled"].set(False)
            self._deactivate_all()
            self._activate_channel(ch_name)
        else:
            self._deactivate_all()

    def _get_save_dir(self) -> Path:
        """Return the directory to save images into."""
        if self.parent is not None:
            return Path(self.parent.dm.active_directory)
        return Path(self.save_dir_var.get())

    def _pick_save_dir(self):
        """Open folder picker for standalone save directory."""
        chosen = filedialog.askdirectory(
            title="Select save directory",
            initialdir=self.save_dir_var.get(),
        )
        if chosen:
            self.save_dir_var.set(chosen)

    def apply_settings(self):
        """Push the currently-enabled channel's settings to hardware."""
        active = next(
            (n for n, v in self.channel_vars.items() if v["enabled"].get()), None
        )
        self._deactivate_all()
        if active:
            self._activate_channel(active)
            print(f"Active channel: {active} | "
                  f"Intensity: {self.channel_vars[active]['level'].get()}% | "
                  f"Exposure: {self.channel_vars[active]['exposure'].get()} ms")
        else:
            print("No channel enabled — all lights off.")

    def snap_image(self):
        """Apply settings, snap a single image, and save to the active directory."""
        self.apply_settings()

        save_dir = self._get_save_dir()
        if not save_dir.exists():
            messagebox.showerror(
                "Save Error",
                f"Save directory does not exist:\n{save_dir}\n\nCreate it or choose another."
            )
            return

        active_ch = next(
            (n for n, v in self.channel_vars.items() if v["enabled"].get()), None
        )

        if self.core:
            try:
                stem = f"{active_ch or 'NONE'}_{self.objective_var.get()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                tfile = umanager.snap_save_image(save_dir, filename_stem=stem)
                # Augment the sidecar JSON with fluorescence-specific metadata
                json_path = tfile.with_suffix('.json')
                fluoro_meta = {
                    "objective": self.objective_var.get(),
                    "channel": active_ch,
                }
                if active_ch:
                    fluoro_meta["intensity_pct"] = self.channel_vars[active_ch]["level"].get()
                    fluoro_meta["exposure_ms"]   = self.channel_vars[active_ch]["exposure"].get()
                if json_path.exists():
                    with open(json_path, 'r') as f:
                        md = json.load(f)
                    md.update(fluoro_meta)
                    with open(json_path, 'w') as f:
                        json.dump(md, f, indent=4)
                print(f"Image saved: {tfile}")
            except Exception as e:
                messagebox.showerror("Snap Error", str(e))
        else:
            stem = f"{active_ch or 'NONE'}_{self.objective_var.get()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"[DEMO] snap_save_image({save_dir}, filename_stem='{stem}')")

    def all_off(self):
        """Disable all channels."""
        for vars_ in self.channel_vars.values():
            vars_["enabled"].set(False)
        self._deactivate_all()
        print("All channels disabled.")

    def update_connection(self, core):
        """Re-attach to a freshly reconnected Micro-Manager instance."""
        self.core = core
        status_color = "#22c55e" if core else "#ef4444"
        status_text  = "CONNECTED" if core else "DEMO MODE"
        self._status_label.config(text=f"● {status_text}", fg=status_color)
        if core:
            self._init_safe_state()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = FluorescenceGUI(root)
    root.mainloop()
