"""Interactive pipeline monitor (`make watch`): candidates, per-stage timeline, files, job dirs.

Pick a candidate on the left. On the right, the Timeline tab lists every ledger event for it
(stage, attempt, cost, outcome); the Files tab browses its directory (blueprint, gate and
quality feedback, red-team, calibration, every authored attempt); the Jobs tab browses the
Harbor job dirs for its authoring and calibration runs. Whatever is highlighted is rendered
in the viewer below (JSON, code, or a condensed trajectory). Read-only.
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, DirectoryTree, Footer, Static, TabbedContent, TabPane

from generator.config import JOBS_DIR, LEDGER_PATH
from scripts import status as st

HIGHLIGHT_SEC = 3.0
MAX_BYTES = 300_000
STATUS_STYLE = {
    "shipped": "green",
    "learnable": "green",
    "building": "cyan",
    "gated": "blue",
    "held": "dim",
    "rejected": "red",
}
SKIP_KEYS = {"audit", "failure", "plan"}


def event_summary(e: dict) -> str:
    """One line for the timeline: the fields that usually explain what happened."""
    r = e["result"]
    bits = []
    for k in ("attempt", "ok", "outcome", "verdict", "decision", "hackable", "reward"):
        if k in r:
            bits.append(f"{k}={r[k]}")
    for k in ("gate_problems", "problems", "reasons"):
        v = r.get(k)
        if v:
            bits.append(f"{k}: " + (str(v[0]) if isinstance(v, list) else str(v))[:90])
    if not bits:
        bits.append(json.dumps({k: v for k, v in r.items() if k not in SKIP_KEYS})[:110])
    return "  ".join(bits)


def ledger_events(cand_id: str) -> list[dict]:
    path = Path(LEDGER_PATH)
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        e = json.loads(line)
        if e["task"] == cand_id or e["task"].startswith(cand_id + "-t"):
            out.append(e)
    return out


def render_trajectory(path: Path) -> Text:
    """Condensed trajectory: one block per step with the agent's message and commands."""
    steps = json.loads(path.read_text()).get("steps", [])
    out = Text()
    for s in steps:
        out.append(f"#{s.get('step_id')} [{s.get('source')}] ", style="bold cyan")
        out.append(f"{s.get('timestamp', '')[11:19]}\n", style="dim")
        msg = (s.get("message") or "").strip()
        if msg:
            out.append(msg[:1500] + ("…" if len(msg) > 1500 else "") + "\n")
        for tc in s.get("tool_calls") or []:
            args = json.dumps(tc.get("arguments", {}))
            out.append(f"  $ {tc.get('function_name')}: {args[:400]}\n", style="yellow")
        obs = s.get("observation")
        if obs:
            res = obs.get("results") if isinstance(obs, dict) else obs
            out.append(f"  → {str(res)[:500]}\n", style="dim")
        out.append("\n")
    return out


def render_file(path: Path):
    size = path.stat().st_size
    if size > MAX_BYTES and path.name != "trajectory.json":
        head = path.read_bytes()[:MAX_BYTES].decode(errors="replace")
        return Text(f"{path} is {size} bytes; showing the first {MAX_BYTES}\n\n{head}")
    if path.name == "trajectory.json":
        return render_trajectory(path)
    text = path.read_text(errors="replace")
    if path.suffix == ".json":
        try:
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except ValueError:
            pass
    lexer = {".md": "markdown", ".sh": "bash", ".py": "python", ".toml": "toml", ".json": "json"}
    lex = "docker" if path.name == "Dockerfile" else lexer.get(path.suffix, "text")
    return Syntax(text, lex, line_numbers=True, word_wrap=True)


class JobsTree(DirectoryTree):
    """Harbor job dirs, limited to the ones that belong to the selected candidate."""

    cand_id = "\0"

    def filter_paths(self, paths):
        root = Path(self.path)
        return [p for p in paths if p.parent != root or self.cand_id in p.name]


