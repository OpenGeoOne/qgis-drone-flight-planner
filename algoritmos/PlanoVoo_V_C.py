# -*- coding: utf-8 -*-

"""
/***************************************************************************
 PlanoVoo
                                 A QGIS plugin
 PlanoVoo
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-12-09
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

from qgis.core import QgsProcessing, QgsProject, QgsProcessingAlgorithm, QgsCoordinateReferenceSystem
from qgis.core import QgsProcessingParameterFolderDestination, QgsProcessingParameterFileDestination
from qgis.core import QgsProcessingParameterVectorLayer, QgsProcessingParameterNumber, QgsProcessingParameterString
from qgis.core import QgsPalLayerSettings, QgsCoordinateTransform
from qgis.core import QgsVectorLayer, QgsPoint, QgsPointXY, QgsField, QgsFields, QgsFeature, QgsGeometry
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from .Funcs import obter_DEM, gerar_KML, gerar_CSV, set_Z_value, reprojeta_camada_WGS84, simbologiaLinhaVoo, simbologiaPontos
import processing
import os
import math
import csv

# pontos_provider Air 2S (5472 × 3648)

class PlanoVoo_V_C(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        diretorio = QgsProject.instance().homePath()

        dirArq = os.path.join(diretorio, 'api_key.txt') # Caminho do arquivo 'ali_key.txt' no mesmo diretório do projeto

        if os.path.exists(dirArq): # Verificar se o arquivo existe
            with open(dirArq, 'r') as file:    # Ler o conteúdo do arquivo (a chave da API)
                api_key = file.read().strip()  # Remover espaços extras no início e fim
        else:
            api_key = ''
        
        self.addParameter(QgsProcessingParameterVectorLayer('circulo_base','Círculo Base de Voo', types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterVectorLayer('ponto_inicial','Posição do Início do Voo', types=[QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterNumber('altura','Altura do Objeto (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=15))
        self.addParameter(QgsProcessingParameterNumber('alturaMin','Altura Inicial (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=2))
        self.addParameter(QgsProcessingParameterNumber('num_partes','Espaçamento Horizontal em PARTES do Círculo Base',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=4,defaultValue=8))
        self.addParameter(QgsProcessingParameterNumber('deltaVertical','Espaçamento Vertical (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=3))
        self.addParameter(QgsProcessingParameterNumber('velocidade','Velocidade do Voo (m/s)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=3))
        self.addParameter(QgsProcessingParameterString('api_key', 'Chave API - OpenTopography',defaultValue=api_key))
        self.addParameter(QgsProcessingParameterFolderDestination('saida_kml', 'Pasta de Saída para o KML (Google Earth)'))
        self.addParameter(QgsProcessingParameterFileDestination('saida_csv', 'Arquivo de Saída CSV (Litchi)',
                                                               fileFilter='CSV files (*.csv)'))
        
    def processAlgorithm(self, parameters, context, feedback):
        teste = False # Quando True mostra camadas intermediárias
        
        # ===== Parâmetros de entrada para variávei s==========================================
        circulo_base = self.parameterAsVectorLayer(parameters, 'circulo_base', context)
        crs = circulo_base.crs()
        
        ponto_inicial = self.parameterAsVectorLayer(parameters, 'ponto_inicial', context)
        ponto_inicial_move = self.parameterAsVectorLayer(parameters, 'ponto_inicial', context) # ponto inicial precisa ser movido para um vértice da Linha de Voo
        
        H = parameters['altura']
        h = parameters['alturaMin']
        num_partes = parameters['num_partes'] # deltaH será calculado
        deltaV = parameters['deltaVertical']
        velocidade = parameters['velocidade']
        
        apikey = parameters['api_key'] # 'd0fd2bf40aa8a6225e8cb6a4a1a5faf7' # Open Topgragraphy DEM Downloader
        
        caminho_kml = parameters['saida_kml']
        arquivo_csv = parameters['saida_csv']
        
        # ===== Verificações =================================================================
        circulo = list(circulo_base.getFeatures())
        if len(circulo) != 1:
            raise ValueError("A camada Cículo Base deve conter somente um círculo.")
        
        if ponto_inicial.featureCount() != 1: # uma outra forma de checar
            raise ValueError("A camada ponto Inicial deve conter somente um ponto.")

        # ===== Cálculos Iniciais ================================================
        circulo_base_geom = circulo[0].geometry()
        
        ponto = list(ponto_inicial.getFeatures())
        ponto_inicial_geom = ponto[0].geometry()

        # Cálculo do deltaH
        bounding_box = circulo_base_geom.boundingBox()
        centro = bounding_box.center()
        raio = bounding_box.width() / 2
        comprimento_circulo = circulo_base_geom.length()
        deltaH = comprimento_circulo / num_partes
        
        # Determina as alturas das linhas de Voo
        alturas = [i for i in range(h, H + h + 1, deltaV)]

        feedback.pushInfo(f"Altura: {H}, Delta Horizontal: {round(deltaH,2)}, Delta Vertical: {deltaV}")
        
        # =====================================================================
        # ===== OpenTopography ================================================
       
        # Reprojetar para WGS 84 (EPSG:4326), usado pelo OpenTopography
        crs_wgs = QgsCoordinateReferenceSystem(4326)
        transformador = QgsCoordinateTransform(crs, crs_wgs, QgsProject.instance())
        
        #camadaMDE = obter_DEM(circulo_base_geom, transformador, apikey, feedback)
        
        #QgsProject.instance().addMapLayer(camadaMDE)
        
        camadaMDE = QgsProject.instance().mapLayersByName("DEM")[0]
        
        # ====================================================================
        # ===== Criar Polígono Circunscrito ==================================
        
        # Calcular vértices do polígono inscrito
        pontos = []
        for i in range(num_partes):
            angulo = math.radians(360 / num_partes * i)
            x = centro.x() + raio * math.cos(angulo)
            y = centro.y() + raio * math.sin(angulo)
            pontos.append(QgsPointXY(x, y))
        
        # Criar geometria do polígono
        polygon_geometry = QgsGeometry.fromPolygonXY([pontos])
        
        # Criar uma camada Pontos com os deltaH sobre o Círculo Base e depois empilhar com os deltaH
        camada_linha_voo = QgsVectorLayer('Polygon?crs=' + crs.authid(), 'Linha de Voo', 'memory')
        linha_voo_provider = camada_linha_voo.dataProvider()

        # Definir campos
        campos = QgsFields()
        campos.append(QgsField("id", QVariant.Int))
        campos.append(QgsField("alturavoo", QVariant.Double))
        linha_voo_provider.addAttributes(campos)
        camada_linha_voo.updateFields()

        camada_linha_voo.startEditing
        
        # Adicionar polígonos com alturas diferentes
        linha_id = 1
        
        for altura in alturas:
            feature = QgsFeature()
            feature.setGeometry(polygon_geometry)  # Reutilizar a mesma geometria
            feature.setAttributes([linha_id, altura])  # Atribuir ID e altura
            linha_voo_provider.addFeature(feature)
            
            linha_id += 1

        # Atualizar a camada
        camada_linha_voo.updateExtents()
        camada_linha_voo.commitChanges
        
        # Simbologia
        simbologiaLinhaVoo("VC", camada_linha_voo)

        # ===== LINHA DE VOO ==============================
        QgsProject.instance().addMapLayer(camada_linha_voo)
        
        # Reprojetar linha_voo_layer para WGS84 (4326)
        linhas_voo_reproj = reprojeta_camada_WGS84(camada_linha_voo, crs_wgs, transformador)
        
        # LineString para LineStringZ
        linhas_voo_reproj = set_Z_value(linhas_voo_reproj, z_field="altitude")
        
        if teste == True:
            QgsProject.instance().addMapLayer(linhas_voo_reproj)
        
        # ===== Final Linha de Voo ============================================
        # =====================================================================
        
        
        # ==========================================================================================================
        # ===== Determinar o vértice mais próximo ao ponto inicial e depois deslocar ===============================
        ponto_inicial_xy = ponto_inicial_geom.asPoint()
        menor_distancia = float('inf')
        vertice_mais_proximo = None

        for vertice in pontos:
            distancia = math.sqrt((vertice.x() - ponto_inicial_xy.x())**2 + (vertice.y() - ponto_inicial_xy.y())**2)
            if distancia < menor_distancia:
                menor_distancia = distancia
                vertice_mais_proximo = vertice

        # Atualizar o ponto inicial para o vértice mais próximo
        novo_ponto_inicial_geom = QgsGeometry.fromPointXY(vertice_mais_proximo)

        camada_ponto_inicial_provider = ponto_inicial_move.dataProvider()

        ponto_inicial_move.startEditing()

        # Atualizar a geometria do ponto inicial para o vértice mais próximo
        for feature in ponto_inicial_move.getFeatures():
            if feature.geometry().asPoint() == ponto_inicial_xy:
                # Atualizar a geometria do ponto inicial
                feature.setGeometry(novo_ponto_inicial_geom)
                ponto_inicial_move.updateFeature(feature)  # Salvar a atualização
                break  # Atualizar apenas o primeiro ponto encontrado (ou o correto)

        ponto_inicial_move.commitChanges()
        ponto_inicial_move.triggerRepaint()
        
        # ==========================================================================================
        # =====Criar a camada Pontos de Fotos=======================================================
        
        # Criar uma camada Pontos com os deltaH sobre o Círculo Base e depois empilhar com os deltaH
        pontos_fotos = QgsVectorLayer('Point?crs=' + crs.authid(), 'Pontos Fotos', 'memory')
        pontos_provider = pontos_fotos.dataProvider()

        # Definir campos
        campos = QgsFields()
        campos.append(QgsField("id", QVariant.Int))
        campos.append(QgsField("latitude", QVariant.Double))
        campos.append(QgsField("longitude", QVariant.Double))
        campos.append(QgsField("altitude", QVariant.Double))
        campos.append(QgsField("alturavoo", QVariant.Double))
        campos.append(QgsField("angulo", QVariant.Double))
        pontos_provider.addAttributes(campos)
        pontos_fotos.updateFields()
        
        pontoID = 1
        
        # Criar os vértices da primeira carreira de pontos
        features = camada_linha_voo.getFeatures()
        feature = next(features)  # Obter a primeira e única feature
        polygon_geometry = feature.geometry()
        vertices = list(polygon_geometry.vertices()) 
        
        # Remover o último vértice -  Um polígono fechado, o primeiro e o último vértice têm as mesmas coordenadas
        vertices = vertices[:-1]
        
        # feedback.pushInfo(f"Ponto Incial {i}: {ponto_inicial}     Area {polygon_geometry.area()}")
        # feedback.pushInfo(f"Vértices: {vertices}")
        
        # Garantir que os vértices estejam no sentido horário
        if polygon_geometry.area() > 0:  # Se a área for positiva, os vértices estão no sentido anti-horário
            vertices.reverse()

        # feedback.pushInfo(f"Vértices: {vertices}")
        
        # Determinar o ponto inicial
        ponto_inicial_geom = ponto_inicial_move.getFeatures().__next__().geometry()
        ponto_inicial = ponto_inicial_geom.asPoint()
   
        # Verificar qual vértice o ponto inicial coincide
        idx_ponto_inicial = None
        for i, v in enumerate(vertices):
            if QgsPointXY(v).distance(ponto_inicial) < 1e-6:  # Tolera um pequeno erro de precisão
                idx_ponto_inicial = i
                break
    
        # feedback.pushInfo(f"IDX: {idx_ponto_inicial}")
        
        # Se o ponto inicial está na posição 0 não precisamos fazer nada; só verificar a ordem a seguir
        if idx_ponto_inicial != 0:
            vertices_reordenados = vertices[idx_ponto_inicial:] + vertices[:idx_ponto_inicial]
        else:
            vertices_reordenados = vertices  # Caso não encontre, mantém a lista original    
        
        # for v in vertices_reordenados:
        #     feedback.pushInfo(f"Vértice {v}")
            
        # Criar os pontos para as outras linhas de Voo
        for idx, altura in enumerate(alturas, start=1):  # Cada altura corresponde a uma linha de voo
            for v in vertices_reordenados:
                ponto_geom = QgsGeometry.fromPointXY(QgsPointXY(v.x(), v.y()))

                # Obter altitude do MDE
                ponto_wgs = transformador.transform(QgsPointXY(v.x(), v.y()))
                value, result = camadaMDE.dataProvider().sample(QgsPointXY(ponto_wgs), 1)  # Amostragem no raster
                altitude = value if result else 0

                # Calcular o ângulo do ponto
                centroide = circulo_base_geom.centroid().asPoint()  # Obter o centro geométrico do objeto
                dx = v.x() - centroide.x()
                dy = v.y() - centroide.y()
                angulo_rad = math.atan2(dx, dy)          # Ângulo em radianos
                angulo_graus = math.degrees(angulo_rad)  # Converter para graus
                angulo = (angulo_graus + 180) % 360      # Inverter o ângulo para que seja para o centro
                
                ponto_feature = QgsFeature()
                ponto_feature.setFields(campos)
                ponto_feature.setAttribute("id", pontoID)
                ponto_feature.setAttribute("latitude", v.y())
                ponto_feature.setAttribute("longitude", v.x())
                ponto_feature.setAttribute("altitude", altura + altitude)
                ponto_feature.setAttribute("alturavoo", altura)
                ponto_feature.setAttribute("angulo", angulo)
                ponto_feature.setGeometry(ponto_geom)
                pontos_provider.addFeature(ponto_feature)
                
                pontoID += 1

        # Atualizar a camada
        pontos_fotos.updateExtents()
        pontos_fotos.commitChanges()
        
        # Point para PointZ
        pontos_fotos = set_Z_value(pontos_fotos, z_field="altitude")
        
        # Simbologia
        simbologiaPontos(pontos_fotos)
        
        # ===== PONTOS FOTOS ==========================
        QgsProject.instance().addMapLayer(pontos_fotos)

        #pontos_fotos = QgsProject.instance().mapLayersByName("Pontos Fotos")[0]
        
        # Reprojetar camada Pontos Fotos de UTM para WGS84 (4326)
        pontos_reproj = reprojeta_camada_WGS84(pontos_fotos, crs_wgs, transformador)
        
        # Point para PointZ
        pontos_reproj = set_Z_value(pontos_reproj, z_field="altitude")
        
        if teste == True:
            QgsProject.instance().addMapLayer(pontos_reproj)
            
        feedback.pushInfo("")
        feedback.pushInfo("Linha de Voo e Pontos para Fotos concluídos com sucesso!")
        
        # ===== Final Pontos Fotos ============================================
        # =====================================================================
        
        # =========Exportar para o Google  E a r t h   P r o  (kml)================================================
        
        if caminho_kml: # Verificar se o caminho KML está preenchido 
            arquivo_kml = caminho_kml + r"\Pontos Fotos.kml"
            gerar_KML(pontos_reproj, arquivo_kml, "Pontos Fotos", crs_wgs, feedback)
            
            arquivo_kml = caminho_kml + r"\Linha de Voo.kml"
            gerar_KML(linhas_voo_reproj, arquivo_kml, "Linha de Voo", crs_wgs, feedback)
        else:
            feedback.pushInfo("Caminho KML não especificado. Etapa de exportação ignorada.")
       
        # =============L I T C H I==========================================================
        
        if arquivo_csv and arquivo_csv.endswith('.csv'): # Verificar se o caminho CSV está preenchido
            gerar_CSV("VC", pontos_reproj, arquivo_csv, velocidade, deltaH, 0, H)
        else:
            feedback.pushInfo("Caminho CSV não especificado. Etapa de exportação ignorada.")

        # ============= Mensagem de Encerramento =====================================================
        feedback.pushInfo("")
        feedback.pushInfo("Plano de Voo Vertical Circular executado com sucesso.") 
        
        return {}
        
    def name(self):
        return 'PlanoVooVC'.lower()

    def displayName(self):
        return self.tr('Circular')

    def group(self):
        return 'Pontos Fotos - Voo Vertical'

    def groupId(self):
        return 'Pontos Fotos - Voo Vertical'
        
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PlanoVoo_V_C()
    
    def tags(self):
        return self.tr('Flight Plan,Measure,Topography').split(',')

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/PlanoVoo.png'))
    
    texto = "Este algoritmo calcula um 'Voo Circular' e uma camada dos 'Pontos' para Fotos. \
            Gera ainda: a planilha CSV para importar no Litchi e o arquivo KML para Google Earth. \
            Se você usa um aplicativo para Voo que não seja o Litchi, pode usar os pontos gerados no QGIS."
    figura = 'images/PlanoVoo2.jpg'

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
  