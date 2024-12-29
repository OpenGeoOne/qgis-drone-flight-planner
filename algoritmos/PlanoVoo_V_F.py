# -*- coding: utf-8 -*-

"""
/***************************************************************************
 PlanoVoo
                                 A QGIS plugin
 PlanoVoo
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-12-02
        copyright            : (C) 2024 by Prof Cazaroli e Leandro França
        email                : contato@geoone.com.br
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Prof Cazaroli e Leandro França'
__date__ = '2024-12-02'
__copyright__ = '(C) 2024 by Prof Cazaroli e Leandro França'
__revision__ = '$Format:%H$'

from qgis.core import *
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from .Funcs import verificar_plugins, obter_DEM, gerar_KML, gerar_CSV, set_Z_value, reprojeta_camada_WGS84, simbologiaLinhaVoo, simbologiaPontos, calculaDistancia_Linha_Ponto
import processing
import os
import math
import numpy as np
import csv

# pontos_provider Air 2S (5472 × 3648)

class PlanoVoo_V_F(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        my_settings = QgsSettings()
        try:
            api_key = my_settings.value("OpenTopographyDEMDownloader/ot_api_key", "")
        except:
            api_key = ''

        self.addParameter(QgsProcessingParameterVectorLayer('linha_base','Flight Base Line', types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterVectorLayer('objeto','Position of the Facade', types=[QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterNumber('altura','Facade Height (m)',
                                                       type=QgsProcessingParameterNumber.Double, minValue=2,defaultValue=15))
        self.addParameter(QgsProcessingParameterNumber('alturaMin','Start Height (m)',
                                                       type=QgsProcessingParameterNumber.Double, minValue=2,defaultValue=2))
        self.addParameter(QgsProcessingParameterNumber('dc','Sensor: Horizontal Size (m)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0,defaultValue=13.2e-3)) # igual p/o Phantom 4 Pro e Air 2S (5472 × 3648)
        self.addParameter(QgsProcessingParameterNumber('dl','Sensor: Vertical Size (m)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0,defaultValue=8.8e-3)) # igual p/o Phantom 4 Pro e Air 2S (5472 × 3648)
        self.addParameter(QgsProcessingParameterNumber('f','Sensor: Focal Length (m)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0,defaultValue=8.38e-3)) # Para o Air 2S - Phantom 4 Pro é f = 9e-3
        self.addParameter(QgsProcessingParameterNumber('percL','Side Overlap (75% = 0.75)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0.60,defaultValue=0.75))
        self.addParameter(QgsProcessingParameterNumber('percF','Forward Overlap (85% = 0.85)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0.60,defaultValue=0.85))
        self.addParameter(QgsProcessingParameterString('api_key', 'API key - OpenTopography plugin',defaultValue=api_key))
        self.addParameter(QgsProcessingParameterNumber('velocidade','Flight Speed (m/s)',
                                                       type=QgsProcessingParameterNumber.Double, minValue=2,defaultValue=3))
        self.addParameter(QgsProcessingParameterNumber('tempo','Time to Wait for Photo (seconds)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=0,defaultValue=2))
        self.addParameter(QgsProcessingParameterFolderDestination('saida_kml', 'Output Folder for KML (Google Earth)'))
        self.addParameter(QgsProcessingParameterFileDestination('saida_csv', 'Output CSV File (Litchi)',
                                                               fileFilter='CSV files (*.csv)'))

    def processAlgorithm(self, parameters, context, feedback):
        teste = False # Quando True mostra camadas intermediárias

        # ===== Parâmetros de entrada para variáveis =========================================================
        linha_base = self.parameterAsVectorLayer(parameters, 'linha_base', context)
        crs = linha_base.crs()

        objeto = self.parameterAsVectorLayer(parameters, 'objeto', context)

        H = parameters['altura']
        h = parameters['alturaMin']
        dc = parameters['dc']
        dl = parameters['dl']
        f = parameters['f']
        percL = parameters['percL'] # Lateral
        percF = parameters['percF'] # Frontal
        velocidade = parameters['velocidade']
        tempo = parameters['tempo']

        apikey = parameters['api_key']

        caminho_kml = parameters['saida_kml']
        arquivo_csv = parameters['saida_csv']

        # ===== Verificações ===================================================================================

        # Verificar se os plugins estão instalados
        plugins_verificar = ["OpenTopography-DEM-Downloader", "lftools", "kmltools"]
        verificar_plugins(plugins_verificar, feedback)

        # Verificar as Geometrias
        if linha_base.featureCount() != 1:
            raise ValueError("Linha Base deve conter somente uma linha.")

        if objeto.featureCount() != 1:
            raise ValueError("Objeto deve conter somente um ponto.")

        linha = next(linha_base.getFeatures())
        linha_base_geom = linha.geometry()

        # Obtem a distância da Linha de Voo ao Objeto
        p = list(objeto.getFeatures())
        ponto_base_geom = p[0].geometry()

        dist_objeto = calculaDistancia_Linha_Ponto(linha_base_geom, ponto_base_geom)

        if dist_objeto <= 10:
            raise ValueError(f"A distância horizontal ({round(dist_objeto, 2)}) está com 10 metros ou menos.")

        feedback.pushInfo(f"Distância Linha de Voo ao Objeto: {round(dist_objeto, 2)}     Altura do Objeto: {round(H, 2)}")

        # =====Cálculo das Sobreposições=========================================
        # Distância das linhas de voo paralelas - Espaçamento Lateral
        # H é dist_objeto
        tg_alfa_2 = dc / (2 * f)
        D_lat = dc * dist_objeto / f
        SD_lat = percL * D_lat
        h1 = SD_lat / (2 * tg_alfa_2)
        deltaLat = SD_lat * (dist_objeto / h1 - 1)

        # Espaçamento Frontal entre as fotografias- Espaçamento Frontal
        tg_alfa_2 = dl / (2 * f)
        D_front = dl * dist_objeto / f
        SD_front = percF * D_front
        h1 = SD_front / (2 * tg_alfa_2)
        deltaFront = SD_front * (dist_objeto / h1 - 1)

        feedback.pushInfo(f"Delta Horizontal: {round(deltaFront, 2)}     Delta Vertical: {round(deltaLat, 2)}")

        # Obtem as alturas das linhas de Voo (range só para números inteiros)
        alturas = [i for i in np.arange(h, H + h + 1, deltaLat)]

        # Obtem as distâncias nas linhas de Voo
        comprimento_linha_base = linha_base_geom.length() # comprimento da linha
        distancias = [i for i in np.arange(0, comprimento_linha_base, deltaFront)]

        feedback.pushInfo(f"Comprimento Linha Base: {comprimento_linha_base} \n Alturas: {alturas}     Distancias: {distancias}")

        # =====================================================================
        # ===== OpenTopography ================================================

        # Reprojetar para WGS 84 (EPSG:4326), usado pelo OpenTopography
        crs_wgs = QgsCoordinateReferenceSystem(4326)
        transformador = QgsCoordinateTransform(crs, crs_wgs, QgsProject.instance())

        #camadaMDE = obter_DEM("VF", linha_base_geom, transformador, apikey, feedback)

        #QgsProject.instance().addMapLayer(camadaMDE)

        camadaMDE = QgsProject.instance().mapLayersByName("DEM")[0]

        # =============================================================================================
        # ===== Criar a camada Pontos de Fotos ========================================================

        # Criar uma camada Pontos com os deltaFront sobre a linha Base e depois empilhar com os deltaFront
        pontos_fotos = QgsVectorLayer('Point?crs=' + crs.authid(), 'Pontos Fotos', 'memory')
        pontos_provider = pontos_fotos.dataProvider()

        # Definir campos
        campos = QgsFields()
        campos.append(QgsField("id", QVariant.Int))
        campos.append(QgsField("linha", QVariant.Int))
        campos.append(QgsField("latitude", QVariant.Double))
        campos.append(QgsField("longitude", QVariant.Double))
        campos.append(QgsField("altitude", QVariant.Double))
        campos.append(QgsField("alturavoo", QVariant.Double))
        pontos_provider.addAttributes(campos)
        pontos_fotos.updateFields()

        pontoID = 1

        # Verificar a posição da linha base em relação ao objeto que se quer medir
        if linha_base_geom.isMultipart():
            partes = linha_base_geom.asGeometryCollection()
            linha_base_geom = partes[0]  # Pegue a primeira linha da MultiLineString
        else:
            linha_base_geom = linha_base_geom[0].geometry()

        linha = linha_base_geom.asPolyline()

        # Coordenadas da linha base
        p1 = linha[0]
        p2 = linha[-1]

        # Ângulo em relação ao norte (em graus)
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        angulo_linha_base = math.degrees(math.atan2(dx, dy))

        # Calcular a perpendicular (90 graus)
        angulo_perpendicular = (angulo_linha_base + 90) % 360

        # Verificar orientação do ponto em relação à linha base
        objeto_feature = objeto.getFeature(0)
        objeto_geom = objeto_feature.geometry()
        objeto_point = objeto_geom.asPoint()

        # Calcular a equação da linha base (Ax + By + C = 0)
        A = p2.y() - p1.y()
        B = p1.x() - p2.x()
        C = p2.x() * p1.y() - p1.x() * p2.y()

        # Verificar o sinal ao substituir as coordenadas do ponto de orientação
        orientacao = A * objeto_point.x() + B * objeto_point.y() + C

        # Ajustar o ângulo da perpendicular com base na orientação
        if orientacao < 0:
            angulo_perpendicular += 180
            angulo_perpendicular %= 360

        feedback.pushInfo(f"Ângulo da linha base: {angulo_linha_base:.2f}°")
        feedback.pushInfo(f"Ângulo da perpendicular em relação ao Norte: {angulo_perpendicular:.2f}°")

        # Criar as carreiras de pontos
        for idx, altura in enumerate(alturas, start=1):  # Cada altura representa uma "linha"
            # Alternar o sentido
            if idx % 2 == 0:  # "Linha de vem" (segunda, quarta, ...)
                dist_horiz = reversed(distancias)
            else:  # "Linha de vai" (primeira, terceira, ...)
                dist_horiz = distancias

            for d in dist_horiz:
                if d == comprimento_linha_base:  # Ajuste para evitar problemas com interpolate
                    d = comprimento_linha_base

                ponto = linha_base_geom.interpolate(d).asPoint()
                ponto_geom = QgsGeometry.fromPointXY(QgsPointXY(ponto))
                # Transformar coordenada do ponto para CRS do raster
                ponto_wgs = transformador.transform(QgsPointXY(ponto.x(), ponto.y()))

                # Obter valor de Z do MDE
                value, result = camadaMDE.dataProvider().sample(QgsPointXY(ponto_wgs), 1)  # Resolução de amostragem
                if result:
                    a = value
                else:
                    feedback.pushWarning(f"Falha ao obter altitude para o ponto {f.id()}")
                    a = 0

                # Criar o recurso de ponto
                ponto_feature = QgsFeature()
                ponto_feature.setFields(campos)
                ponto_feature.setAttribute("id", pontoID)
                ponto_feature.setAttribute("linha", idx)  # Linha correspondente à altura
                ponto_feature.setAttribute("latitude", ponto.y())
                ponto_feature.setAttribute("longitude", ponto.x())
                ponto_feature.setAttribute("altitude", a + float(altura))
                ponto_feature.setAttribute("alturavoo", float(altura))
                ponto_feature.setGeometry(ponto_geom)
                pontos_provider.addFeature(ponto_feature)

                pontoID += 1

        # Atualizar a camada
        pontos_fotos.updateExtents()
        pontos_fotos.commitChanges()

        # Point para PointZ
        pontos_fotos = set_Z_value(pontos_fotos, z_field="altitude")

        # Reprojetar camada Pontos Fotos de UTM para WGS84 (4326)
        pontos_reproj = reprojeta_camada_WGS84(pontos_fotos, crs_wgs, transformador)

        # Point para PointZ
        pontos_reproj = set_Z_value(pontos_reproj, z_field="altitude")

        # Simbologia
        simbologiaPontos(pontos_reproj)

        # ===== PONTOS FOTOS ==========================
        QgsProject.instance().addMapLayer(pontos_reproj)

        # ===== Final Pontos Fotos ============================================
        # =====================================================================


        # =============================================================================================
        # ===== Criar Linhas de Voo ===================================================================

        linha_voo_layer = QgsVectorLayer('LineString?crs=' + crs.authid(), 'Linha de Voo', 'memory')
        linhavoo_provider = linha_voo_layer.dataProvider()

        # Definir campos
        campos = QgsFields()
        campos.append(QgsField("id", QVariant.Int))
        campos.append(QgsField("altitude", QVariant.Double))
        linhavoo_provider.addAttributes(campos)
        linha_voo_layer.updateFields()

        # Obter as altitudes médias por linha de voo

        # Obter valores únicos do campo 'linha'
        valores_unicos = pontos_fotos.uniqueValues(pontos_fotos.fields().indexFromName('linha'))

        # Iterar pelos valores únicos do campo 'linha'
        for linha_atual in valores_unicos:
            # Criar filtro para obter os pontos da linha atual
            filtro = f'"linha" = {linha_atual}'
            pontos_filtrados = pontos_fotos.getFeatures(QgsFeatureRequest().setFilterExpression(filtro))

            soma_altitude = 0
            contador = 0
            geometria_pontos = []

            # Processar as feições da linha atual
            for f in pontos_filtrados:
                altitude = f['altitude']
                soma_altitude += altitude
                contador += 1
                geometria_pontos.append(f.geometry().asPoint())

            # Calcular a média de altitude
            media = soma_altitude / contador

            # Criar e adicionar a feição para a linha de voo atual
            nova_linha_voo = QgsFeature()
            nova_linha_voo.setFields(linha_voo_layer.fields())
            nova_linha_voo.setAttribute("id", linha_atual)
            nova_linha_voo.setAttribute("altitude", media)

            # Criar a geometria da linha de voo
            nova_linha_voo.setGeometry(QgsGeometry.fromPolylineXY(geometria_pontos))
            linhavoo_provider.addFeature(nova_linha_voo)

        # Atualizar a camada de linha de voo
        linha_voo_layer.updateExtents()
        linha_voo_layer.triggerRepaint()

        # Reprojetar linha_voo_layer para WGS84 (4326)
        linha_voo_reproj = reprojeta_camada_WGS84(linha_voo_layer, crs_wgs, transformador)

        # Polygon para PolygonZ
        linha_voo_reproj = set_Z_value(linha_voo_reproj, z_field="altitude")

        # Configurar simbologia de seta
        simbologiaLinhaVoo("VF", linha_voo_reproj)

        # ===== LINHA DE VOO ==============================
        QgsProject.instance().addMapLayer(linha_voo_reproj)

        # ===== Final Linha de Voo ============================================
        # =====================================================================

        feedback.pushInfo("")
        feedback.pushInfo("Linha de Voo e Pontos para Fotos concluídos com sucesso!")

        # =========Exportar para o Google  E a r t h   P r o  (kml)================================================

        # Verifica se o caminho é válido, não é 'TEMPORARY OUTPUT' e é um diretório
        if caminho_kml and caminho_kml != 'TEMPORARY OUTPUT' and os.path.isdir(caminho_kml):
            arquivo_kml = caminho_kml + r"\Pontos Fotos.kml"
            gerar_KML(pontos_reproj, arquivo_kml, crs_wgs, feedback)

            arquivo_kml = caminho_kml + r"\Linha de Voo.kml"
            gerar_KML(linha_voo_reproj, arquivo_kml, crs_wgs, feedback)
        else:
            feedback.pushInfo("Caminho KML não especificado. Etapa de exportação ignorada.")

        # =============L I T C H I==========================================================

        if arquivo_csv and arquivo_csv.endswith('.csv'): # Verificar se o caminho CSV está preenchido
            gerar_CSV("VF", pontos_reproj, arquivo_csv, velocidade, tempo, deltaFront, angulo_perpendicular, H)
        else:
            feedback.pushInfo("Caminho CSV não especificado. Etapa de exportação ignorada.")

        # ============= Mensagem de Encerramento =====================================================
        feedback.pushInfo("")
        feedback.pushInfo("Plano de Voo Vertical de Fachada executado com sucesso.")

        return {}

    def name(self):
        return 'PlanoVooVF'.lower()

    def displayName(self):
        return self.tr('Facade')

    def group(self):
        return 'Vertical Flight'

    def groupId(self):
        return 'vertical'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PlanoVoo_V_F()

    def tags(self):
        return self.tr('Flight Plan,Measure,Topography,Fachada,Vertical,Front,View').split(',')

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/Vertical.png'))

    texto = """Este algoritmo calcula um 'Voo para Fachada' gerando a 'Linha do Voo' e uma camada de 'Pontos' para Fotos.
            Gera ainda: a planilha CSV para importar no Litchi e o arquivo KML para Google Earth.
            Se você usa um aplicativo para Voo que não seja o Litchi, pode usar os pontos gerados no QGIS ou os arquivos KML
            Dados:
            1. Linha Base de Voo
            2. Um Ponto para indicar o Ponto Extremo da Fachada
            3. Altura do Objeto (m)
            4. Altura Inicial do Voo (m)
            5. Espaçamento Horizontal (m)
            6. Espaçamento Vertical (m)
            7. Velocidade do Voo (m/s)
            8. Tempo de espera para tirar a Foto (s)
            9. Chave API do Open Topography
            10. Caminho para gravar os KML
            11. Arquivo para gravar o CSV para o Litchi
            """
    figura = 'images/VooVF1.jpg'

    def shortHelpString(self):
        corpo = '''<div align="center">
                      <img src="'''+ os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figura) +'''">
                      </div>
                      <div align="right">
                      <p align="right">
                      <b>Autores: Prof Cazaroli     -     Leandro França</b>
                      </p>GeoOne</div>
                    </div>'''
        return self.tr(self.texto) + corpo
