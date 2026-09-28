"""Añade un anexo interno versionado sin sustituir el formato de la consultora."""
import json
import zipfile
from lxml import etree as ET
from migrar_machotes_v2 import ROOT, BENCHMARK, W, paragraph, save
from editorial import configurar

TAG = 'integracion_metodologica_2_3'


def actualizar():
    definitions = json.loads((ROOT / 'config/definiciones_cngmd.json').read_text(encoding='utf-8'))
    weights = json.loads((ROOT / 'config/ponderacion.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(BENCHMARK) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    root = ET.fromstring(files['word/document.xml'])
    body = root.find(W + 'body')
    for node in list(body):
        tag = node.find('./' + W + 'sdtPr/' + W + 'tag')
        if tag is not None and tag.get(W + 'val') == TAG:
            body.remove(node)
    block = ET.Element(W + 'sdt')
    properties = ET.SubElement(block, W + 'sdtPr')
    ET.SubElement(properties, W + 'tag').set(W + 'val', TAG)
    content = ET.SubElement(block, W + 'sdtContent')
    def add(text, heading=False):
        content.append(configurar(paragraph(text), 'medicion', 'subcapitulo' if heading else 'cuerpo'))
    add('Anexo 3. Integración metodológica 2.3', True)
    add('Este anexo prevalece sobre los criterios históricos incompatibles del cuerpo anterior. Conserva 18 indicadores y escala de 1 a 5. Las nuevas convenciones son decisiones de integración del equipo, no estándares externos verificados. Es material interno; no se entrega con el estudio municipal.')
    add('Ponderación y cobertura', True)
    add('Protección civil: 25%; condiciones del personal: 35%; inteligencia y eficiencia policial: 40%. Dentro de cada dimensión, los indicadores 2, 4, 5, 10, 11, 12, 13 y 14 pesan 2; los restantes pesan 1. Sólo entran al promedio puntajes observados y acreditados.')
    add('Cobertura mínima: 2 de 3, 5 de 7 y 6 de 8 indicadores por dimensión, además de seis de los ocho prioritarios. El modo completo requiere los dieciocho. Con pendientes, el máximo es MUY BIEN. Un universo no aplicable requiere una metodología específica y bloquea la calificación conjunta; no equivale a incumplimiento.')
    for item in weights['candados_adicionales']:
        add('Candado ' + str(item['id']) + ': ' + item['condicion'] + ' ' +
            item.get('requisito', item.get('efecto', ' '.join(item.get('requisitos', [])))))
    add('Definición de la evidencia', True)
    add('Cada confirmación requiere fuente conservada con huella, año, localizador y revisión. Los manuales censales describen variables, pero no acreditan por sí solos qué variable se copió al paquete municipal. No se asigna 1 por una celda vacía. Los candados de falta de respuesta requieren acreditar esa causa.')
    add('Las correspondencias explícitas se resuelven automáticamente desde las entradas, conservando regla y coordenadas. El título Certificado Único Policial vigente y su porcentaje publicado permiten homologar la ficha 7 con la definición general, sin reconstruir denominadores ni declarar una verificación externa. No se exige un complemento para repetir lo ya identificado; las ambigüedades y contradicciones se conservan para revisión.')
    add('Personal: utilizar corporaciones policiales, sin administrativos, en las tasas; el denominador es población documentada por año. Una plantilla menor de 15 limita la ficha 4 a 4. Control de confianza: aprobatorias vigentes; CUP: vigente. Capacitación: no confundir con profesionalización ni sumar participantes duplicados. La capacitación de protección civil distingue personal de la unidad de cursos a la población.')
    add('Equipo: cantidades asignadas al cierre, no compras anuales; cámaras: en servicio. Población municipal y estatal de la misma serie, fecha y método para comparaciones. Puestas a disposición: separar MP de justicia cívica y dividir entre incidencia comparable, no población. El máximo requiere revisión documentada de derechos humanos y uso de la fuerza; una razón superior al doble estatal no obtiene 5.')
    for key, label in (('proteccion_civil', 'Ficha 3. Cobertura temática'), ('llamadas', 'Ficha 15. Registro y respuesta')):
        scale = definitions['escalas_operativas'][key]
        add(label, True)
        add(scale['descripcion'])
        for score, text in sorted(scale['niveles'].items(), reverse=True):
            add('Nivel ' + score + ': ' + text + '.')
        add(scale['origen'])
    add('Valoración provisional y revisión editorial', True)
    add('Una apreciación provisional se conserva separada del puntaje, con base y confianza. No aumenta cobertura ni estrecha el intervalo extremo de 1 a 5; el escenario intermedio, cuando puede calcularse, no es un resultado observado. El texto exige lectura de los datos y revisión semántica; no se asignan párrafos automáticamente según el color. Los 144 cierres anunciados no se recibieron y no forman parte del catálogo disponible.')
    add('Capacitación policial: dos o más grupos núcleo positivos en la edición reciente permiten nivel indicativo 3; uno permite 2. Los rótulos equivalentes cuentan una vez y nunca se suman asistentes entre cursos. La falta de un tema no prueba ausencia. En llamadas, dos cortes recientes con conteos permiten nivel indicativo 3 de continuidad de la serie, condicionado a confirmar competencia y universo, con confianza baja. No acredita operación municipal ni eficacia de atención. Son lecturas provisionales, no puntajes imputados.')
    section = body.find(W + 'sectPr')
    body.insert(list(body).index(section) if section is not None else len(body), block)
    files['word/document.xml'] = ET.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
    save(BENCHMARK, files)


if __name__ == '__main__':
    actualizar()
    print('Benchmark interno actualizado con anexo 2.3; formato y guía de la consultora sin cambios.')
