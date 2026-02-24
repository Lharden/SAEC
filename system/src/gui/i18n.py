"""Centralized GUI internationalization module.

Usage:
    from gui.i18n import t, set_language, get_language

    label = t("menu.file")        # Returns string in active language
    set_language("en-UK")         # Switch language (requires GUI restart)
    current = get_language()      # "pt-BR" or "en-UK"
"""

from __future__ import annotations

_current_language: str = "pt-BR"

# ── String catalog ─────────────────────────────────────────────────
# Keys are grouped by component: menu.*, status.*, run.*, setup.*,
# startup.*, queue.*, outputs.*, toolbar.*, dialog.*, profile.*
#
# Untranslatable terms (Pipeline, YAML, PDF, etc.) stay as-is.

_STRINGS: dict[str, dict[str, str]] = {}


def _add(key: str, pt: str, en: str) -> None:
    _STRINGS[key] = {"pt-BR": pt, "en-UK": en}


# ═══════════════════════════════════ MENUS ══════════════════════════
_add("menu.file", "Arquivo", "File")
_add("menu.exit", "Sair  Ctrl+Q", "Exit  Ctrl+Q")
_add("menu.workspace", "Workspace", "Workspace")
_add("menu.select_workspace", "Selecionar Workspace...  Ctrl+W", "Select Workspace...  Ctrl+W")
_add("menu.project", "Projeto", "Project")
_add("menu.new_project", "Novo Projeto...", "New Project...")
_add("menu.configure_profile", "Configurar Perfil...", "Configure Profile...")
_add("menu.pipeline", "Pipeline", "Pipeline")
_add("menu.run", "Executar  Ctrl+R", "Run  Ctrl+R")
_add("menu.cancel", "Cancelar  Ctrl+Shift+C", "Cancel  Ctrl+Shift+C")
_add("menu.export_summary", "Exportar Relatório...", "Export Summary Report...")
_add("menu.view", "Visualizar", "View")
_add("menu.refresh_outputs", "Atualizar Outputs  F5", "Refresh Outputs  F5")
_add("menu.clear_logs", "Limpar Logs  Ctrl+L", "Clear Logs  Ctrl+L")
_add("menu.diagnostics", "Diagnósticos", "Diagnostics")
_add("menu.profile", "Perfil", "Profile")
_add("menu.notify_completion", "Notificar ao Concluir", "Notify On Completion")
_add("menu.help", "Ajuda", "Help")
_add("menu.help_troubleshooting", "Ajuda e Solução de Problemas  F1", "Help and Troubleshooting  F1")
_add("menu.about", "Sobre", "About")

# ═══════════════════════════════════ TOOLBAR TOOLTIPS ═══════════════
_add("toolbar.run", "Executar pipeline (Ctrl+R)", "Run pipeline (Ctrl+R)")
_add("toolbar.cancel", "Cancelar execução (Ctrl+Shift+C)", "Cancel active run (Ctrl+Shift+C)")
_add("toolbar.refresh", "Atualizar outputs (F5)", "Refresh outputs (F5)")
_add("toolbar.workspace", "Alterar workspace (Ctrl+W)", "Change workspace (Ctrl+W)")
_add("toolbar.new", "Criar novo projeto", "Create new project")
_add("toolbar.diag", "Abrir aba de diagnósticos", "Open diagnostics tab")
_add("toolbar.settings", "Abrir assistente de configuração", "Open setup wizard")
_add("toolbar.help", "Ajuda / Solução de problemas (F1)", "Help / Troubleshooting (F1)")

