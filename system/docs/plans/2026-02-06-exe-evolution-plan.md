# SAEC-O&G Professional .EXE Evolution Plan

> **Status:** Phase 1 MVP COMPLETE. This plan covers Phases 2-4.
> **Target audience:** Academic peers (thesis committee, research colleagues)
> **UI style:** Faithful Win98 retro (tkinter/ttk, enhanced theming)
> **Portability:** Self-contained .exe, zero prerequisites on target machine
> **Priority order:** Robustness > Features > UI Polish > Packaging

---

## Phase 2: Robustness (Bulletproof for Demos)

> Goal: The app never crashes, never loses data, and always gives clear feedback.

### Task 2.1: Thread-safe RunQueue

**Files:**
- Modify: `system/src/run_queue.py`
- Create: `system/tests/test_run_queue.py`

**Step 1: Add threading.Lock to RunQueue**
- Wrap all `_items` mutations in `with self._lock:`
- Protect `pending_count`, `running_item`, `snapshot()` reads

**Step 2: Write concurrency tests (RED → GREEN)**
- Test: enqueue from main thread while job runner reads from worker thread
- Test: cancel while start_next is executing
- Test: snapshot consistency under concurrent modification

**Step 3: Validate**
- `python -m pytest tests/test_run_queue.py -v`

---

### Task 2.2: Global exception handler + error dialogs

**Files:**
- Modify: `system/src/gui/app.py`
- Create: `system/src/gui/dialog_error.py`

**Step 1: Override Tk.report_callback_exception**
- Catch unhandled exceptions in GUI callbacks
- Show user-friendly error dialog (Win98-styled messagebox)
- Log full traceback to file

**Step 2: Wrap job runner thread in try/except**
- Catch exceptions in `PipelineJobRunner._run_process()`
- Map common errors to user messages:
  - `FileNotFoundError` → "Python interpreter not found"
  - `PermissionError` → "Access denied to output folder"
  - `subprocess.TimeoutExpired` → "Pipeline timed out after X minutes"
  - Generic → "Unexpected error. Check logs for details."

**Step 3: Add error dialog with "Copy to Clipboard" button**
- Traceback text in scrollable read-only field
- "Copy Error" button for easy bug reporting

---

### Task 2.3: Structured logging to file

**Files:**
- Create: `system/src/log_config.py`
- Modify: `system/src/gui/panel_logs.py`
- Modify: `system/src/gui/app.py`

**Step 1: Configure Python logging module**
- `RotatingFileHandler` → `{project_root}/logs/saec-og.log` (max 5MB, 3 backups)
- `StreamHandler` → feed LogsPanel via queue
- Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

**Step 2: Add log level filter to LogsPanel**
- Combobox: ALL / INFO / WARNING / ERROR
- Filter displayed lines without losing history

**Step 3: Add scrollback limit to LogsPanel**
- Cap at 5000 lines, trim oldest 1000 when exceeded
- Show "[... N earlier lines trimmed]" marker

---

### Task 2.4: Graceful shutdown

**Files:**
- Modify: `system/src/gui/app.py`
- Modify: `system/src/job_runner.py`

**Step 1: Intercept WM_DELETE_WINDOW**
- If job running: show "Pipeline is running. Cancel and quit?" dialog
- If queue has pending jobs: show "N jobs pending. Quit anyway?"

**Step 2: Implement clean cancellation**
- Send SIGTERM (or terminate() on Windows) to subprocess
- Wait up to 5 seconds for graceful exit
- Force-kill if still running after timeout
- Clean up temp files

**Step 3: Save session state on exit**
- Persist queue history to disk (see Task 2.6)
- Save window geometry
- Flush log handlers

---

### Task 2.5: Subprocess timeout

**Files:**
- Modify: `system/src/job_runner.py`
- Modify: `system/src/presets.py`

**Step 1: Add timeout_minutes to RunRequest**
- Default: 30 minutes
- Configurable per preset (pilot=10min, batch=60min)

