from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKBOOK = PROJECT_ROOT / "data/raw/主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.xlsx"


def console_python_executable() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        sibling = executable.with_name("python.exe")
        if sibling.exists():
            return str(sibling)
    return str(executable)


def python_command(*args: str) -> list[str]:
    return [console_python_executable(), *args]


def hidden_process_flags() -> int:
    if os.name != "nt":
        return 0
    return subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP


@dataclass
class ManagedProcess:
    name: str
    command: list[str]
    cwd: Path = PROJECT_ROOT
    process: subprocess.Popen[str] | None = None

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


class DevDashboard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Game Character AI 启动面板")
        self.geometry("1120x760")
        self.minsize(980, 620)

        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.processes: dict[str, ManagedProcess] = {
            "ollama": ManagedProcess("Ollama", ["ollama", "serve"]),
            "api": ManagedProcess("FastAPI", python_command("-m", "uvicorn", "src.api:app", "--host", "127.0.0.1", "--port", "8000", "--reload")),
            "gradio": ManagedProcess("Gradio", python_command("-m", "src.gradio_app")),
        }
        self.workbook_path = tk.StringVar(value=str(DEFAULT_WORKBOOK))
        self.status_vars = {key: tk.StringVar(value="未启动") for key in self.processes}

        self._build_ui()
        self.after(120, self._drain_logs)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Game Character AI 演示控制台", font=("Microsoft YaHei UI", 17, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="打开项目目录", command=lambda: self._open_path(PROJECT_ROOT)).pack(side=tk.RIGHT)

        service_box = ttk.LabelFrame(root, text="服务启动", padding=12)
        service_box.pack(fill=tk.X, pady=(14, 10))

        self._service_row(service_box, 0, "ollama", "Ollama 模型服务", "本地大模型运行服务，默认地址 http://127.0.0.1:11434")
        self._service_row(service_box, 1, "api", "FastAPI 后端", "对外提供 /chat、/search、/editor、/permissions 等接口")
        self._service_row(service_box, 2, "gradio", "Gradio 调试页", "用于调试检索结果、提示词和模型回复")

        action_box = ttk.LabelFrame(root, text="数据准备", padding=12)
        action_box.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(action_box, text="标注表：").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(action_box, textvariable=self.workbook_path).grid(row=0, column=1, sticky=tk.EW, pady=4)
        ttk.Button(action_box, text="选择 XLSX", command=self._choose_workbook).grid(row=0, column=2, padx=8, pady=4)
        ttk.Button(action_box, text="转换当前 XLSX", command=self.convert_current_workbook).grid(row=0, column=3, padx=(0, 8), pady=4)
        ttk.Button(action_box, text="转换全部 XLSX", command=self.convert_all_workbooks).grid(row=0, column=4, padx=(0, 8), pady=4)
        ttk.Button(action_box, text="刷新 metadata + vector_db", command=self.prepare_without_xlsx).grid(row=0, column=5, pady=4)
        action_box.columnconfigure(1, weight=1)

        quick_box = ttk.LabelFrame(root, text="常用页面", padding=12)
        quick_box.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(quick_box, text="FastAPI 文档 /docs", command=lambda: webbrowser.open("http://127.0.0.1:8000/docs")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(quick_box, text="健康检查 /health", command=lambda: webbrowser.open("http://127.0.0.1:8000/health")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(quick_box, text="权限管理", command=lambda: webbrowser.open("http://127.0.0.1:8000/permissions-ui")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(quick_box, text="结构化编辑器", command=lambda: webbrowser.open("http://127.0.0.1:8000/editor")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(quick_box, text="Gradio", command=lambda: webbrowser.open("http://127.0.0.1:7860")).pack(side=tk.LEFT)

        log_box = ttk.LabelFrame(root, text="运行日志", padding=8)
        log_box.pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(log_box)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text="清空日志", command=self.clear_log).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="停止全部", command=self.stop_all).pack(side=tk.RIGHT)
        self.log_text = tk.Text(log_box, wrap=tk.WORD, height=20, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)

    def _service_row(self, parent: ttk.Frame, row: int, key: str, title: str, detail: str) -> None:
        ttk.Label(parent, text=title, font=("Microsoft YaHei UI", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Label(parent, text=detail).grid(row=row, column=1, sticky=tk.W, pady=5)
        ttk.Label(parent, textvariable=self.status_vars[key], width=10).grid(row=row, column=2, sticky=tk.E, padx=8, pady=5)
        ttk.Button(parent, text="启动", command=lambda: self.start_process(key)).grid(row=row, column=3, padx=4, pady=5)
        ttk.Button(parent, text="停止", command=lambda: self.stop_process(key)).grid(row=row, column=4, padx=4, pady=5)
        parent.columnconfigure(1, weight=1)

    def start_process(self, key: str) -> None:
        item = self.processes[key]
        if item.is_running():
            self._log(item.name, "已经在运行。")
            return
        try:
            item.process = subprocess.Popen(
                item.command,
                cwd=str(item.cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=hidden_process_flags(),
            )
        except FileNotFoundError as exc:
            self._log(item.name, f"启动失败：找不到命令 {item.command[0]!r}。{exc}")
            messagebox.showerror("启动失败", f"找不到命令：{item.command[0]}\n请确认它已安装并加入 PATH。")
            return
        except Exception as exc:
            self._log(item.name, f"启动失败：{exc}")
            messagebox.showerror("启动失败", str(exc))
            return

        self.status_vars[key].set("运行中")
        self._log(item.name, "启动命令：" + " ".join(item.command))
        threading.Thread(target=self._read_process_output, args=(key,), daemon=True).start()

    def stop_process(self, key: str) -> None:
        item = self.processes[key]
        if not item.is_running():
            self.status_vars[key].set("未启动")
            self._log(item.name, "当前没有运行中的进程。")
            return
        assert item.process is not None
        self._log(item.name, "正在停止...")
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(item.process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
            else:
                item.process.terminate()
                item.process.wait(timeout=5)
        except Exception:
            item.process.kill()
        finally:
            self.status_vars[key].set("已停止")

    def stop_all(self) -> None:
        for key in list(self.processes):
            self.stop_process(key)

    def convert_current_workbook(self) -> None:
        workbook = Path(self.workbook_path.get().strip('" '))
        if not workbook.exists():
            messagebox.showerror("文件不存在", f"找不到 XLSX：\n{workbook}")
            return
        command = python_command("-m", "src.xlsx_to_editor_json", str(workbook))
        self._run_once("XLSX", command)

    def convert_all_workbooks(self) -> None:
        if not messagebox.askyesno(
            "确认转换全部 XLSX",
            "将扫描 data/raw 下所有 XLSX/XLSM 文件，跳过模板，并重新生成对应的 .editor.json。是否继续？",
        ):
            return
        command = python_command("-m", "src.prepare_source_data", "--skip-metadata", "--skip-vector")
        self._run_once("XLSX-All", command)

    def prepare_without_xlsx(self) -> None:
        command = python_command("-m", "src.prepare_source_data", "--skip-xlsx")
        self._run_once("Prepare", command)

    def _run_once(self, label: str, command: list[str]) -> None:
        self._log(label, "执行命令：" + " ".join(command))
        threading.Thread(target=self._run_once_worker, args=(label, command), daemon=True).start()

    def _run_once_worker(self, label: str, command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.log_queue.put((label, line.rstrip()))
            code = process.wait()
            self.log_queue.put((label, f"命令结束，退出码 {code}"))
        except Exception as exc:
            self.log_queue.put((label, f"执行失败：{exc}"))

    def _read_process_output(self, key: str) -> None:
        item = self.processes[key]
        process = item.process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            self.log_queue.put((item.name, line.rstrip()))
        code = process.wait()
        self.log_queue.put((item.name, f"进程退出，退出码 {code}"))
        self.status_vars[key].set("已退出")

    def _drain_logs(self) -> None:
        while True:
            try:
                label, line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(label, line)
        self.after(120, self._drain_logs)

    def _log(self, label: str, line: str) -> None:
        self.log_queue.put((label, line))

    def _append_log(self, label: str, line: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{label}] {line}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _choose_workbook(self) -> None:
        path = filedialog.askopenfilename(
            title="选择剧情标注 XLSX",
            initialdir=str(PROJECT_ROOT / "data/raw"),
            filetypes=[("Excel 工作簿", "*.xlsx *.xlsm"), ("所有文件", "*.*")],
        )
        if path:
            self.workbook_path.set(path)

    def _open_path(self, path: Path) -> None:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.as_uri())

    def _on_close(self) -> None:
        running = [item.name for item in self.processes.values() if item.is_running()]
        if running and not messagebox.askyesno("退出", "还有服务正在运行，是否停止全部并退出？"):
            return
        self.stop_all()
        self.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the local Game Character AI development dashboard.")
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = DevDashboard()
    app.workbook_path.set(str(args.workbook))
    app.mainloop()


if __name__ == "__main__":
    main()
