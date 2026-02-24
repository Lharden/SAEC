# Sistema de Projetos e Persistência de Configurações - Implementation Plan

> **For cloud provider:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implementar sistema de projetos com persistência de configurações por projeto, configurações padrão em branco para novos projetos, remoção do "Win98 Edition" do título, e adição de tooltips de ajuda no GUI.

**Architecture:** 
- Cada projeto terá seu próprio arquivo `.env` dentro da pasta do projeto (`projects/<id>/.env`)
- Configurações globais (como janela, preset) continuarão em `~/.saec-og/ui_settings.json`
- Ao abrir, usuário escolhe entre continuar projeto existente ou criar novo
- Tooltips serão adicionados próximos a campos principais usando o sistema existente

**Tech Stack:** Python 3.11+, Tkinter, JSON persistence

---

## Task 1: Modificar DEFAULT_VALUES em dialog_setup.py

**Files:**
- Modify: `system/src/gui/dialog_setup.py:103-125`

**Step 1: Alterar modelos padrão para vazio em novos projetos**

```python
# Em DEFAULT_VALUES, mudar:
"ANTHROPIC_MODEL": "",  # Era "provider-model-1"
"OPENAI_MODEL": "",     # Era "provider-model-2"
```

**Step 2: Manter outros valores padrão para Ollama (local)**

Os valores Ollama podem permanecer pois são modelos locais.

---

## Task 2: Criar funções de persistência de config por projeto

**Files:**
- Create: `system/src/gui/project_config.py`

**Step 1: Criar módulo para gerenciar configurações por projeto**

```python
"""Project-specific configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from gui.dialog_setup import DEFAULT_VALUES


class ProjectConfig:
    """Manages project-specific .env configuration."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.env_path = self.project_root / ".env"

    def exists(self) -> bool:
        """Check if project has saved configuration."""
        return self.env_path.exists()

    def load(self) -> dict[str, str]:
        """Load configuration from project .env file."""
        if not self.env_path.exists():
            return {}
        
        values: dict[str, str] = {}
        for raw in self.env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def save(self, values: dict[str, str]) -> None:
        """Save configuration to project .env file."""
        self.project_root.mkdir(parents=True, exist_ok=True)
        
        lines: list[str] = ["# SAEC Project Configuration"]
        
        for key in sorted(values.keys()):
            value = values[key]
            if value:
                lines.append(f'{key}={value}')
        
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def get_effective_values(self) -> dict[str, str]:
        """Get effective values merging with defaults."""
        effective = dict(DEFAULT_VALUES)
        saved = self.load()
        effective.update(saved)
        return effective


def get_blank_project_defaults() -> dict[str, str]:
    """Get blank defaults for new projects (API keys and models empty)."""
    return {
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENAI_BASE_URL": "",
        "ANTHROPIC_MODEL": "",
        "OPENAI_MODEL": "",
        "OLLAMA_ENABLED": "true",
        "OLLAMA_BASE_URL": "http://localhost:11434/v1",
        "PRIMARY_PROVIDER": "ollama",
        "PROVIDER_EXTRACT": "auto",
        "PROVIDER_REPAIR": "auto",
        "PROVIDER_QUOTES": "auto",
        "PROVIDER_CASCADE_API": "auto",
        "USE_TWO_PASS": "true",
        "OLLAMA_MODEL_CLOUD": "glm-4.7:cloud",
        "OLLAMA_MODEL_CLOUD_FALLBACK": "kimi-k2.5:cloud",
        "OLLAMA_MODEL_CODER": "qwen3-vl:8b",
        "OLLAMA_MODEL_VISION": "qwen3-vl:8b",
        "OLLAMA_EXTRACTION_MODEL": "glm-4.7:cloud",
        "OLLAMA_REPAIR_MODEL": "glm-4.7:cloud",
        "OLLAMA_OCR_MODEL": "glm-ocr:latest",
        "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text-v2-moe:latest",
    }
```

**Step 2: Testar o módulo**

Criar teste simples para verificar leitura/escrita.

---

