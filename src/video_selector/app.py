from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Static,
)

from video_selector.cache import CacheRefreshProgress, CacheRefreshResult, VideoCache
from video_selector.duration import (
    DurationParseError,
    format_duration,
    parse_duration,
    parse_tolerance,
)
from video_selector.export import export_matches
from video_selector.search import SearchResult, find_matches


DEFAULT_MAX_RESULTS = 20
DEFAULT_TIMEOUT_SECONDS = 60


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

    #refresh-progress {
        margin-bottom: 1;
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
    cache: VideoCache

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="form"):
                yield Label("Inputs", classes="section-title")
                yield Input(
                    placeholder="Target duration, e.g. 123, 01:23, 01:02:03",
                    id="target",
                )
                yield Input(
                    value="-1,10",
                    placeholder="Tolerance seconds, e.g. -1,10",
                    id="tolerance",
                )
                yield Input(placeholder="Root directory, Enter loads cache", id="root")
                yield Input(placeholder="Optional output directory", id="output")
                yield Input(
                    value=str(DEFAULT_MAX_RESULTS),
                    placeholder="Max results",
                    id="max-results",
                )
                yield Input(
                    value="1", placeholder="Min files per result", id="min-files"
                )
                yield ProgressBar(id="refresh-progress")
                with Horizontal(classes="button-row"):
                    yield Button("Refresh Cache", id="refresh-cache", variant="primary")
                    yield Button("Find", id="find", variant="success")
                with Horizontal(classes="button-row"):
                    yield Button("All", id="select-all")
                    yield Button("None", id="clear-selection")
            with Vertical(id="workspace"):
                yield Label("Directories", classes="section-title")
                with VerticalScroll(id="directory-list"):
                    yield Static("Enter a root directory and refresh cache.")
                yield Label("Results", classes="section-title")
                yield RichLog(id="results", wrap=True, highlight=True)
        yield Static("Ready.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.directories = []
        self.cache = VideoCache()
        self.query_one("#refresh-progress", ProgressBar).update(total=1, progress=0)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "refresh-cache":
            await self.refresh_cache()
        elif button_id == "find":
            await self.find_matches()
        elif button_id == "select-all":
            self.set_all_directories(True)
        elif button_id == "clear-selection":
            self.set_all_directories(False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "root":
            return
        root_text = event.value.strip()
        if not root_text:
            self.set_status("Root directory is required.")
            return

        root = Path(root_text).expanduser().resolve()
        if await self.load_cached_directories(root):
            self.set_status(f"Loaded {len(self.directories)} cached directories.")

    async def refresh_cache(self) -> None:
        root_text = self.query_one("#root", Input).value.strip()
        if not root_text:
            self.set_status("Root directory is required.")
            return

        root = Path(root_text).expanduser().resolve()
        self.clear_results()
        self.update_refresh_progress(CacheRefreshProgress("discovering", 0, 1))
        self.set_status(f"Refreshing cache under {root} ...")
        try:
            result = await asyncio.to_thread(
                self.cache.refresh_root,
                root,
                progress=self.threaded_refresh_progress,
            )
        except Exception as exc:
            self.directories = []
            self.render_directories(root, [])
            self.set_status(f"Cache refresh failed: {exc}")
            return

        await self.load_cached_directories(root)
        self.render_refresh_result(result)

    def render_directories(self, root: Path, directories: list[Path]) -> None:
        container = self.query_one("#directory-list", VerticalScroll)
        container.remove_children()

        if not directories:
            container.mount(Static("No cached directories found. Refresh cache first."))
            return

        checkboxes: list[Checkbox] = []
        for directory in directories:
            try:
                label = str(directory.relative_to(root))
            except ValueError:
                label = str(directory)
            checkbox = Checkbox(label, value=False)
            checkbox.directory_path = directory
            checkboxes.append(checkbox)
        container.mount_all(checkboxes)

    async def load_cached_directories(self, root: Path) -> bool:
        try:
            directories = await asyncio.to_thread(self.cache.list_directories, root)
        except Exception as exc:
            self.directories = []
            self.render_directories(root, [])
            self.set_status(f"Could not read cache: {exc}")
            return False

        self.directories = directories
        self.render_directories(root, directories)
        return True

    def set_all_directories(self, value: bool) -> None:
        for checkbox in self.query("#directory-list Checkbox"):
            checkbox.value = value

    async def find_matches(self) -> None:
        try:
            target = parse_duration(self.query_one("#target", Input).value)
            tolerance = parse_tolerance(self.query_one("#tolerance", Input).value)
            output_text = self.query_one("#output", Input).value.strip()
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

        self.set_status("Reading cache and searching combinations ...")
        self.clear_results()
        job = await asyncio.to_thread(
            run_match_job,
            self.cache,
            selected_dirs,
            target,
            tolerance,
            max_results,
            min_files,
        )
        export_path: Path | None = None
        if output_text and job.result.matches:
            try:
                export_path = await asyncio.to_thread(
                    export_matches,
                    job.result.matches,
                    Path(output_text),
                )
            except Exception as exc:
                self.render_results(job, target, min_files)
                self.set_status(f"Results found, but export failed: {exc}")
                return

        self.render_results(job, target, min_files, export_path)

    def selected_directories(self) -> list[Path]:
        selected: list[Path] = []
        for checkbox in self.query("#directory-list Checkbox"):
            if checkbox.value:
                selected.append(checkbox.directory_path)
        return selected

    def render_results(
        self,
        job: MatchJob,
        target: float,
        min_files: int,
        export_path: Path | None = None,
    ) -> None:
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
            f"Read {job.video_count} cached videos",
            f"target {format_duration(target)}",
            f"min files {min_files}",
            f"returned {len(job.result.matches)} matches",
        ]
        if job.result.capped:
            status_parts.append("stopped at max results")
        if job.result.timed_out:
            status_parts.append(f"timed out after {DEFAULT_TIMEOUT_SECONDS:g}s")
        if export_path is not None:
            status_parts.append(f"exported to {export_path}")
        self.set_status("; ".join(status_parts) + ".")

    def clear_results(self) -> None:
        self.query_one("#results", RichLog).clear()

    def set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def threaded_refresh_progress(self, progress: CacheRefreshProgress) -> None:
        self.call_from_thread(self.update_refresh_progress, progress)

    def update_refresh_progress(self, progress: CacheRefreshProgress) -> None:
        bar = self.query_one("#refresh-progress", ProgressBar)
        total = max(progress.total, 1)
        bar.update(total=total, progress=progress.completed)
        if progress.phase == "discovering":
            self.set_status("Discovering videos for cache refresh ...")
        elif progress.phase == "refreshing":
            self.set_status(
                f"Refreshing cache {progress.completed}/{progress.total} ..."
            )
        elif progress.phase == "done":
            self.set_status(f"Cache refresh processed {progress.total} videos.")

    def render_refresh_result(self, result: CacheRefreshResult) -> None:
        log = self.query_one("#results", RichLog)
        log.clear()
        if result.warnings:
            log.write("Warnings:")
            for warning in result.warnings[:20]:
                log.write(f"  - {warning}")
            if len(result.warnings) > 20:
                log.write(f"  - ... {len(result.warnings) - 20} more warnings")

        self.set_status(
            "Cache refreshed: "
            f"{result.total} videos, "
            f"{result.probed} probed, "
            f"{result.reused} reused, "
            f"{result.removed} stale removed, "
            f"{len(result.warnings)} warnings."
        )


def run_match_job(
    cache: VideoCache,
    directories: list[Path],
    target: float,
    tolerance: tuple[float, float],
    max_results: int,
    min_files: int,
) -> MatchJob:
    videos = cache.list_videos(directories)
    result = find_matches(
        videos,
        target=target,
        tolerance=tolerance,
        max_results=max_results,
        min_files=min_files,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )
    return MatchJob(result=result, warnings=[], video_count=len(videos))


def main() -> None:
    VideoSelectorApp().run()
