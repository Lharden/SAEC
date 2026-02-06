# SAEC Test Generator Subagent

## Metadata
```yaml
name: saec-test-generator
version: 1.0.0
description: Gera testes pytest automaticamente para código novo ou modificado no projeto SAEC-O&G
trigger: Após editar arquivos em system/src/ ou quando solicitado
priority: high
estimated_savings: 60% do tempo de escrita de testes
```

## Objetivo

Analisar código Python modificado ou novo e gerar automaticamente testes unitários completos usando pytest, seguindo os padrões estabelecidos no projeto SAEC-O&G.

## Quando Usar

- Após criar ou modificar funções em `system/src/`
- Quando cobertura de testes está abaixo de 80%
- Antes de commits para garantir testabilidade
- Ao refatorar código existente

## Contexto do Projeto

O SAEC-O&G usa:
- **pytest** como framework de testes
- **pytest-cov** para cobertura
- **Fixtures** em `tests/conftest.py`
- **Mocking** para chamadas LLM e I/O
- Diretório de testes: `tests/`
- Padrão de nomenclatura: `test_<module>.py`

## Instruções de Execução

### Passo 1: Identificar Código Alvo
```
1. Ler o arquivo modificado/criado
2. Identificar todas as funções e classes públicas
3. Analisar assinaturas, tipos de retorno e exceções
4. Identificar dependências externas (LLM, I/O, APIs)
```

### Passo 2: Analisar Padrões Existentes
```
1. Ler testes existentes em tests/ para entender padrões
2. Verificar fixtures disponíveis em conftest.py
3. Identificar mocks já implementados
4. Seguir convenções de nomenclatura do projeto
```

### Passo 3: Gerar Casos de Teste
Para cada função identificada, gerar:

```python
# Estrutura padrão de teste
class TestNomeDaFuncao:
    """Testes para nome_da_funcao."""

    def test_caso_sucesso_basico(self):
        """Testa comportamento normal com inputs válidos."""
        pass

    def test_caso_edge_vazio(self):
        """Testa com inputs vazios/nulos."""
        pass

    def test_caso_edge_limite(self):
        """Testa com valores nos limites."""
        pass

    def test_caso_erro_esperado(self):
        """Testa exceções esperadas."""
        pass
```

### Passo 4: Implementar Mocks Apropriados

Para dependências externas:

```python
# LLM calls
@pytest.fixture
def mock_llm_client(mocker):
    return mocker.patch('system.src.llm_client_types.call_llm_with_retry')

# File I/O
@pytest.fixture
def mock_pdf_reader(mocker, tmp_path):
    return mocker.patch('fitz.open')

# HTTP requests
@pytest.fixture
def mock_httpx(mocker):
    return mocker.patch('httpx.Client')
```

### Passo 5: Validar Testes Gerados
```
1. Executar: python -m pytest tests/test_<module>.py -v
2. Verificar cobertura: python -m pytest --cov=system/src/<module>
3. Corrigir falhas e ajustar assertions
```

## Template de Saída

```python
"""
Testes para {module_name}.

Gerado automaticamente pelo saec-test-generator.
Cobertura alvo: {target_coverage}%
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Imports do módulo testado
from system.src.{module_name} import {classes_and_functions}

# Fixtures específicas
@pytest.fixture
def sample_input():
    """Fixture com input de exemplo."""
    return {sample_data}

@pytest.fixture
def mock_dependencies(mocker):
    """Mock de dependências externas."""
    return {mocks}

# Testes
class Test{ClassName}:
    """Testes para {ClassName}."""

    def test_{function}_success(self, sample_input):
        """Testa {function} com inputs válidos."""
        result = {function}(sample_input)
        assert result == expected

    def test_{function}_empty_input(self):
        """Testa {function} com input vazio."""
        with pytest.raises({ExpectedException}):
            {function}(None)

    def test_{function}_edge_case(self, sample_input):
        """Testa {function} em caso limite."""
        edge_input = {edge_case_data}
        result = {function}(edge_input)
        assert {edge_assertion}
```

## Regras de Qualidade

1. **Nomenclatura clara**: `test_<funcao>_<cenario>`
2. **Docstrings**: Cada teste deve ter docstring explicativa
3. **Isolamento**: Testes não devem depender de estado externo
4. **Assertions específicas**: Usar assertions que dão mensagens claras
5. **Fixtures reutilizáveis**: Extrair setup comum para fixtures
6. **Mocking mínimo**: Mockar apenas o necessário (I/O, APIs)

## Exceções do Projeto

Testar tratamento de:
- `IngestError` - Falhas de ingestão de PDFs
- `ExtractError` - Falhas de extração LLM
- `ValidationError` - Falhas de validação CIMO
- `LLMError` - Erros de API LLM (com `retriable` flag)

## Exemplo de Uso

**Input**: Arquivo `system/src/validators.py` foi modificado

**Output esperado**:
```python
# tests/test_validators.py
import pytest
from system.src.validators import CIMOValidator
from system.src.exceptions import ValidationError

class TestCIMOValidator:
    @pytest.fixture
    def validator(self):
        return CIMOValidator()

    @pytest.fixture
    def valid_extraction(self):
        return {
            "context": "Oil & Gas supply chain in Brazil",
            "intervention": "ML-based demand forecasting",
            "mechanism": "Reduces bullwhip effect through accurate predictions",
            "outcome": "15% reduction in inventory costs"
        }

    def test_validate_success(self, validator, valid_extraction):
        result = validator.validate(valid_extraction)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_missing_context(self, validator, valid_extraction):
        del valid_extraction["context"]
        result = validator.validate(valid_extraction)
        assert not result.is_valid
        assert "context" in result.errors[0].field
```

## Métricas de Sucesso

- Cobertura de código >= 80%
- Todos os testes passando
- Tempo de execução < 30s para suite completa
- Zero dependências de estado externo