## Task 3: Criar diálogo de seleção de projeto no início

**Files:**
- Create: `system/src/gui/dialog_startup.py`

**Step 1: Criar diálogo de startup para escolher novo ou existente**

```python
"""Startup dialog for selecting project mode."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path


def prompt_startup_choice(
    parent: tk.Misc,
    recent_workspaces: list[str],
) -> tuple[str, Path | None] | None:
    """
    Show startup dialog to choose between new or existing project.
    
    Returns:
        ("new", workspace_path) or ("existing", workspace_path) or None if cancelled
    """
    dialog = tk.Toplevel(parent)
    dialog.title("SAEC - Selecionar Projeto")
    dialog.configure(bg="#C0C0C0")
    dialog.resizable(False, False)
    
    if isinstance(parent, (tk.Tk, tk.Toplevel)):
        dialog.transient(parent)
    dialog.grab_set()
    
    result: tuple[str, Path | None] | None = None
    
    container = tk.Frame(dialog, bg="#C0C0C0", padx=20, pady=20)
    container.pack(fill="both", expand=True)
    
    # Title
    tk.Label(
        container,
        text="Bem-vindo ao SAEC",
        font=("MS Sans Serif", 12, "bold"),
        bg="#C0C0C0",
    ).pack(pady=(0, 10))
    
    tk.Label(
        container,
        text="Escolha uma opção para continuar:",
        bg="#C0C0C0",
    ).pack(pady=(0, 20))
    
    # Recent workspaces frame
    recent_frame = ttk.LabelFrame(container, text="Workspaces Recentes", padding=10)
    recent_frame.pack(fill="x", pady=(0, 10))
    
    workspace_var = tk.StringVar()
    if recent_workspaces:
        workspace_var.set(recent_workspaces[0])
        recent_combo = ttk.Combobox(
            recent_frame,
            textvariable=workspace_var,
            values=recent_workspaces,
            width=50,
            state="readonly",
        )
        recent_combo.pack(fill="x")
    else:
        tk.Label(
            recent_frame,
            text="Nenhum workspace recente",
            bg="#C0C0C0",
            fg="#666666",
        ).pack()
    
    # Buttons frame
    buttons_frame = tk.Frame(container, bg="#C0C0C0")
    buttons_frame.pack(fill="x", pady=20)
    
    def on_new_project():
        nonlocal result
        ws = workspace_var.get()
        if ws:
            result = ("new", Path(ws))
        else:
            result = ("new", None)
        dialog.destroy()
    
    def on_continue_project():
        nonlocal result
        ws = workspace_var.get()
        if not ws and not recent_workspaces:
            messagebox.showwarning(
                "Workspace necessário",
                "Selecione um workspace primeiro.",
                parent=dialog,
            )
            return
        result = ("existing", Path(ws) if ws else None)
        dialog.destroy()
    
    def on_browse_workspace():
        from tkinter import filedialog
        selected = filedialog.askdirectory(
            parent=dialog,
            title="Selecionar Workspace",
        )
        if selected:
            workspace_var.set(selected)
            if recent_workspaces:
                recent_combo.configure(values=[selected] + recent_workspaces)
    
    # New project button
    tk.Button(
        buttons_frame,
        text="🆕 Novo Projeto",
        command=on_new_project,
        bg="#C0C0C0",
        width=20,
        height=2,
    ).pack(side="left", padx=5)
    
    # Continue button
    tk.Button(
        buttons_frame,
        text="📁 Continuar Projeto",
        command=on_continue_project,
        bg="#C0C0C0",
        width=20,
        height=2,
    ).pack(side="left", padx=5)
    
    # Browse button
    tk.Button(
        buttons_frame,
        text="📂 Procurar...",
        command=on_browse_workspace,
        bg="#C0C0C0",
        width=15,
        height=2,
    ).pack(side="left", padx=5)
    
    # Cancel button
    tk.Button(
        container,
        text="Cancelar",
        command=dialog.destroy,
        bg="#C0C0C0",
    ).pack(pady=(10, 0))
    
    # Center dialog
    dialog.update_idletasks()
    dw = dialog.winfo_width()
    dh = dialog.winfo_height()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    dialog.geometry(f"+{x}+{y}")
    
    dialog.wait_window()
    return result
```

