# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

import subprocess
import os


class KillLauncher:
    def __init__(self, launcher):
        self.launcher = launcher

    def populate(self):
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        if result.returncode != 0:
            label_text = "Failed to get processes"
            button = self.launcher.create_button_with_metadata(label_text, "")
            self.launcher.list_box.append(button)
            self.launcher.current_apps = []
            return

        lines = result.stdout.splitlines()
        processes = []
        for line in lines[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            try:
                pid = int(parts[1])
                cpu = float(parts[2])
                mem = float(parts[3])
                cmd = parts[10]
                if pid != os.getpid():  # exclude self
                    processes.append((pid, cpu, mem, cmd))
            except ValueError:
                continue

        # sort by -cpu, -mem
        processes.sort(key=lambda x: (-x[1], -x[2]))

        for pid, cpu, mem, cmd in processes[:50]:  # limit to 50
            label_text = f"{cmd} (CPU: {cpu:.1f}%, MEM: {mem:.1f}%)"
            button = self.launcher.create_button_with_metadata(label_text, "")
            button.connect("clicked", self.on_kill_clicked, pid)
            self.launcher.list_box.append(button)
        self.launcher.current_apps = []

    def on_kill_clicked(self, button, pid):
        try:
            subprocess.run(["kill", str(pid)], check=True)
            # refresh
            self.launcher.selected_row = None
            self.launcher.populate_apps(">kill")
        except subprocess.CalledProcessError:
            print(f"Failed to kill {pid}")
