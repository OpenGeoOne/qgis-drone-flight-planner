# -*- coding: utf-8 -*-

"""
/***************************************************************************
 Flight Planner - A QGIS plugin

 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-11-05
        copyright            : (C) 2024 by Prof Cazaroli e Leandro França
        email                : contato@geoone.com.br
 ****************************************************************************/
"""

__author__ = 'Prof Cazaroli e Leandro França'
__date__ = '2024-11-05'
__copyright__ = '(C) 2024 by Prof Cazaroli e Leandro França'
__revision__ = '$Format:%H$'

import os
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

# Importa os algoritmos
from .algoritmos.PlanoVoo_H_Sensor import PlanoVoo_H_Sensor
from .algoritmos.PlanoVoo_H_Manual import PlanoVoo_H_Manual
from .algoritmos.PlanoVoo_H_Manual_RC2_Controler import PlanoVoo_H_Manual_RC2_Controler
from .algoritmos.PlanoVoo_V_F import PlanoVoo_V_F
from .algoritmos.PlanoVoo_V_C import PlanoVoo_V_C

class PlanoVooProvider(QgsProcessingProvider):
    def __init__(self):
        super().__init__()

    def unload(self):
        pass

    def loadAlgorithms(self):
        self.addAlgorithm(PlanoVoo_H_Manual())
        self.addAlgorithm(PlanoVoo_H_Manual_RC2_Controler())
        self.addAlgorithm(PlanoVoo_H_Sensor())
        self.addAlgorithm(PlanoVoo_V_C())
        self.addAlgorithm(PlanoVoo_V_F())

    def id(self):
        return 'GeoFlightPlanner'

    def name(self):
        return self.tr('GeoFlight Planner')

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), 'images', 'FlightPlanner.png'))

    def longName(self):
        return self.name()