# ═══════════════════════════════════ LAYOUT TOOLTIPS ════════════════
_add("tooltip.workspace_combo", "Selecione uma pasta de workspace", "Select a workspace folder")
_add("tooltip.project_combo", "Selecione um projeto existente", "Select an existing project")
_add("tooltip.browse_workspace", "Procurar pastas de workspace", "Browse workspace folders")
_add("tooltip.new_project", "Criar um novo projeto", "Create a new project")
_add("tooltip.articles_entry", "Pasta de artigos (override ou padrão do projeto)", "Articles folder (override or project default)")
_add("tooltip.browse_articles", "Selecionar pasta externa com PDFs", "Select an external folder with PDFs")
_add("tooltip.clear_articles", "Reverter para pasta padrão de artigos", "Revert to project default articles folder")

# ═══════════════════════════════════ LAYOUT LABELS ══════════════════
_add("layout.workspace", "Workspace", "Workspace")
_add("layout.project", "Projeto", "Project")
_add("layout.articles", "Artigos", "Articles")
_add("layout.browse", "Procurar...", "Browse...")
_add("layout.new", "Novo...", "New...")
_add("layout.clear", "Limpar", "Clear")

# ═══════════════════════════════════ STATUS PANEL ═══════════════════
_add("status.workspace", "Workspace:", "Workspace:")
_add("status.project", "Projeto:", "Project:")
_add("status.articles", "Artigos:", "Articles:")
_add("status.input_pdfs", "PDFs de entrada:", "Input PDFs:")
_add("status.yaml_outputs", "Saídas YAML:", "YAML outputs:")
_add("status.consolidated", "Consolidados:", "Consolidated files:")
_add("status.queue_pending", "Fila pendente:", "Queue pending:")
_add("status.queue_running", "Em execução:", "Queue running:")
_add("status.runs_success", "Sucesso:", "Runs success:")
_add("status.runs_failed", "Falhas:", "Runs failed:")
_add("status.runs_cancelled", "Cancelados:", "Runs cancelled:")
_add("status.progress", "Progresso:", "Progress:")
_add("status.idle", "Ocioso", "Idle")
_add("status.article", "Artigo:", "Article:")
_add("status.elapsed", "Decorrido:", "Elapsed:")
_add("status.article_n_of_m", "Artigo {current}/{total}", "Article {current}/{total}")
_add("status.step_n_of_m", "Etapa {current}/{total}", "Step {current}/{total}")
_add("status.step_n", "Etapa {current}", "Step {current}")
_add("status.external", "(externo)", "(external)")
_add("status.default_articles", "inputs/articles/ (padrão)", "inputs/articles/ (default)")

# ═══════════════════════════════════ RUN PANEL ══════════════════════
_add("run.title", "Pipeline Run", "Pipeline Run")
_add("run.preset", "Preset", "Preset")
_add("run.mode", "Modo", "Mode")
_add("run.step", "Etapa", "Step")
_add("run.article_id", "ID do Artigo", "Article ID")
_add("run.log_level", "Nível de log", "Log level")
_add("run.dry_run", "Simulação", "Dry run")
_add("run.force", "Forçar", "Force")
_add("run.queue_run", "Iniciar Execução", "Queue Run")
_add("run.cancel", "Cancelar", "Cancel")

# Run panel tooltips
_add("run.tooltip.preset", "Escolha uma configuração predefinida de pipeline", "Choose a predefined pipeline configuration")
_add("run.tooltip.mode", "all = processar todos os artigos, step = executar etapa única", "all = process every article, step = run single step")
_add("run.tooltip.step", "1=Setup, 2=Ingest PDFs, 3=Extract LLM, 5=Consolidar", "1=Setup, 2=Ingest PDFs, 3=Extract LLM, 5=Consolidate")
_add("run.tooltip.article", "ID do artigo opcional, exemplo: ART_001", "Optional article id, example: ART_001")
_add("run.tooltip.dry_run", "Simular execução sem gravar resultados", "Simulate execution without writing outputs")
_add("run.tooltip.force", "Reprocessar TUDO mesmo que já existam arquivos", "Reprocess ALL outputs even if files already exist")
_add("run.tooltip.queue_run", "Iniciar execução do pipeline (Ctrl+R)", "Start pipeline execution (Ctrl+R)")
_add("run.tooltip.cancel", "Cancelar execução ativa (Ctrl+Shift+C)", "Cancel active run (Ctrl+Shift+C)")

