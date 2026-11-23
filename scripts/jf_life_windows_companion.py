#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from jf_life_local import resolve_state_dir

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_command(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class CompanionApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("JF LIFE Windows Companion")
        self.geometry("980x700")
        self.state_dir = tk.StringVar(
            value=str(resolve_state_dir(None))
        )
        self.external_source = tk.StringVar(value="DriveD=D:\\")
        self.icloud_source = tk.StringVar(value="iCloud=")
        self.outlook_client_id = tk.StringVar(value="")
        self.token_value = tk.StringVar(value="")
        self.api_host = tk.StringVar(value="0.0.0.0")
        self.api_port = tk.StringVar(value="8712")
        self.live_interval_seconds = tk.StringVar(value="300")
        self.live_cycles = tk.StringVar(value="0")
        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        grid = ttk.Frame(main)
        grid.pack(fill="x")
        for index, (label, variable) in enumerate(
            [
                ("State directory", self.state_dir),
                ("External source", self.external_source),
                ("iCloud source", self.icloud_source),
                ("Outlook client ID", self.outlook_client_id),
            ]
        ):
            ttk.Label(grid, text=label).grid(row=index, column=0, sticky="w", padx=(0, 8), pady=4)
            ttk.Entry(grid, textvariable=variable, width=95).grid(
                row=index, column=1, sticky="ew", pady=4
            )
        grid.columnconfigure(1, weight=1)

        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=(10, 8))
        button_specs = [
            ("Run inventory", self.run_inventory),
            ("Build recovery plan", self.run_recovery_plan),
            ("Outlook connect", self.outlook_connect),
            ("Outlook inventory", self.outlook_inventory),
            ("Outlook plan", self.outlook_plan),
            ("Outlook apply (approved only)", self.outlook_apply),
            ("Build dashboard", self.build_dashboard),
        ]
        for idx, (label, command) in enumerate(button_specs):
            ttk.Button(actions, text=label, command=command).grid(
                row=0, column=idx, padx=4, pady=4
            )

        api_frame = ttk.LabelFrame(main, text="Companion API (for iPhone app)", padding=8)
        api_frame.pack(fill="x", pady=6)
        ttk.Label(api_frame, text="Host").grid(row=0, column=0, sticky="w")
        ttk.Entry(api_frame, textvariable=self.api_host, width=16).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(api_frame, text="Port").grid(row=0, column=2, sticky="w")
        ttk.Entry(api_frame, textvariable=self.api_port, width=10).grid(row=0, column=3, sticky="w", padx=6)
        ttk.Button(api_frame, text="Generate pairing token", command=self.generate_token).grid(
            row=0, column=4, padx=8
        )
        ttk.Label(api_frame, textvariable=self.token_value, foreground="#f0cc73").grid(
            row=0, column=5, sticky="w"
        )
        ttk.Button(api_frame, text="Start API server", command=self.start_api_server).grid(
            row=0, column=6, padx=8
        )

        live_frame = ttk.LabelFrame(main, text="Live updates", padding=8)
        live_frame.pack(fill="x", pady=6)
        ttk.Label(live_frame, text="Interval (sec)").grid(row=0, column=0, sticky="w")
        ttk.Entry(live_frame, textvariable=self.live_interval_seconds, width=10).grid(
            row=0, column=1, sticky="w", padx=6
        )
        ttk.Label(live_frame, text="Cycles (0 = forever)").grid(row=0, column=2, sticky="w")
        ttk.Entry(live_frame, textvariable=self.live_cycles, width=10).grid(
            row=0, column=3, sticky="w", padx=6
        )
        ttk.Button(live_frame, text="Live sync (run once)", command=self.run_live_once).grid(
            row=0, column=4, padx=8
        )
        ttk.Button(live_frame, text="Start live sync loop", command=self.start_live_loop).grid(
            row=0, column=5, padx=8
        )

        self.output = tk.Text(main, height=25, wrap="word")
        self.output.pack(fill="both", expand=True, pady=(8, 0))
        self.output.insert("end", "JF LIFE companion ready.\n")

    def append_output(self, text: str) -> None:
        self.output.insert("end", text)
        self.output.see("end")

    def run_task(self, title: str, args: list[str]) -> None:
        def worker() -> None:
            self.append_output(f"\n[{title}] running...\n")
            completed = run_command(args)
            if completed.stdout:
                self.append_output(completed.stdout + ("\n" if not completed.stdout.endswith("\n") else ""))
            if completed.stderr:
                self.append_output("[stderr]\n" + completed.stderr + ("\n" if not completed.stderr.endswith("\n") else ""))
            self.append_output(f"[{title}] exit {completed.returncode}\n")
            if completed.returncode != 0:
                messagebox.showerror("JF LIFE Companion", f"{title} failed with exit {completed.returncode}.")

        threading.Thread(target=worker, daemon=True).start()

    def base_sources(self) -> list[str]:
        args: list[str] = []
        for value in (self.external_source.get().strip(), self.icloud_source.get().strip()):
            if value:
                args += ["--source", value]
        return args

    def run_inventory(self) -> None:
        args = [
            str(REPO_ROOT / "scripts/jf_life_inventory.py"),
            "--state-dir",
            self.state_dir.get().strip(),
            *self.base_sources(),
        ]
        self.run_task("inventory", args)

    def run_recovery_plan(self) -> None:
        args = [
            str(REPO_ROOT / "scripts/jf_life_recovery.py"),
            "plan",
            "--state-dir",
            self.state_dir.get().strip(),
        ]
        self.run_task("recovery-plan", args)

    def outlook_connect(self) -> None:
        client_id = self.outlook_client_id.get().strip()
        if not client_id:
            messagebox.showinfo("JF LIFE Companion", "Set Outlook client ID first.")
            return
        args = [
            str(REPO_ROOT / "scripts/jf_life_outlook.py"),
            "--state-dir",
            self.state_dir.get().strip(),
            "connect",
            "--client-id",
            client_id,
        ]
        self.run_task("outlook-connect", args)

    def outlook_inventory(self) -> None:
        args = [
            str(REPO_ROOT / "scripts/jf_life_outlook.py"),
            "--state-dir",
            self.state_dir.get().strip(),
            "inventory",
        ]
        self.run_task("outlook-inventory", args)

    def outlook_plan(self) -> None:
        args = [
            str(REPO_ROOT / "scripts/jf_life_outlook.py"),
            "--state-dir",
            self.state_dir.get().strip(),
            "plan",
            "--all-unread",
        ]
        self.run_task("outlook-plan", args)

    def outlook_apply(self) -> None:
        args = [
            str(REPO_ROOT / "scripts/jf_life_outlook.py"),
            "--state-dir",
            self.state_dir.get().strip(),
            "apply",
            "--apply",
        ]
        self.run_task("outlook-apply", args)

    def build_dashboard(self) -> None:
        args = [
            str(REPO_ROOT / "scripts/jf_life_dashboard.py"),
            "--state-dir",
            self.state_dir.get().strip(),
        ]
        self.run_task("dashboard", args)

    def generate_token(self) -> None:
        args = [
            str(REPO_ROOT / "scripts/jf_life_companion_api.py"),
            "--state-dir",
            self.state_dir.get().strip(),
            "--print-token",
        ]
        completed = run_command(args)
        if completed.returncode != 0:
            messagebox.showerror("JF LIFE Companion", completed.stderr or "Token generation failed.")
            return
        token = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
        self.token_value.set(token)
        self.append_output(f"[pairing-token] {token}\n")

    def start_api_server(self) -> None:
        state_dir = self.state_dir.get().strip()
        host = self.api_host.get().strip() or "0.0.0.0"
        port = self.api_port.get().strip() or "8712"
        token = self.token_value.get().strip()
        args = [
            str(REPO_ROOT / "scripts/jf_life_companion_api.py"),
            "--state-dir",
            state_dir,
            "--host",
            host,
            "--port",
            port,
        ]
        if token:
            args += ["--pairing-token", token]
        self.run_task("companion-api", args)

    def _live_sync_args(self, cycles: str) -> list[str]:
        args = [
            str(REPO_ROOT / "scripts/jf_life_live_sync.py"),
            "--state-dir",
            self.state_dir.get().strip(),
            "--interval-seconds",
            self.live_interval_seconds.get().strip() or "300",
            "--cycles",
            cycles,
        ]
        args += self.base_sources()
        client_id = self.outlook_client_id.get().strip()
        if client_id:
            args += ["--outlook-client-id", client_id]
        return args

    def run_live_once(self) -> None:
        self.run_task("live-sync", self._live_sync_args("1"))

    def start_live_loop(self) -> None:
        cycles = self.live_cycles.get().strip() or "0"
        self.run_task("live-sync-loop", self._live_sync_args(cycles))


def main() -> int:
    app = CompanionApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
