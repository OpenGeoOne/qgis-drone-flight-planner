# -*- coding: utf-8 -*-

"""
/***************************************************************************
 PlanoVoo
                                 A QGIS plugin
 PlanoVoo
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-11-05
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
__date__ = '2024-11-05'
__copyright__ = '(C) 2024 by Prof Cazaroli e Leandro França'
__revision__ = '$Format:%H$'

from qgis.core import *
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from .Funcs import verificar_plugins, obter_DEM, gerar_KML, gerar_CSV, set_Z_value, reprojeta_camada_WGS84, simbologiaLinhaVoo, simbologiaPontos, verificarCRS, loadParametros, saveParametros, removeLayersReproj, criarLinhaVoo
from ..images.Imgs import *
import processing
import os
import math
import csv

# pontos_provider Air 2S (5472 × 3648)

class PlanoVoo_H(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        hVoo, sensorH, sensorV, dFocal, sLateral, sFrontal, veloc, tStay, api_key, sKML, sCSV = loadParametros("H")

        self.addParameter(QgsProcessingParameterVectorLayer('terreno', 'Area', types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterVectorLayer('primeira_linha','First line - direction flight', types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterNumber('H','Flight Height (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=50,defaultValue=hVoo))
        self.addParameter(QgsProcessingParameterNumber('dc','Sensor: Horizontal Size (mm)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0,defaultValue=sensorH)) # default p/o Phantom 4 Pro e Air 2S
        self.addParameter(QgsProcessingParameterNumber('dl','Sensor: Vertical Size (mm)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0,defaultValue=sensorV)) # default p/o Phantom 4 Pro e Air 2S 
        self.addParameter(QgsProcessingParameterNumber('f','Sensor: Focal Length (mm)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0,defaultValue=dFocal)) # default o Air 2S - Phantom 4 Pro 
        self.addParameter(QgsProcessingParameterNumber('percL','Side Overlap (75% = 0.75)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0.30,defaultValue=sLateral))
        self.addParameter(QgsProcessingParameterNumber('percF','Forward Overlap (85% = 0.85)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0.60,defaultValue=sFrontal))
        self.addParameter(QgsProcessingParameterNumber('velocidade','Flight Speed (m/s)',
                                                       type=QgsProcessingParameterNumber.Double, minValue=2,defaultValue=veloc))
        self.addParameter(QgsProcessingParameterNumber('tempo','Time to Wait for Photo (seconds)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=0,defaultValue=tStay))
        self.addParameter(QgsProcessingParameterRasterLayer('raster','Input Raster (if any)'))
        self.addParameter(QgsProcessingParameterString('api_key', 'API key - OpenTopography plugin (uses an orthometric surface)', defaultValue=api_key))
        self.addParameter(QgsProcessingParameterFolderDestination('saida_kml', 'Output Folder for KML (Google Earth)', defaultValue=sKML))
        self.addParameter(QgsProcessingParameterFileDestination('saida_csv', 'Output CSV File (Litchi)', fileFilter='CSV files (*.csv)', defaultValue=sCSV))

    def processAlgorithm(self, parameters, context, feedback):
        teste = False # Quando True mostra camadas intermediárias

        # =====Parâmetros de entrada para variáveis==============================
        area_layer = self.parameterAsVectorLayer(parameters, 'terreno', context)

        primeira_linha  = self.parameterAsVectorLayer(parameters, 'primeira_linha', context)
        
        camadaMDE = self.parameterAsRasterLayer(parameters, 'raster', context)

        H = parameters['H']
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

        # ===== Grava Parâmetros =====================================================
        saveParametros("H", parameters['H'], parameters['velocidade'], parameters['tempo'], parameters['saida_kml'], parameters['saida_csv'], parameters['dc'], parameters['dl'], parameters['f'], parameters['percL'], parameters['percF'])
        
        # ===== Verificações =====================================================

        # Verificar o SRC das Camadas
        crs = area_layer.crs()
        crsL = primeira_linha.crs() # não usamos o crsL, apenas para verificar a camada
        if crs != crsL:
            raise ValueError("Both layers must be from the same CRS.")

        if "UTM" in crs.description().upper():
            feedback.pushInfo(f"The layer 'Area' is already in CRS UTM.")
        elif "WGS 84" in crs.description().upper() or "SIRGAS 2000" in crs.description().upper():
            crs = verificarCRS(area_layer, feedback)
            nome = area_layer.name() + "_reproject"
            area_layer = QgsProject.instance().mapLayersByName(nome)[0]
        else:
            raise Exception(f"Layer must be WGS84 or SIRGAS2000 or UTM. Other ({crs.description().upper()}) not supported")

        if "UTM" in crsL.description().upper():
            feedback.pushInfo(f"The layer 'First line - direction flight' is already in CRS UTM.")
        elif "WGS 84" in crsL.description().upper() or "SIRGAS 2000" in crsL.description().upper():
            verificarCRS(primeira_linha, feedback)
            nome = primeira_linha.name() + "_reproject"
            primeira_linha = QgsProject.instance().mapLayersByName(nome)[0]
        else:
            raise Exception(f"Layer must be WGS84 or SIRGAS2000 or UTM. Other ({crs.description().upper()}) not supported")

        # Verificar se os plugins estão instalados
        plugins_verificar = ["OpenTopography-DEM-Downloader", "lftools", "kmltools"]
        verificar_plugins(plugins_verificar, feedback)

        # Verificar as Geometrias
        poligono_features = next(area_layer.getFeatures()) # dados do Terreno
        poligono_geom = poligono_features.geometry()
        if poligono_geom.isMultipart():
            poligono_geom = poligono_geom.asGeometryCollection()[0]

        linha_features = next(primeira_linha.getFeatures())
        linha_geom = linha_features.geometry()
        if linha_geom.isMultipart():
            linha_geom = linha_geom.asGeometryCollection()[0]

        if area_layer.featureCount() != 1:
            raise ValueError("The Area must contain only one polygon.")

        if primeira_linha.featureCount() != 1:
            raise ValueError("The First Line must contain only one line.")

         # =====Cálculo das Sobreposições=========================================
        # Distância das linhas de voo paralelas - Espaçamento Lateral
        tg_alfa_2 = dc / (2 * f)
        D_lat = dc * H / f
        SD_lat = percL * D_lat
        h1 = SD_lat / (2 * tg_alfa_2)
        deltaLat = SD_lat * (H / h1 - 1)

        # Espaçamento Frontal entre as fotografias- Espaçamento Frontal
        tg_alfa_2 = dl / (2 * f)
        D_front = dl * H / f
        SD_front = percF * D_front
        h1 = SD_front / (2 * tg_alfa_2)
        deltaFront = SD_front * (H / h1 - 1)

        feedback.pushInfo(f"Lateral Spacing: {round(deltaLat,2)}, Frontal Spacing: {round(deltaFront,2)}")

        # =====================================================================
        # ===== OpenTopography ================================================

        # Reprojetar para WGS 84 (EPSG:4326), usado pelo OpenTopography
        crs_wgs = QgsCoordinateReferenceSystem(4326)
        transformador = QgsCoordinateTransform(crs, crs_wgs, QgsProject.instance())

        if camadaMDE is None:
            camadaMDE = obter_DEM("H", area_layer, transformador, apikey, feedback)

        #QgsProject.instance().addMapLayer(camadaMDE)

        #camadaMDE = QgsProject.instance().mapLayersByName("DEM")[0]

        # ================================================================================
        # ===== Ajuste da linha sobre um lado do polígono ================================

        # Criar lista de arestas (pares de vértices consecutivos)
        # Verificar se o polígono é multipart ou simples
        if poligono_geom.isMultipart():
            p = poligono_geom.asMultiPolygon()[0][0]
        else:
            p = poligono_geom.asPolygon()[0]

        bordas = [(p[i], p[i + 1]) for i in range(len(p) - 1)]

        if linha_geom.isMultipart():
            linha_base = linha_geom.asMultiPolyline()[0]  # Primeira linha em multipart
        else:
            linha_base = linha_geom.asPolyline()  # Linha simples

        # Calcular direção da linha base (comparar o ponto inicial e final)
        x1_base, y1_base = linha_base[0]
        x2_base, y2_base = linha_base[-1]

        direcao_base = 'direita' if x2_base > x1_base or (x2_base == x1_base and y2_base > y1_base) else 'esquerda'

        # Verificar se a linha base coincide com algum lado do polígono
        linha_base_geom = QgsGeometry.fromPolylineXY(linha_base)

        tolerancia = 0.01
        coincide_com_borda = False

        for v1, v2 in bordas:
            borda_geom = QgsGeometry.fromPolylineXY([v1, v2])

            # Calcular a distância entre a linha base e a borda
            distancia = borda_geom.shortestLine(linha_geom).length()

            # Verificar se a linha base coincide com a borda
            if distancia <= tolerancia:
                coincide_com_borda = True
                break

        if not coincide_com_borda:
            # Encontrar a aresta mais próxima da linha
            min_distancia = float('inf')
            closest_borda = None

            for v1, v2 in bordas:
                borda_geom = QgsGeometry.fromPolylineXY([v1, v2])
                distancia = borda_geom.shortestLine(linha_geom).length()

                if distancia < min_distancia:
                    min_distancia = distancia
                    closest_borda = borda_geom

            # Atualizar a posição da Linha Base
            nova_linha_geom = QgsGeometry.fromPolylineXY(closest_borda.asPolyline())

            with edit(primeira_linha):
                primeira_linha.changeGeometry(linha_features.id(), nova_linha_geom)

            # Encontrar o ponto inicial da linha deslocada
            # Calcular a direção da linha deslocada
            x1, y1 = linha_base[0]
            x2, y2 = linha_base[-1]

            direcao_deslocada = 'direita' if x2 > x1 or (x2 == x1 and y2 > y1) else 'esquerda'

            # Inverter a linha deslocada se as direções forem diferentes
            if direcao_base != direcao_deslocada:
                # Inverter a linha deslocada
                nova_linha_geom_invertida = QgsGeometry.fromPolylineXY(list(reversed(nova_linha_geom.asPolyline())))

                with edit(primeira_linha):
                    primeira_linha.changeGeometry(linha_features.id(), nova_linha_geom_invertida)

        linha_features = next(primeira_linha.getFeatures())
        linha_geom = linha_features.geometry()
        if linha_geom.isMultipart():
            linha_geom = linha_geom.asGeometryCollection()[0]

        # =====================================================================
        # ===== Determinação das Linhas de Voo ================================

        vertices = [QgsPointXY(v) for v in poligono_geom.vertices()] # Extrair os vértices do polígono

        if linha_geom.isMultipart():
            linha_vertices = linha_geom.asMultiPolyline()[0]  # Se a linha for do tipo poly
        else:
            linha_vertices = linha_geom.asPolyline()

        # Criar a geometria da linha base
        linha_base = QgsGeometry.fromPolylineXY([QgsPointXY(p) for p in linha_vertices])

        # Encontrar os pontos extremos de cada lado da linha base (sempre terá 1 ou 2 pontos)
        ponto_extremo_dir = None
        ponto_extremo_esq = None
        dist_max_dir = 0 # float('-inf')
        dist_max_esq = 0 # float('-inf')

        # Iterar sobre os vértices do polígono
        ponto1 = QgsPointXY(linha_vertices[0])
        ponto2 = QgsPointXY(linha_vertices[1])

        for ponto_atual in vertices:
            # Calcular o produto vetorial para determinar se o ponto está à direita ou à esquerda
            produto_vetorial = (ponto2.x() - ponto1.x()) * (ponto_atual.y() - ponto1.y()) - (ponto2.y() - ponto1.y()) * (ponto_atual.x() - ponto1.x())

            # Calcular a distância perpendicular do ponto à linha base
            numerador = abs((ponto2.y() - ponto1.y()) * ponto_atual.x() - (ponto2.x() - ponto1.x()) * ponto_atual.y() + ponto2.x() * ponto1.y() - ponto2.y() * ponto1.x())
            denominador = math.sqrt((ponto2.y() - ponto1.y())**2 + (ponto2.x() - ponto1.x())**2)
            dist_perpendicular = numerador / denominador if denominador != 0 else 0

            # Atualizar o ponto extremo à direita (produto vetorial positivo)
            if produto_vetorial > 0 and dist_perpendicular > dist_max_dir:
                dist_max_dir = dist_perpendicular
                ponto_extremo_dir = ponto_atual

            # Atualizar o ponto extremo à esquerda (produto vetorial negativo)
            elif produto_vetorial < 0 and dist_perpendicular > dist_max_esq:
                dist_max_esq = dist_perpendicular
                ponto_extremo_esq = ponto_atual

        # Adicionar os pontos extremos encontrados à lista
        pontos_extremos = []
        if ponto_extremo_dir:
            pontos_extremos.append(ponto_extremo_dir)
        if ponto_extremo_esq:
            pontos_extremos.append(ponto_extremo_esq)

        # Criar camada temporária para o(s) ponto(s) oposto(s); a maioria das vezes será um ponto só
        pontosExtremos_layer = QgsVectorLayer('Point?crs=' + crs.authid(), 'Pontos Extremos', 'memory')
        pontos_provider = pontosExtremos_layer.dataProvider()
        pontos_provider.addAttributes([QgsField('id', QVariant.Int)])
        pontosExtremos_layer.updateFields()

        # Adicionar os pontos extremos à camada temporária
        for feature_id, ponto in enumerate(pontos_extremos, start=1):
            if ponto:
                ponto_feature = QgsFeature()
                ponto_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(ponto)))
                ponto_feature.setAttributes([feature_id])  # ID do ponto
                pontos_provider.addFeature(ponto_feature)

        if teste == True:
            QgsProject.instance().addMapLayer(pontosExtremos_layer)

        # Criar uma linha estendida sobre a linha base

         # ponto inicial e final da linha base
        p1 = linha_vertices[0]
        p2 = linha_vertices[1]

        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        angulo = math.atan2(dy, dx)

        extensao_x = (dist_max_esq + dist_max_dir) * math.cos(angulo) * 3 # multiplicando por 3 para os casos de escolher um lado mais curto
        extensao_y = (dist_max_esq + dist_max_dir) * math.sin(angulo) * 3

        p1_estendido = QgsPointXY(p1.x() - extensao_x ,p1.y() - extensao_y)
        p2_estendido = QgsPointXY(p2.x() + extensao_x ,p2.y() + extensao_y)
        linha_estendida = QgsGeometry.fromPolylineXY([QgsPointXY(p1_estendido), QgsPointXY(p2_estendido)])

        # Criar camada temporária para a linha estendida
        linhaEstendida_layer = QgsVectorLayer('LineString?crs=' + crs.authid(), 'Linha Estendida', 'memory')
        linha_provider = linhaEstendida_layer.dataProvider()
        linha_provider.addAttributes([QgsField('id', QVariant.Int)])
        linhaEstendida_layer.updateFields()

        linha_feature = QgsFeature()
        linha_feature.setGeometry(linha_estendida)
        linha_feature.setAttributes([1])  # ID da linha estendida
        linha_provider.addFeature(linha_feature)

        if teste == True:
            QgsProject.instance().addMapLayer(linhaEstendida_layer)

        # Criar linhas Paralelas à linha base até o(s) ponto(s) extremo(s)
        paralelas_layer = QgsVectorLayer('LineString?crs=' + crs.authid(), 'Linhas Paralelas', 'memory')
        paralelas_provider = paralelas_layer.dataProvider()
        paralelas_provider.addAttributes([QgsField('id', QVariant.Int)])
        paralelas_layer.updateFields()

        # Incluir a linha como a primeira linha paralela
        primeira_linha_feature = next(primeira_linha.getFeatures())
        primeira_linha = primeira_linha_feature.geometry()

        linha_id = 1
        paralela_feature = QgsFeature()
        paralela_feature.setGeometry(primeira_linha)
        paralela_feature.setAttributes([linha_id])
        paralelas_provider.addFeature(paralela_feature)

        pontos_extremos = []
        if ponto_extremo_dir:  # Se existe o ponto extremo à direita
            dist = linha_estendida.distance(QgsGeometry.fromPointXY(QgsPointXY(ponto_extremo_dir))) if ponto_extremo_dir else 0
            pontos_extremos.append((dist, 1))  # Distância e sentido para o ponto direito

        if ponto_extremo_esq:  # Se existe o ponto extremo à esquerda
            dist = linha_estendida.distance(QgsGeometry.fromPointXY(QgsPointXY(ponto_extremo_esq))) if ponto_extremo_esq else 0
            pontos_extremos.append((dist, -1))  # Distância e sentido para o ponto esquerdo

        # Criar as paralelas em um sentido de cada vez
        for dist, sentido in pontos_extremos:
            deslocamento = deltaLat * sentido  # Usando a direção positiva ou negativa

            while abs(deslocamento) <= dist:  # Criar linhas paralelas até o ponto extremo
                linha_id += 1

                # Deslocamento da linha base para criar a paralela
                parameters = {
                    'INPUT': linhaEstendida_layer,  # Linha base
                    'DISTANCE': deslocamento,
                    'OUTPUT': 'memory:'
                }

                result = processing.run("native:offsetline", parameters)
                linha_paralela_layer = result['OUTPUT']

                # Obter a geometria da linha paralela
                feature = next(linha_paralela_layer.getFeatures(), None)
                linha_geom = feature.geometry() if feature else None

                if linha_geom:
                    # Interseção da linha paralela com o polígono
                    intersecao_geom = linha_geom.intersection(poligono_geom)

                    # Adicionar a paralela à camada
                    paralela_feature = QgsFeature()
                    paralela_feature.setGeometry(intersecao_geom)
                    paralela_feature.setAttributes([linha_id])
                    paralelas_provider.addFeature(paralela_feature)
                    paralelas_layer.updateExtents()

                    # Atualizar a linha base para a próxima paralela
                    linha_estendida = linha_paralela_layer

                    deslocamento += deltaLat * sentido  # Atualizar o deslocamento

        if teste == True:
            QgsProject.instance().addMapLayer(paralelas_layer)

        # Criar a camada com a união das linhas paralelas, criando as Linhas de Voo
        linhas_unidas_layer = QgsVectorLayer('LineString?crs=' + crs.authid(), 'Linhas Unidas', 'memory')
        linhas_provider = linhas_unidas_layer.dataProvider()
        linhas_provider.addAttributes([QgsField('id', QVariant.Int)])
        linhas_unidas_layer.updateFields()

        paralelas_features = list(paralelas_layer.getFeatures())
        linha_id = 1

        for i in range(len(paralelas_features)):
            # Adicionar a linha paralela à camada
            linha_paralela = paralelas_features[i]
            linha_paralela.setAttributes([linha_id])
            linhas_provider.addFeature(linha_paralela)
            linha_id += 1

            # Criar a linha de costura
            if i < len(paralelas_features) - 1:
                geom_atual = paralelas_features[i].geometry()
                geom_seguinte = paralelas_features[i + 1].geometry()

                # Obter os extremos das linhas (direita ou esquerda alternando)
                extremos_atual = list(geom_atual.vertices())
                extremos_seguinte = list(geom_seguinte.vertices())

                if i % 2 == 0:  # Conecta pelo lado direito
                    ponto_inicio = QgsPointXY(extremos_atual[-1])  # Extremo final da linha atual
                    ponto_fim = QgsPointXY(extremos_seguinte[-1])  # Extremo final da próxima linha
                else:  # Conecta pelo lado esquerdo
                    ponto_inicio = QgsPointXY(extremos_atual[0])  # Extremo inicial da linha atual
                    ponto_fim = QgsPointXY(extremos_seguinte[0])  # Extremo inicial da próxima linha

                # Criar a geometria da linha de costura
                conexao_geom = QgsGeometry.fromPolylineXY([ponto_inicio, ponto_fim])
                conexao_feature = QgsFeature()
                conexao_feature.setGeometry(conexao_geom)
                conexao_feature.setAttributes([linha_id])
                linhas_provider.addFeature(conexao_feature)

                linha_id += 1

        # Atualizar extensão da camada de resultado
        linhas_unidas_layer.updateExtents()

        # Verificar se as linhas estão contínuas
        linhas = sorted(linhas_unidas_layer.getFeatures(), key=lambda f: f['id'])

        for i in range(len(linhas) - 1):
            geom_atual = linhas[i].geometry()
            geom_seguinte = linhas[i + 1].geometry()

            # Obter os extremos das linhas (direita ou esquerda alternando)
            extremos_atual = list(geom_atual.vertices())
            extremos_seguinte = list(geom_seguinte.vertices())

            ponto_final_atual = QgsPointXY(extremos_atual[-1].x(), extremos_atual[-1].y())  # Extremo final da linha atual
            ponto_inicial_seguinte = QgsPointXY(extremos_seguinte[0].x(), extremos_seguinte[0].y())  # Extremo inicial da próxima linha

            if ponto_final_atual != ponto_inicial_seguinte: # se for igual continua para a próxima linha
                extremos_seguinte = [QgsPointXY(p.x(), p.y()) for p in reversed(extremos_seguinte)] # Invertemos os vértices da linha seguinte
                geom_seguinte = QgsGeometry.fromPolylineXY(extremos_seguinte)

                # Atualizar imediatamente a geometria da linha na camada
                linhas_unidas_layer.dataProvider().changeGeometryValues({linhas[i + 1].id(): geom_seguinte})

                # Atualizar a linha seguinte na lista local para manter consistência no loop
                linhas[i + 1].setGeometry(geom_seguinte)

        # Atualizar a extensão da camada
        linhas_unidas_layer.updateExtents()
        
        if teste == True:
            QgsProject.instance().addMapLayer(linhas_unidas_layer)
        
        # ===============================================================================
        # =====Criar a camada Pontos de Fotos============================================

        # Criar uma camada Ponto com os deltaFront sobre a linha
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

        linhas = list(linhas_unidas_layer.getFeatures())
        tolerancia = 3  # Margem de 3 metros
        poligono_com_tolerancia = poligono_geom.buffer(tolerancia, 5)

        # Gerar pontos ao longo das linhas
        pontoID = 1
        for linha in linhas:
            geom_linha = linha.geometry()
            comprimento = geom_linha.length()
            distAtual = 0

            while distAtual <= comprimento:
                ponto = geom_linha.interpolate(distAtual).asPoint()
                ponto_geom = QgsGeometry.fromPointXY(QgsPointXY(ponto))

                # Verificar se o ponto está dentro do polígono
                if poligono_com_tolerancia.contains(ponto_geom):
                    ponto_feature = QgsFeature()
                    ponto_feature.setFields(campos)
                    ponto_feature.setAttribute("id", pontoID)
                    ponto_feature.setAttribute("linha", linha["id"])  # Campo 'id' da linha
                    ponto_feature.setAttribute("latitude", ponto.y())
                    ponto_feature.setAttribute("longitude", ponto.x())
                    ponto_feature.setGeometry(ponto_geom)
                    pontos_provider.addFeature(ponto_feature)
                    pontoID += 1

                distAtual += deltaFront
        # Atualizar a camada
        pontos_fotos.updateExtents()
        
        # Obter a altitude dos pontos a partir do MDE
        transformador = QgsCoordinateTransform(pontos_fotos.crs(), camadaMDE.crs(), QgsProject.instance())
        pontos_fotos.startEditing()

        for f in pontos_fotos.getFeatures():
            point = f.geometry().asPoint()

            # Transformar coordenada para o CRS do MDE
            point_transf = transformador.transform(QgsPointXY(point.x(), point.y()))
            
            # Obter o valor de Z do MDE
            value, result = camadaMDE.dataProvider().sample(point_transf, 1)  # Resolução = 1
            if result:
                f["altitude"] = value
                f["alturavoo"] = value + H
                pontos_fotos.updateFeature(f)

        pontos_fotos.commitChanges()

        # Point para PointZ
        pontos_fotos = set_Z_value(pontos_fotos, z_field="alturavoo")

        # Reprojetar camada Pontos Fotos de UTM para WGS84 (4326)
        pontos_reproj = reprojeta_camada_WGS84(pontos_fotos, crs_wgs, transformador)

        # Reprojetar a camada para WGS 84
        pontos_reproj = set_Z_value(pontos_reproj, z_field="alturavoo")

        # Simbologia
        simbologiaPontos(pontos_reproj)

        # ===== PONTOS FOTOS ==========================
        QgsProject.instance().addMapLayer(pontos_reproj)

        # ===== Final Pontos Fotos ============================================
        # =====================================================================
        
        
        # ===============================================================================
        # ===== Criar Linha de Voo ======================================================
        
        linha_voo_reproj = criarLinhaVoo("H", pontos_fotos, crs, crs_wgs, transformador, feedback)
        
        # ===== Final Linha de Voo ============================================ 
        # =====================================================================
        
        feedback.pushInfo("")
        feedback.pushInfo("Flight Line and Photo Spots completed successfully!")

        # =========Exportar para o Google  E a r t h   P r o  (kml)================================================

        # Verifica se o caminho é válido, não é 'TEMPORARY OUTPUT' e é um diretório
        if caminho_kml and caminho_kml != 'TEMPORARY OUTPUT' and os.path.isdir(caminho_kml):
            arquivo_kml = os.path.join(caminho_kml, "Pontos Fotos.kml")
            gerar_KML(pontos_reproj, arquivo_kml, crs_wgs, feedback)

            arquivo_kml = os.path.join(caminho_kml, "Linha de Voo.kml")
            gerar_KML(linha_voo_reproj, arquivo_kml, crs_wgs, feedback)
        else:
            feedback.pushInfo("KML path not specified. Export step skipped.")

        # =============L I T C H I==========================================================

        if arquivo_csv and arquivo_csv.endswith('.csv'): # Verificar se o caminho CSV está preenchido
            gerar_CSV("H", pontos_reproj, arquivo_csv, velocidade, tempo, deltaFront, 360, H)
        else:
            feedback.pushInfo("CSV path not specified. Export step skipped.")

        # ============= Remover Camadas Reproject ===================================================
        
        removeLayersReproj('_reproject') 
        
        # ============= Mensagem de Encerramento =====================================================
        feedback.pushInfo("")
        feedback.pushInfo("Horizontal Flight Plan successfully executed.")
        
        return {}

    def name(self):
        return 'FollowingTerrain'.lower()

    def displayName(self):
        return self.tr('Following terrain')

    def group(self):
        return 'Horizontal Flight'

    def groupId(self):
        return 'horizontal'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PlanoVoo_H()

    def tags(self):
        return self.tr('Flight Plan,Measure,Topography,Plano voo,Plano de voo,voo,drone').split(',')

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/Horizontal.png'))

    texto = """This tool enables drone flight planning for photogrammetry, following terrain elevations and calculating lateral and frontal overlaps.<br>
