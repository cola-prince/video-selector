from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, RichLog, Static

from video_selector.duration import (
    DurationParseError,
    format_duration,
    parse_duration,
    parse_tolerance,
)
from video_selector.probe import probe_videos
from video_selector.scanner import discover_descendant_dirs, find_video_paths
from video_selector.search import SearchResult, find_matches


DEFAULT_MAX_RESULTS = 20
DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class MatchJob:
    result: SearchResult
    warnings: list[str]
    video_count: int


class VideoSelectorApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
        padding: 1;
    }

    #form {
        width: 38;
        min-width: 34;
        padding-right: 1;
    }

    #workspace {
        width: 1fr;
    }

    Input {
        margin-bottom: 1;
    }

    .button-row {
        height: auto;
        margin-bottom: 1;
    }

    Button {
        margin-right: 1;
    }

    #directory-list {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
        margin-bottom: 1;
    }

    #results {
        height: 2fr;
        border: solid $secondary;
    }

    #status {
        height: auto;
        padding: 0 1;
    }

    Label.section-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    directories: list[Path]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="form"):
                yield Label("Inputs", classes="section-title")
                yield Input(placeholder="Target duration, e.g. 123, 01:23, 01:02:03", id="target")
                yield Input(value="-1,10", placeholder="Tolerance seconds, e.g. -1,10", id="tolerance")
                yield Input(placeholder="Root directory", id="root")
                yield Input(value=str(DEFAULT_MAX_RESULTS), placeholder="Max results", id="max-results")
                yield Input(value="1", placeholder="Min files per result", id="min-files")
                with Horizontal(classes="button-row"):
                    yield Button("Scan", id="scan", variant="primary")
                    yield Button("Find", id="find", variant="success")
                with Horizontal(classes="button-row"):
                    yield Button("All", id="select-all")
                    yield Button("None", id="clear-selection")
            with Vertical(id="workspace"):
                yield Label("Directories", classes="section-title")
                with VerticalScroll(id="directory-list"):
                    yield Static("Enter a root directory and press Scan.")
                yield Label("Results", classes="section-title")
                yield RichLog(id="results", wrap=True, highlight=True)
        yield Static("Ready.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.directories = []

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "scan":
            await self.scan_directories()
        elif button_id == "find":
            await self.find_matches()
        elif button_id == "select-all":
            self.set_all_directories(True)
        elif button_id == "clear-selection":
            self.set_all_directories(False)

    async def scan_directories(self) -> None:
        root_text = self.query_one("#root", Input).value.strip()
        if not root_text:
            self.set_status("Root directory is required.")
            return

        root = Path(root_text).expanduser()
        self.set_status(f"Scanning directories under {root} ...")
        try:
            directories = await asyncio.to_thread(discover_descendant_dirs, root)
        except Exception as exc:
            self.directories = []
            self.render_directories(root, [])
            self.set_status(f"Directory scan failed: {exc}")
            return

        self.directories = directories
        self.render_directories(root, directories)
        self.set_status(f"Found {len(directories)} descendant directories.")

    def render_directories(self, root: Path, directories: list[Path]) -> None:
        container = self.query_one("#directory-list", VerticalScroll)
        container.remove_children()

        if not directories:
            container.mount(Static("No descendant directories found."))
            return

        checkboxes: list[Checkbox] = []
        for directory in directories:
            label = str(directory.relative_to(root))
            checkbox = Checkbox(label, value=False)
            checkbox.directory_path = directory
            checkboxes.append(checkbox)
        container.mount_all(checkboxes)

    def set_all_directories(self, value: bool) -> None:
        for checkbox in self.query("#directory-list Checkbox"):
            checkbox.value = value

    async def find_matches(self) -> None:
        try:
            target = parse_duration(self.query_one("#target", Input).value)
            tolerance = parse_tolerance(self.query_one("#tolerance", Input).value)
            max_results = int(self.query_one("#max-results", Input).value.strip())
            min_files = int(self.query_one("#min-files", Input).value.strip())
            if max_results <= 0:
                raise ValueError("Max results must be greater than zero.")
            if min_files <= 0:
                raise ValueError("Min files per result must be greater than zero.")
        except (DurationParseError, ValueError) as exc:
            self.set_status(str(exc))
            return

        selected_dirs = self.selected_directories()
        if not selected_dirs:
            self.set_status("Select at least one directory.")
            return

        self.set_status("Scanning videos and searching combinations ...")
        self.clear_results()
        job = await asyncio.to_thread(
            run_match_job,
            selected_dirs,
            target,
            tolerance,
            max_results,
            min_files,
            DEFAULT_TIMEOUT_SECONDS,
        )
        self.render_results(job, target, min_files)

    def selected_directories(self) -> list[Path]:
        selected: list[Path] = []
        for checkbox in self.query("#directory-list Checkbox"):
            if checkbox.value:
                selected.append(checkbox.directory_path)
        return selected

    def render_results(self, job: MatchJob, target: float, min_files: int) -> None:
        log = self.query_one("#results", RichLog)
        log.clear()

        if job.warnings:
            log.write("Warnings:")
            for warning in job.warnings[:20]:
                log.write(f"  - {warning}")
            if len(job.warnings) > 20:
                log.write(f"  - ... {len(job.warnings) - 20} more warnings")
            log.write("")

        if not job.result.matches:
            log.write("No matching combinations found.")
        else:
            for index, match in enumerate(job.result.matches, start=1):
                log.write(
                    f"[{index}] total={format_duration(match.total_duration)} "
                    f"delta={format_duration(match.delta)} files={len(match.files)}"
                )
                for video in match.files:
                    log.write(f"  {video.path}")
                log.write("")

        status_parts = [
            f"Scanned {job.video_count} videos",
            f"target {format_duration(target)}",
            f"min files {min_files}",
            f"returned {len(job.result.matches)} matches",
        ]
        if job.result.capped:
            status_parts.append("stopped at max results")
        if job.result.timed_out:
            status_parts.append(f"timed out after {DEFAULT_TIMEOUT_SECONDS:g}s")
        self.set_status("; ".join(status_parts) + ".")

    def clear_results(self) -> None:
        self.query_one("#results", RichLog).clear()

    def set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)


def run_match_job(
    directories: list[Path],
    target: float,
    tolerance: tuple[float, float],
    max_results: int,
    min_files: int,
    timeout_seconds: float,
) -> MatchJob:
    paths = find_video_paths(directories)
    videos, warnings = probe_videos(paths)
    result = find_matches(
        videos,
        target=target,
        tolerance=tolerance,
        max_results=max_results,
        min_files=min_files,
        timeout_seconds=timeout_seconds,
    )
    return MatchJob(result=result, warnings=warnings, video_count=len(videos))


def main() -> None:
    VideoSelectorApp().run()