**Step 2: Implement timeout in _run_process**
- Monitor elapsed time in reader thread
- On timeout: terminate process, set status="timeout", log warning

**Step 3: Show timeout in QueuePanel**
- New status value: "timeout" with distinct color (orange)

---

### Task 2.6: Queue persistence

**Files:**
- Modify: `system/src/run_queue.py`
- Modify: `system/src/gui/app.py`

**Step 1: Serialize queue to JSON**
- Save completed/failed/cancelled jobs to `{workspace}/.saec/queue_history.json`
- On startup: load history into QueuePanel for reference
- Running/pending jobs NOT restored (they didn't finish)

**Step 2: Limit history size**
- Keep last 100 jobs, trim oldest on save

---

### Task 2.7: Input validation

**Files:**
- Modify: `system/src/gui/panel_run.py`
- Modify: `system/src/job_runner.py`

**Step 1: Validate before enqueue**
- Article ID: must match pattern `ART_\d{3}` or be empty (all)
- Step: must be in {1, 2, 3, 5}
- Project must be selected
- Workspace must exist

**Step 2: Show inline validation errors**
- Red border on invalid fields (Win98 style: red text label below field)
- Disable "Run" button until all fields valid

---

### Task 2.8: Error classification from subprocess

**Files:**
- Create: `system/src/error_classifier.py`
- Modify: `system/src/gui/panel_queue.py`

**Step 1: Parse stderr/stdout patterns**
- Map known patterns to user-friendly messages:
  - `ModuleNotFoundError` → "Missing dependency: {module}"
  - `ConnectionError` → "Cannot reach Ollama/API server"
  - `yaml.YAMLError` → "Malformed YAML in extraction output"
  - `FileNotFoundError: .*\.pdf` → "PDF file not found: {path}"
  - Exit code 0 → "Completed successfully"
  - Exit code 1 → "Pipeline error (see logs)"
  - Exit code -15 → "Cancelled by user"

**Step 2: Show classified error in QueuePanel tooltip**
- Hover over failed job → show classified error message

---

### Task 2.9: Window state persistence

**Files:**
- Modify: `system/src/settings_store.py`
- Modify: `system/src/gui/app.py`

**Step 1: Save geometry on exit**
- Window position (x, y), size (width, height)
- PanedWindow sash position (left/right split ratio)
- Active tab index

**Step 2: Restore on startup**
- Validate saved geometry is within current screen bounds
- Fall back to defaults if monitor changed

---

## Phase 3: Features (Professional Functionality)

> Goal: The app does everything a researcher needs without touching the terminal.

### Task 3.1: Safety guardrails

**Files:**
- Create: `system/src/safety_policy.py`
- Modify: `system/src/gui/panel_run.py`
- Create: `system/tests/test_safety_policy.py`

**Step 1: Define policy rules**
- `force=True` requires confirmation dialog
- `force=True` + `mode=all` requires DOUBLE confirmation ("This will reprocess ALL articles")
- Cannot run pipeline without at least 1 PDF in `inputs/articles/`
- Cannot run extraction (step 3) without ingest (step 2) outputs existing

**Step 2: Implement confirmation dialogs**
- Win98-styled warning dialog with yellow triangle icon
- "Are you sure?" + description of what will happen
- Checkbox: "Don't ask again this session" (not persisted)

**Step 3: Tests**
- `python -m pytest tests/test_safety_policy.py -v`

---

### Task 3.2: YAML preview panel

**Files:**
- Create: `system/src/gui/panel_yaml_preview.py`
- Modify: `system/src/gui/panel_outputs.py`

**Step 1: Add preview pane to Outputs tab**
- Split Outputs tab: file list (top) + preview (bottom)
- On file select: load and display YAML content

**Step 2: Basic syntax highlighting**
- Keys in bold
- Strings in dark blue
- CIMO section headers highlighted
- Read-only text widget with horizontal scroll

**Step 3: CIMO summary view**
- Toggle button: "Raw YAML" / "CIMO Summary"
- Summary view: formatted table showing C, I, M, O fields with labels

---

### Task 3.3: Progress indicators

**Files:**
- Modify: `system/src/gui/panel_status.py`
- Modify: `system/src/job_runner.py`

**Step 1: Parse pipeline stdout for progress markers**
- Detect patterns: `[Article X/N]`, `[Step 2/5]`, percentage markers
- Update StatusPanel progress bar accordingly

**Step 2: Add progress bar to status bar**
- Win98-style segmented progress bar (blue blocks)
- Show "Processing article 3 of 47..." text
- Indeterminate mode when progress can't be parsed

**Step 3: Elapsed time display**
- Show elapsed time since job started: "Running: 02:34"
- On completion: "Completed in 05:12"

---

### Task 3.4: Output filtering and search

**Files:**
- Modify: `system/src/gui/panel_outputs.py`

**Step 1: Add filter bar above file list**
- Combobox: All / YAML / Logs / Consolidated
- Text entry: filter by filename (substring match)

**Step 2: Sort controls**
- Click column headers to sort by name/date/size
- Arrow indicator on active sort column

---

### Task 3.5: Diagnostics panel

**Files:**
- Create: `system/src/gui/panel_diagnostics.py`
- Create: `system/src/health_check.py`
- Modify: `system/src/gui/app.py`

**Step 1: Health check module**
- Check Ollama connectivity: `GET http://localhost:11434/api/tags`
- Check API keys configured: read `.env` for ANTHROPIC_API_KEY, OPENAI_API_KEY
- Check disk space: warn if < 1GB free
- Check available models: list Ollama models
- Check Python packages: verify critical imports

**Step 2: Diagnostics tab in GUI**
- New tab in right panel: "Diagnostics"
- Table: Check / Status (OK/WARN/FAIL) / Details
- "Run Checks" button to refresh
- Auto-run on workspace selection

**Step 3: Startup health check**
- Run critical checks (Python, disk space) on app startup
- Show warning banner if any FAIL

---

### Task 3.6: Keyboard shortcuts

**Files:**
- Modify: `system/src/gui/app.py`

**Step 1: Bind shortcuts**
- `Ctrl+R` → Run pipeline (same as clicking Run button)
- `Ctrl+Shift+C` → Cancel running job
- `Ctrl+L` → Clear logs
- `Ctrl+W` → Change workspace
- `F5` → Refresh outputs
- `Ctrl+Q` → Quit (with graceful shutdown)
- `F1` → Help/About

**Step 2: Show shortcuts in menu items**
- File > Quit    Ctrl+Q
- Pipeline > Run    Ctrl+R
- etc.

---

### Task 3.7: Context menus

**Files:**
- Modify: `system/src/gui/panel_outputs.py`
- Modify: `system/src/gui/panel_queue.py`

**Step 1: Output explorer context menu**
- Right-click on file: Open / Open Containing Folder / Copy Path / Delete
- Right-click on empty area: Refresh / Open Project Folder

**Step 2: Queue context menu**
- Right-click on job: View Logs / Copy Command / Cancel (if running)

---

### Task 3.8: Tooltips

**Files:**
- Create: `system/src/gui/tooltip.py`
- Modify: all panel files

**Step 1: Implement Win98-style tooltip widget**
- Yellow background (#FFFFE1), black text, 1px black border
- Show after 500ms hover, hide on mouse leave
- Max width 300px, word wrap

**Step 2: Add tooltips to all controls**
- Preset selector: "Choose a predefined pipeline configuration"
- Mode dropdown: "all = process every article, step = run single step"
- Dry-run checkbox: "Simulate execution without making changes"
- Force checkbox: "Reprocess articles even if outputs exist"
- Run button: "Start pipeline execution (Ctrl+R)"
- Every toolbar button, menu item, and panel control

---

### Task 3.9: About dialog

**Files:**
- Create: `system/src/gui/dialog_about.py`

**Step 1: Create Win98-style About dialog**
- Project name: "SAEC-O&G"
- Subtitle: "Sistema Autonomo de Extracao CIMO para Oleo & Gas"
- Version: read from `__version__` or hardcoded
- Author: user's name
- Institution: university/program name
- Tech stack: Python, Tkinter, PyInstaller, Ollama
- Win98 logo area (optional bitmap)

---

### Task 3.10: Export summary report

**Files:**
- Create: `system/src/export_report.py`
- Modify: `system/src/gui/app.py`

**Step 1: Generate extraction summary CSV**
- Columns: Article ID, Title, Status, C count, I count, M count, O count, Quality Score, Timestamp
- Source: scan `outputs/yamls/` directory

**Step 2: Add menu item**
- Pipeline > Export Summary Report...
- File save dialog → choose location for CSV

**Step 3: Optional HTML report**
- Formatted table with color-coded quality scores
- Suitable for thesis appendix

---

### Task 3.11: Job completion notification

**Files:**
- Modify: `system/src/gui/app.py`

**Step 1: Flash taskbar on completion**
- Use `wm_attributes('-topmost', True/False)` flash technique
- Or `ctypes` call to `FlashWindowEx` on Windows

**Step 2: Optional sound**
- Win98 "tada.wav" or system default notification sound
- Setting to enable/disable

---

### Task 3.12: Real-time article counter

**Files:**
- Modify: `system/src/gui/panel_status.py`
- Modify: `system/src/job_runner.py`

**Step 1: Parse stdout for article progress**
- Regex: `\[(\d+)/(\d+)\]` or `Processing article (\d+) of (\d+)`
- Update StatusPanel: "Processing 3/47 articles"

**Step 2: Show in status bar**
- Format: "Article 3/47 | Step: Extraction | Elapsed: 02:34"

---

## Phase 4: UI Polish (Faithful Win98 Aesthetic)

> Goal: Looks like a real Win98 application, not a homework tkinter project.

### Task 4.1: Toolbar with pixel art icons

**Files:**
- Create: `system/src/gui/toolbar.py`
- Create: `system/src/gui/resources/icons/` (16x16 BMP/PNG files)
- Modify: `system/src/gui/app.py`

**Step 1: Create 16x16 pixel art icons**
- Using code-generated icons (no external assets needed):
  - Play triangle (green) → Run
  - Stop square (red) → Cancel
  - Refresh arrows (blue) → Refresh
  - Folder (yellow) → Open Folder
  - Gear (gray) → Settings
  - Question mark (blue) → Help
  - Document (white) → New Project
  - Magnifier (blue) → Diagnostics

**Step 2: Build toolbar frame**
- Horizontal frame below menu bar
- Raised relief buttons with icon + optional text
- Separator lines between groups
- Win98 sunken border on toolbar frame

---

### Task 4.2: Splash screen

**Files:**
- Create: `system/src/gui/splash.py`
- Modify: `system/gui_main.py`

**Step 1: Create splash window**
- Overrideredirect (no title bar)
- Centered on screen
- Project name in large text
- Version and author below
- Win98-style segmented progress bar
- Background: classic Win98 gray

**Step 2: Show for 2 seconds during startup**
- Display splash → initialize app → destroy splash → show main window
- Progress bar advances during initialization steps

---

### Task 4.3: Custom .exe icon

**Files:**
- Create: `system/src/gui/resources/saec-og.ico`
- Modify: `system/SAEC-OG.spec`

**Step 1: Generate .ico file**
- Multi-resolution: 16x16, 32x32, 48x48, 256x256
- Design: Oil rig or gear motif with "SAEC" text
- Can be generated via Pillow script or manually created

**Step 2: Wire into PyInstaller spec**
- `icon='src/gui/resources/saec-og.ico'` in EXE() block

**Step 3: Set window icon**
- `self.iconbitmap('saec-og.ico')` in app.py

---

### Task 4.4: Status bar enhancements

**Files:**
- Modify: `system/src/gui/app.py`
- Modify: `system/src/gui/layout_main.py`

**Step 1: Multi-section status bar**
- Section 1: Status message ("Ready" / "Running pipeline...")
- Section 2: Article counter ("3/47")
- Section 3: Elapsed time
- Section 4: Clock (HH:MM)
- Win98 sunken relief on each section

---

### Task 4.5: Treeview icons

**Files:**
- Modify: `system/src/gui/panel_outputs.py`
- Modify: `system/src/gui/panel_queue.py`

**Step 1: Create file type icons (16x16)**
- YAML: blue document icon
- PDF: red document icon
- LOG: gray notepad icon
- CSV: green table icon
- Folder: yellow folder icon

**Step 2: Assign icons in Treeview**
- Use `image` parameter in treeview.insert()

---

### Task 4.6: Disabled state styling

**Files:**
- Modify: `system/src/gui/panel_run.py`
- Modify: `system/src/gui/app.py`

**Step 1: Disable controls when appropriate**
- No workspace selected → disable everything except workspace selector
- No project selected → disable Run, Outputs, Diagnostics
- Job running → disable Run button, enable Cancel
- Proper gray-out visual (Win98 disabled look)

---

### Task 4.7: PanedWindow resize grips

**Files:**
- Modify: `system/src/gui/layout_main.py`

**Step 1: Replace fixed layout with PanedWindow**
- Left panel (RunPanel + StatusPanel) + Right panel (tabs)
- Draggable sash with Win98 grip dots
- Minimum sizes: left 280px, right 400px
- Persist sash position (via settings_store)

---

## Phase 5: Packaging (Self-Contained .exe)

> Goal: Double-click SAEC-OG.exe on any Windows 10/11 machine and it just works.

### Task 5.1: Optimize PyInstaller bundle

**Files:**
- Modify: `system/SAEC-OG.spec`
- Modify: `system/build_exe.bat`

**Step 1: Audit included packages**
- Run `pyinstaller --debug` to list all collected modules
- Exclude unnecessary packages aggressively:
  - Already excluded: torch, tensorflow, sklearn, cv2, chromadb, onnxruntime
  - Also exclude: matplotlib, scipy, numpy (if not needed by core)
  - Keep: tkinter, pathlib, json, yaml, subprocess, threading, logging

**Step 2: Choose onedir vs onefile**
- Recommend: `--onedir` (faster startup, easier debugging)
- Bundle as ZIP for distribution if desired
- Test: `--onefile` as alternative (slower startup but single file)

**Step 3: UPX compression**
- Install UPX, add `--upx-dir` to spec
- Typical reduction: 40-60% on exe size

---

### Task 5.2: Graceful handling of missing dependencies

**Files:**
- Modify: `system/src/gui/app.py`
- Create: `system/src/gui/dialog_setup.py`

**Step 1: First-run wizard**
- Detect if `.env` exists with API keys
- If not: show setup dialog
  - "Welcome to SAEC-O&G!"
  - Text fields for: Anthropic API Key, OpenAI API Key (optional)
  - Ollama URL (default: http://localhost:11434)
  - "Test Connection" button
  - Save to project `.env`

**Step 2: Handle missing Ollama gracefully**
- On startup: try connecting to Ollama
- If unavailable: show info banner "Ollama not detected - API-only mode"
- Disable local-only preset, show warning on local_only selection

---

### Task 5.3: Version stamping

**Files:**
- Create: `system/src/version.py`
- Modify: `system/SAEC-OG.spec`

**Step 1: Central version file**
```python
__version__ = "1.0.0"
__build_date__ = "2026-02-06"
```

**Step 2: Embed in .exe metadata**
- PyInstaller `version_info` parameter
- Visible in Windows File Properties > Details:
  - Product name: SAEC-O&G
  - File description: Sistema Autonomo de Extracao CIMO
  - Product version: 1.0.0

---

### Task 5.4: Clean machine testing

**Files:**
- Create: `system/docs/testing-checklist.md`

**Step 1: Test matrix**
- Windows 10 (clean VM)
- Windows 11 (clean VM)
- Verify: app launches, workspace creation works, settings persist
- Verify: proper error message if Ollama/APIs unavailable
- Verify: no "DLL not found" errors
- Verify: file dialogs work, output explorer opens files

---

### Task 5.5: Bundle prompts and assets

**Files:**
- Modify: `system/SAEC-OG.spec`

**Step 1: Verify bundled data files**
- `prompts/guia_v3_3_prompt.md` → included
- `prompts/local_extraction_prompt.md` → included
- `src/gui/resources/icons/` → included (when created)
- `src/gui/resources/saec-og.ico` → included

**Step 2: Use sys._MEIPASS for resource paths**
- Modify resource loading to work both in dev and bundled mode
- Helper function: `get_resource_path(relative_path)` using `sys._MEIPASS`

---

## Implementation Order (Recommended)

```
WEEK 1: Robustness Core
  2.1 Thread-safe queue
  2.2 Global exception handler
  2.3 Logging to file
  2.4 Graceful shutdown

WEEK 2: Robustness Complete
  2.5 Subprocess timeout
  2.6 Queue persistence
  2.7 Input validation
  2.8 Error classification
  2.9 Window state persistence

WEEK 3: Core Features
  3.1 Safety guardrails
  3.5 Diagnostics panel
  3.6 Keyboard shortcuts
  3.8 Tooltips

WEEK 4: Rich Features
  3.2 YAML preview
  3.3 Progress indicators
  3.4 Output filtering
  3.7 Context menus

WEEK 5: UI Polish
  4.1 Toolbar with icons
  4.2 Splash screen
  4.3 Custom .exe icon
  4.4 Status bar enhancements
  4.5 Treeview icons
  4.6 Disabled state styling
  4.7 PanedWindow resize grips

WEEK 6: Packaging & Polish
  5.1 Optimize PyInstaller bundle
  5.2 First-run wizard
  5.3 Version stamping
  5.4 Clean machine testing
  5.5 Bundle prompts and assets
  3.9 About dialog
  3.10 Export summary report
  3.11 Job completion notification
  3.12 Real-time article counter
```

---

## Dependency Graph

```
2.1 (thread safety) ← 2.6 (queue persistence)
2.2 (exception handler) ← 2.4 (graceful shutdown)
2.3 (logging) ← 3.3 (progress indicators)
2.7 (input validation) ← 3.1 (safety guardrails)
3.5 (diagnostics) ← 5.2 (first-run wizard)
4.1 (toolbar icons) ← 4.5 (treeview icons)
4.3 (exe icon) ← 5.1 (pyinstaller bundle)
5.3 (version) ← 3.9 (about dialog)
```

Tasks without arrows can be parallelized freely.

---

## Quality Gates (Apply to ALL tasks)

Before marking any task complete:
- [ ] Unit tests pass: `python -m pytest tests/ -v`
- [ ] Type hints on public functions
- [ ] Proper exception handling (no bare `except:`)
- [ ] Logging with structured fields
- [ ] Win98 theme consistency (use `win98_theme.py` colors)
- [ ] Works in both dev mode (`python gui_main.py`) and bundled mode (`.exe`)

---

## Total Feature Count: 40

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1: MVP | 12 | COMPLETE |
| Phase 2: Robustness | 9 | PENDING |
| Phase 3: Features | 12 | PENDING |
| Phase 4: UI Polish | 7 | PENDING |
| Phase 5: Packaging | 5 | PENDING |
| **Total** | **45** | **12/45 done** |
