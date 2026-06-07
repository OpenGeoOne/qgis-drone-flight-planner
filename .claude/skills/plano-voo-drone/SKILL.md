---
name: plano-voo-drone
description: Gera, adapta ou explica rotinas de planejamento de voo do GeoFlight Planner. Use para novo tipo de voo, cálculo de GSD/espaçamentos, ou adaptação de parâmetros.
---

# Planejamento de Voo — GeoFlight Planner

## Solicitação
$ARGUMENTS

## Algoritmos existentes
!`ls algoritmos/PlanoVoo_*.py 2>/dev/null`

## Parâmetros salvos (QgsSettings)
!`python3 -c "
from qgis.core import QgsSettings
s = QgsSettings(); p = 'qgis-drone-flight-planner/'
for k in ['nameDrone','sensorH','sensorV','dFocal','hVooS','dlS','dfS']:
    v = s.value(p+k)
    if v: print(f'{k}: {v}')
" 2>/dev/null || echo "Execute dentro do QGIS"`

---

Com base em `$ARGUMENTS`:

- **"novo voo [tipo]"** → gere algoritmo completo no padrão do projeto
- **"explique [algoritmo]"** → explique parâmetros e fluxo
- **"adapte [algo] para [mudança]"** → modifique preservando o padrão
- **"calcule [parâmetros]"** → GSD, espaçamentos, número de fotos

Fórmulas do projeto:
```
largSolo = (sensorH / dFocal) * altVoo        # m
altSolo  = (sensorV / dFocal) * altVoo         # m
dFront   = largSolo * (1 - percF)              # m entre fotos
dLat     = altSolo  * (1 - percL)              # m entre faixas
GSD      = (sensorH * altVoo * 100) / (dFocal * largImgPx)  # cm/px
```

Voo circular (VC): `n_voltas = ceil((hObj - altMin) / dVertVC)`, pontos por volta = `360 // anguloFotoVC`, heading = `(azimute + 180) % 360`.

Fluxo horizontal sempre: `processar_voo_horizontal → montar_LISTA_PONTOS → salvar_outputs → post_process_comum`.