# ═══════════════════════════════════ QUEUE PANEL ════════════════════
_add("queue.tab", "Fila", "Queue")
_add("queue.col_job", "Job", "Job")
_add("queue.col_status", "Status", "Status")
_add("queue.col_mode", "Modo", "Mode")
_add("queue.col_step", "Etapa", "Step")
_add("queue.col_article", "Artigo", "Article")
_add("queue.col_created", "Criado", "Created")
_add("queue.col_finished", "Finalizado", "Finished")
_add("queue.col_code", "Código", "Code")
_add("queue.view_logs", "Ver Logs", "View Logs")
_add("queue.copy_command", "Copiar Comando", "Copy Command")
_add("queue.cancel_job", "Cancelar Job", "Cancel Job")
_add("queue.tooltip", "Clique com botão direito para ver logs, copiar comando ou cancelar.", "Right-click a job for logs, command copy, or cancel.")

# ═══════════════════════════════════ OUTPUTS PANEL ══════════════════
_add("outputs.tab", "Saídas", "Outputs")
_add("outputs.refresh", "Atualizar", "Refresh")
_add("outputs.open", "Abrir", "Open")
_add("outputs.copy_path", "Copiar Caminho", "Copy Path")
_add("outputs.open_folder", "Abrir Pasta", "Open Folder")
_add("outputs.open_project_folder", "Abrir Pasta do Projeto", "Open Project Folder")
_add("outputs.delete", "Excluir", "Delete")
_add("outputs.type_filter", "Tipo:", "Type:")
_add("outputs.find", "Buscar:", "Find:")
_add("outputs.col_name", "Nome", "Name")
_add("outputs.col_type", "Tipo", "Type")
_add("outputs.col_size", "Tamanho", "Size")
_add("outputs.col_modified", "Modificado", "Modified")
_add("outputs.tooltip.refresh", "Recarregar arquivos de saída", "Reload output files")
_add("outputs.tooltip.open", "Abrir arquivo selecionado", "Open selected file")
_add("outputs.tooltip.copy_path", "Copiar caminho completo do arquivo", "Copy selected file full path")
_add("outputs.tooltip.type_filter", "Filtrar arquivos por categoria", "Filter files by output category")
_add("outputs.tooltip.find", "Buscar arquivos pelo nome", "Search files by name")

# ═══════════════════════════════════ LOGS PANEL ═════════════════════
_add("logs.tab", "Logs", "Logs")

# ═══════════════════════════════════ DIAGNOSTICS PANEL ══════════════
_add("diagnostics.tab", "Diagnósticos", "Diagnostics")

# ═══════════════════════════════════ PROFILE PANEL ══════════════════
_add("profile.tab", "Perfil", "Profile")
_add("profile.configure", "Configurar...", "Configure...")
_add("profile.export_yaml", "Exportar YAML", "Export YAML")

# ═══════════════════════════════════ STARTUP DIALOG ═════════════════
_add("startup.title", "SAEC - Selecionar Projeto", "SAEC - Select Project")
_add("startup.welcome", "Bem-vindo ao SAEC", "Welcome to SAEC")
_add("startup.choose", "Escolha uma opção para continuar:", "Choose an option to continue:")
_add("startup.recent", "Workspaces Recentes", "Recent Workspaces")
_add("startup.no_recent", "Nenhum workspace recente", "No recent workspace")
_add("startup.new_project", "Novo Projeto", "New Project")
_add("startup.continue_project", "Continuar Projeto", "Continue Project")
_add("startup.browse", "Procurar...", "Browse...")
_add("startup.cancel", "Cancelar", "Cancel")
_add("startup.workspace_required", "Workspace necessário", "Workspace required")
_add("startup.select_workspace_first", "Selecione um workspace primeiro.", "Select a workspace first.")

