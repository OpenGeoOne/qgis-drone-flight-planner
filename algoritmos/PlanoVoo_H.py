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

from qgis.core import QgsProcessing, QgsProject, QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer, QgsProcessingParameterNumber
from qgis.core import QgsTextFormat, QgsTextBufferSettings, QgsProcessingParameterFileDestination
from qgis.core import QgsPalLayerSettings, QgsVectorLayerSimpleLabeling
from qgis.core import QgsVectorLayer, QgsPoint, QgsPointXY, QgsField, QgsFields, QgsFeature, QgsGeometry
from qgis.core import QgsMarkerSymbol, QgsSingleSymbolRenderer, QgsSimpleLineSymbolLayer, QgsLineSymbol
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor, QFont, QIcon
from PyQt5.QtCore import QVariant
import processing
import os
import math

# Dados Air 2S (5472 × 3648)

class PlanoVoo_H(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('terreno', 'Terreno do Voo', types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterNumber('h','Altura de Voo',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=50,defaultValue=100))
        self.addParameter(QgsProcessingParameterNumber('dc','Tamanho do Sensor Horizontal (m)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0,defaultValue=13.2e-3)) # igual p/o Phantom 4 Pro (5472 × 3648)
        self.addParameter(QgsProcessingParameterNumber('dl','Tamanho do Sensor Vertical (m)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0,defaultValue=8.8e-3)) # igual p/o Phantom 4 Pro
        self.addParameter(QgsProcessingParameterNumber('f','Distância Focal (m)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0,defaultValue=8.38e-3)) # Phantom 4 Pro é f = 9e-3
        self.addParameter(QgsProcessingParameterNumber('percL','Percentual de sobreposição Lateral (75% = 0.75)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0.60,defaultValue=0.75))
        self.addParameter(QgsProcessingParameterNumber('percF','Percentual de sobreposição Frontal (85% = 0.85)',
                                                       type=QgsProcessingParameterNumber.Double,
                                                       minValue=0.60,defaultValue=0.85))
        self.addParameter(QgsProcessingParameterFileDestination('saida_csv', 'Arquivo de Saída CSV para o Litchi',
                                                               fileFilter='CSV files (*.csv)'))
        self.addParameter(QgsProcessingParameterFileDestination('saida_kml', 'Arquivo de Saída KML para o Google Earth',
                                                               fileFilter='KML files (*.kml)'))
        
    def processAlgorithm(self, parameters, context, model_feedback):
        # =====Parâmetros de entrada para variáveis========================
        camada = self.parameterAsVectorLayer(parameters, 'terreno', context)
        crs = camada.crs()

        H = parameters['h']
        dc = parameters['dc']
        dl = parameters['dl']
        f = parameters['f']
        percL = parameters['percL'] # Lateral
        percF = parameters['percF'] # Frontal
        caminho_csv = parameters['saida_csv']
        caminho_kml = parameters, ['saida_kml']
        
        # =====Cálculo das Sobreposições====================================
        # Distância das linhas de voo paralelas - Espaçamento Lateral
        tg_alfa_2 = dc / (2 * f)
        D_lat = dc * H / f
        SD_lat = percL * D_lat
        h1 = SD_lat / (2 * tg_alfa_2)
        deltaLat = SD_lat * (H / h1 - 1)

        if deltaLat > 0: # valor negativo para ser do Norte para o Sul
            deltaLat = deltaLat * (-1)

        # Espaçamento Frontal entre as fotografias- Espaçamento Frontal
        tg_alfa_2 = dl / (2 * f)
        D_front = dl * H / f
        SD_front = percF * D_front
        h1 = SD_front / (2 * tg_alfa_2)
        deltaFront = SD_front * (H / h1 - 1)
        
        #feedback.pushInfo(f"Delta Lateral: {deltaLat}, Delta Frontal: {deltaFront}")
        
        # =====================================================================
        # ===== Determinação das Linhas de Voo ================================
        f = next(camada.getFeatures())
        geom = f.geometry()
        
        vertices = list(geom.vertices())
        
        # maior distância entre vértices -> maior_distancia
        maior_distancia = 0

        for i in range(len(vertices)):
            for j in range(i + 1, len(vertices)):
                ponto_a = vertices[i]
                ponto_b = vertices[j]
                
                # Calcular a distância entre os dois vértices
                dist = ponto_a.distance(ponto_b)
                
                # Verificar se essa distância é a maior encontrada até agora
                if dist > maior_distancia:
                    maior_distancia = dist
        
        # maior lado do polígono -> maior_lado (distância), p1 e p2 (geom Pontos) e lado_mais_longo (geom Linha)
        p1 = p2 = None
        maior_lado = 0

        for i in range(len(vertices) - 1):
            ponto_a = vertices[i]
            ponto_b = vertices[i + 1]
            
            # Calcular a distância entre os dois pontos
            dist = ponto_a.distance(ponto_b)
            
            # Verificar se essa distância é a maior
            if dist > maior_lado:
                maior_lado = dist
                p1 = ponto_a
                p2 = ponto_b

        lado_mais_longo = QgsGeometry.fromPolylineXY([QgsPointXY(p1), QgsPointXY(p2)])
        
        # Agora, encontrar o vértice mais oposto -> dist_P (distância) e ponto_oposto (geom Ponto)
        ponto_oposto = None
        dist_P = 0 

        for i in range(len(vertices)):
            ponto_atual = vertices[i]
            
            # Calcular a distância entre o ponto atual e o maior lado do polígono
            dist = lado_mais_longo.distance(QgsGeometry.fromPointXY(QgsPointXY(ponto_atual)))
             
            # Verificar se é a maior distância
            if dist > dist_P:
                dist_P = dist
                ponto_oposto = ponto_atual
        
        # Criar a linha temporária sobre o lado mais longo do Polígono = Primeira Linha  
        lado_layer = QgsVectorLayer('LineString?crs=' + crs.authid(), 'Lado Mais Longo', 'memory')
        lado_provider = lado_layer.dataProvider()
        lado_provider.addAttributes([QgsField('id', QVariant.Int)])
        lado_layer.updateFields()

        lado_feature = QgsFeature()
        lado_feature.setGeometry(lado_mais_longo)
        lado_feature.setAttributes([1]) 
        lado_provider.addFeature(lado_feature)

        QgsProject.instance().addMapLayer(lado_layer)

        # Criar camada temporária para o ponto oposto
        ponto_layer = QgsVectorLayer('Point?crs=' + crs.authid(), 'Ponto Oposto', 'memory')
        ponto_provider = ponto_layer.dataProvider()
        ponto_provider.addAttributes([QgsField('id', QVariant.Int)])
        ponto_layer.updateFields()

        ponto_feature = QgsFeature()
        ponto_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(ponto_oposto)))
        ponto_feature.setAttributes([1])  # Atribuindo um valor qualquer, pode ser ajustado
        ponto_provider.addFeature(ponto_feature)

        QgsProject.instance().addMapLayer(ponto_layer)
  
        # Criar as Paralelas
        paralelas_layer = QgsVectorLayer('LineString?crs=' + crs.authid(), 'Linhas Paralelas', 'memory')
        paralelas_provider = paralelas_layer.dataProvider()
        paralelas_provider.addAttributes([QgsField('id', QVariant.Int)])
        paralelas_layer.updateFields()
        
        # Incluir o lado mais longo como a primeira linha paralela
        linha_id = 1
        paralela_feature = QgsFeature()
        paralela_feature.setGeometry(lado_mais_longo)
        paralela_feature.setAttributes([linha_id])
        paralelas_provider.addFeature(paralela_feature)

        # cálculo do ângulo da linha do lado mais longo do polígono  
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        angulo = math.atan2(dy, dx)
        
        # Ângulo perpendicular (90 graus ou π/2 radianos)
        angulo_perpendicular = angulo + math.pi / 2
        
        deslocamento = deltaLat

        extensao_x = maior_lado * math.cos(angulo)
        extensao_y = maior_lado * math.sin(angulo)
            
        while True:
            desloc_x = deslocamento * math.cos(angulo_perpendicular)
            desloc_y = deslocamento * math.sin(angulo_perpendicular)
            
            p1_deslocado = QgsPointXY(p1.x() + desloc_x, p1.y() + desloc_y)
            p2_deslocado = QgsPointXY(p2.x() + desloc_x, p2.y() + desloc_y)

            p1_estendido = QgsPointXY(p1_deslocado.x() - extensao_x ,p1_deslocado.y() - extensao_y)
            p2_estendido = QgsPointXY(p2_deslocado.x() + extensao_x ,p2_deslocado.y() + extensao_y)
            
            # Criar a linha paralela estendida e depois realizar a interseção
            linha_estendida = QgsGeometry.fromPolylineXY([p1_deslocado, p2_deslocado])
            #linha_estendida = QgsGeometry.fromPolylineXY([p1_estendido, p2_estendido])
            linha_paralela = linha_estendida.intersection(geom)
            
            paralela_feature = QgsFeature()
            paralela_feature.setGeometry(linha_paralela)
            paralela_feature.setAttributes([linha_id])
            paralelas_provider.addFeature(paralela_feature)

            deslocamento += deltaLat
            linha_id += 1
            
            if linha_id > 30:
                break

        QgsProject.instance().addMapLayer(paralelas_layer)

        return {}
        """
        pN = pontoN.y()
        pS = pontoS.y()
        pW = pontoW.x()
        pE = pontoE.x()

        print('N',pN)
        print('S',pS)
        print('W',pW)
        print('E',pE)

        dNS = abs(pN-pS) # cálculo das distâncias extremas Norte-Sul
        dWE = abs(pW-pE) # Oeste-Leste

        print('Norte-Sul',dNS)
        print('Oeste-Leste',dWE)

        # =====================================================================


        # =====Criar Linha do lado polígono mais ao Norte========================
        maxNorte = float('-inf')
        limiteMaisNorte = None

        f = next(camada.getFeatures()) # Obter a primeira feature (único polígono)

        geom = f.geometry() # Obter a geometria do polígono

        pols = geom.asPolygon() # obter o Lado do Terreno mais ao Norte
        for p in pols:
            for i in range(len(p) - 1):
                ponto1 = p[i]
                ponto2 = p[i + 1]
                pontoMedio = QgsPoint((ponto1.x() + ponto2.x()) / 2, (ponto1.y() + ponto2.y()) / 2)
                if pontoMedio.y() > maxNorte: # obter a maior Latitude
                    maxNorte = pontoMedio.y()
                    limiteMaisNorte = (ponto1, ponto2)

        p1, p2 = limiteMaisNorte
        x1, y1 = p1.x(),p1.y()
        x2, y2 = p2.x(),p2.y()

        print(x1, y1)
        print(x2, y2)
        
        p1 = QgsPointXY(x1, y1)
        p2 = QgsPointXY(x2, y2)

        dLinha = p1.distance(p2) # cálculo da medida da Linha
        print('Medida da Linha',dLinha)
        
        if dWE > dLinha: # redefinindo o tamanho da Linha criada
            extender = (dWE - dLinha) / 2

        camadaLinha = QgsVectorLayer(f"LineString?crs={crs}", "Lado Mais ao Norte", "memory")
        provider = camadaLinha.dataProvider()

        provider.addAttributes([QgsField("ID", QVariant.Int)]) 
        camadaLinha.updateFields() # Adicionar um campo de ID à nova camada

        linha = QgsFeature() # Criar uma nova feição com a aresta mais ao norte
        linha.setGeometry(QgsGeometry.fromPolylineXY([p1, p2]))
        linha.setAttributes([1])

        provider.addFeatures([linha]) # Adicionar a feição à camada
        camadaLinha.updateExtents()
        
        # =====Extender a Linha criada com os extremos W e E====================
        if dWE > dLinha: # redefinindo o tamanho da Linha criada
            estender = (dWE - dLinha) / 2 # metade no início e no fim

        alg_params = {
            'INPUT': camadaLinha,
            'START_DISTANCE':estender,
            'END_DISTANCE':estender,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }

        outputs['linhaExtendida'] = processing.run('native:extendlines', alg_params, context=context,
                                                       feedback=feedback, is_child_algorithm=True)

        # =====Linhas paralelas a partir da Linha criada=======================
        n = int(dNS / deltaLat) * -1 # número de Linhas e negativo N para S
        alg_params = {
            'INPUT': outputs['linhaExtendida']['OUTPUT'],
            'COUNT':n,
            'OFFSET':deltaLat,
            'SEGMENTS':8,
            'JOIN_STYLE':0,
            'MITER_LIMIT':2,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }

        outputs['linhas'] = processing.run('native:arrayoffsetlines', alg_params, context=context,
                                                       feedback=feedback, is_child_algorithm=True)
        
        # =====Unir as Linhas //s ============================================
        camadaLinhas = context.getMapLayer(outputs['linhas']['OUTPUT'])

        todasLinhas = [f for f in camadaLinhas.getFeatures()]

        paresPontos = []
        for i, f in enumerate(todasLinhas): # obtém os pares de Pontos de cada Linha
            geom = f.geometry()
            p = geom.asPolyline()
            
            p1, p2 = p[0], p[1]
            paresPontos.append([p1,p2])
            
        # print(paresPontos)

        pontosOrdenados = sorted(paresPontos, key=lambda sublist: sublist[0].y(), reverse=True)

        # for sublist in pontosOrdenados:
        #     print("\n".join([str(point) for point in sublist]))
        #     print()  # Adiciona uma linha em branco entre cada sublista

        pontos = [] # pontos para a uniao com as linhas //s
        i = 0

        for p in pontosOrdenados:
            if i%2 == 0:
                p = QgsPointXY(p[1].x(), p[1].y())
            else:
                p = QgsPointXY(p[0].x(), p[0].y())
            
            p1, p2 = p[0], p[1]
            
            i+=1    
            # print(p1,p2)
            
            pontos.append(p)

        # print(pontos)

        # Criar as novas linhas unindo cada par de pontos à linha correspondente
        camadaLinhas.startEditing()

        for i, p1 in enumerate(pontos):
            # print(i, p)

            try:
                p2 = pontosOrdenados[i+1][1] if i%2 == 0 else pontosOrdenados[i+1][0]
                # if i%2 == 0:
                #     p2 = pontosOrdenados[i+1][1]
                # else:
                #     p2 = pontosOrdenados[i+1][0]
                
                # print(p2)
            except IndexError:
                break

            novaLinha = QgsFeature() # criar uma linha com os pontos p1 e p2 
            novaLinha.setGeometry(QgsGeometry.fromPolylineXY([p1, p2]))
            camadaLinhas.dataProvider().addFeatures([novaLinha])
            
        camadaLinhas.updateExtents()
        camadaLinhas.commitChanges()
        
        # =====Transformar várias linhas em uma só==============================
        geomTotal = None

        # Iterar sobre as features da camada de entrada para unir todas as geometrias
        for f in camadaLinhas.getFeatures():
            geom = f.geometry()
            if geomTotal is None:
                geomTotal = geom
            else:
                geomTotal = geomTotal.combine(geom)

        # Criar a nova feature com a geometria unificada
        nova_feature = QgsFeature()
        nova_feature.setGeometry(geomTotal)

        # Criar a nova camada temporária
        camadaLinhaVoo = QgsVectorLayer("Linestring?crs=crs", "LinhaVoo", "memory")

        camadaLinhaVoo.dataProvider().addFeatures([nova_feature])

        # Criar o símbolo de linha
        simbolo = QgsSimpleLineSymbolLayer.create({'color': '#fd1b07', 'width': 1.45})
        s = QgsLineSymbol([simbolo])
        camadaLinhaVoo.renderer().setSymbol(s)

        camadaLinhaVoo.triggerRepaint()
        QgsProject.instance().addMapLayer(camadaLinhaVoo)

        # =====Criar uma camada Ponto com os deltaFront sobre a linha===========
        camadaPontos = QgsVectorLayer(f"Point?crs={crs}", "Pontos", "memory")
        dados = camadaPontos.dataProvider()

        # Definir campos
        campos = QgsFields()
        campos.append(QgsField("id", QVariant.Int))
        campos.append(QgsField("latitude", QVariant.Double))
        campos.append(QgsField("longitude", QVariant.Double))
        dados.addAttributes(campos)
        camadaPontos.updateFields()

        # Iterar sobre as linhas e criar pontos espaçados
        features = camadaLinhaVoo.getFeatures()
        pontoID = 0

        for f in features:
            geom = f.geometry()
            distVoo = geom.length()
            
            x = 0
            while x < distVoo:
                ponto = geom.interpolate(x).asPoint()
                
                nova_feature = QgsFeature()
                nova_feature.setFields(campos)
                nova_feature.setAttribute("id", pontoID)
                nova_feature.setAttribute("latitude", ponto.y())
                nova_feature.setAttribute("longitude", ponto.x())
                
                nova_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(ponto)))
                
                dados.addFeature(nova_feature)
                
                pontoID += 1
                x += deltaFront

        # Adicionar camada de pontos ao projeto
        QgsProject.instance().addMapLayer(camadaPontos)

        # Simbologia e Rótulo
        simbolo = QgsMarkerSymbol.createSimple({'color': 'blue', 'size': '3'})
        renderer = QgsSingleSymbolRenderer(simbolo)
        camadaPontos.setRenderer(renderer)

        settings = QgsPalLayerSettings()
        settings.fieldName = "id"
        settings.isExpression = True
        settings.enabled = True

        textoF = QgsTextFormat()
        textoF.setFont(QFont("Arial", 10, QFont.Bold))
        textoF.setSize(10)

        bufferS = QgsTextBufferSettings()
        bufferS.setEnabled(True)
        bufferS.setSize(1)  # Tamanho do buffer em milímetros
        bufferS.setColor(QColor("white"))  # Cor do buffer

        textoF.setBuffer(bufferS)
        settings.setFormat(textoF)

        camadaPontos.setLabelsEnabled(True)
        camadaPontos.setLabeling(QgsVectorLayerSimpleLabeling(settings))

        camadaPontos.triggerRepaint()
        QgsProject.instance().addMapLayer(camadaPontos)
        
        return
        """
    def name(self):
        return 'PlanoVooH'.lower()

    def displayName(self):
        return self.tr('Pontos Fotos - Voo Horizontal')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return ''
        
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PlanoVoo_H()
    
    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/PlanoVoo.png'))
    
    texto = "Este algoritmo calcula a sobreposição lateral e frontal de Voo de Drone, \
            fornecendo uma camada da 'Linha do Voo' e uma camada dos 'Pontos' para Fotos. \
            Gera ainda: a planilha CSV para importar no Litchi e o arquivo KML para Google Earth. \
            Se você usa um aplicativo para Voo que não seja o Litchi, pode usar os pontos gerados no QGIS."
    figura = 'images/PlanoVoo1.jpg'

    def shortHelpString(self):
        corpo = '''<div align="center">
                      <img src="'''+ os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figura) +'''">
                      </div>
                      <div align="right">
                      <p align="right">
                      <b>'Autor: Prof Cazaroli     -     Leandro França'</b>
                      </p>'Geoone'</div>
                    </div>'''
        return self.tr(self.texto) + corpo