from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterField,
    QgsProcessingParameterFile,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSink,
    QgsProcessingException,
    QgsField,
    QgsFeature,
    QgsPoint,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
    QgsFields,
    QgsProcessing
)
from qgis import processing
from qgis.PyQt.QtCore import QVariant, QCoreApplication
import csv
import os

class ExtractSelectedFeaturesToCSV(QgsProcessingAlgorithm):
    INPUT_POINT_LAYER = 'INPUT_POINT_LAYER'
    INPUT_FID_FIELD = 'INPUT_FID_FIELD'
    INPUT_CSV_FILE = 'INPUT_CSV_FILE'
    OUTPUT_CSV_NAME = 'OUTPUT_CSV_NAME'
    OUTPUT_LAYER = 'OUTPUT_LAYER'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ExtractSelectedFeaturesToCSV()

    def name(self):
        return 'extractselectedfeaturestocsv'

    def displayName(self):
        return self.tr('Extrair Feições Selecionadas para CSV')

    def group(self):
        return self.tr('Script Customizado')

    def groupId(self):
        return 'customscripts'

    def shortHelpString(self):
        return self.tr("Extrai feições selecionadas de uma camada de pontos para um arquivo CSV e cria uma camada temporária 3D para conferência.")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_POINT_LAYER,
                self.tr('Camada de pontos'),
                types=[QgsProcessing.TypeVectorPoint],
                defaultValue=None
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.INPUT_FID_FIELD,
                self.tr('Campo de índice ou fid'),
                parentLayerParameterName=self.INPUT_POINT_LAYER,
                type=QgsProcessingParameterField.Numeric,
                allowMultiple=False,
                defaultValue=None
            )
        )

        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_CSV_FILE,
                self.tr('Arquivo CSV de entrada'),
                behavior=QgsProcessingParameterFile.File,
                extension='csv',
                defaultValue=None
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.OUTPUT_CSV_NAME,
                self.tr('Nome do novo arquivo CSV (sem extensão)'),
                multiLine=False,
                defaultValue='output'
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LAYER,
                self.tr('Camada de saída (temporária)'),
                QgsProcessing.TypeVectorPoint
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        point_layer = self.parameterAsVectorLayer(parameters, self.INPUT_POINT_LAYER, context)
        fid_field_name = self.parameterAsString(parameters, self.INPUT_FID_FIELD, context)
        csv_file = self.parameterAsString(parameters, self.INPUT_CSV_FILE, context)
        output_csv_name = self.parameterAsString(parameters, self.OUTPUT_CSV_NAME, context)

        # Validação
        num_features = point_layer.featureCount()

        with open(csv_file, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            records = [row for row in reader if row]  # Ignorar linhas vazias

        num_records = len(records)

        feedback.pushInfo(self.tr(f"Número de feições na camada: {num_features}"))
        feedback.pushInfo(self.tr(f"Número de registros válidos no CSV (sem contar cabeçalho e linhas vazias): {num_records}"))

        if num_features != num_records:
            feedback.pushInfo(self.tr(f"ERRO: Número de feições ({num_features}) não corresponde ao número de registros válidos no CSV ({num_records})."))
            return {}

        # Obter feições selecionadas
        selected_features = point_layer.selectedFeatures()
        if not selected_features:
            raise QgsProcessingException(self.tr("Nenhuma feição selecionada. Selecione as feições antes de continuar."))

        selected_fids = [feature[fid_field_name] for feature in selected_features]
        feedback.pushInfo(self.tr(f"Feições selecionadas: {', '.join(map(str, selected_fids))}"))

        # Extrair registros correspondentes usando o fid como índice da linha (subtraindo 1)
        selected_records = []
        for fid in selected_fids:
            if 1 <= fid <= len(records):
                selected_records.append(records[fid - 1])

        # Salvar novo CSV
        new_csv_path = os.path.join(os.path.dirname(csv_file), f"{output_csv_name}.csv")
        with open(new_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(selected_records)

        feedback.pushInfo(self.tr(f"Novo arquivo CSV salvo em: {new_csv_path}"))

        # Criar camada de pontos temporária 3D (PointZ)
        temp_layer = QgsVectorLayer("PointZ?crs=EPSG:4326", "Temporary Points 3D", "memory")
        provider = temp_layer.dataProvider()

        # Adicionar campos
        new_fields = QgsFields()
        for field_name in header:
            new_fields.append(QgsField(field_name, QVariant.String))
        provider.addAttributes(new_fields)
        temp_layer.updateFields()

        # Ler e adicionar features
        with open(new_csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lon = float(row['longitude'])
                    lat = float(row['latitude'])
                    alt = float(row['altitude(m)'])

                    point = QgsPoint(lon, lat, alt)
                    feature = QgsFeature()
                    feature.setGeometry(QgsGeometry.fromPoint(point))

                    attrs = [row[field] for field in header]
                    feature.setAttributes(attrs)
                    provider.addFeature(feature)
                except Exception as e:
                    feedback.pushInfo(self.tr(f"Erro ao processar registro: {e}"))
                    continue  # Ignorar registros com valores inválidos

        temp_layer.updateExtents()
        QgsProject.instance().addMapLayer(temp_layer)
        feedback.pushInfo(self.tr("Camada de pontos 3D temporária criada com sucesso."))

        # Salvar feições selecionadas
        output_layer_path = os.path.join(os.path.dirname(csv_file), f"{output_csv_name}_selected_features.shp")
        processing.run("native:saveselectedfeatures", {
            'INPUT': point_layer,
            'OUTPUT': output_layer_path
        })
        feedback.pushInfo(self.tr(f"Feições selecionadas salvas em: {output_layer_path}"))

        return {self.OUTPUT_LAYER: temp_layer.id()}
