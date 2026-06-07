# CLAUDE.md — GeoFlight Planner v4.0.0

## O que é este projeto

Plugin **GeoFlight Planner** — planejamento de voo com drones para QGIS.
Autores: Prof Cazaroli, Dr. Leandro França, Prof. Ilton Freitas.
Repositório: https://github.com/OpenGeoOne/qgis-drone-flight-planner

---

## Ambiente

| Item | Valor |
|---|---|
| QGIS | 3.40 mínimo / compatível com 4.0 |
| Python | 3.12 embutido no QGIS |
| Qt | PyQt5 e PyQt6 (`supportsQt6=True`) |
| Arquitetura | Processing Plugin (`hasProcessingProvider=yes`) |
| SO desenvolvimento | macOS |

---

## Estrutura real do projeto

```
qgis-drone-flight-planner/
├── __init__.py               # classFactory → PlanoVoo.py
├── PlanoVoo.py               # class GeoFlightPlanner
├── PlanoVoo_provider.py      # class PlanoVooProvider(QgsProcessingProvider)
├── main.py                   # menus e ações
├── metadata.txt              # versão 4.0.0
├── images/
│   └── Imgs.py               # ícones embutidos como base64
├── algoritmos/
│   ├── Funcs.py              # todas as funções utilitárias compartilhadas
│   ├── PlanoVoo_H_Sensor.py  # Horizontal por sensor (câmera da calculadora)
│   ├── PlanoVoo_H_Manual.py  # Horizontal com distâncias manuais
│   ├── PlanoVoo_H_Dji_Fly.py # Horizontal para DJI Fly app
│   ├── PlanoVoo_H_Line.py    # Horizontal por número de linhas
│   ├── PlanoVoo_VF.py        # Vertical Fachada
│   ├── PlanoVoo_VC.py        # Vertical Circular
│   ├── CSV_Simplify.py       # Simplificar waypoints CSV
│   └── CSV_Merge.py          # Mesclar arquivos CSV
├── calculator/
│   ├── calculators.py        # Calculator_Dialog (PyQt)
│   └── drone_data.json       # banco de dados de drones e câmeras
└── XML/
    └── template.xml          # template KMZ DJI
```

---

## Funções de Funcs.py — importar sempre com path relativo

```python
from .Funcs import (
    saveParametros, loadParametros,
    meters2degrees, azimute, distancia,
    pontos_na_linha, linhas_voo_poligono,
    pontos_conexao, heading_para_proximo,
    processar_voo_horizontal,
    csv_como_layer, criar_layer_path,
    montar_LISTA_PONTOS, salvar_outputs,
    post_process_comum,
    _gerar_CSV, _salvar_kml
)
```

---

## Padrão de algoritmo QgsProcessingAlgorithm — QGIS 3.44/4.0

```python
# -*- coding: utf-8 -*-
from qgis.core import *
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
from ..images.Imgs import *
import os
from .Funcs import loadParametros, saveParametros, salvar_outputs, post_process_comum

class PlanoVoo_NOVO(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        param1, param2 = loadParametros("TIPO_VOO")

        self.addParameter(QgsProcessingParameterFeatureSource(
            'terreno', 'Área de voo',
            types=[QgsProcessing.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterNumber(
            'altura', 'Altura de voo (m)',
            type=QgsProcessingParameterNumber.Double,
            minValue=2, maxValue=500, defaultValue=param1
        ))
        self.addParameter(QgsProcessingParameterNumber(
            'percL', 'Sobreposição lateral (75% = 0.75)',
            type=QgsProcessingParameterNumber.Double,
            minValue=0.30, maxValue=0.95, defaultValue=param2
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            'kml', 'Abrir KML no Google Earth', defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            'saida_csv', 'Arquivo CSV de saída (Litchi)',
            fileFilter='CSV files (*.csv)', defaultValue=''
        ))

    def processAlgorithm(self, parameters, context, feedback):
        area    = self.parameterAsSource(parameters, 'terreno', context)
        altVoo  = self.parameterAsDouble(parameters, 'altura', context)
        percL   = self.parameterAsDouble(parameters, 'percL', context)
        abrir_kml = self.parameterAsBool(parameters, 'kml', context)
        arquivo_csv = self.parameterAsFile(parameters, 'saida_csv', context)

        if area.featureCount() != 1:
            raise QgsProcessingException("❌ Selecione exatamente 1 polígono!")

        feedback.pushInfo(f"✅ Iniciando: altitude={altVoo}m")

        for i, feat in enumerate(area.getFeatures()):
            if feedback.isCanceled():
                return {}
            feedback.setProgress(int(i / area.featureCount() * 100))
            # ... lógica ...

        saveParametros("TIPO_VOO", h=altVoo, csv=arquivo_csv)
        post_process_comum(context, feedback, csv_path=arquivo_csv)
        return {}

    def name(self):        return 'flight_plan_novo'
    def displayName(self): return self.tr('Novo Plano de Voo')
    def group(self):       return self.tr('Horizontal Flight Plan')
    def groupId(self):     return 'horizontal'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), '..', 'images', 'Horizontal.png'))

    def tr(self, string):
        return QCoreApplication.translate('PlanoVoo_NOVO', string)

    def createInstance(self):
        return PlanoVoo_NOVO()
```

---

## Regras de código — obrigatórias

