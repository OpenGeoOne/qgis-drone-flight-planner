---
name: debug-plugin
description: Diagnostica erros do GeoFlight Planner. Use quando algoritmo falhar, plugin não carregar, CSV errado ou crash.
---

# Debug — GeoFlight Planner v4.0.0

## Erro ou sintoma
$ARGUMENTS

## Log Python do QGIS
!`find . -name "*.log" -newer metadata.txt 2>/dev/null | xargs tail -20 2>/dev/null || echo "Ver: View → Panels → Log Messages → aba Python"`

---

Diagnostique o erro em `$ARGUMENTS`.

**Erros conhecidos desta versão:**

`"Drone sensor data not found"` → Calculator não configurado. Abrir GSD Calculator, selecionar drone, confirmar.

`"Select 1 polygon/line feature!"` → camada com 0 ou N>1 feições selecionadas.

Plugin não aparece → verificar `hasProcessingProvider=yes` no `metadata.txt`; checar imports em `PlanoVoo_provider.py` no Log Messages.

`"wrapped C++ object deleted"` → camada removida do projeto durante execução.

CSV criado mas camadas não aparecem → `post_process_comum()` não chamado ou deu erro silencioso.

Parâmetros não persistem → `saveParametros()` não chamado no final de `processAlgorithm()`.

Import falhando → verificar se todos os imports internos usam `.` ou `..`.

Erro Qt5/Qt6 em diálogo → `try: dlg.exec() except AttributeError: dlg.exec_()`.

Geometry error no VC → camada de linha deve ser `"LineString"` (não `"MultiLineString"`) na URI.

**Resposta:** PROBLEMA / CAUSA / CORREÇÃO com código corrigido, em ordem de prioridade.
