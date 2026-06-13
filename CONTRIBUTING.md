# Contributing to Tith Worker

Thanks for your interest in improving **Tith Worker**! Contributions of all
kinds are welcome — bug reports, feature ideas, documentation fixes and code.

This project is maintained by **Corpozy Group** and **Ponir**.

---

## Code of Conduct

Be respectful and constructive. Harassment, personal attacks and spam are not
tolerated. Assume good intent and keep discussions focused on the project.

---

## Ways to Contribute

- 🐛 **Report bugs** — open an issue describing what happened vs. what you expected.
- 💡 **Suggest features** — open an issue explaining the use case.
- 📝 **Improve docs** — fixes to the README or this guide are always welcome.
- 🔧 **Submit code** — fix a bug or implement an agreed-upon feature.

---

## Development Setup

> Requires **Windows 10/11** and **Python 3.10+** (3.12 recommended).

```powershell
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/<your-username>/Tith-worker.git
cd Tith-worker

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python main.py
```

---

## Reporting a Bug

Before opening an issue, please search existing issues to avoid duplicates.
A good bug report includes:

- **Environment** — Windows version, Python version (`python --version`).
- **Steps to reproduce** — a numbered list.
- **Expected vs. actual** behavior.
- **Logs** — relevant lines from `logs/activity.log` if applicable.
- **Screenshots** — if the issue is visual.

---

## Submitting Changes (Pull Requests)

1. **Open an issue first** for anything beyond a trivial fix, so the approach
   can be discussed before you invest time.
2. **Create a branch** from `main`:
   ```powershell
   git checkout -b feature/short-description
   ```
3. **Make your change** following the [style guidelines](#coding-guidelines).
4. **Test it** — see [Testing](#testing).
5. **Commit** with a clear message (see [Commit Messages](#commit-messages)).
6. **Push** to your fork and **open a Pull Request** against `main`.
7. Fill in the PR description: what changed, why, and how you tested it.
   Link the related issue (e.g. `Closes #12`).

Keep PRs focused — one logical change per PR is easier to review.

---

## Coding Guidelines

The codebase is plain Python + Tkinter with no build step. Please match the
existing style:

- **Follow [PEP 8](https://peps.python.org/pep-0008/)** — 4-space indentation,
  `snake_case` for functions/variables, `PascalCase` for classes.
- **Keep modules focused** — recording, playback, idle detection and
  scheduling each live in their own file. Put new logic where it belongs.
- **Match the surrounding code** — naming, section comments
  (`# ── Section ──`), and the existing comment density.
- **No new hard-coded names** — reuse the `APP_NAME` / branding constants in
  `main.py` instead of duplicating strings.
- **Keep the UI responsive** — long-running work (playback, monitors) runs on
  background threads; never block the Tkinter main loop. Marshal UI updates
  back with `self.after(...)`.
- **Preserve the safety stops** — any playback path must remain interruptible
  by `F9`/`F10`, the configurable hotkey, and the top-left corner emergency
  stop.
- **Avoid adding dependencies** unless necessary. If you do, add them to
  `requirements.txt` with a minimum version.

---

## Testing

There is no automated test suite yet, so please verify changes manually before
submitting:

1. **Compile check** — must pass with no errors:
   ```powershell
   python -m py_compile main.py recorder.py player.py idle_detector.py scheduler.py
   ```
2. **Smoke test the app** — launch it and exercise the areas you touched:
   - Record a short macro and stop with `F9`.
   - Play it back (single, all-in-order, looped).
   - Confirm the safety stops still work (`F10`, top-left corner).
   - Check the Scheduler / Idle / Stats tabs if relevant.

Contributions that add automated tests are very welcome.

---

## Commit Messages

Write clear, imperative-mood messages:

```
Add configurable countdown duration

The countdown was hard-coded to 3 seconds. This adds a spinbox in the
Playback Options group and wires it through to the player.
```

- First line: a short summary (~50 chars), imperative ("Add", "Fix", "Update").
- Blank line, then an optional body explaining *what* and *why*.

---

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE) that covers this project.