- **Nunca `print()`** — usar `feedback.pushInfo()` / `feedback.pushWarning()`
- **Nunca `raise Exception`** — usar `raise QgsProcessingException("❌ msg")`
- **Sempre `feedback.isCanceled()`** em loops
- **Sempre `saveParametros()`** no final de `processAlgorithm`
- **Sempre `post_process_comum()`** no final para carregar camadas
- **Imports internos sempre relativos**: `from .Funcs import` / `from ..images.Imgs import *`
- **Mensagens com emojis**: ✅ sucesso, ❌ erro, ⚠️ aviso

---

## Persistência de parâmetros — QgsSettings

Prefixo fixo: `"qgis-drone-flight-planner/"`

Dados do drone (gravados pela Calculator):
```python
s = QgsSettings()
p = "qgis-drone-flight-planner/"
nameDrone = s.value(p + "nameDrone")
sensorH   = s.value(p + "sensorH")   # largura sensor (mm)
sensorV   = s.value(p + "sensorV")   # altura sensor (mm)
dFocal    = s.value(p + "dFocal")    # distância focal (mm)
```

Tipos de voo em `saveParametros/loadParametros`:
`"H_Sensor"`, `"H_Manual"`, `"H_Manual_Dji_Fly"`, `"H_Line"`, `"VF"`, `"VC"`, `"Simplify"`, `"Merge"`

---

## Parâmetros de voo — referência

| Variável | Unidade | Significado |
|---|---|---|
| `altVoo` | m | Altitude (AGL) |
| `percL` | decimal | Sobreposição lateral (0.75 = 75%) |
| `percF` | decimal | Sobreposição frontal (0.85 = 85%) |
| `velocidade` | m/s | Velocidade (0.5–20) |
| `tempo` | s | Tempo de espera para foto |
| `gimbalAng` | graus | Ângulo gimbal (-90 a 70) |
| `dVertVC` | m | Espaçamento vertical (voo circular) |
| `anguloFotoVC` | graus | Ângulo entre fotos no arco |
| `pontoInicial` | graus | Azimute de início do voo circular |
| `dist` | m | Distância da fachada (VF/VC) |
| `sensorH` | mm | Largura do sensor |
| `sensorV` | mm | Altura do sensor |
| `dFocal` | mm | Distância focal |

---

## Fórmulas fotogramétricas

```python
# Cobertura no solo
largSolo = (sensorH / dFocal) * altVoo        # m (direção de voo)
altSolo  = (sensorV / dFocal) * altVoo         # m (lateral)

# Espaçamentos
deltaFront_m = largSolo * (1 - percF)           # m entre fotos
deltaLat_m   = altSolo  * (1 - percL)           # m entre faixas

# Converter para graus (operação interna — plugin opera em EPSG:4326)
deltaFront_g = meters2degrees(deltaFront_m, lat_centro, SRC)
deltaLat_g   = meters2degrees(deltaLat_m,   lat_centro, SRC)

# GSD
GSD = (sensorH * altVoo * 100) / (dFocal * largImgPx)  # cm/px
```

---

## Fluxo horizontal (H_Sensor / H_Manual)

```
Area polígono + Linha de direção
    ↓
processar_voo_horizontal()  →  gera linhas paralelas
    ↓
montar_LISTA_PONTOS()       →  waypoints + pontos de conexão
    ↓
heading_para_proximo()      →  heading de cada ponto
    ↓
salvar_outputs()            →  CSV Litchi + camada pontos + camada linha
    ↓
post_process_comum()        →  adiciona camadas ao projeto QGIS
```

---

## IDs dos algoritmos registrados

| Classe | ID Processing |
|---|---|
| `PlanoVoo_H_Sensor` | `GeoFlightPlanner:flight_plan_h_sensor` |
| `PlanoVoo_H_Manual` | `GeoFlightPlanner:flight_plan_h_manual` |
| `PlanoVoo_H_Dji_Fly` | `GeoFlightPlanner:flight_plan_h_dji_fly` |
| `PlanoVoo_H_Line` | `GeoFlightPlanner:flight_plan_h_line` |
| `PlanoVoo_VF` | `GeoFlightPlanner:flight_plan_vf` |
| `PlanoVoo_VC` | `GeoFlightPlanner:flight_plan_vc` |
| `CSV_Simplify` | `GeoFlightPlanner:simplifyWaypoints` |
| `CSV_Merge` | `GeoFlightPlanner:mergecsv` |

---

## Compatibilidade Qt5/Qt6

```python
# Em diálogos (calculator/calculators.py):
try:
    dlg.exec()      # Qt6 / QGIS 4.0
except AttributeError:
    dlg.exec_()     # Qt5 / QGIS 3.x
```

---

## Adicionar novo algoritmo — checklist

1. Criar `algoritmos/PlanoVoo_NOVO.py`
2. Importar e registrar em `PlanoVoo_provider.py`:
   ```python
   from .algoritmos.PlanoVoo_NOVO import PlanoVoo_NOVO
   # em loadAlgorithms():
   self.addAlgorithm(PlanoVoo_NOVO())
   ```
3. Conectar ao menu em `main.py`
4. Adicionar tipo em `saveParametros/loadParametros` de `Funcs.py`
5. Recarregar com Plugin Reloader (Ctrl+F5)

---

## Skills disponíveis

| Comando | O que faz |
|---|---|
| `/novo-algoritmo` | Scaffolding de novo QgsProcessingAlgorithm |
| `/review-plugin` | Auditoria técnica do plugin ou algoritmo |
| `/doc-funcao` | Documenta funções sem docstring |
| `/plano-voo-drone` | Gera/adapta rotina de planejamento de voo |
| `/debug-plugin` | Diagnostica erros específicos deste plugin |