# ═══════════════════════════════════ SETUP DIALOG ═══════════════════
_add("setup.title", "Configuração - Credenciais, Provedores e Modelos", "Setup - Credentials, Providers & Models")
_add("setup.tab_credentials", "Credenciais e Provedores", "Credentials & Providers")
_add("setup.tab_models", "Modelos", "Models")
_add("setup.api_keys", "Chaves de API", "API Keys")
_add("setup.cloud_key_1", "Chave API cloud (provedor 1)", "Cloud API key (provider 1)")
_add("setup.cloud_key_1_help", "Chave de API cloud (provedor 1). Deixe em branco se não usar.", "Cloud API key (provider 1). Leave blank if not used.")
_add("setup.cloud_key_2", "Chave API cloud (provedor 2)", "Cloud API key (provider 2)")
_add("setup.cloud_key_2_help", "Chave de API cloud (provedor 2, compatível com endpoint customizável). Deixe em branco se não usar.", "Cloud API key (provider 2, compatible with custom endpoint). Leave blank if not used.")
_add("setup.cloud_base_url", "URL base API cloud (provedor 2)", "Cloud API base URL (provider 2)")
_add("setup.cloud_base_url_help", "URL base para API cloud do provedor 2. Ex: https://api.seu-provedor.com/v1", "Base URL for cloud API provider 2. E.g.: https://api.your-provider.com/v1")
_add("setup.provider_strategy", "Estratégia de Provedor", "Provider Strategy")
_add("setup.primary_provider", "Provedor principal", "Primary provider")
_add("setup.primary_provider_help", "Provedor LLM principal: 'ollama' para local; 'openai'/'anthropic' representam rotas cloud configuradas.", "Primary LLM provider: 'ollama' for local; 'openai'/'anthropic' represent configured cloud routes.")
_add("setup.ollama_url", "URL base do Ollama", "Ollama base URL")
_add("setup.ollama_url_help", "URL do servidor Ollama local. Padrão: http://localhost:11434/v1", "Ollama local server URL. Default: http://localhost:11434/v1")
_add("setup.enable_ollama", "Habilitar provedor Ollama", "Enable Ollama provider")
_add("setup.enable_two_pass", "Habilitar extração/reparo em duas passagens", "Enable two-pass extraction/repair")
_add("setup.show_routing", "Exibir roteamento avançado", "Show advanced routing")
_add("setup.hide_routing", "Ocultar roteamento avançado", "Hide advanced routing")
_add("setup.routing_title", "Roteamento por Função", "Per-Function Routing")
_add("setup.routing_hint", "Deixe em 'auto' para seguir o provedor principal.", "Leave on 'auto' to follow primary provider.")
_add("setup.detected_models", "Modelos Ollama Detectados", "Detected Ollama Models")
_add("setup.detected_count", "Modelos detectados: {count}", "Detected models: {count}")
_add("setup.no_models", "Nenhum modelo detectado do Ollama.", "No models detected from Ollama.")
_add("setup.cloud_models", "Modelos de API Cloud", "Cloud API Models")
_add("setup.cloud_model_1", "Modelo cloud (provedor 1)", "Cloud model (provider 1)")
_add("setup.cloud_model_1_help", "Nome do modelo cloud para o provedor 1. Deixe em branco para não usar.", "Cloud model name for provider 1. Leave blank if not used.")
_add("setup.cloud_model_2", "Modelo cloud (provedor 2)", "Cloud model (provider 2)")
_add("setup.cloud_model_2_help", "Nome do modelo cloud para o provedor 2. Deixe em branco para não usar.", "Cloud model name for provider 2. Leave blank if not used.")
_add("setup.model_assignments", "Atribuição de Modelos Ollama", "Ollama Model Assignments")
_add("setup.save", "Salvar", "Save")
_add("setup.cancel", "Cancelar", "Cancel")
_add("setup.refresh", "Atualizar", "Refresh")
_add("setup.language", "Idioma / Language", "Language / Idioma")
_add("setup.language_help", "Idioma da interface. Requer reinício da GUI.", "Interface language. Requires GUI restart.")
_add("setup.language_pt", "Português (BR)", "Português (BR)")
_add("setup.language_en", "English (UK)", "English (UK)")
_add("setup.restart_note", "Alteração de idioma requer reinício da GUI.", "Language change requires GUI restart.")
_add("setup.welcome_title", "Configuração do SAEC", "SAEC Setup")
_add("setup.welcome_subtitle", "Configure credenciais, provedores e modelos abaixo.", "Configure credentials, providers, and models below.")
_add("setup.dialog_title", "SAEC — Configuração", "SAEC — Settings")
_add("setup.provider_routing", "Roteamento de Provedor", "Provider Routing")
_add("setup.refresh_models", "Atualizar Modelos", "Refresh Models")
_add("setup.gui_language", "Idioma da GUI", "GUI Language")
_add("setup.language_restart_hint", "Requer reinício", "Requires restart")
_add("setup.model_reranker", "Reranker", "Reranker")
_add("setup.strategy", "Estratégia", "Strategy")