It generates <b>KML</b> files for 3D visualization in <b>Google Earth</b> and a <b>CSV</b> file compatible with the <b>Litchi app</b>.
<p>It can also be used with other flight applications by utilizing the KML files for flight lines and waypoints.</p>
<b>Requirements: </b>Plugins <b>LFTools</b>, <b>Open Topography</b>, and <b>KML Tools</b> installed in QGIS.</p>
<p><b>Tips:</b><o:p></o:p></p>
<ul style="margin-top: 0cm;" type="disc">
  <li><a href="https://geoone.com.br/opentopography-qgis/">Obtain the API Key for the Open Topography plugin</a><o:p></o:p></span></li>
  <li><a href="https://geoone.com.br/plano-de-voo-para-drone-com-python/#sensor">Check your drone sensor parameters</a><o:p></o:p></li>
</ul>
"""

    figura2 = 'images/Terrain_Follow.jpg'

    def shortHelpString(self):
        corpo = '''<div align="center">
                      <img src="'''+ os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figura2) +'''">
                      </div>
                      <div align="right">
                      <p align="right">
                      <b>Autores: Prof Cazaroli & Leandro França</b>
                      </p>
                      <a target="_blank" rel="noopener noreferrer" href="https://geoone.com.br/"><img title="GeoOne" src="data:image/png;base64,'''+ GeoOne +'''"></a>
					  <p><i>"Mapeamento automatizado, fácil e direto ao ponto é na GeoOne!"</i></p>
                      </div>
                    </div>'''
        return self.tr(self.texto) + corpo
