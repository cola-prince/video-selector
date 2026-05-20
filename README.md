# video-selector

<p align="center">
  <img src="assets/video-selector-logo.png" alt="video-selector logo" width="180">
</p>

A local TUI for finding combinations of video files whose total duration matches an existing audio duration.

## Usage

```bash
uv sync --extra dev
uv run video-selector
```

When running from source, the app requires `ffprobe` to be available on `PATH`.
Release executables built by GitHub Actions bundle `ffprobe`.

Click `Refresh Cache` for a root directory to store local video metadata. After
that, the directory list and matching flow read from the cache; press Enter in
the root input to load existing cached directories without refreshing.

Supported duration formats:

- `123`
- `01:23`
- `01:02:03`

Tolerance uses seconds as `lower,upper`, for example `-1,10`.
