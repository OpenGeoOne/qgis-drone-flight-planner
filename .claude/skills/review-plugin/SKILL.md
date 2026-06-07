---
name: review-plugin
description: Auditoria técnica do GeoFlight Planner. Use para revisar algoritmo ou verificar antes de release.
---

# Review — GeoFlight Planner

## Alvo
$ARGUMENTS

## Código a revisar
!`find ${ARGUMENTS:-.} -name "*.py" -not -path "*__pycache__*" -not -path "*.git*" 2>/dev/null | head -8 | xargs cat 2>/dev/null`

---

Revise verificando:

**Estrutura:** herda `QgsProcessingAlgorithm`; `name()` minúsculas; `createInstance()`; registrado no provider; conectado em `main.py`.

**`initAlgorithm`:** `loadParametros()` chamado; limites em todos os `QgsProcessingParameterNumber`; parâmetro `kml`; saída como `FileDestination`.

**`processAlgorithm`:** sem `print()` — só `feedback.pushInfo/Warning`; `isCanceled()` nos loops; exceções como `QgsProcessingException`; emojis nas mensagens; `saveParametros()` e `post_process_comum()` no final.

**Imports:** todos internos com `.` ou `..`; `from ..images.Imgs import *`; `from .Funcs import` específico.

**Qt5/Qt6:** diálogos com `try: exec() except: exec_()`.

**Drones/fotogrametria:** sobreposições como decimal (0.75, não 75); altitude em metros AGL; GSD com unidades corretas.

Relatório: 🔴 CRÍTICO | 🟡 AVISO | 🟢 OK — com correção para cada problema. Pronto para release? Sim/Não/Ressalvas.
