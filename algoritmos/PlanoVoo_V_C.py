# -*- coding: utf-8 -*-

"""
/***************************************************************************
 Flight Planner - Vertical Flight Circular
                                 A QGIS plugin
 Flight Planner VC
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

from qgis.core import *
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from .Funcs import verificar_plugins, gerar_kml, gerar_CSV, set_Z_value, reprojeta_camada_WGS84, simbologiaLinhaVoo, simbologiaPontos, verificarCRS, duplicaPontoInicial, loadParametros, saveParametros, removeLayersReproj
from ..images.Imgs import *
import processing
import os
import math
import csv

class PlanoVoo_V_C(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        hObj, altMinVC, nPartesVC, dVertVC, velocVC, tStayVC, skml, sCSV = loadParametros("VC")

        self.addParameter(QgsProcessingParameterVectorLayer('circulo_base','Flight Base Circle', types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterVectorLayer('ponto_inicial','Start Point', types=[QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterNumber('altura','Object Height (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=hObj))
        self.addParameter(QgsProcessingParameterNumber('alturaMin','Start Height (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=0.5,defaultValue=altMinVC))
        self.addParameter(QgsProcessingParameterNumber('num_partes','Horizontal Division into PARTS of Base Circle',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=4,defaultValue=nPartesVC))
        self.addParameter(QgsProcessingParameterNumber('deltaVertical','Vertical Spacing (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=0.5,defaultValue=dVertVC))
        self.addParameter(QgsProcessingParameterNumber('velocidade','Flight Speed (m/s)',
                                                       type=QgsProcessingParameterNumber.Double, minValue=1,defaultValue=velocVC))
        self.addParameter(QgsProcessingParameterNumber('tempo','Time to Wait for Photo (seconds)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=0,defaultValue=tStayVC))
        self.addParameter(QgsProcessingParameterRasterLayer('raster','Input Raster (if any)', optional=True))
        self.addParameter(QgsProcessingParameterFolderDestination('saida_kml', 'Output Folder for kml (Google Earth)', defaultValue=skml))
        self.addParameter(QgsProcessingParameterFileDestination('saida_csv', 'Output CSV File (Litchi)', fileFilter='CSV files (*.csv)', defaultValue=sCSV))

    def processAlgorithm(self, parameters, context, feedback):
        teste = False # Quando True mostra camadas intermediárias

        # ===== Parâmetros de entrada para variáveis ==========================================
        circulo_base = self.parameterAsVectorLayer(parameters, 'circulo_base', context)

        ponto_inicial = self.parameterAsVectorLayer(parameters, 'ponto_inicial', context)

        camadaMDE = self.parameterAsRasterLayer(parameters, 'raster', context)

        H = parameters['altura']
        h = parameters['alturaMin']
        num_partes = parameters['num_partes'] # deltaH será calculado
        deltaV = parameters['deltaVertical']
        velocidade = parameters['velocidade']
        tempo = parameters['tempo']
        caminho_kml = self.parameterAsFile(parameters, 'saida_kml', context)
        arquivo_csv = self.parameterAsFile(parameters, 'saida_csv', context)

        # ===== Grava Parâmetros =====================================================
        saveParametros("VC", parameters['altura'], parameters['velocidade'], parameters['tempo'], parameters['saida_kml'], parameters['saida_csv'], None, None, None, None, None, None, parameters['deltaVertical'], None, None, parameters['alturaMin'], parameters['num_partes'])
        
        # ===== Verificações =================================================================

        # Verificar o SRC das Camadas
        crs = circulo_base.crs()
        crsP = ponto_inicial.crs() # não usamos o crsP, apenas para verificar a camada
        if crs != crsP:
            raise ValueError("❌ Both layers must be from the same CRS.")

        if "UTM" in crs.description().upper():
            feedback.pushInfo(f"The layer 'Flight Base Circle' is already in CRS UTM.")
        elif "WGS 84" in crs.description().upper() or "SIRGAS 2000" in crs.description().upper():
            crs = verificarCRS(circulo_base, feedback)
            nome = circulo_base.name() + "_reproject"
            circulo_base = QgsProject.instance().mapLayersByName(nome)[0]
        else:
            raise Exception(f"❌ Layer must be WGS84 or SIRGAS2000 or UTM. Other ({crs.description().upper()}) not supported")

        if "UTM" in crsP.description().upper():
            feedback.pushInfo(f"The layer 'Start Point' is already in CRS UTM.")
            ponto_inicial_move = self.parameterAsVectorLayer(parameters, 'ponto_inicial', context)
        elif "WGS 84" in crsP.description().upper() or "SIRGAS 2000" in crsP.description().upper():
            verificarCRS(ponto_inicial, feedback)
            nome = ponto_inicial.name() + "_reproject"
            ponto_inicial = QgsProject.instance().mapLayersByName(nome)[0]

            duplicaPontoInicial(ponto_inicial)
            nome = ponto_inicial.name() + "_move"
            ponto_inicial_move = QgsProject.instance().mapLayersByName(nome)[0]
        else:
            raise Exception(f"❌ Layer must be WGS84 or SIRGAS2000 or UTM. Other ({crs.description().upper()}) not supported")

        # Verificar se os plugins estão instalados
        plugins_verificar = ["lftools"]
        verificar_plugins(plugins_verificar, feedback)

        # Verificar as Geometrias
        if circulo_base.featureCount() != 1:
            raise ValueError("❌ Flight base Circle must contain only one circle.")

        if ponto_inicial.featureCount() != 1:
            raise ValueError("❌ Start Point must contain only on point.")

        # ===== Cálculos Iniciais ================================================

        # Determina as alturas das linhas de Voo
        c = next(circulo_base.getFeatures())
        circulo_base_geom = c.geometry()
        if circulo_base_geom.isMultipart():
            circulo_base_geom = circulo_base_geom.asGeometryCollection()[0]

        p = next(ponto_inicial.getFeatures())
        ponto_inicial_geom = p.geometry()
        if ponto_inicial_geom.isMultipart():
            ponto_inicial_geom = ponto_inicial_geom.asGeometryCollection()[0]

        # Cálculo do deltaH
        bounding_box = circulo_base_geom.boundingBox()
        centro = bounding_box.center()
        raio = bounding_box.width() / 2
        comprimento_circulo = circulo_base_geom.length()
        deltaH = comprimento_circulo / num_partes

        alturas = [i for i in range(h, H + h + 1, deltaV)]

        feedback.pushInfo(f"✅ Height: {H}, Horizontal Spacing: {round(deltaH,2)}, Vertical Spacing: {deltaV}")

        # =========================================================================
        # Reprojetar para WGS 84 (EPSG:4326), usado pelo OpenTopography
        crs_wgs = QgsCoordinateReferenceSystem(4326)
        transformador = QgsCoordinateTransform(crs, crs_wgs, QgsProject.instance())

        # =========================================================================
        # ===== Criar Polígono Inscrito ===========================================
        # Calcular vértices do polígono inscrito
        pontos = []
        for i in range(num_partes):
            angulo = math.radians(360 / num_partes * i)
            x = centro.x() + raio * math.cos(angulo)
            y = centro.y() + raio * math.sin(angulo)
            pontos.append(QgsPointXY(x, y))

        # Criar geometria do polígono
        polygon_geometry = QgsGeometry.fromPolygonXY([pontos])

        # ===============================================================================
        # ===== Criar a camada "Linha de Voo" ===========================================

        linhas_circulares_layer = QgsVectorLayer('Polygon?crs=' + crs.authid(), 'Flight Line', 'memory')
        linhas_circulares_provider = linhas_circulares_layer.dataProvider()

        # Definir campos
        campos = QgsFields()
        campos.append(QgsField("id", QVariant.Int))
        campos.append(QgsField("alturavoo", QVariant.Double))
        linhas_circulares_provider.addAttributes(campos)
        linhas_circulares_layer.updateFields()

        linhas_circulares_layer.startEditing

        # Adicionar polígonos com alturas diferentes
        linha_id = 1

        for altura in alturas:
            feature = QgsFeature()
            feature.setGeometry(polygon_geometry)  # Reutilizar a mesma geometria
            feature.setAttributes([linha_id, altura])  # Atribuir ID e alturavoo
            linhas_circulares_provider.addFeature(feature)

            linha_id += 1

        linhas_circulares_layer.commitChanges()
        
         # Reprojetar linha Voo para WGS84 (4326)
        linha_voo_reproj = reprojeta_camada_WGS84(linhas_circulares_layer, crs_wgs, transformador)

        # LineString paraLineStringZ
        linha_voo_reproj = set_Z_value(linha_voo_reproj, z_field="alturavoo")

        # Configurar simbologia
        simbologiaLinhaVoo('VC', linha_voo_reproj)

        # ===== LINHA VOO =================================
        QgsProject.instance().addMapLayer(linha_voo_reproj)
        
        feedback.pushInfo("")
        feedback.pushInfo("✅ Flight Line generated.")

        # ==========================================================================================
        # =====Criar a camada Pontos de Fotos=======================================================

        # Determinar o vértice mais próximo ao ponto inicial e depois deslocar
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
        
        # Criar uma camada Pontos com os deltaH sobre o Círculo Base e depois empilhar com os deltaH
        pontos_fotos = QgsVectorLayer('Point?crs=' + crs.authid(), 'Photo Points', 'memory')
        pontos_provider = pontos_fotos.dataProvider()

        # Definir campos
        campos = QgsFields()
        campos.append(QgsField("id", QVariant.Int))
        campos.append(QgsField("linha", QVariant.Int))
        campos.append(QgsField("latitude", QVariant.Double))
        campos.append(QgsField("longitude", QVariant.Double))
        campos.append(QgsField("altitude", QVariant.Double))
        campos.append(QgsField("alturavoo", QVariant.Double))
        campos.append(QgsField("angulo", QVariant.Double))
        pontos_provider.addAttributes(campos)
        pontos_fotos.updateFields()

        pontos_fotos.startEditing()
        
        pontoID = 1

        # Criar os vértices da primeira carreira de pontos
        features = linhas_circulares_layer.getFeatures()
        feature = next(features)  # Obter a primeira e única feature
        polygon_geometry = feature.geometry()
        vertices = list(polygon_geometry.vertices())

        # Remover o último vértice -  Um polígono fechado, o primeiro e o último vértice têm as mesmas coordenadas
        vertices = vertices[:-1]

        # Garantir que os vértices estejam no sentido horário
        if polygon_geometry.area() > 0:  # Se a área for positiva, os vértices estão no sentido anti-horário
            vertices.reverse()

        # Determinar o ponto inicial
        ponto_inicial_geom = ponto_inicial_move.getFeatures().__next__().geometry()
        ponto_inicial = ponto_inicial_geom.asPoint()

        # Verificar qual vértice o ponto inicial coincide
        idx_ponto_inicial = None
        for i, v in enumerate(vertices):
            if QgsPointXY(v).distance(ponto_inicial) < 1e-6:  # Tolera um pequeno erro de precisão
                idx_ponto_inicial = i
                break

        # Se o ponto inicial está na posição 0 não precisamos fazer nada; só verificar a ordem a seguir
        if idx_ponto_inicial != 0:
            vertices_reordenados = vertices[idx_ponto_inicial:] + vertices[:idx_ponto_inicial]
        else:
            vertices_reordenados = vertices  # Caso não encontre, mantém a lista original

        # Criar os pontos para as outras linhas de Voo
        for idx, altura in enumerate(alturas, start=1):  # Cada altura corresponde a uma linha de voo
            for v in vertices_reordenados:
                ponto_geom = QgsGeometry.fromPointXY(QgsPointXY(v.x(), v.y()))

                # Obter altitude do MDE
                param_kml = 'relativeToGround'
                if camadaMDE:
                    param_kml = 'absolute'
                    ponto_wgs = transformador.transform(QgsPointXY(v.x(), v.y()))
                    value, result = camadaMDE.dataProvider().sample(QgsPointXY(ponto_wgs), 1)  # Amostragem no raster
                    a = value if result else 0
                else:
                    a = 0

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
                ponto_feature.setAttribute("linha", idx)
                ponto_feature.setAttribute("latitude", v.y())
                ponto_feature.setAttribute("longitude", v.x())
                ponto_feature.setAttribute("altitude", a)
                ponto_feature.setAttribute("alturavoo", float(altura))
                ponto_feature.setAttribute("angulo", angulo)
                ponto_feature.setGeometry(ponto_geom)
                pontos_provider.addFeature(ponto_feature)

                pontoID += 1

        # Atualizar a camada
        pontos_fotos.commitChanges()
        pontos_fotos.updateExtents()

        # Reprojetar camada Pontos Fotos de UTM para WGS84 (4326)
        pontos_reproj = reprojeta_camada_WGS84(pontos_fotos, crs_wgs, transformador)

        # Point para PointZ
        pontos_reproj = set_Z_value(pontos_reproj, z_field="alturavoo")

        # Simbologia
        simbologiaPontos(pontos_reproj)
        
        # ===== PONTOS FOTOS ==========================
        QgsProject.instance().addMapLayer(pontos_reproj)

        feedback.pushInfo("")
        feedback.pushInfo("✅ Flight Line and Photo Spots completed.")
        
        # ========= Exportar para o Google  E a r t h   P r o  (kml) =======================

        feedback.pushInfo("")
        
        if caminho_kml and caminho_kml != 'TEMPORARY OUTPUT' and os.path.isdir(caminho_kml):
            arquivo_kml = os.path.join(caminho_kml, "Pontos Fotos.kml")
            gerar_kml(pontos_reproj, arquivo_kml, crs_wgs, param_kml, feedback)

            arquivo_kml = os.path.join(caminho_kml, "Linha de Voo.kml")
            gerar_kml(linha_voo_reproj, arquivo_kml, crs_wgs, param_kml, feedback)
        else:
            feedback.pushInfo("❌ kml path not specified. Export step skipped.")

        # ============= L I T C H I ================================================================

        feedback.pushInfo("")

        if arquivo_csv and arquivo_csv.endswith('.csv'): # Verificar se o caminho CSV está preenchido
            gerar_CSV("VC", pontos_reproj, arquivo_csv, velocidade, tempo, deltaH, 0, H, feedback)
        else:
            feedback.pushInfo("❌ CSV path not specified. Export step skipped.")

        # ============= Remover Camadas Reproject e Move =============================================
        
        removeLayersReproj('_reproject') 
        removeLayersReproj('_move')    
        
        # ============= Mensagem de Encerramento =====================================================
        feedback.pushInfo("")
        feedback.pushInfo("✅ Circular Vertical Flight Plan successfully executed.")
        feedback.pushInfo("")
        
        return {}

    def name(self):
        return 'PlanoVooVC'.lower()

    def displayName(self):
        return self.tr('Circular')

    def group(self):
        return 'Vertical Flight'

    def groupId(self):
        return 'vertical'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PlanoVoo_V_C()

    def tags(self):
        return self.tr('Flight Plan,Measure,Topography').split(',')

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images/Vertical.png'))

    texto = """This tool is designed to plan vertical and circular flights, ideal for 3D inspection and mapping projects around towers and similar objects.<br>
