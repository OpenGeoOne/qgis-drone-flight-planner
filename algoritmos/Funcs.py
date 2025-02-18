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
#import simplekml

# def gerar_kml(layer, arquivo_kml, crs_wgs, altitude_mode, feedback=None):
#    kml = simplekml.Kml()

#    fields = [field.name() for field in layer.fields()]

#    # Identify altitude fields
#    altitude_field = "altitude" if "altitude" in fields else None
#    flight_altitude_field = "alturavoo" if "alturavoo" in fields else None

#    for feature in layer.getFeatures():
#       geom = feature.geometry()

#       # Get altitude values
#       altitude_value = feature[altitude_field] if altitude_field and feature[altitude_field] is not None else None
#       flight_altitude_value = feature[flight_altitude_field] if flight_altitude_field else 50  # Default value

#       # Set the correct height based on altitude mode
#       if altitude_mode == "absolute":
#          altitude = altitude_value if altitude_value is not None else flight_altitude_value
#       else:  # relativeToGround → Always use flight_altitude_value
#          altitude = flight_altitude_value

#       if geom.type() == 0:  # Point
#          pt = geom.asPoint()
#          p = kml.newpoint(name=f"Feature {feature.id()}", coords=[(pt.x(), pt.y(), altitude)])
#          p.altitudemode = altitude_mode
#          p.gxaltitudemode = altitude_mode  # 🔥 Ensure Google Earth respects the mode
#          p.extrude = 1  # 🔥 Force elevation

#       elif geom.type() == 1:  # Line
#          coords = [(pt.x(), pt.y(), altitude) for pt in geom.asPolyline()]
#          ls = kml.newlinestring(name=f"Feature {feature.id()}", coords=coords)
#          ls.altitudemode = altitude_mode
#          ls.gxaltitudemode = altitude_mode
#          ls.extrude = 1

#          # Apply Red Color and Increase Line Width
#          linestyle = simplekml.Style()
#          linestyle.linestyle.color = simplekml.Color.red  # Red color
#          linestyle.linestyle.width = 5  # Line thickness
#          ls.style = linestyle  # Apply the style to the line

#    # Save the KML file
#    kml.save(arquivo_kml)

#    feedback.pushInfo(f"✅ KML files successfully generated: {arquivo_kml}")

#    return {}

def gerar_CSV(flight_type, pontos_fotos, arquivo_csv, velocidade, tempo, delta, angulo, H, terrain=None, deltaFront_op=None):

   # Criar o arquivo CSV do Litchi
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
            above_ground = 0 # Above Ground não habilitado para voos verticais

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

         if deltaFront_op == 1:   # valor = 1 is seconds; caso tenha sido escolhido por tempo no Voo Horizontal Manual
            time_interval = delta
            dist_interval = -1
         elif deltaFront_op == 0: # valor = 0 is meters; caso tenha sido escolhido por distância no Voo Horizontal Manual
            time_interval = -1
            dist_interval = delta
         else:                  # None para todos os voos que não Horizontal Manual
            time_interval = -1
            dist_interval = delta

         # Ler os dados da camada Pontos
         for f in pontos_fotos.getFeatures():
            # Extrair os valores dos campos da camada
            longitude = f['longitude']
            latitude = f['latitude']

            if flight_type == "VF":
               alturavoo = f['height']
            elif flight_type == "VC":
               alturavoo = f['height']
               angulo = f['angle']

            # Criar um dicionário de dados para cada item do CSV
            data = {
               "latitude": f"{latitude:.8f}",
               "longitude": f"{longitude:.8f}",
               "altitude(m)": f"{alturavoo:.1f}",
               "heading(deg)": f"{angulo:.0f}",
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
               "photo_timeinterval": time_interval,
               "photo_distinterval": dist_interval}

            # Escrever a linha no CSV
            writer.writerow(data)


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