---

## Task 4: Modificar app.py para usar configurações por projeto

**Files:**
- Modify: `system/src/gui/app.py`

**Step 1: Adicionar imports**

```python
# Adicionar aos imports existentes:
from gui.project_config import ProjectConfig, get_blank_project_defaults
from gui.dialog_startup import prompt_startup_choice
```

**Step 2: Modificar __init__ para remover "Win98 Edition"**

```python
# Linha 85, mudar de:
self.title("SAEC - Win98 Edition")
# Para:
self.title("SAEC")
```

**Step 3: Modificar _ensure_first_run_setup para usar projeto**

```python
def _ensure_first_run_setup(self) -> None:
    """Show startup dialog and handle project selection."""
    settings = self._settings_store.load()
    recent = settings.get("recent_workspaces", [])
    
    # Show startup dialog
    choice = prompt_startup_choice(self, recent)
    if choice is None:
        # User cancelled - use last workspace if available
        last_ws = settings.get("last_workspace", "")
        if last_ws and Path(last_ws).exists():
            self._set_workspace(Path(last_ws))
        return
    
    action, workspace = choice
    
    if action == "new":
        # New project flow
        if workspace is None:
            # Need to browse for workspace
            from gui.dialog_workspace import choose_workspace
            workspace = choose_workspace(self, initial_dir=Path.home())
            if workspace is None:
                return
        
        self._set_workspace(workspace)
        
        # Create new project
        if self.workspace_root:
            from gui.dialog_project import prompt_new_project
            name = prompt_new_project(self)
            if name:
                self._on_new_project_with_name(name)
                # Configure with blank defaults
                self._configure_blank_project()
    else:
        # Continue existing project
        if workspace is None and recent:
            workspace = Path(recent[0])
        
        if workspace and workspace.exists():
            self._set_workspace(workspace)
            # Load last project for this workspace
            ws_key = str(workspace)
            last_project = settings.get("last_project_by_workspace", {}).get(ws_key, "")
            if last_project:
                # Will auto-load project config via _select_project_from_label
                self._restore_last_project(last_project)

def _configure_blank_project(self) -> None:
    """Configure new project with blank defaults."""
    if not self.project_root:
        return
    
    config = ProjectConfig(self.project_root)
    blank_defaults = get_blank_project_defaults()
    config.save(blank_defaults)
    
    # Write to .env
    self._write_env_file(blank_defaults)
    
    # Show setup dialog for user to configure
    self._open_setup_dialog()

def _restore_last_project(self, project_id: str) -> None:
    """Restore last selected project."""
    if not self.workspace_root:
        return
    
    root = self.workspace_root / "projects" / project_id
    if not root.exists():
        return
    
    # Find label for this project
    projects = list_projects(self.workspace_root)
    for project in projects:
        if project.project_id == project_id:
            label = f"{project.project_id} | {project.name}"
            self.layout.project_combo.set(label)
            self._select_project_from_label(label)
            break
```

**Step 4: Modificar _select_project_from_label para carregar config do projeto**

```python
def _select_project_from_label(self, label: str) -> None:
    if self.workspace_root is None:
        return

    project_id = self._project_name_to_id.get(label)
    if project_id is None:
        project_id = label.split(" | ", 1)[0] if " | " in label else label

    root = self.workspace_root / "projects" / project_id
    self.project_root = root.resolve()
    
    # Load project-specific configuration
    self._load_project_config()

    self._restore_articles_override()
    self.layout.outputs_panel.set_project_root(self.project_root)
    self.layout.status_panel.set_project(self.project_root, articles_dir=self._effective_articles_dir())
    self.layout.status_var.set(f"Project selected: {project_id}")
    self._settings_store.set_last_project(self.workspace_root, project_id)

    self._configure_logging(self.project_root / "logs")
    self._run_diagnostics_checks()
    self._refresh_enabled_states()

def _load_project_config(self) -> None:
    """Load project-specific .env configuration."""
    if not self.project_root:
        return
    
    config = ProjectConfig(self.project_root)
    if config.exists():
        # Load project-specific values
        values = config.load()
        self._write_env_file(values)
        self.layout.status_var.set(f"Configurações do projeto carregadas")
    else:
        # No project config yet - create with defaults
        pass
```

