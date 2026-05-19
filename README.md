# video-selector

A local TUI for finding combinations of video files whose total duration matches an existing audio duration.

## Usage

```bash
uv sync --extra dev
uv run video-selector
```

The app requires `ffprobe` to be available on `PATH`.

Supported duration formats:

- `123`
- `01:23`
- `01:02:03`

Tolerance uses seconds as `lower,upper`, for example `-1,10`.