def verificar_plugins(plugins_list, feedback=None): # Não está sendo usada
    # Obter a lista de todos os plugins instalados
    installed_plugins = qgis.utils.plugins.keys()

    plugins_not_installed = [plugin for plugin in plugins_list if plugin not in installed_plugins]

    # Se houver plugins não instalados, levantar erro
    if plugins_not_installed:
       raise Exception(f"❌ The following plugins are not installed: {', '.join(plugins_not_installed)}")
    else:
       feedback.pushInfo(f"✅ All plugins are installed: {plugins_list}")

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
      raise Exception(f"❌ Layer must be WGS84 or SIRGAS2000 or UTM. Other ({descricao_crs_layer.upper()}, EPSG:{epsg_code_layer}) not supported")

   crs_utm = QgsCoordinateReferenceSystem(f"EPSG:{epsg_code}")
   feedback.pushInfo(f"✅ Reprojecting to CRS EPSG:{epsg_code} - {crs_utm.description()}")

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
      hVooS = my_settings.value("qgis-drone-flight-planner/hVooS", 100)
      ab_groundS = my_settings.value("qgis-drone-flight-planner/ab_groundS", True)
      sensorH = my_settings.value("qgis-drone-flight-planner/sensorH", 13.2) # Air 2S
      sensorV = my_settings.value("qgis-drone-flight-planner/sensorV", 8.8)
      dFocal = my_settings.value("qgis-drone-flight-planner/dFocal", 8.38)
      sLateral = my_settings.value("qgis-drone-flight-planner/sLateral", 0.75)
      sFrontal = my_settings.value("qgis-drone-flight-planner/sFrontal", 0.85)
      velocHs = my_settings.value("qgis-drone-flight-planner/velocHs", 8)
      tStayHs = my_settings.value("qgis-drone-flight-planner/tStayHs", 0)
   elif tipoVoo == "H_Manual":
      hVooM = my_settings.value("qgis-drone-flight-planner/hVooM", 100)
      ab_groundM = my_settings.value("qgis-drone-flight-planner/ab_groundM", True)
      dl_manualH = my_settings.value("qgis-drone-flight-planner/dl_manualH", 10)
      df_op = my_settings.value("qgis-drone-flight-planner/df_op", 0)
      df_manualH = my_settings.value("qgis-drone-flight-planner/df_manualH", 10)
      velocHm = my_settings.value("qgis-drone-flight-planner/velocHm", 8)
      tStayHm = my_settings.value("qgis-drone-flight-planner/tStayHm", 0)
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

   #skml = my_settings.value("qgis-drone-flight-planner/skml", "")
   sCSV = my_settings.value("qgis-drone-flight-planner/sCSV", "")

   if tipoVoo == "H_Sensor":
      return hVooS, ab_groundS, sensorH, sensorV, dFocal, sLateral, sFrontal, velocHs, tStayHs, sCSV
   elif tipoVoo == "H_Manual":
      return hVooM, ab_groundM, dl_manualH, df_op, df_manualH, velocHm, tStayHm, sCSV
   elif tipoVoo == "VF":
      return hFac, altMinVF, dl_manualVF, df_manualVF, velocVF, tStayVF, sCSV
   elif tipoVoo == "VC":
      return hObj, altMinVC, nPartesVC, dVertVC, velocVC, tStayVC, sCSV

def saveParametros(tipoVoo, h, v, t, sCSV, ab_ground=None, sensorH=None, sensorV=None, dFocal=None, sLateral=None, sFrontal=None, dl=None, dfop=None, df=None, alt_min=None, nPartesVC=None):
   my_settings = QgsSettings()

   if tipoVoo == "H_Sensor":
      my_settings.setValue("qgis-drone-flight-planner/hVooS", h)
      my_settings.setValue("qgis-drone-flight-planner/ab_groundS", ab_ground)
      my_settings.setValue("qgis-drone-flight-planner/sensorH", sensorH)
      my_settings.setValue("qgis-drone-flight-planner/sensorV", sensorV)
      my_settings.setValue("qgis-drone-flight-planner/dFocal", dFocal)
      my_settings.setValue("qgis-drone-flight-planner/sLateral", sLateral)
      my_settings.setValue("qgis-drone-flight-planner/sFrontal", sFrontal)
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
      my_settings.setValue("qgis-drone-flight-planner/altMinVF", alt_min)
      my_settings.setValue("qgis-drone-flight-planner/dl_manualVF", dl)
      my_settings.setValue("qgis-drone-flight-planner/df_manualVF", df)
      my_settings.setValue("qgis-drone-flight-planner/velocVF", v)
      my_settings.setValue("qgis-drone-flight-planner/tStayVF", t)
   elif tipoVoo == "VC":
      my_settings.setValue("qgis-drone-flight-planner/hObj", h)
      my_settings.setValue("qgis-drone-flight-planner/altMinVC", alt_min)
      my_settings.setValue("qgis-drone-flight-planner/nPartesVC", nPartesVC)
      my_settings.setValue("qgis-drone-flight-planner/dVertVC", dl)
      my_settings.setValue("qgis-drone-flight-planner/velocVC", v)
      my_settings.setValue("qgis-drone-flight-planner/tStayVC", t)

   #my_settings.setValue("qgis-drone-flight-planner/skml", skml)
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
