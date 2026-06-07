---
name: doc-funcao
description: Documenta funções do GeoFlight Planner sem docstring. Use para Funcs.py, algoritmos ou calculadora.
---

# Documentar Funções — GeoFlight Planner

## Alvo
$ARGUMENTS

## Funções sem docstring
!`python3 -c "
import ast
try:
    tree = ast.parse(open('${ARGUMENTS:-algoritmos/Funcs.py}').read())
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and not ast.get_docstring(n):
            print(f'linha {n.lineno}: def {n.name}()')
except Exception as e: print(e)
" 2>/dev/null`

---

Adicione docstrings em português às funções listadas.

**Padrão:**
- Descrição + qual algoritmo chama a função
- `Args`: tipo + unidade obrigatória (m, mm, graus, m/s, cm/px, decimal 0-1)
- `Returns`: o que retorna e em que unidade
- `Raises`: só se lança `QgsProcessingException`
- `Note`: se exige CRS projetado ou não roda fora do QGIS

Entregar código completo (corpo + docstring), pronto para substituir no arquivo.