**Step 5: Modificar _write_env_file para salvar também no projeto**

```python
def _write_env_file(self, values: dict[str, str]) -> None:
    """Write env file to system root and project if applicable."""
    # Write to system root (existing behavior)
    self._write_env_to_path(self._env_path, values)
    
    # Also save to project if we have one
    if self.project_root:
        project_config = ProjectConfig(self.project_root)
        project_config.save(values)
        self.layout.status_var.set(f"Configurações salvas no projeto")

def _write_env_to_path(self, env_path: Path, values: dict[str, str]) -> None:
    """Internal: write env values to specific path."""
    updates = {
        key: ("" if value is None else str(value))
        for key, value in values.items()
    }
    existing_text = ""
    trailing_newline = True
    lines: list[str]

    if env_path.exists():
        existing_text = env_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        lines = existing_text.splitlines()
        trailing_newline = existing_text.endswith(("\n", "\r"))
        if not lines:
            lines = ["# SAEC runtime configuration"]
    else:
        lines = ["# SAEC runtime configuration"]

    existing_keys: set[str] = set()
    rendered_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            rendered_lines.append(line)
            continue

        key, _current_value = line.split("=", 1)
        clean_key = key.strip()
        existing_keys.add(clean_key)
        if clean_key in updates:
            rendered_lines.append(f"{clean_key}={updates[clean_key]}")
        else:
            rendered_lines.append(line)

    appended: list[tuple[str, str]] = []
    for key, value in updates.items():
        if key not in existing_keys:
            appended.append((key, value))

    if (
        "OLLAMA_ENABLED" not in existing_keys
        and not any(key == "OLLAMA_ENABLED" for key, _ in appended)
    ):
        appended.append(("OLLAMA_ENABLED", "true"))

    for key, value in appended:
        rendered_lines.append(f"{key}={value}")

    output = "\n".join(rendered_lines)
    if trailing_newline:
        output += "\n"

    env_path.write_text(output, encoding="utf-8")
```

---

## Task 5: Adicionar tooltips com "?" no dialog_setup.py

**Files:**
- Modify: `system/src/gui/dialog_setup.py`

**Step 1: Adicionar função helper para criar label com tooltip**

```python
def _create_help_label(parent: tk.Misc, text: str, tooltip_text: str, row: int, col: int = 0) -> tk.Label:
    """Create a label with a help icon that shows tooltip on hover."""
    frame = tk.Frame(parent, bg=parent.cget("bg"))
    frame.grid(row=row, column=col, sticky="w", pady=3)
    
    label = tk.Label(frame, text=text, bg=parent.cget("bg"))
    label.pack(side="left")
    
    help_btn = tk.Label(
        frame,
        text=" ?",
        bg="#E0E0E0",
        fg="#000080",
        font=("MS Sans Serif", 8, "bold"),
        relief="raised",
        bd=1,
        padx=2,
    )
    help_btn.pack(side="left", padx=(4, 0))
    
    from gui.tooltip import Tooltip
    Tooltip(help_btn, tooltip_text, delay_ms=300)
    
    return label
```

**Step 2: Substituir labels existentes por versões com help**

Para os campos principais, modificar as linhas que criam os labels:

```python
# Exemplo para API Keys section:
_create_help_label(
    tab1_inner,
    "Cloud API key (provider 1)",
    "Chave de API cloud do provedor 1. Deixe em branco se não usar.",
    row
)
row += 1

_create_help_label(
    tab1_inner,
    "Cloud API key (provider 2)",
    "Chave de API cloud do provedor 2 (endpoint customizável). Deixe em branco se não usar.",
    row
)
row += 1
```

**Step 3: Adicionar tooltips para Provider Strategy**

