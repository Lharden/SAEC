#!/usr/bin/env python3
"""
Gera contexto estrutural do projeto SAEC-O&G para sessões do Claude Code.
Executa análise estática e salva em MEMORY.md.
"""

import os
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
MEMORY_DIR = Path(os.path.expanduser("~/.claude/projects/C--Users-Leonardo-Documents-Computing-Projeto-Mestrado-files-files-articles-00-Dados-RSL/memory"))

def count_lines(filepath: Path) -> int:
    try:
        return sum(1 for _ in filepath.open(encoding='utf-8', errors='ignore'))
    except:
        return 0

def analyze_python_file(filepath: Path) -> dict:
    """Extrai classes e funções de um arquivo Python."""
    classes, functions = [], []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('class '):
                    name = stripped.split('(')[0].split(':')[0].replace('class ', '')
                    classes.append(name)
                elif stripped.startswith('def ') and not line.startswith(' '):
                    name = stripped.split('(')[0].replace('def ', '')
                    functions.append(name)
    except:
        pass
    return {'classes': classes, 'functions': functions[:10]}  # Limita funções

def analyze_structure() -> dict:
    """Analisa estrutura completa do projeto."""
    structure = {
        'system_src': [],
        'tests': [],
        'prompts': [],
        'adapters': [],
        'total_lines': 0,
        'key_files': {}
    }

    # system/src/
    src_dir = PROJECT_ROOT / 'system' / 'src'
    if src_dir.exists():
        for py_file in sorted(src_dir.glob('*.py')):
            lines = count_lines(py_file)
            structure['total_lines'] += lines
            analysis = analyze_python_file(py_file)
            structure['system_src'].append({
                'name': py_file.name,
                'lines': lines,
                'classes': analysis['classes'],
                'functions': analysis['functions']
            })
            if py_file.name in ['processors.py', 'llm_client.py', 'validators.py', 'config.py']:
                structure['key_files'][py_file.name] = {
                    'path': str(py_file.relative_to(PROJECT_ROOT)),
                    'lines': lines,
                    'classes': analysis['classes']
                }

    # adapters/
    adapters_dir = PROJECT_ROOT / 'system' / 'src' / 'adapters'
    if adapters_dir.exists():
        for py_file in sorted(adapters_dir.glob('*.py')):
            lines = count_lines(py_file)
            structure['total_lines'] += lines
            structure['adapters'].append({
                'name': py_file.name,
                'lines': lines
            })

    # tests/
    tests_dir = PROJECT_ROOT / 'tests'
    if tests_dir.exists():
        for py_file in sorted(tests_dir.glob('test_*.py')):
            lines = count_lines(py_file)
            structure['tests'].append({
                'name': py_file.name,
                'lines': lines
            })

    # prompts/
    prompts_dir = PROJECT_ROOT / 'system' / 'prompts'
    if prompts_dir.exists():
        for prompt_file in sorted(prompts_dir.glob('*.md')):
            lines = count_lines(prompt_file)
            structure['prompts'].append({
                'name': prompt_file.name,
                'lines': lines
            })

    return structure

def generate_memory_content(structure: dict) -> str:
    """Gera conteúdo formatado para MEMORY.md."""

    lines = [
        "# SAEC-O&G - Contexto Estrutural",
        f"*Atualizado: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## Arquitetura do Pipeline",
        "```",
        "PDF → [Ingest] → Hybrid Content → [Extract LLM] → YAML → [Validate/Repair] → Final",
        "```",
        "",
        "## Arquivos Principais (`system/src/`)",
        ""
    ]

    # Key files primeiro
    for fname, info in structure.get('key_files', {}).items():
        classes_str = ', '.join(info['classes'][:3]) if info['classes'] else 'funções'
        lines.append(f"- **{fname}** ({info['lines']}L): {classes_str}")

    lines.extend(["", "## Outros Módulos", ""])

    # Outros arquivos src
    for f in structure.get('system_src', []):
        if f['name'] not in structure.get('key_files', {}):
            lines.append(f"- `{f['name']}` ({f['lines']}L)")

    # Adapters
    if structure.get('adapters'):
        lines.extend(["", "## Adapters", ""])
        for f in structure['adapters']:
            lines.append(f"- `{f['name']}` ({f['lines']}L)")

    # Prompts
    if structure.get('prompts'):
        lines.extend(["", "## Prompts LLM", ""])
        for f in structure['prompts']:
            lines.append(f"- `{f['name']}` ({f['lines']}L)")

    # Testes
    if structure.get('tests'):
        lines.extend(["", f"## Testes ({len(structure['tests'])} arquivos)", ""])

    # Stats
    lines.extend([
        "",
        "## Estatísticas",
        f"- Total: ~{structure['total_lines']} linhas Python",
        f"- Testes: {len(structure.get('tests', []))} arquivos",
        "",
        "## Token Hotspots (para otimização)",
        "1. `guia_v3_3_prompt.md` - 9.7KB enviado em cada chamada LLM",
        "2. Repair loop - reenvia conteúdo completo até 3x",
        "3. RAG Store existe mas **não está integrado** ao pipeline",
        "4. Pipeline Cascade (local-first) **implementado mas não ativo**",
        "",
        "## Links Rápidos",
        "- Pipeline principal: `system/src/processors.py`",
        "- Cliente LLM: `system/src/llm_client.py`",
        "- Validação CIMO: `system/src/validators.py`",
        "- RAG (não usado): `system/src/adapters/rag_store.py`",
        "- Cascade (não ativo): `system/src/pipeline_cascade.py`"
    ])

    return '\n'.join(lines)

def main():
    print("Analisando estrutura do projeto SAEC-O&G...")
    structure = analyze_structure()

    content = generate_memory_content(structure)

    # Salva no MEMORY.md
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    memory_file = MEMORY_DIR / 'MEMORY.md'

    with open(memory_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] Contexto salvo em: {memory_file}")
    print(f"  - {len(structure.get('system_src', []))} módulos src")
    print(f"  - {len(structure.get('adapters', []))} adapters")
    print(f"  - {len(structure.get('tests', []))} testes")
    print(f"  - ~{structure['total_lines']} linhas total")

    # Também salva JSON para referência
    json_file = MEMORY_DIR / 'structure.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(structure, f, indent=2)

    return structure

if __name__ == '__main__':
    main()
