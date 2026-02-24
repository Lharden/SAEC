"""Profile engine for project-scoped extraction schemas."""

from .loader import ProfileLoadError, load_profile_spec
from .models import (
    CURRENT_PROFILE_SCHEMA_VERSION,
    SUPPORTED_PROFILE_SCHEMA_VERSIONS,
    ProfileSpec,
)
from .project_profiles import (
    ActiveProfileRef,
    RunProfileSnapshot,
    build_universal_profile_prompt,
    bootstrap_profile,
    export_profile_template_xlsx,
    get_active_profile_ref,
    has_active_profile,
    import_profile_xlsx,
    import_profile_yaml,
    is_default_cimo_profile,
    load_active_profile_spec,
    resolve_profile_prompt_path,
    resolve_runtime_project_root,
    require_project_profile,
    snapshot_active_profile_for_run,
)
from .validator import (
    evaluate_profile_rules,
    validate_dict_with_profile,
    validate_rule_expression,
    validate_rule_expressions,
)

__all__ = [
    "ActiveProfileRef",
    "CURRENT_PROFILE_SCHEMA_VERSION",
    "ProfileLoadError",
    "ProfileSpec",
    "RunProfileSnapshot",
    "SUPPORTED_PROFILE_SCHEMA_VERSIONS",
    "build_universal_profile_prompt",
    "bootstrap_profile",
    "export_profile_template_xlsx",
    "evaluate_profile_rules",
    "get_active_profile_ref",
    "has_active_profile",
    "import_profile_xlsx",
    "import_profile_yaml",
    "is_default_cimo_profile",
    "load_active_profile_spec",
    "load_profile_spec",
    "resolve_profile_prompt_path",
    "resolve_runtime_project_root",
    "require_project_profile",
    "snapshot_active_profile_for_run",
    "validate_dict_with_profile",
    "validate_rule_expression",
    "validate_rule_expressions",
]
