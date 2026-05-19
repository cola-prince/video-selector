# video-selector

A local TUI for finding combinations of video files whose total duration matches an existing audio duration.

## Usage

```bash
uv sync --extra dev
uv run video-selector
```

When running from source, the app requires `ffprobe` to be available on `PATH`.
Release executables built by GitHub Actions bundle `ffprobe`.

Supported duration formats:

- `123`
- `01:23`
- `01:02:03`

Tolerance uses seconds as `lower,upper`, for example `-1,10`.

## Build release executables

The repository includes a GitHub Actions workflow at `.github/workflows/build.yml`.
It builds Linux x64, Windows x64, macOS arm64, and macOS x64 executables with PyInstaller.

Run it manually from GitHub:

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Select **Build executables**.
4. Click **Run workflow**.
5. Download the four artifacts from the completed workflow run.

Create a tagged build from your local clone:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow also runs automatically for pushed tags matching `v*`.
