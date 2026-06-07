---
name: novo-algoritmo
description: Cria scaffolding de novo QgsProcessingAlgorithm para o GeoFlight Planner. Use quando quiser adicionar novo tipo de voo ou ferramenta CSV.
---

# Novo Algoritmo — GeoFlight Planner

## Solicitação
$ARGUMENTS

## Algoritmos já registrados
!`grep "self.addAlgorithm" PlanoVoo_provider.py 2>/dev/null`

## Funções disponíveis em Funcs.py
!`grep "^def " algoritmos/Funcs.py 2>/dev/null`

---

Com base em `$ARGUMENTS`, gere o arquivo `algoritmos/PlanoVoo_NOME.py` completo.

Se vazio, pergunte: nome, tipo (Horizontal / Vertical / CSV) e parâmetros específicos.

**Sempre incluir:**
1. Cabeçalho padrão do projeto (autores, data, copyright)
2. `initAlgorithm`: `loadParametros()` no início; limites em todos os `QgsProcessingParameterNumber`; parâmetro `kml`; saída `FileDestination`
3. `processAlgorithm`: validações com `QgsProcessingException`; emojis ✅❌⚠️; `isCanceled()` em loops; `saveParametros()` + `post_process_comum()` no final
4. Todos os métodos obrigatórios: `name()`, `displayName()`, `group()`, `groupId()`, `icon()`, `tr()`, `createInstance()`

Após gerar, mostrar o que adicionar em `PlanoVoo_provider.py` e `main.py`.