```python
_create_help_label(
    tab1_inner,
    "Primary provider",
    "Provedor LLM principal: 'ollama' para local; 'openai'/'anthropic' representam rotas cloud configuradas.",
    row
)
row += 1

_create_help_label(
    tab1_inner,
    "Ollama base URL",
    "URL do servidor Ollama local. Padrão: http://localhost:11434/v1",
    row
)
row += 1
```

**Step 4: Adicionar tooltips para Models section**

```python
_create_help_label(
    cloud_frame,
    "Cloud model (provider 1)",
    "Nome do modelo cloud do provedor 1 (ex: provider-model-name). Deixe em branco para não usar.",
    0
)

_create_help_label(
    cloud_frame,
    "Cloud model (provider 2)",
    "Nome do modelo cloud do provedor 2 (ex: provider-model-name). Deixe em branco para não usar.",
    1
)
```

---

## Task 6: Criar testes para novas funcionalidades

**Files:**
- Create: `system/tests/test_project_config.py`

**Step 1: Testar ProjectConfig**

```python
"""Tests for project-specific configuration management."""

import tempfile
from pathlib import Path

import pytest

from gui.project_config import ProjectConfig, get_blank_project_defaults


class TestProjectConfig:
    def test_exists_returns_false_when_no_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            assert not config.exists()

    def test_exists_returns_true_when_env_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            config.save({"TEST_KEY": "value"})
            assert config.exists()

    def test_load_returns_empty_dict_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            assert config.load() == {}

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            values = {"KEY1": "value1", "KEY2": "value2"}
            config.save(values)
            loaded = config.load()
            assert loaded["KEY1"] == "value1"
            assert loaded["KEY2"] == "value2"

    def test_get_effective_values_merges_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            config.save({"ANTHROPIC_API_KEY": "my-key"})
            effective = config.get_effective_values()
            assert effective["ANTHROPIC_API_KEY"] == "my-key"
            # Should have default values for other keys
            assert "OLLAMA_ENABLED" in effective

    def test_blank_defaults_have_empty_api_keys(self):
        blank = get_blank_project_defaults()
        assert blank["ANTHROPIC_API_KEY"] == ""
        assert blank["OPENAI_API_KEY"] == ""
        assert blank["ANTHROPIC_MODEL"] == ""
        assert blank["OPENAI_MODEL"] == ""
        # But Ollama values should be present
        assert blank["OLLAMA_ENABLED"] == "true"
```

---

## Task 7: Verificar e ajustar testes existentes

**Files:**
- Modify: `system/tests/test_settings_store.py` (se necessário)

**Step 1: Rodar testes existentes**

```bash
cd system && python -m pytest tests/ -v -k "settings" --tb=short
```

**Step 2: Verificar se testes de GUI ainda passam**

```bash
cd system && python -m pytest tests/test_gui_app.py -v --tb=short
```

---

## Task 8: Atualizar imports e verificar integração

**Files:**
- Modify: `system/src/gui/__init__.py` (se existir ou criar)

**Step 1: Garantir que novos módulos são importáveis**

Verificar que o novo módulo `project_config.py` pode ser importado de `app.py`.

---

## Resumo das Mudanças

### Arquivos Criados:
1. `system/src/gui/project_config.py` - Gerenciamento de config por projeto
2. `system/src/gui/dialog_startup.py` - Diálogo inicial de seleção
3. `system/tests/test_project_config.py` - Testes

### Arquivos Modificados:
1. `system/src/gui/app.py` - Lógica principal de startup e config
2. `system/src/gui/dialog_setup.py` - Tooltips e defaults em branco

### Comportamento Novo:
1. Ao abrir o programa, diálogo pergunta: Novo Projeto ou Continuar
2. Novos projetos começam com API keys e modelos em branco
3. Projetos existentes carregam suas configurações salvas
4. Ao salvar no Setup, configurações vão para o projeto (.env local)
5. Título mudou de "SAEC - Win98 Edition" para "SAEC"
6. Tooltips "?" aparecem em campos principais do Setup