# Model group names
_add("setup.group_extraction", "Extração", "Extraction")
_add("setup.group_processing", "Processamento", "Processing")
_add("setup.group_cascade", "Cascade", "Cascade")
_add("setup.group_utilities", "Utilitários", "Utilities")

# Model labels
_add("setup.model_main", "Extração principal", "Main extraction")
_add("setup.model_fallback", "Extração fallback", "Extraction fallback")
_add("setup.model_vision", "Páginas com visão", "Vision pages")
_add("setup.model_coder", "Formatador YAML", "YAML formatter")
_add("setup.model_cascade_extract", "Extração cascade", "Cascade extraction")
_add("setup.model_cascade_repair", "Reparo cascade", "Cascade repair")
_add("setup.model_ocr", "Modelo OCR", "OCR model")
_add("setup.model_embedding", "RAG embedding", "RAG embedding")

# Provider routing labels
_add("setup.route_extract", "Extração principal", "Main extraction")
_add("setup.route_repair", "Reparo YAML", "YAML repair")
_add("setup.route_quotes", "Verificação de quotes", "Quote recheck")
_add("setup.route_cascade_api", "Escalação cascade API", "Cascade API escalation")

# Provider routing descriptions
_add("setup.route_extract_help", "Provedor para extração principal de artigos.", "Provider for main article extraction.")
_add("setup.route_repair_help", "Provedor para passagem de reparo schema/validação.", "Provider for schema/validation repair pass.")
_add("setup.route_quotes_help", "Provedor para tentativas de recuperação/verificação de quotes.", "Provider for quote recovery/recheck attempts.")
_add("setup.route_cascade_api_help", "Provedor usado quando cascade escala para API.", "Provider used when cascade escalates to API.")

# ═══════════════════════════════════ DIALOGS ════════════════════════
_add("dialog.error_title", "Erro do SAEC", "SAEC Error")
_add("dialog.error_unexpected", "Ocorreu um erro inesperado: {error}", "An unexpected error occurred: {error}")
_add("dialog.copy_clipboard", "Copiar para Área de Transferência", "Copy to Clipboard")
_add("dialog.ok", "OK", "OK")
_add("dialog.yes", "Sim", "Yes")
_add("dialog.no", "Não", "No")
_add("dialog.close", "Fechar", "Close")

_add("dialog.project_required", "Projeto necessário", "Project required")
_add("dialog.select_project_first", "Selecione um projeto antes de exportar o relatório.", "Select a project before exporting summary report.")
_add("dialog.no_outputs_title", "Sem saídas", "No outputs")
_add("dialog.no_outputs_msg",
     "Nenhum diretório de saída YAML encontrado para este projeto.\n\n"
     "Como resolver:\n"
     "1. Execute a Etapa 2 (Ingest) para este projeto.\n"
     "2. Execute a Etapa 3 (Extract) para gerar arquivos YAML.\n"
     "3. Tente exportar novamente.",
     "No YAML output directory found for this project.\n\n"
     "How to fix:\n"
     "1. Run Step 2 (Ingest) for this project.\n"
     "2. Run Step 3 (Extract) to generate YAML files.\n"
     "3. Try exporting again.")
