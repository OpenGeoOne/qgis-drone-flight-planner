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

from qgis.core import QgsProcessing, QgsProject, QgsProcessingAlgorithm, QgsWkbTypes, QgsVectorFileWriter
from qgis.core import QgsProcessingParameterVectorLayer, QgsProcessingParameterNumber, QgsProcessingParameterString
from qgis.core import QgsTextFormat, QgsTextBufferSettings, QgsProcessingParameterFileDestination, QgsCoordinateReferenceSystem
from qgis.core import QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsProcessingParameterBoolean, QgsCoordinateTransform
from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsPoint, QgsPointXY, QgsField, QgsFields, QgsFeature, QgsGeometry
from qgis.core import QgsMarkerSymbol, QgsSingleSymbolRenderer, QgsSimpleLineSymbolLayer, QgsLineSymbol, QgsMarkerLineSymbolLayer, QgsFillSymbol
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor, QFont, QIcon
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction, QMessageBox
import processing
import os
import math
import csv

# pontos_provider Air 2S (5472 × 3648)

class PlanoVoo_V_C(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('circulo_base','Círculo Base de Voo', types=[QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterVectorLayer('ponto_inicial','Posição do Início do Voo', types=[QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterNumber('altura','Altura do Objeto (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=15))
        self.addParameter(QgsProcessingParameterNumber('alturaMin','Altura Inicial (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=2))
        self.addParameter(QgsProcessingParameterNumber('num_partes','Espaçamento Horizontal (em partes do Círculo Base)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=4,defaultValue=8))
        self.addParameter(QgsProcessingParameterNumber('deltaVertical','Espaçamento Vertical (m)',
                                                       type=QgsProcessingParameterNumber.Integer, minValue=2,defaultValue=3)) 
        self.addParameter(QgsProcessingParameterString('api_key', 'Chave API - OpenTopography',defaultValue='d0fd2bf40aa8a6225e8cb6a4a1a5faf7'))
        self.addParameter(QgsProcessingParameterFileDestination('saida_csv', 'Arquivo de Saída CSV para o Litchi',
                                                               fileFilter='CSV files (*.csv)'))
        self.addParameter(QgsProcessingParameterFileDestination('saida_kml', 'Arquivo de Saída KML para o Google Earth',
                                                               fileFilter='KML files (*.kml)'))
        
    def processAlgorithm(self, parameters, context, feedback):
        teste = False # Quando True mostra camadas intermediárias
        
        # =====Parâmetros de entrada para variáveis========================
        circulo_base = self.parameterAsVectorLayer(parameters, 'circulo_base', context)
        crs = circulo_base.crs()
        
        ponto_inicial = self.parameterAsVectorLayer(parameters, 'ponto_inicial', context)

        H = parameters['altura']
        h = parameters['alturaMin']
        num_partes = parameters['num_partes'] # deltaH será calculado
        deltaV = parameters['deltaVertical']
        
        apikey = parameters['api_key'] # 'd0fd2bf40aa8a6225e8cb6a4a1a5faf7' # Open Topgragraphy DEM Downloader
        
        caminho_kml = parameters['saida_kml']
        caminho_csv = parameters['saida_csv']
        
        # Verificações
        circulo = list(circulo_base.getFeatures())
        if len(circulo) != 1:
            raise ValueError("A camada Cículo Base deve conter somente um círculo.")
        
        if ponto_inicial.featureCount() != 1: # uma outra forma de checar
            raise ValueError("A camada ponto Inicial deve conter somente um ponto.")

        # Cálculos Iniciais
        circulo_base_geom = circulo[0].geometry()
        
        ponto = list(ponto_inicial.getFeatures())
        ponto_inicial_geom = ponto[0].geometry()

        # Cálculo do deltaH
        bounding_box = circulo_base_geom.boundingBox()
        centro = bounding_box.center()
        raio = bounding_box.width() / 2
        comprimento_circulo = circulo_base_geom.length()
        deltaH = comprimento_circulo / num_partes
        
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
        linha_voo_provider.addAttributes(campos)
        camada_linha_voo.updateFields()

        camada_linha_voo.startEditing
        
        # Adicionar o novo polígono à camada
        feature = QgsFeature()
        feature.setGeometry(polygon_geometry)
        feature.setAttributes([1])  # Atribuindo um valor de ID
        linha_voo_provider.addFeature(feature)

        # Atualizar a camada
        camada_linha_voo.updateExtents()
        camada_linha_voo.commitChanges
        
        # Simbologia
        simbologia = QgsFillSymbol.createSimple({
            'color': 'transparent',  # Sem preenchimento
            'outline_color': 'green',  # Contorno verde
            'outline_width': '0.8'  # Largura do contorno
        })

        camada_linha_voo.setRenderer(QgsSingleSymbolRenderer(simbologia))  
        
        QgsProject.instance().addMapLayer(camada_linha_voo)
        
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
        
        camada_ponto_inicial = QgsProject.instance().mapLayersByName('Ponto_Inicial_V')[0]
        camada_ponto_inicial_provider = camada_ponto_inicial.dataProvider()

        camada_ponto_inicial.startEditing()

        # Atualizar a geometria do ponto inicial para o vértice mais próximo
        for feature in camada_ponto_inicial.getFeatures():
            if feature.geometry().asPoint() == ponto_inicial_xy:
                # Atualizar a geometria do ponto inicial
                feature.setGeometry(novo_ponto_inicial_geom)
                camada_ponto_inicial.updateFeature(feature)  # Salvar a atualização
                break  # Atualizar apenas o primeiro ponto encontrado (ou o correto)

        camada_ponto_inicial.commitChanges()
        camada_ponto_inicial.triggerRepaint()
        
        # Determina as alturas das linhas de Voo
        alturas = [i for i in range(h, H + h + 1, deltaV)]

        feedback.pushInfo(f"Altura: {H}, Delta Horizontal: {deltaH}, Delta Vertical: {deltaV}")
        
        # =====================================================================
        # Obter o MDE com OpenTopography para depois determinar as altitudes dos Pontos de Foto
        feedback.pushInfo("Obtendo as Altitudes com o OpenTopography")
       
        # Reprojetar para WGS 84 (EPSG:4326), usado pelo OpenTopography
        crs_wgs = QgsCoordinateReferenceSystem(4326)
        transformador = QgsCoordinateTransform(crs, crs_wgs, QgsProject.instance())
        """
        # Determinar o bounding box da linha em WGS 84
        bounds = circulo_base_geom.boundingBox()
        ponto_min = transformador.transform(QgsPointXY(bounds.xMinimum(), bounds.yMinimum()))
        ponto_max = transformador.transform(QgsPointXY(bounds.xMaximum(), bounds.yMaximum()))

        pontoN = ponto_max.y()
        pontoS = ponto_min.y()
        pontoW = ponto_min.x()
        pontoE = ponto_max.x()

        # Certificar que a área do bounding box seja grande o suficiente
        bbox_area_min = 2.5  # Área mínima em km²
        bbox_area = (pontoE - pontoW) * (pontoN - pontoS) * 111 * 111  # Aproximação em km²
        if bbox_area < bbox_area_min:
            aumento = ((bbox_area_min / bbox_area)**0.5 - 1) / 2
            ajuste_lat_extra = aumento * (pontoN - pontoS)
            ajuste_long_extra = aumento * (pontoE - pontoW)
            pontoN += ajuste_lat_extra
            pontoS -= ajuste_lat_extra
            pontoW -= ajuste_long_extra
            pontoE += ajuste_long_extra

        # Obter o DEM da área
        coordenadas = f'{pontoW},{pontoE},{pontoS},{pontoN}'
        area = f"{coordenadas}[EPSG:4326]"

        result = processing.run(
            "OTDEMDownloader:OpenTopography DEM Downloader", {
                'DEMs': 7,  # Copernicus Global DSM 30m
                'Extent': area,
                'API_key': apikey,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })

        output_path = result['OUTPUT']
        camadaMDE = QgsRasterLayer(output_path, "DEM")

        QgsProject.instance().addMapLayer(camadaMDE)
        """
        camadaMDE = QgsProject.instance().mapLayersByName("DEM")[0]
        
        # =====================================================================
        # =====Criar a camada Pontos de Fotos==================================
        # Criar uma camada Pontos com os deltaH sobre o Círculo Base e depois empilhar com os deltaH
        pontos_fotos = QgsVectorLayer('Point?crs=' + crs.authid(), 'Pontos Fotos', 'memory')
        pontos_provider = pontos_fotos.dataProvider()

        # Definir campos
        campos = QgsFields()
        campos.append(QgsField("id", QVariant.Int))
        campos.append(QgsField("circulo", QVariant.Int))
        campos.append(QgsField("latitude", QVariant.Double))
        campos.append(QgsField("longitude", QVariant.Double))
        campos.append(QgsField("altitude", QVariant.Double))
        campos.append(QgsField("alturavoo", QVariant.Double))
        pontos_provider.addAttributes(campos)
        pontos_fotos.updateFields()
        
        pontoID = 1
        
        # Criar as carreiras de pontos
        features = camada_linha_voo.getFeatures() # Obter a geometria do polígono (camada_linha_voo) e seus vértices
        feature = next(features)  # Obter a primeira e única feature
        polygon_geometry = feature.geometry()
        vertices = list(polygon_geometry.vertices())
        
        # Determinar o ponto inicial
        ponto_inicial_geom = camada_ponto_inicial.getFeatures().__next__().geometry()
        ponto_inicial_xy = ponto_inicial_geom.asPoint()
        
        # Localizar o índice do ponto inicial nos vértices
        idx_ponto_inicial = min(
            range(len(vertices)),
            key=lambda i: QgsPointXY(vertices[i]).distance(ponto_inicial_xy)
        )

        # Reorganizar os vértices para começar no ponto inicial
        vertices_reorganizados = vertices[idx_ponto_inicial:] + vertices[:idx_ponto_inicial]

        # Garantir o sentido horário
        if not is_clockwise(vertices_reorganizados):
            vertices_reorganizados.reverse()

        for idx, altura in enumerate(alturas, start=1):  # Cada altura corresponde a uma linha de voo
            # Alternar o sentido (horário/anti-horário) com base no índice da linha
            if idx % 2 == 0:
                vertices_atual = list(reversed(vertices_reorganizados))  # Sentido anti-horário
            else:
                vertices_atual = vertices_reorganizados  # Sentido horário

            # Criar os pontos para a linha de voo
            for vertice in vertices_atual:
                # Criar a geometria do ponto
                ponto_geom = QgsGeometry.fromPointXY(QgsPointXY(vertice.x(), vertice.y()))

                # Obter altitude do MDE
                ponto_wgs = transformador.transform(QgsPointXY(vertice.x(), vertice.y()))
                value, result = camadaMDE.dataProvider().sample(QgsPointXY(ponto_wgs), 1)  # Amostragem no raster
                altitude = value if result else 0

                # Criar o recurso do ponto
                ponto_feature = QgsFeature()
                ponto_feature.setFields(campos)
                ponto_feature.setAttribute("id", pontoID)
                ponto_feature.setAttribute("linha_voo", idx)  # Linha de voo correspondente
                ponto_feature.setAttribute("latitude", vertice.y())
                ponto_feature.setAttribute("longitude", vertice.x())
                ponto_feature.setAttribute("altitude", altura + altitude)
                ponto_feature.setAttribute("alturavoo", altura)
                ponto_feature.setGeometry(ponto_geom)

                pontos_provider.addFeature(ponto_feature)
                pontoID += 1
        
        # Atualizar a camada
        pontos_fotos.updateExtents()
        pontos_fotos.commitChanges()
        
        # Simbologia
        simbolo = QgsMarkerSymbol.createSimple({'color': 'blue', 'size': '3'})
        renderer = QgsSingleSymbolRenderer(simbolo)
        pontos_fotos.setRenderer(renderer)

        # Rótulos
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

        pontos_fotos.setLabelsEnabled(True)
        pontos_fotos.setLabeling(QgsVectorLayerSimpleLabeling(settings))

        pontos_fotos.triggerRepaint()
        
        QgsProject.instance().addMapLayer(pontos_fotos)
        
        feedback.pushInfo("")
        feedback.pushInfo("Pontos para Fotos concluídos com sucesso!")
        
        #pontos_fotos = QgsProject.instance().mapLayersByName("Pontos Fotos")[0]

        """
        # =========Exportar para o Google  E a r t h   P r o  (kml)================================================
        
        # Reprojetar camada Pontos Fotos de UTM para WGS84 (4326)
        pontos_reproj = QgsVectorLayer('Point?crs=' + crs_wgs.authid(), 'Pontos Reprojetados', 'memory') 
        pontos_reproj.startEditing()
        pontos_reproj.dataProvider().addAttributes(pontos_fotos.fields())
        pontos_reproj.updateFields()

        # Reprojetar os pontos
        for f in pontos_fotos.getFeatures():
            geom = f.geometry()
            geom.transform(transformador)
            reproj = QgsFeature()
            reproj.setGeometry(geom)
            reproj.setAttributes(f.attributes())
            pontos_reproj.addFeature(reproj)

        pontos_reproj.commitChanges()
        
        if caminho_kml and caminho_kml.endswith('.kml'): # Verificar se o caminho KML está preenchido 
            # Configure as opções para gravar o arquivo
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.fileEncoding = 'UTF-8'
            options.driverName = 'KML'
            options.crs = crs_wgs
            options.layerOptions = ['ALTITUDE_MODE=absolute'] 
            
            # Escrever a camada no arquivo KML
            grava = QgsVectorFileWriter.writeAsVectorFormat(pontos_reproj, caminho_kml, options)
            
            if grava == QgsVectorFileWriter.NoError:
                feedback.pushInfo(f"Arquivo KML exportado com sucesso para: {caminho_kml}")
            else:
                feedback.pushInfo(f"Erro ao exportar o arquivo KML: {grava}")
        else:
            feedback.pushInfo("Caminho KML não especificado. Etapa de exportação ignorada.")

        if teste == True:
            QgsProject.instance().addMapLayer(pontos_reproj)
        
        # =============L I T C H I==========================================================
        
        if caminho_csv and caminho_csv.endswith('.csv'): # Verificar se o caminho CSV está preenchido
            # Definir novos campos xcoord e ycoord com coordenadas geográficas
            pontos_reproj.dataProvider().addAttributes([QgsField("xcoord", QVariant.Double), QgsField("ycoord", QVariant.Double)])
            pontos_reproj.updateFields()

            # Obtenha o índice dos novos campos
            idx_x = pontos_reproj.fields().indexFromName('xcoord')
            idx_y = pontos_reproj.fields().indexFromName('ycoord')

            # Inicie a edição da camada
            pontos_reproj.startEditing()

            for f in pontos_reproj.getFeatures():
                geom = f.geometry()
                if geom.isEmpty():
                    continue

                ponto = geom.asPoint()
                x = ponto.x()
                y = ponto.y()

                f.setAttribute(idx_x, x)
                f.setAttribute(idx_y, y)

                pontos_reproj.updateFeature(f)

            pontos_reproj.commitChanges()

            # deletar campos desnecessários
            campos = ['circulo', 'latitude', 'longitude']
            
            pontos_reproj.startEditing()
            
            # Obtem os índices dos campos a serem deletados
            indices = [pontos_reproj.fields().indexFromName(campo) for campo in campos if campo in pontos_reproj.fields().names()]
            
            pontos_reproj.deleteAttributes(indices)
            
            pontos_reproj.commitChanges()
                
            # Mudar Sistema numérico - ponto no lugar de vírgula para separa a parte decimal - Campos Double para String
            def addCampo(camada, field_name, field_type):
                camada.dataProvider().addAttributes([QgsField(field_name, field_type)])
                camada.updateFields()
                    
            pontos_reproj.startEditing()

            # Adicionar campos de texto em Pontos Reordenados
            addCampo(pontos_reproj, 'xcoord ', QVariant.String) # o espaço é para diferenciar; depois vamos deletar os campos antigos
            addCampo(pontos_reproj, 'ycoord ', QVariant.String)
            addCampo(pontos_reproj, 'alturavoo ', QVariant.String)

            for f in pontos_reproj.getFeatures():
                x1= str(f['xcoord']).replace(',', '.')
                x2 = str(f['ycoord']).replace(',', '.')
                x3 = str(f['alturavoo']).replace(',', '.')

                # Formatar os valores como strings com ponto como separador decimal
                x1 = "{:.6f}".format(float(x1))
                x2 = "{:.6f}".format(float(x2))
                x3 = "{:.6f}".format(float(x3))

                # Atualizar os valores dos campos de texto
                f['xcoord '] = x1
                f['ycoord '] = x2
                f['alturavoo '] = x3

                pontos_reproj.updateFeature(f)

            pontos_reproj.commitChanges()

            # Lista de campos Double a serem removidos de Pontos Reprojetados
            camposDel = ['xcoord', 'ycoord', 'alturavoo'] # sem o espaço
            
            pontos_reproj.startEditing()
            pontos_reproj.dataProvider().deleteAttributes([pontos_reproj.fields().indexOf(campo) for campo in camposDel if pontos_reproj.fields().indexOf(campo) != -1])
            pontos_reproj.commitChanges()

            if teste == True:
                QgsProject.instance().addMapLayer(pontos_reproj)
            
            # Exportar para o Litch (CSV já preparado)
            # Criar o arquivo CSV
            with open(caminho_csv, mode='w', newline='') as csvfile:
                # Definir os cabeçalhos do arquivo CSV
                fieldnames = [
                        "latitude", "longitude", "altitude(m)",
                        "heading(deg)", "curvesize(m)", "rotationdir",
                        "gimbalmode", "gimbalpitchangle",
                        "actiontype1", "actionparam1", "altitudemode", "speed(m/s)",
                        "poi_latitude", "poi_longitude", "poi_altitude(m)", "poi_altitudemode",
                        "photo_timeinterval", "photo_distinterval"]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                # Ler os dados da camada Pontos
                for f in pontos_reproj.getFeatures():
                    # Extrair os valores dos campos da camada
                    x_coord = f['xcoord '] 
                    y_coord = f['ycoord ' ]
                    alturavoo = f['alturavoo ' ]

                    # Criar um dicionário de dados para cada Círculo do CSV
                    data = {
                        "latitude": y_coord,
                        "longitude": x_coord,
                        "altitude(m)": alturavoo,
                        "heading(deg)": angulo_perpendicular,
                        "curvesize(m)": 0,
                        "rotationdir": 0,
                        "gimbalmode": 2,
                        "gimbalpitchangle": 0,
                        "actiontype1": 1.0,
                        "actionparam1": 0,
                        "altitudemode": 0,
                        "speed(m/s)": 0,
                        "poi_latitude": 0,
                        "poi_longitude": 0,
                        "poi_altitude(m)": 0,
                        "poi_altitudemode": 0,
                        "photo_timeinterval": -1.0,
                        "photo_distinterval": deltaH}

                    # Escrever o Círculo no CSV
                    writer.writerow(data)
        else:
            feedback.pushInfo("Caminho CSV não especificado. Etapa de exportação ignorada.")

        # Mensagem de Encerramento
        feedback.pushInfo("")
        feedback.pushInfo("Plano de Voo Vertical executado com sucesso.") 
        """  
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
  