It enables the creation of an optimized flight path to capture detailed images of the object's surroundings.
<p><b>Required configurations:</b></p>
<ul>
  <li><b>Estimated object height:</b><span> Defines the highest point of the structure to be inspected.<o:p></o:p></span></li>
  <li class="MsoNormal" style=""><b><span>Vertical spacing:</span></b><span> Determines the distance between capture levels along the object's height.<o:p></o:p></span></li>
  <li class="MsoNormal" style=""><b><span>Number of photos per base circle (segments):</span></b><span> Specifies the number of photos to be captured at each circular level.<o:p></o:p></span></li>
</ul>
<p><span>The outputs are <b>kml</b> files for 3D visualization in <b>Google Earth</b> and a <b>CSV</b> file compatible with the <b>Litchi app</b>. It can also be used with other flight applications by utilizing the kml files for flight lines and waypoints.</span></p>
<p><b><span>Requirements:</span></b><span> Plugin <b>LFTools</b> installed in QGIS.</span></p>
<p><b>Tips:</b></p>
<ul>
  <li><a href="https://geoone.com.br/opentopography-qgis/">Obtain the MDE for the Open Topography plugin</a></li>
  <li><a href="https://geoone.com.br/plano-de-voo-para-drone-com-python/#sensor">Check your drone sensor parameters</a></li>
            """

    figura = 'images/Circular.jpg'

    def shortHelpString(self):
        corpo = '''<div align="center">
                      <img src="'''+ os.path.join(os.path.dirname(os.path.dirname(__file__)), self.figura) +'''">
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