class WatchApp(App):
    TITLE = "pipeline watch"
    CSS = """
    #left { width: 64; border: round $primary; }
    #right { width: 1fr; }
    #tabs { height: 45%; }
    #viewer { height: 1fr; border: round $primary; }
    #head { height: 1; background: $panel; padding: 0 1; }
    DataTable, DirectoryTree { height: 1fr; }
    """
    BINDINGS: ClassVar = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("h", "toggle_held", "Show/hide held"),
        ("1", "tab('timeline')", "Timeline"),
        ("2", "tab('files')", "Files"),
        ("3", "tab('jobs')", "Jobs"),
    ]

    def __init__(self, every: int) -> None:
        super().__init__()
        self.every = every
        self.show_held = False
        self.records: list[dict] = []
        self.changed: dict[str, float] = {}
        self.prev: dict[str, tuple] = {}
        self.selected = ""
        self.events: list[dict] = []
        self.spend = ""
        self.spend_at = 0.0

    def compose(self) -> ComposeResult:
        yield Static("loading…", id="head")
        with Horizontal():
            with Vertical(id="left"):
                yield DataTable(id="cands", cursor_type="row", zebra_stripes=True)
            with Vertical(id="right"):
                with TabbedContent(id="tabs"):
                    with TabPane("Timeline [1]", id="timeline"):
                        yield DataTable(id="events", cursor_type="row", zebra_stripes=True)
                    with TabPane("Files [2]", id="files"):
                        yield DirectoryTree(".", id="filetree")
                    with TabPane("Jobs [3]", id="jobs"):
                        yield JobsTree(str(JOBS_DIR), id="jobtree")
                with VerticalScroll(id="viewer"):
                    yield Static("Select a candidate, then an event or file.", id="view")
        yield Footer()

    def on_mount(self) -> None:
        cols = ("id", "slug", "status", "phase", "a", "age", "cal")
        self.query_one("#cands", DataTable).add_columns(*cols)
        self.query_one("#events", DataTable).add_columns("time", "stage", "$", "secs", "summary")
        self.set_interval(self.every, self.action_refresh)
        self.action_refresh()

    def action_tab(self, name: str) -> None:
        self.query_one("#tabs", TabbedContent).active = name

    def action_toggle_held(self) -> None:
        self.show_held = not self.show_held
        self.draw_candidates()

    def action_refresh(self) -> None:
        self.run_worker(self.load, thread=True, exclusive=True, group="load")

    def load(self) -> None:
        counts, shipped, records = st.candidate_records()
        if time.time() - self.spend_at > 60:
            usage = st._run(
                "uv", "run", "--quiet", "--env-file", ".env",
                "python", "-m", "scripts.openrouter_usage",
            ).splitlines()  # fmt: skip
            self.spend = "  ".join(x.strip() for x in usage[:2])
            self.spend_at = time.time()
        head = (
            ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
            + f" | shipped {shipped} | procs {len(st.processes())}"
            + f" | containers {len(st.containers())} | {self.spend}"
        )
        events = ledger_events(self.selected) if self.selected else []
        self.call_from_thread(self.apply, records, head, events)

    def apply(self, records: list[dict], head: str, events: list[dict]) -> None:
        now = time.time()
        for r in records:
            sig = (r["status"], r["phase"], r["attempt"], r["verdict"])
            if r["id"] in self.prev and self.prev[r["id"]] != sig:
                self.changed[r["id"]] = now
            self.prev[r["id"]] = sig
        self.records = records
        grew = len(events) != len(self.events)
        self.events = events
        stamp = f"{datetime.now(UTC):%H:%M:%S}Z"
        self.query_one("#head", Static).update(f"{stamp}  {head}")
        self.draw_candidates()
        if grew:
            self.draw_events()

    def draw_candidates(self) -> None:
        table = self.query_one("#cands", DataTable)
        rows = [r for r in self.records if self.show_held or r["status"] != "held"]
        rows.sort(key=lambda r: (r["status"] != "building", r["id"]))
        now = time.time()
        keys = [r["id"] for r in rows]
        rebuild = keys != [k.value for k in table.rows]
        if rebuild:
            table.clear()
        for i, r in enumerate(rows):
            hot = now - self.changed.get(r["id"], 0) < HIGHLIGHT_SEC
            base = "black on yellow" if hot else STATUS_STYLE.get(r["status"], "")
            cells = (r["id"][-12:], r["slug"][:28], r["status"], r["phase"],
                     r["attempt"], r["age"], r["verdict"])  # fmt: skip
            texts = [Text(c, style=base) for c in cells]
            if rebuild:
                table.add_row(*texts, key=r["id"])
            else:
                for col, t in enumerate(texts):
                    table.update_cell_at((i, col), t)
        if rebuild:
            for i, r in enumerate(rows):
                if r["id"] == self.selected:
                    table.move_cursor(row=i, scroll=False)

    def draw_events(self) -> None:
        table = self.query_one("#events", DataTable)
        cursor = table.cursor_row
        table.clear()
        for i, e in enumerate(self.events):
            table.add_row(
                e["ts"][5:19].replace("T", " "),
                e["stage"],
                f"{e['cost_usd']:.2f}",
                f"{e['seconds']:.0f}",
                event_summary(e),
                key=str(i),
            )
        if self.events:
            table.move_cursor(row=min(cursor, len(self.events) - 1), scroll=False)

    def show(self, renderable) -> None:
        self.query_one("#view", Static).update(renderable)
        self.query_one("#viewer", VerticalScroll).scroll_home(animate=False)

    def on_data_table_row_highlighted(self, ev: DataTable.RowHighlighted) -> None:
        if ev.row_key is None or ev.row_key.value is None:
            return
        if ev.data_table.id == "cands":
            if ev.row_key.value != self.selected:
                self.select_candidate(ev.row_key.value)
        elif ev.data_table.id == "events":
            idx = int(ev.row_key.value)
            if 0 <= idx < len(self.events):
                body = json.dumps(self.events[idx], indent=2, ensure_ascii=False)
                self.show(Syntax(body, "json", word_wrap=True))

    def select_candidate(self, cand_id: str) -> None:
        self.selected = cand_id
        self.events = ledger_events(cand_id)
        self.draw_events()
        rec = next((r for r in self.records if r["id"] == cand_id), None)
        if rec:
            tree = self.query_one("#filetree", DirectoryTree)
            tree.path = rec["path"]
            tree.reload()
        jobs = self.query_one("#jobtree", JobsTree)
        jobs.cand_id = cand_id
        jobs.reload()
        n = len(self.events)
        self.show(Text(f"{cand_id}: {n} ledger events. Pick one, or browse Files/Jobs."))

    def on_directory_tree_file_selected(self, ev: DirectoryTree.FileSelected) -> None:
        try:
            self.show(render_file(ev.path))
        except (OSError, ValueError) as exc:
            self.show(Text(f"cannot render {ev.path}: {exc}"))


def run(every: int) -> int:
    WatchApp(every).run()
    return 0
