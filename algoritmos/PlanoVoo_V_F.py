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

from qgis.core import QgsProcessing, QgsProject, QgsProcessingAlgorithm, QgsProcessingParameterFolderDestination
from qgis.core import QgsProcessingParameterVectorLayer, QgsProcessingParameterNumber, QgsProcessingParameterString
from qgis.core import QgsTextFormat, QgsTextBufferSettings, QgsCoordinateReferenceSystem, QgsProcessingParameterFileDestination
from qgis.core import QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsCoordinateTransform
from qgis.core import QgsVectorLayer, QgsPoint, QgsPointXY, QgsField, QgsFields, QgsFeature, QgsGeometry
from qgis.core import QgsMarkerSymbol, QgsSingleSymbolRenderer, QgsSimpleLineSymbolLayer, QgsLineSymbol, QgsMarkerLineSymbolLayer
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor, QFont, QIcon
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from .Funcs import obter_DEM, gerar_KML, gerar_CSV, set_Z_value, reprojeta_camada_WGS84, simbologiaLinhaVoo, simbologiaPontos
import processing
import os
import math
import csv

# pontos_provider Air 2S (5472 × 3648)

class PlanoVoo_V_F(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        diretorio = QgsProject.instance().homePath()

        dirArq = os.path.join(diretorio, 'api_key.txt') # Caminho do arquivo 'ali_key.txt' no mesmo diretório do projeto

        if os.path.exists(dirArq): # Verificar se o arquivo existe
            with open(dirArq, 'r') as file:    # Ler o conteúdo do arquivo (a chave da API)
                api_key = file.read().strip()  # Remover espaços extras no início e fim
        else:
            api_key = ''
        
        self.addParameter(QgsProcessingParameterVectorLayer('linha_base','Linha Base de Voo', types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterVectorLayer('objeto','Posição do Objeto a ser medido', types=[QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterNumber('altura','Altura do Objeto (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=15))
        self.addParameter(QgsProcessingParameterNumber('alturaMin','Altura Inicial (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=2))
        self.addParameter(QgsProcessingParameterNumber('deltaHorizontal','Espaçamento Horizontal (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=5))
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
        
        # ===== Parâmetros de entrada para variáveis =========================================================
        linha_base = self.parameterAsVectorLayer(parameters, 'linha_base', context)
        crs = linha_base.crs()
        
        objeto = self.parameterAsVectorLayer(parameters, 'objeto', context)

        H = parameters['altura']
        h = parameters['alturaMin']
        deltaH = parameters['deltaHorizontal']
        deltaV = parameters['deltaVertical']
        velocidade = parameters['velocidade']
        
        apikey = parameters['api_key'] # 'd0fd2bf40aa8a6225e8cb6a4a1a5faf7' # Open Topgragraphy DEM Downloader
        
        caminho_kml = parameters['saida_kml']
        arquivo_csv = parameters['saida_csv']
        
        # ===== Verificações ===================================================================================
        linha = list(linha_base.getFeatures())
        if len(linha) != 1:
            raise ValueError("A camada Linha Base deve conter somente uma linha.")
        
        linha_base_geom = linha[0].geometry()  # Obter a geometria da linha base
        
        # Verificar se delatH é mútiplo do comprimento da Linha Base
        comprimento = round(linha_base_geom.length()) # como as vezes nao conseguimos um número inteiro na obtenção da Linha Base
        
        restante = comprimento % deltaH
           
        if restante > 0:
            raise ValueError(f"O espaçamento horizontal ({deltaH}) não é múltiplo do comprimento total da Linha Base ({comprimento}).")
        
        if objeto.featureCount() != 1: # uma outra forma de checar
            raise ValueError("A camada ponto Objeto deve conter somente um ponto.")
        
        # Determina as alturas das linhas de Voo
        alturas = [i for i in range(h, H + h + 1, deltaV)]
        
        # Determina as distâncias nas linhas de Voo
        distancias = [i for i in range(0, comprimento + 1, deltaH)]
        
        feedback.pushInfo(f"Altura: {H}, Delta Horizontal: {deltaH}, Delta Vertical: {deltaV}")
        
        # =====================================================================
        # ===== OpenTopography ================================================
       
        # Reprojetar para WGS 84 (EPSG:4326), usado pelo OpenTopography
        crs_wgs = QgsCoordinateReferenceSystem(4326)
        transformador = QgsCoordinateTransform(crs, crs_wgs, QgsProject.instance())
        
        camadaMDE = obter_DEM("VF", linha_base_geom, transformador, apikey, feedback)
        
        QgsProject.instance().addMapLayer(camadaMDE)
        
        #camadaMDE = QgsProject.instance().mapLayersByName("DEM")[0]
        
        # =============================================================================================
        # ===== Criar Linhas de Voo ===================================================================
        camadaLinhaVoo = QgsVectorLayer('LineStirng?crs=' + crs.authid(), 'Linha de Voo', 'memory')
        linhavoo_provider = camadaLinhaVoo.dataProvider()

        # Definir campos
        campos = QgsFields()
        campos.append(QgsField("id", QVariant.Int))
        campos.append(QgsField("alturavoo", QVariant.Double))
        linhavoo_provider.addAttributes(campos)
        camadaLinhaVoo.updateFields()
        
        linhaID = 1
        
        # Criar as linhas de voo com elevação
        for linha_idx, altura in enumerate(alturas, start=1):  # Cada altura representa uma "linha"
            verticesLinha = []

            # Alternar o sentido da linha
            if linha_idx % 2 == 0:  # "Linha de vem" (segunda, quarta, ...)
                distancias_atual = reversed(distancias)
            else:  # "Linha de vai" (primeira, terceira, ...)
                distancias_atual = distancias

            for d in distancias_atual:
                if d == comprimento:  # Ajuste para evitar problemas com interpolate
                    d -= 0.01

                # Interpolar o ponto ao longo da linha base
                ponto = linha_base_geom.interpolate(d).asPoint()
                ponto_geom = QgsGeometry.fromPointXY(QgsPointXY(ponto))
                
                # Transformar coordenada do ponto para CRS do raster
                ponto_wgs = transformador.transform(QgsPointXY(ponto.x(), ponto.y()))

                # Obter valor de Z do MDE
                value, result = camadaMDE.dataProvider().sample(QgsPointXY(ponto_wgs), 1)  # Resolução de amostragem
                if result:
                    a = value
                else:
                    feedback.pushWarning(f"Falha ao obter altitude para o ponto em distância {d}")
                    a = 0

                # Adicionar o ponto com elevação (x, y, z)
                verticesLinha.append(QgsPoint(ponto.x(), ponto.y(), altura + a))

            # Criar a linha com os vértices
            if len(verticesLinha) > 1:
                linhaFeature = QgsFeature()
                linhaFeature.setFields(campos)
                linhaFeature.setAttribute("id", linhaID)
                linhaFeature.setAttribute("alturavoo", altura)
                linhaFeature.setGeometry(QgsGeometry.fromPolyline(verticesLinha))
                linhavoo_provider.addFeature(linhaFeature)

                linhaID += 1

        # Atualizar a camada
        camadaLinhaVoo.updateExtents()
        camadaLinhaVoo.commitChanges()
        
        # LineString para LineStringZ
        camadaLinhaVoo = set_Z_value(camadaLinhaVoo, z_field="alturavoo")
        
        # Simbologia
        simbologiaLinhaVoo("VF", camadaLinhaVoo)

        # ===== LINHA DE VOO ============================
        QgsProject.instance().addMapLayer(camadaLinhaVoo)

        # Reprojetar linha_voo_layer para WGS84 (4326)
        linha_voo_reproj = reprojeta_camada_WGS84(camadaLinhaVoo, crs_wgs, transformador)
        
        # LineString para LineStringZ
        linha_voo_reproj = set_Z_value(linha_voo_reproj, z_field="altitude")
        
        if teste == True:
            QgsProject.instance().addMapLayer(linha_voo_reproj)
        
        # ===== Final Linha de Voo ============================================
        # =====================================================================
        

        # =============================================================================================
        # ===== Criar a camada Pontos de Fotos ========================================================
    
        # Criar uma camada Pontos com os deltaH sobre a linha Base e depois empilhar com os deltaH
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
        for linha_idx, altura in enumerate(alturas, start=1):  # Cada altura representa uma "linha"
            # Alternar o sentido
            if linha_idx % 2 == 0:  # "Linha de vem" (segunda, quarta, ...)
                distancias_atual = reversed(distancias)
            else:  # "Linha de vai" (primeira, terceira, ...)
                distancias_atual = distancias
            
            for d in distancias_atual:
                if d == comprimento:  # Ajuste para evitar problemas com interpolate
                    d -= 0.01

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
                ponto_feature.setAttribute("linha", linha_idx)  # Linha correspondente à altura
                ponto_feature.setAttribute("latitude", ponto.y())
                ponto_feature.setAttribute("longitude", ponto.x())
                ponto_feature.setAttribute("altitude", altura + a)
                ponto_feature.setAttribute("alturavoo", altura)
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
            gerar_KML(pontos_reproj, arquivo_kml, nome="Pontos Fotos", crs_wgs, feedback=feedback)
            
            arquivo_kml = caminho_kml + r"\Linha de Voo.kml"
            gerar_KML(linhas_reproj, arquivo_kml, nome="Linha de Voo", crs_wgs, feedback=feedback)
        else:
            feedback.pushInfo("Caminho KML não especificado. Etapa de exportação ignorada.")
        
        # =============L I T C H I==========================================================
        
        if arquivo_csv and arquivo_csv.endswith('.csv'): # Verificar se o caminho CSV está preenchido
            gerar_CSV("VF", pontos_reproj, arquivo_csv, velocidade, deltaH, angulo_perpendicular, H feedback=feedback)
        else:
            feedback.pushInfo("Caminho CSV não especificado. Etapa de exportação ignorada.")

        # Mensagem de Encerramento
        feedback.pushInfo("")
        feedback.pushInfo("Plano de Voo Vertical de Fachada executado com sucesso.") 
          
        return {}
        
    def name(self):
        return 'PlanoVooVF'.lower()

    def displayName(self):
        return self.tr('Fachada')

    def group(self):
        return 'Pontos Fotos - Voo Vertical'

    def groupId(self):
        return 'Pontos Fotos - Voo Vertical'
        
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PlanoVoo_V_F()
    
    def tags(self):
        return self.tr('Flight Plan,Measure,Topography').split(',')

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/PlanoVoo.png'))
    
    texto = "Este algoritmo calcula a 'Linha do Voo' e uma camada dos 'Pontos' para Fotos. \
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
  