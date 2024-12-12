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
__date__ = '2024-11-05'
__copyright__ = '(C) 2024 by Prof Cazaroli e Leandro França'
__revision__ = '$Format:%H$'

from qgis.core import QgsProcessing, QgsProject, QgsProcessingAlgorithm, QgsWkbTypes, QgsVectorFileWriter, QgsProcessingParameterFolderDestination
from qgis.core import QgsProcessingParameterVectorLayer, QgsProcessingParameterNumber, QgsProcessingParameterString, QgsProcessingParameterFileDestination
from qgis.core import QgsTextFormat, QgsTextBufferSettings, QgsCoordinateReferenceSystem, QgsProperty
from qgis.core import QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsProcessingParameterBoolean, QgsCoordinateTransform
from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsPoint, QgsPointXY, QgsField, QgsFields, QgsFeature, QgsGeometry
from qgis.core import QgsMarkerSymbol, QgsSingleSymbolRenderer, QgsSimpleLineSymbolLayer, QgsLineSymbol, QgsMarkerLineSymbolLayer
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor, QFont, QIcon
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction, QMessageBox
import processing
import os
import math
import csv

# pontos_provider Air 2S (5472 × 3648)

class PlanoVoo_V(QgsProcessingAlgorithm):
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
        self.addParameter(QgsProcessingParameterFileDestination('saida_csv', 'Arquivo de Saída CSV (Litchi)',
                                                               fileFilter='CSV files (*.csv)'))
        self.addParameter(QgsProcessingParameterFolderDestination('saida_kml', 'Pasta de Saída para o KML (Google Earth)'))
        
    def processAlgorithm(self, parameters, context, feedback):
        teste = False # Quando True mostra camadas intermediárias
        
        # =====Parâmetros de entrada para variáveis========================
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
        caminho_csv = parameters['saida_csv']
        
        feedback.pushInfo(f"Altura: {H}, Delta Horizontal: {deltaH}, Delta Vertical: {deltaV}")
        
        # Verificações
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
        
        # =====================================================================
        # =====Criar a camada Pontos de Fotos==================================
        
        # Obter a Altitude dos pontos das Fotos com OpenTopography
        feedback.pushInfo("Obtendo as Altitudes com o OpenTopography")
       
        # Reprojetar para WGS 84 (EPSG:4326), usado pelo OpenTopography
        crs_wgs = QgsCoordinateReferenceSystem(4326)
        transformador = QgsCoordinateTransform(crs, crs_wgs, QgsProject.instance())
        
        # Determinar o bounding box da linha em WGS 84
        bounds = linha_base_geom.boundingBox()
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
        
        # Filtrar o MDE com (Relevo / Filtro do MDE) do LFTools
        result = processing.run(
            "lftools:demfilter", {'INPUT': camadaMDE,
                                  'KERNEL':0,'OUTPUT':'TEMPORARY_OUTPUT','OPEN':False})
        output_path = result['OUTPUT']
        camadaMDE = QgsRasterLayer(output_path, "DEM_Filtrado")

        QgsProject.instance().addMapLayer(camadaMDE)
        
        #camadaMDE = QgsProject.instance().mapLayersByName("DEM_Filtrado")[0]
        
        # =====================================================================
        # =====Criar a camada Pontos de Fotos==================================
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
        
        distancias = [i for i in range(0, comprimento + 1, deltaH)]
        alturas = [i for i in range(h, H + h + 1, deltaV)]

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
       
        # Verificar orientação do ponto em relação à linha base
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
            options.field_name = 'id'
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
            campos = ['linha', 'latitude', 'longitude']
            
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
            
            # Formatar os valores como strings com ponto como separador decimal
            v = str(velocidade).replace(',', '.')
            velocidade = "{:.6f}".format(float(v))
            
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

                    # Criar um dicionário de dados para cada linha do CSV
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
                        "speed(m/s)": velocidade,
                        "poi_latitude": 0,
                        "poi_longitude": 0,
                        "poi_altitude(m)": 0,
                        "poi_altitudemode": 0,
                        "photo_timeinterval": -1.0,
                        "photo_distinterval": deltaH}

                    # Escrever a linha no CSV
                    writer.writerow(data)
        else:
            feedback.pushInfo("Caminho CSV não especificado. Etapa de exportação ignorada.")

        # Mensagem de Encerramento
        feedback.pushInfo("")
        feedback.pushInfo("Plano de Voo Vertical executado com sucesso.") 
          
        return {}
        
    def name(self):
        return 'PlanoVooV'.lower()

    def displayName(self):
        return self.tr('Fachada')

    def group(self):
        return 'Pontos Fotos - Voo Vertical'

    def groupId(self):
        return 'Pontos Fotos - Voo Vertical'
        
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PlanoVoo_V()
    
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
  