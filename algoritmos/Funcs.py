# -*- coding: utf-8 -*-

"""
/***************************************************************************
 GeoFlight Planner - Functions
                                 A QGIS plugin
 GeoFlight Planner
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

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsVectorLayer,
    QgsProject,
    QgsFeature,
    QgsGeometry
)

from qgis.core import *
from qgis.PyQt.QtGui import QColor, QFont
from PyQt5.QtCore import QVariant
import qgis.utils
import processing
import csv

# def obter_DEM(flight_type, layer, transformador, apikey, feedback=None, bbox_area_min=2.5):
#    # Obter a Altitude dos pontos das Fotos com OpenTopography
#    feedback.pushInfo("Getting Altitudes with OpenTopography")
   
#    # Determinar o bounding box da linha em WGS 84
#    bounds = layer.boundingBox()
#    ponto_min = transformador.transform(QgsPointXY(bounds.xMinimum(), bounds.yMinimum()))
#    ponto_max = transformador.transform(QgsPointXY(bounds.xMaximum(), bounds.yMaximum()))

#    pontoN = ponto_max.y()
#    pontoS = ponto_min.y()
#    pontoW = ponto_min.x()
#    pontoE = ponto_max.x()

#    # Certificar que a área do bounding box seja grande o suficiente
#    bbox_area = (pontoE - pontoW) * (pontoN - pontoS) * 111 * 111  # Aproximação em km²
#    if bbox_area < bbox_area_min:
#       aumento = ((bbox_area_min / bbox_area) ** 0.5 - 1) / 2
      
#       ajuste_lat_extra = aumento * (pontoN - pontoS)
#       ajuste_long_extra = aumento * (pontoE - pontoW)
      
#       pontoN += ajuste_lat_extra
#       pontoS -= ajuste_lat_extra
#       pontoW -= ajuste_long_extra
#       pontoE += ajuste_long_extra

#    # Obter o DEM da área
#    coordenadas = f'{pontoW},{pontoE},{pontoS},{pontoN}'
#    area = f"{coordenadas}[EPSG:4326]"

#    # Atualmente, o OpenTopography não oferece modelos de elevação diretamente referenciados ao elipsoide (como o WGS84)
#    # Ele utiliza uma superfície ortométrica como referência, que é baseada no Geoid EGM96 (Earth Gravitational Model 1996)
#    # Isso significa que as elevações fornecidas pelo Copernicus DSM estão em relação ao nível médio do mar, e não ao elipsoide
   
#    result = processing.run(
#       "OTDEMDownloader:OpenTopography DEM Downloader", {
#          'DEMs': 7,  # Copernicus Global DSM 30m
#          'Extent': area,
#          'API_key': apikey,
#          'OUTPUT': 'TEMPORARY_OUTPUT'
#       })

#    output_path = result['OUTPUT']
#    camadaMDE = QgsRasterLayer(output_path, "DEM")

#    # Filtrar o MDE com (Relevo / Filtro do MDE) do LFTools
#    result = processing.run(
#       "lftools:demfilter", {
#          'INPUT': camadaMDE,
#          'KERNEL': 0,
#          'OUTPUT': 'TEMPORARY_OUTPUT',
#          'OPEN': False
#       })
#    output_path = result['OUTPUT']
#    camadaMDE = QgsRasterLayer(output_path, "DEM")

#    feedback.pushInfo("DEM successfully processed!")
   
#    return camadaMDE
 
def criarLinhaVoo(flight_type, layer, crs_wgs, transformador, feedback=None):
   # Reprojetar linha_voo_layer para WGS84 (4326)
   linha_voo_reproj = reprojeta_camada_WGS84(layer, crs_wgs, transformador)

   # Polygon para PolygonZ
   linha_voo_reproj = set_Z_value(linha_voo_reproj, z_field="altitude")

   # Configurar simbologia de seta
   simbologiaLinhaVoo(flight_type, linha_voo_reproj)

   # ===== LINHA DE VOO ==============================
   linha_voo_reproj.setName("Flight Line")
   
   QgsProject.instance().addMapLayer(linha_voo_reproj)

   return linha_voo_reproj

def gerar_kmz(layer, arquivo_kmz, crs_wgs, altitude_mode, feedback=None):
   campos = [field.name() for field in layer.fields()]
   
   # result = processing.run("kmltools:exportkmz", {
   #       'InputLayer': layer,
   #       'NameField': 'id',                     # Campo para o nome das feições no kmz
   #       'UseGoogleIcon': 1,                    # Ícone padrão do Google Earth
   #       'AltitudeInterpretation': 1,           # Interpretar altitude
   #       'AltitudeMode': altitude_mode,         # Altitude relativa ao terreno=1 e absoluta=2
   #       'AltitudeModeField': '',
   #       'AltitudeField': 'altitude',           # Campo com o valor Z
   #       'AltitudeAddend': 0,                   # Adicionar valor extra à altitude
   #       'OutputKmz': arquivo_kmz,              # Arquivo de saída
   #       'LineWidthFactor': 2,                  # Define a largura das linhas no kmz
   #       'UseDescBR': True,                     # Usar descrição em formato brasileiro
   #       'DateStampField': '',
   #       'TimeStampField': '',
   #       'DateBeginField': '',
   #       'TimeBeginField': '',
   #       'DateEndField': '',
   #       'TimeEndField': ''
   # }, feedback=feedback)
   
   
   result = processing.run("kmltools:exportkmz", {
      'InputLayer':layer,
      'SelectedFeaturesOnly':False,
      'NameField':'id',                       # Campo para o nome das feições no kmz
      'HiddenPolygonPointLabel':False,
      'DescriptionField':['id'],
      'ExportStyle':True,
      'UseGoogleIcon':1,                      # Ícone padrão do Google Earth
      'AltitudeInterpretation':1,
      'AltitudeMode':altitude_mode,           # Altitude relativa ao terreno=1 e absoluta=2
      'AltitudeModeField':'altitude',         # Campo com o valor Z; pode ser zero se não tiver Raster selecionado
      'AltitudeField':'',
      'AltitudeAddend':0,
      'ExtendSidesToGround':False,
      'DateTimeStampField':'',
      'DateTimeBeginField':'',
      'DateTimeEndField':'',
      'PhotoField':'',
      'OutputKmz':arquivo_kmz,                 # Arquivo de saída
      'LineWidthFactor':2,                     # Define a largura das linhas no kmz
      'SubFolderField':'',
      'UseDescBR':True,                        # Usar descrição em formato brasileiro
      'DateStampField':'',
      'TimeStampField':'',
      'DateBeginField':'',
      'TimeBeginField':'',
      'DateEndField':'',
      'TimeEndField':''})
   
   feedback.pushInfo(f"kmz successfully exported to: {arquivo_kmz}")
   
   return result

   """ Não leva para Google Earth Pro com a identificação dos IDs e não vai altitude mode = absolute
   # Configuração das opções para gravar o arquivo
   options = QgsVectorFileWriter.SaveVectorOptions()
   options.fileEncoding = 'UTF-8'
   options.crs = crs_wgs
   options.driverName = 'kmz'
   options.includeZ = True
   #options.fieldName = 'id'
   options.altitudemode = 'absolute'
   #options.layerOptions = ['ALTITUDE_MODE=absolute']
   
   # Escrever a camada no arquivo kmz
   grava = QgsVectorFileWriter.writeAsVectorFormat(layer, arquivo_kmz, options)

   if grava == QgsVectorFileWriter.NoError:
      feedback.pushInfo(f"Arquivo kmz exportado com sucesso para: {arquivo_kmz}")
   else:
      feedback.pushInfo(f"Erro ao exportar o arquivo kmz: {grava}")
   
   return {}
   """
   
def gerar_CSV(flight_type, pontos_reproj, arquivo_csv, velocidade, tempo, delta, angulo, H, terrain=None):
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
   campos = ['latitude', 'longitude']
   
   pontos_reproj.startEditing()
   
   # Obtem os índices dos campos a serem deletados
   indices = [pontos_reproj.fields().indexFromName(campo) for campo in campos if campo in pontos_reproj.fields().names()]
   
   pontos_reproj.deleteAttributes(indices)
   
   pontos_reproj.commitChanges()
         
   # Mudar Sistema numérico - ponto no lugar de vírgula para separa a parte decimal - Campos Double para String        
   pontos_reproj.startEditing()

   # Adicionar campos de texto em Pontos Reordenados
   addCampo(pontos_reproj, 'xcoord ', QVariant.String) # o espaço é para diferenciar; depois vamos deletar os campos antigos
   addCampo(pontos_reproj, 'ycoord ', QVariant.String)
   
   if flight_type == "VF":
      addCampo(pontos_reproj, 'alturasolo ', QVariant.String)
      
   if flight_type == "VC":
      addCampo(pontos_reproj, 'alturasolo ', QVariant.String)
      addCampo(pontos_reproj, 'angulo ', QVariant.String)   
   
   for f in pontos_reproj.getFeatures():
         x1= str(f['xcoord']).replace(',', '.')
         x2 = str(f['ycoord']).replace(',', '.')
         
         if flight_type == "VF":
            x3 = str(f['alturasolo']).replace(',', '.')
         
         if flight_type == "VC":
            x3 = str(f['alturasolo']).replace(',', '.')
            x4 = str(f['angulo']).replace(',', '.')
         
         # Formatar os valores como strings com ponto como separador decimal
         x1 = "{:.6f}".format(float(x1))
         x2 = "{:.6f}".format(float(x2))
         
         if flight_type == "VF":
            x3 = "{:.6f}".format(float(x3))

         if flight_type == "VC":
            x3 = "{:.6f}".format(float(x3))
            x4 = "{:.6f}".format(float(x4))

         # Atualizar os valores dos campos de texto
         f['xcoord '] = x1
         f['ycoord '] = x2
         
         if flight_type == "VF":
            f['alturasolo '] = x3
         
         if flight_type == "VC":
            f['alturasolo '] = x3
            f['angulo '] = x4

         pontos_reproj.updateFeature(f)

   pontos_reproj.commitChanges()

   # Lista de campos Double a serem removidos de Pontos Reprojetados
   if flight_type == "H":
      camposDel = ['xcoord', 'ycoord'] # sem o espaço
   elif flight_type == "VF":
      camposDel = ['xcoord', 'ycoord', 'alturasolo']
   elif flight_type == "VC":
      camposDel = ['xcoord', 'ycoord', 'alturasolo', 'angulo']
      
   pontos_reproj.startEditing()
   pontos_reproj.dataProvider().deleteAttributes([pontos_reproj.fields().indexOf(campo) for campo in camposDel if pontos_reproj.fields().indexOf(campo) != -1])
   pontos_reproj.commitChanges()
   
   # Formatar os valores como strings com ponto como separador decimal
   v = str(velocidade).replace(',', '.')
   velocidade = "{:.6f}".format(float(v))
   
   # Exportar para o Litch (CSV já preparado)
   # Criar o arquivo CSV
   with open(arquivo_csv, mode='w', newline='') as csvfile:
         # Definir os cabeçalhos do arquivo CSV
         fieldnames = [
               "latitude", "longitude", "altitude(m)",
               "heading(deg)", "curvesize(m)", "rotationdir",
               "gimbalmode", "gimbalpitchangle",
               "actiontype1", "actionparam1", "actiontype2", "actionparam2",
               "actiontype3", "actionparam3", "actiontype4", "actionparam4",
               "actiontype5", "actionparam5", "actiontype6", "actionparam6",
               "actiontype7", "actionparam7", "actiontype8", "actionparam8",
               "actiontype9", "actionparam9", "actiontype10", "actionparam10",
               "actiontype11", "actionparam11", "actiontype12", "actionparam12",
               "actiontype13", "actionparam13", "actiontype14", "actionparam14",
               "actiontype15", "actionparam15", "altitudemode", "speed(m/s)",
               "poi_latitude", "poi_longitude", "poi_altitude(m)", "poi_altitudemode",
               "photo_timeinterval", "photo_distinterval"]
         
         writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
         writer.writeheader()
         
         if flight_type == "H":
            alturavoo = H
            mode_gimbal = 2
            angulo_gimbal = -90
            if terrain:
               above_ground = 1 # Above Ground habilitado
            else:
               above_ground = 0 # Above Ground não habilitado
         else:
            mode_gimbal = 0
            angulo_gimbal = 0
            above_ground = 0 # Above Ground não habilitado
            
         if tempo == 0:
            t1 = 1          # TAKE_PHOTO
            t2 = 0
            t3 = -1
            t4 = 0
         else:
            t1 = 0          # STAY n segundos
            t2 = tempo*1000 
            t3 = 1          # TAKE_PHOTO
            t4 = 0
            
         # Ler os dados da camada Pontos
         for f in pontos_reproj.getFeatures():
            # Extrair os valores dos campos da camada
            x_coord = f['xcoord '] 
            y_coord = f['ycoord ']
            
            if flight_type == "VF":
               alturavoo = f['alturasolo ']
            elif flight_type == "VC":
               alturavoo = f['alturasolo ']
               angulo = f['angulo ']
               
            # Criar um dicionário de dados para cada item do CSV
            data = {
               "latitude": y_coord,
               "longitude": x_coord,
               "altitude(m)": alturavoo,
               "heading(deg)": angulo,
               "curvesize(m)": 0,
               "rotationdir": 0,
               "gimbalmode": mode_gimbal,
               "gimbalpitchangle": angulo_gimbal,
               "actiontype1": t1,     
               "actionparam1": t2,
               "actiontype2": t3,
               "actionparam2": t4,
               "actiontype3": -1, 
               "actionparam3": 0,
               "actiontype4": -1,
               "actionparam4": 0,
               "actiontype5": -1,
               "actionparam5": 0,
               "actiontype6": -1,
               "actionparam6": 0,
               "actiontype7": -1,
               "actionparam7": 0,
               "actiontype8": -1,
               "actionparam8": 0,
               "actiontype9": -1,
               "actionparam9": 0,
               "actiontype10": -1,
               "actionparam10": 0,
               "actiontype11": -1,
               "actionparam11": 0,
               "actiontype12": -1,
               "actionparam12": 0,
               "actiontype13": -1,
               "actionparam13": 0,
               "actiontype14": -1,
               "actionparam14": 0,
               "actiontype15": -1,
               "actionparam15": 0,
               "altitudemode": above_ground,
               "speed(m/s)": velocidade,
               "poi_latitude": 0,
               "poi_longitude": 0,
               "poi_altitude(m)": 0,
               "poi_altitudemode": 0,
               "photo_timeinterval": -1,
               "photo_distinterval": delta}

            # Escrever a linha no CSV
            writer.writerow(data)
            
   return {}

def addCampo(layer, field_name, field_type):
      layer.dataProvider().addAttributes([QgsField(field_name, field_type)])
      layer.updateFields()
      
def set_Z_value(layer, z_field):
    result = processing.run("native:setzvalue", {
        'INPUT': layer,
        'Z_VALUE': QgsProperty.fromExpression(f'"{z_field}"'),
        'OUTPUT': 'TEMPORARY_OUTPUT'
    })
    
    output_layer = result['OUTPUT']
    output_layer.setName(layer.name())
    
    return output_layer
 
def reprojeta_camada_WGS84(layer, crs_wgs, transformador):
   geometry_type = layer.geometryType()
   
   # Criar camada reprojetada com base no tipo de geometria
   if geometry_type == QgsWkbTypes.PointGeometry:
      tipo_layer = "Point"
   elif geometry_type == QgsWkbTypes.LineGeometry:
      tipo_layer = "LineString"
   elif geometry_type == QgsWkbTypes.PolygonGeometry:
      tipo_layer = "Polygon"
   
   # Criar a nova camada reprojetada em memória
   reproj_layer = QgsVectorLayer(f"{tipo_layer}?crs={crs_wgs.authid()}", f"{layer.name()}", "memory")
    
   reproj_layer.startEditing()
   reproj_layer.dataProvider().addAttributes(layer.fields())
   reproj_layer.updateFields()

   # Reprojetar feições
   for f in layer.getFeatures():
      geom = f.geometry()
      geom.transform(transformador)
      reproj = QgsFeature()
      reproj.setGeometry(geom)
      reproj.setAttributes(f.attributes())
      reproj_layer.addFeature(reproj)

   reproj_layer.commitChanges()
   
   return reproj_layer

def simbologiaLinhaVoo(flight_type, layer):
   if flight_type == "H":
      line_symbol = QgsLineSymbol.createSimple({'color': 'blue', 'width': '0.3'})  # Linha base

      seta = QgsMarkerSymbol.createSimple({'name': 'arrow', 'size': '5', 'color': 'blue', 'angle': '90'})

      marcador = QgsMarkerLineSymbolLayer()
      marcador.setInterval(30)  # Define o intervalo entre as setas (marcadores)
      marcador.setSubSymbol(seta)
      
      layer.renderer().symbol().appendSymbolLayer(marcador)
   elif flight_type == "VF" or flight_type == "VC":
      simbologia = QgsLineSymbol.createSimple({
            'color': 'green',        # Cor da linha
            'width': '0.8'           # Largura da linha
         })
      layer.setRenderer(QgsSingleSymbolRenderer(simbologia))
      
      if flight_type == "VF": 
         # Rótulo
         label_settings = QgsPalLayerSettings()
         label_settings.fieldName = 'id'  # Campo que será usado como rótulo
         label_settings.placement = QgsPalLayerSettings.Line
         label_settings.enabled = True

         # Criar configurações de renderização de rótulos
         text_format = QgsTextFormat()
         text_format.setSize(10)  # Tamanho da fonte
         text_format.setColor(QColor('blue'))  # Cor do texto
         text_format.setFont(QFont('Arial'))  # Fonte do texto

         label_settings.setFormat(text_format)

         # Aplicar rótulos à camada
         labeling = QgsVectorLayerSimpleLabeling(label_settings)
         layer.setLabelsEnabled(True)
         layer.setLabeling(labeling)
         layer.triggerRepaint()
       
   return

def simbologiaPontos(layer):
   simbolo = QgsMarkerSymbol.createSimple({'color': 'blue', 'size': '3'})
   renderer = QgsSingleSymbolRenderer(simbolo)
   layer.setRenderer(renderer)

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

   layer.setLabelsEnabled(True)
   layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))

   layer.triggerRepaint()
   
   return

def verificar_plugins(plugins_list, feedback=None):
    # Obter a lista de todos os plugins instalados
    installed_plugins = qgis.utils.plugins.keys()
    
    plugins_not_installed = [plugin for plugin in plugins_list if plugin not in installed_plugins]
    
    # Se houver plugins não instalados, levantar erro
    if plugins_not_installed:
       raise Exception(f"The following plugins are not installed: {', '.join(plugins_not_installed)}")
    else:
       feedback.pushInfo(f"All plugins are installed: {plugins_list}")
    
    return
 
def calculaDistancia_Linha_Ponto(line_geom, point_geom):
   distancia = line_geom.distance(point_geom)

   return distancia   

def verificarCRS(layer, feedback=None):
   # UTM Norte / UTM 32601 a 32660 / 31918 a 31924 / SIRGAS2000 UTM 31957 a 31965 S
   # UTM Sul  /  UTM 32701 a 32760 / 31925 a 31927 / SIRGAS2000 UTM 31978 a 31985 S

   crs_layer = layer.crs()
   descricao_crs_layer = crs_layer.description()
   epsg_code_layer = crs_layer.authid()
    
   extent = layer.extent()
   lat_media = (extent.yMinimum() + extent.yMaximum()) / 2.0  # Latitude média
   long_media = (extent.xMinimum() + extent.xMaximum()) / 2.0  # Longitude média
   
   utm_zone = int((long_media + 180) / 6) + 1  # Calcula a zona UTM
   
   if lat_media >= 0:
      hemisferio = "Norte"
   else:
      hemisferio = "Sul"
   
   if "WGS 84" in descricao_crs_layer.upper():
        if hemisferio == "Norte":
            epsg_code = 32600 + utm_zone  # WGS 84 Hemisfério Norte
        else:
            epsg_code = 32700 + utm_zone  # WGS 84 Hemisfério Sul
   elif "SIRGAS 2000" in descricao_crs_layer.upper():
      if hemisferio == "Norte":
            epsg_code = 31956 + utm_zone      # SIRGAS 2000 Hemisfério Norte
      else:
            epsg_code = 31978 + utm_zone - 18 # SIRGAS 2000 Hemisfério Sul
   else:
      raise Exception(f"Layer must be WGS84 or SIRGAS2000 or UTM. Other ({descricao_crs_layer.upper()}, EPSG:{epsg_code_layer}) not supported")
   
   crs_utm = QgsCoordinateReferenceSystem(f"EPSG:{epsg_code}")
   feedback.pushInfo(f"Reprojecting for CRS EPSG:{epsg_code} - {crs_utm.description()}")

   # Reprojetar a camada para o CRS UTM apropriado
   transform_context = QgsProject.instance().transformContext()
   transform = QgsCoordinateTransform(crs_layer, crs_utm, transform_context)

   # Determina o tipo de geometria da camada original
   geometry_type = layer.geometryType()  # 0: Point, 1: Line, 2: Polygon
   if geometry_type == 0:
      geometry_string = "Point"
   elif geometry_type == 1:
      geometry_string = "LineString"
   elif geometry_type == 2:
      geometry_string = "Polygon"

   # Cria uma nova camada para armazenar os dados reprojetados
   camada_reprojetada = QgsVectorLayer(
            f"{geometry_string}?crs=EPSG:{epsg_code}",
            f"{layer.name()}_reproject",
            "memory")
   
   nova_data_provider = camada_reprojetada.dataProvider()

   # Adiciona os campos da camada original à nova amada
   nova_data_provider.addAttributes(layer.fields())
   camada_reprojetada.updateFields()

   # Reprojeta os recursos (features) da camada original
   camada_reprojetada.startEditing()
   for feature in layer.getFeatures():
      geom = feature.geometry()
      if geom:
         geom.transform(transform)  # Aplica a transformação
         feature.setGeometry(geom)
         nova_data_provider.addFeatures([feature])
   camada_reprojetada.commitChanges()
   
   QgsProject.instance().addMapLayer(camada_reprojetada)
   
   return crs_utm  
      
def duplicaPontoInicial(layer):
   crs = layer.crs()
   
   geometry_type = layer.wkbType()
   duplicated_layer = QgsVectorLayer(f"{QgsWkbTypes.displayString(geometry_type)}?crs={crs.authid()}", 
                                       f"{layer.name()}_move", "memory")
   
   # Copia os campos da camada original para a nova camada
   duplicated_layer.dataProvider().addAttributes(layer.fields())
   duplicated_layer.updateFields()
   
   # Copia as feições (geometria e atributos) da camada original
   duplicated_layer.startEditing()
   for feature in layer.getFeatures():
      duplicated_layer.addFeature(feature)
   duplicated_layer.commitChanges()
   
   # Adiciona a nova camada ao projeto
   QgsProject.instance().addMapLayer(duplicated_layer)
   
   return

def loadParametros(tipoVoo):
   my_settings = QgsSettings()
   
   if tipoVoo == "H_Sensor":
      hVoo = my_settings.value("qgis-drone-flight-planner/hVooS", 100)
      ab_groundS = my_settings.value("qgis-drone-flight-planner/ab_groundS", True)
      sensorH = my_settings.value("qgis-drone-flight-planner/sensorH", 13.2)
      sensorV = my_settings.value("qgis-drone-flight-planner/sensorV", 8.8)
      dFocal = my_settings.value("qgis-drone-flight-planner/dFocal", 8.38)
      sLateralH = my_settings.value("qgis-drone-flight-planner/sLateralH", 0.75)
      sFrontalH = my_settings.value("qgis-drone-flight-planner/sFrontalH", 0.85)
      velocH = my_settings.value("qgis-drone-flight-planner/velocHs", 8)
      tStayH = my_settings.value("qgis-drone-flight-planner/tStayHs", 0)
   elif tipoVoo == "H_Manual":
      hVoo = my_settings.value("qgis-drone-flight-planner/hVooM", 100)
      ab_groundM = my_settings.value("qgis-drone-flight-planner/ab_groundM", True)
      dl_manualH = my_settings.value("qgis-drone-flight-planner/dl_manualH", 10)
      df_op = my_settings.value("qgis-drone-flight-planner/df_op", 0)
      df_manualH = my_settings.value("qgis-drone-flight-planner/df_manualH", 10)
      velocH = my_settings.value("qgis-drone-flight-planner/velocHm", 8)
      tStayH = my_settings.value("qgis-drone-flight-planner/tStayHm", 0)
   elif tipoVoo == "VF":
      hFac = my_settings.value("qgis-drone-flight-planner/hFac", 15)
      altMinVF = my_settings.value("qgis-drone-flight-planner/altMinVF", 0.5)
      dl_manualVF = my_settings.value("qgis-drone-flight-planner/dl_manualVF", 5)
      df_manualVF = my_settings.value("qgis-drone-flight-planner/df_manualVF", 3)
      velocVF = my_settings.value("qgis-drone-flight-planner/velocVF", 1)
      tStayVF = my_settings.value("qgis-drone-flight-planner/tStayVF", 2)
   elif tipoVoo == "VC": 
      hObj = my_settings.value("qgis-drone-flight-planner/hObj", 15)
      altMinVC = my_settings.value("qgis-drone-flight-planner/altMinVC", 0.5)  
      nPartesVC = my_settings.value("qgis-drone-flight-planner/nPartesVC", 8)
      dVertVC = my_settings.value("qgis-drone-flight-planner/dVertVC", 3)
      velocVC = my_settings.value("qgis-drone-flight-planner/velocVC", 1)
      tStayVC = my_settings.value("qgis-drone-flight-planner/tStayVC", 2)
      
   skmz = my_settings.value("qgis-drone-flight-planner/skmz", "")
   sCSV = my_settings.value("qgis-drone-flight-planner/sCSV", "")
      
   if tipoVoo == "H_Sensor":
      return hVoo, ab_groundS, sensorH, sensorV, dFocal, sLateralH, sFrontalH, velocH, tStayH, skmz, sCSV
   elif tipoVoo == "H_Manual":
      return hVoo, ab_groundM, dl_manualH, df_op, df_manualH, velocH, tStayH, skmz, sCSV
   elif tipoVoo == "VF":
      return hFac, altMinVF, dl_manualVF, df_manualVF, velocVF, tStayVF, skmz, sCSV
   elif tipoVoo == "VC":
      return hObj, altMinVC, nPartesVC, dVertVC, velocVC, tStayVC, skmz, sCSV
   
def saveParametros(tipoVoo, h, v, t, skmz, sCSV, ab_ground=None, sensorH=None, sensorV=None, dFocal=None, sLateral=None, sFrontal=None, dl=None, dfop=None, df=None, aM=None, nVC=None, dVC=None):
   my_settings = QgsSettings()
   
   if tipoVoo == "H_Sensor":
      my_settings.setValue("qgis-drone-flight-planner/hVooS", h)
      my_settings.setValue("qgis-drone-flight-planner/ab_groundS", ab_ground)
      my_settings.setValue("qgis-drone-flight-planner/sensorH", sensorH)
      my_settings.setValue("qgis-drone-flight-planner/sensorV", sensorV)
      my_settings.setValue("qgis-drone-flight-planner/dFocal", dFocal)
      my_settings.setValue("qgis-drone-flight-planner/sLateralH", sLateral)
      my_settings.setValue("qgis-drone-flight-planner/sFrontalH", sFrontal)
      my_settings.setValue("qgis-drone-flight-planner/velocHs", v)
      my_settings.setValue("qgis-drone-flight-planner/tStayHs", t)
   elif tipoVoo == "H_Manual":
      my_settings.setValue("qgis-drone-flight-planner/hVooM", h)
      my_settings.setValue("qgis-drone-flight-planner/ab_groundM", ab_ground)
      my_settings.setValue("qgis-drone-flight-planner/dl_manualH", dl)
      my_settings.setValue("qgis-drone-flight-planner/df_op", dfop)
      my_settings.setValue("qgis-drone-flight-planner/df_manualH", df)
      my_settings.setValue("qgis-drone-flight-planner/velocHm", v)
      my_settings.setValue("qgis-drone-flight-planner/tStayHm", t)
   elif tipoVoo == "VF":
      my_settings.setValue("qgis-drone-flight-planner/hFac", h)
      my_settings.setValue("qgis-drone-flight-planner/altMinVF", aM)
      my_settings.setValue("qgis-drone-flight-planner/dl_manualVF", dl)
      my_settings.setValue("qgis-drone-flight-planner/df_manualVF", df)
      my_settings.setValue("qgis-drone-flight-planner/velocVF", v)
      my_settings.setValue("qgis-drone-flight-planner/tStayVF", t)
   elif tipoVoo == "VC":
      my_settings.setValue("qgis-drone-flight-planner/hObj", h)
      my_settings.setValue("qgis-drone-flight-planner/altMinVC", aM)
      my_settings.setValue("qgis-drone-flight-planner/nPartesVC", nVC)
      my_settings.setValue("qgis-drone-flight-planner/dVertVC", dVC)
      my_settings.setValue("qgis-drone-flight-planner/velocVC", v)
      my_settings.setValue("qgis-drone-flight-planner/tStayVC", t)
   
   my_settings.setValue("qgis-drone-flight-planner/skmz", skmz)
   my_settings.setValue("qgis-drone-flight-planner/sCSV", sCSV)

   return

def removeLayersReproj(txtFinal):
   layers_to_remove = []
   for layer in QgsProject.instance().mapLayers().values():
      # Verificar se o nome da camada termina com '_reproject' ou '_move'
      if layer.name().endswith(txtFinal):
            layers_to_remove.append(layer)

   # Remover as camadas que atendem ao critério
   for layer in layers_to_remove:
      QgsProject.instance().removeMapLayer(layer)
            
   return