_add("dialog.no_yamls_title", "Sem arquivos YAML", "No YAML files")
_add("dialog.no_yamls_msg",
     "A pasta YAML existe, mas nenhum arquivo .yaml foi encontrado.\n\n"
     "Como resolver:\n"
     "1. Execute a Etapa 3 (Extract).\n"
     "2. Verifique a Fila/Logs para artigos com falha.\n"
     "3. Exporte novamente quando ao menos um YAML for gerado.",
     "The YAML folder exists, but no .yaml files were found.\n\n"
     "How to fix:\n"
     "1. Run Step 3 (Extract).\n"
     "2. Check Queue/Logs for failed articles.\n"
     "3. Export again when at least one YAML is generated.")
_add("dialog.export_title", "Exportar Relatório", "Export Summary Report")
_add("dialog.export_html", "Gerar também relatório HTML?", "Generate HTML summary too?")
_add("dialog.export_html_title", "Exportar HTML", "Export HTML")
_add("dialog.summary_exported", "Relatório exportado: {filename}", "Summary exported: {filename}")
_add("dialog.delete_file", "Excluir arquivo", "Delete file")
_add("dialog.delete_confirm", "Excluir arquivo?\n{filename}", "Delete file?\n{filename}")
_add("dialog.delete_failed", "Falha ao excluir", "Delete failed")
_add("dialog.open_failed", "Falha ao abrir", "Open failed")

_add("dialog.provider_setup_title", "Configuração de provedor incompleta", "Provider setup incomplete")
_add("dialog.provider_setup_msg",
     "Nenhum provedor está pronto no momento.\n\n"
     "Como resolver:\n"
     "1. Configure chave(s) de API cloud/URL base no Setup, ou\n"
     "2. Inicie o Ollama (ollama serve) com URL válida.\n\n"
     "Depois execute os Diagnósticos novamente.",
     "No provider is currently ready.\n\n"
     "How to fix:\n"
     "1. Configure cloud API key(s)/base URL in Setup, or\n"
     "2. Start Ollama (ollama serve) and keep a valid Ollama URL.\n\n"
     "Then run Diagnostics again.")

_add("dialog.startup_checks_failed", "Verificações iniciais falharam. Abra a aba Diagnósticos.", "Startup checks failed. Open Diagnostics tab.")
_add("dialog.startup_checks_warnings", "Verificações iniciais concluídas com avisos.", "Startup checks completed with warnings.")

# ═══════════════════════════════════ PROJECT DIALOG ═════════════════
_add("project.select_workspace", "Selecionar Workspace", "Select Workspace")


# ═══════════════════════ API ════════════════════════════════════════


def t(key: str, **kwargs: object) -> str:
    """Return translated string for *key* in the active language.

    Supports format placeholders: ``t("status.article_n_of_m", current=1, total=10)``.
    Falls back to ``en-UK`` then to the key itself if missing.
    """
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_current_language) or entry.get("en-UK") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def set_language(lang: str) -> None:
    """Set the active language (``'pt-BR'`` or ``'en-UK'``)."""
    global _current_language
    if lang in ("pt-BR", "en-UK"):
        _current_language = lang


def get_language() -> str:
    """Return the active language code."""
    return _current_language


def available_languages() -> list[tuple[str, str]]:
    """Return list of (code, display_label) for each supported language."""
    return [
        ("pt-BR", "Português (BR)"),
        ("en-UK", "English (UK)"),
    ]


def all_keys() -> list[str]:
    """Return all registered translation keys (for testing)."""
    return sorted(_STRINGS.keys())
