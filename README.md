# Estudio de seguridad municipal · v2 / metodología 2.3

El pipeline llena el capítulo SEGURIDAD del formato de la consultora con una interpretación escrita de las estadísticas municipales. Produce un único documento: **`{municipio} Estudio Seguridad.docx`**. La redacción relaciona los hallazgos con sus implicaciones y recomendaciones; las calificaciones se sustentan en el benchmark del proyecto.

Los tres documentos de referencia tienen funciones distintas:

| Documento en `templates/` | Función |
| --- | --- |
| `Machote general medicion version final.docx` | Formato de la consultora y orden del estudio final. |
| `Machote general medicion version final rzg investigación.docx` | Guía para interpretar los apartados y definir las variables. |
| `Machote_seguridad_general_con_calificacion.docx` | Benchmark de evaluación: 18 fichas, 90 criterios, escala y candados. |

La base operativa [seguridad_medicion.docx](templates/seguridad_medicion.docx) se deriva de esos documentos y tiene **25 variables de texto**. Se conservan el formato y la guía de la consultora. El benchmark interno incorpora un anexo de integración 2.3 que declara los cambios respecto de las fichas históricas. No se entrega al cliente ese documento interno.

## Preparar un municipio

En `input/word/` se requiere `{municipio} PAQUETE SEGURIDAD.docx`. Puede acompañarse de `{municipio} Anexo.docx`, que permite contrastar información e incorporar sus gráficas originales cuando esté disponible. El municipio debe coincidir en ambos nombres.

```sh
python3 -m pip install -r requirements.txt
python3 scripts/validar_plantilla.py
python3 scripts/ejecutar_pipeline.py --preparar --estado "Nombre del estado"
```

La lectura del texto incrustado en las gráficas utiliza Tesseract instalado en el equipo. En macOS: `brew install tesseract tesseract-lang`; en Debian/Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-spa`. Se prefiere español y se usa inglés si español no está disponible. Si falta el motor o una imagen no puede leerse, la preparación registra el aviso y conserva las tablas; las aclaraciones que dependan de esa imagen quedan pendientes.

`--preparar` genera `output/json/{slug}_evidencia_seguridad.json` con estadísticas, correspondencias documentadas, calificaciones y un catálogo de gráficas existentes. El estado debe quedar identificado por la documentación o declararse expresamente cuando falte el Anexo.

Para la revisión actual de Apodaca, ejecutar `python3 scripts/ejecutar_pipeline.py --preparar --complemento input/complementos/apodaca.json`. El complemento conserva los CSV municipales del CNGMD y la población censal 2020 consultada al INEGI. Las tasas recientes usan esa población sólo como **base fija de referencia**, no como población observada en 2022 o 2024. El token de la API permanece en `.env` e ignorado por Git; los archivos municipales y las fuentes descargadas permanecen en `input/`, también ignorados.

La ficha 18 puede reunir datos de CNGMD y SESNSP, pero requiere procedencia por campo y conciliación expresa antes de calificarse. El descubrimiento y la auditoría opcionales de CSV del SESNSP están descritos en [recolección de datos](RECOLECCION_DATOS.md); no se consultan ni incorporan cifras externas durante la ejecución ordinaria.

El programa reconoce lo que los títulos, las columnas y el texto de las gráficas de Seguridad permiten establecer y lo relaciona con los parámetros generales. La lectura de imágenes conserva texto, procedencia y huella; aclara conceptos sin sustituir las cifras de las tablas ni ampliar los años indicados en el título. No exige una confirmación manual para cada celda. Los datos de cada municipio proceden de `input/`; el material recibido en `new-elements`, fuera del repositorio, aporta criterios generales, no estadísticas municipales. Sus reglas incorporadas se conservan en `config/`.

Un agente editorial o una persona redacta y revisa `input/redaccion/{slug}.json`. Este archivo contiene los dos resúmenes, los 18 análisis, la bibliografía y la selección de ilustraciones. Cada párrafo remite a hechos verificables; las fuentes y el benchmark quedan vinculados por sus huellas. No se necesita una API key. Un nuevo municipio o una fuente modificada requiere una nueva interpretación revisada.

```sh
python3 scripts/ejecutar_pipeline.py --estado "Nombre del estado"
```

Opciones principales:

- `--input` y `--output`: carpetas de entradas y salidas.
- `--redaccion`: ubicación alternativa de la interpretación editorial.
- `--complemento input/complementos/{slug}.json`: evidencia opcional para resolver denominadores y ambigüedades que no aclara el paquete; véase [recolección](RECOLECCION_DATOS.md). No requiere volver a declarar lo ya reconocido ni autoriza buscar cifras externas automáticamente.
- `--esquema dimensiones_ponderadas|dimensiones_iguales|global`: ponderación principal o comparación explícita; la principal es 25/35/40.
- `--calificacion disponibles|evaluables|completo`: valoración con los puntajes acreditados, umbrales de cobertura mayores o evaluación estricta de los 18 indicadores.
- `--graficas originales|ninguna`: reutilizar las ilustraciones seleccionadas de los documentos fuente o entregar sólo texto.

Los valores predeterminados son `disponibles` y `originales`. Las gráficas se importan sin redibujarlas; no se agregan tablas ni se construyen nuevas gráficas. Una selección editorial omite imágenes incoherentes con las tablas o innecesarias para la explicación.

## Evaluación y presentación

La [metodología](METODOLOGIA.md) distingue las dos ediciones censales recientes para los indicadores 1–16 de los dos años recientes para 17–18. Los datos desconocidos conservan `null`.

El modo predeterminado `disponibles` calcula una categoría con los indicadores que sí tienen puntaje acreditado: exige al menos uno por dimensión y uno prioritario, conserva pesos y candados, y muestra «COBERTURA PARCIAL» cuando hay pendientes. Una valoración provisional no entra al promedio; los faltantes siguen en `null`. La nota del Word declara la cobertura y advierte que la categoría puede cambiar. `evaluables` mantiene el umbral más exigente de 2/3, 5/7 y 6/8 por dimensión y seis de los ocho prioritarios; `completo` exige 18 puntajes. Si ni siquiera el modo disponible tiene cobertura básica, el estudio se publica sin categoría conjunta. `--preparar` permite revisar la evidencia sin sustituir el Word anterior.

Las definiciones 2.4.3, dentro de la integración 2.3, distinguen dato explícito, homologación y lectura condicional. Por ejemplo, el título «Certificado Único Policial vigente» permite reconocer ese porcentaje bajo la definición adoptada. Una gráfica que dice «aprobó las evaluaciones» aclara la aprobación, aunque no acredita vigencia; «cámaras en funcionamiento» aclara el estado de los equipos, aunque sigue haciendo falta población para calcular tasas. Las valoraciones provisionales de capacitación o continuidad de llamadas describen lo disponible, sin completar artificialmente la cobertura. Cada decisión conserva sus referencias; las lecturas de imágenes y las evaluaciones se recalculan antes de renderizar.

La interpretación editorial debe actualizarse a 2.3 y revisarse de nuevo: cambiar sólo sus huellas no basta. El catálogo recibido aporta encuadres y ejemplos, no análisis municipales terminados ni los 144 cierres anunciados. No se requiere un servicio de IA. La consulta opcional al Banco de Indicadores del INEGI sí requiere el token local; la preparación ordinaria usa los archivos conservados y no hace llamadas de red.

La entrega usa Archivo, el logo de la consultora, el formato editorial solicitado y ningún resaltado amarillo. Los títulos de 24 pt tienen interlineado mínimo de 14 pt para evitar recortes. Las gráficas originales conservan los textos y tipografías incrustados en sus imágenes; cambiarlos exigiría redibujarlas. El documento visible no contiene instrucciones, nombres de archivos internos ni referencias a una versión de trabajo.

## Salidas y mantenimiento

```text
output/word/{municipio} Estudio Seguridad.docx
output/json/{slug}_diagnostico_seguridad_municipal.json
output/json/{slug}_estudio_seguridad_renderizado.json
```

`{municipio}` conserva su nombre legible; `{slug}` usa minúsculas, sin acentos y con guiones bajos. Una generación exitosa publica esos tres artefactos y limpia las salidas anteriores. Si falla la preparación o la sustitución, se conserva o restaura la entrega previa. Entradas, redacción municipal y salidas se excluyen de Git.

Si cambian los documentos de referencia, revisar sus modificaciones y regenerar en este orden:

```sh
python3 scripts/actualizar_benchmark_v23.py
python3 scripts/estructurar_reglas.py
python3 scripts/migrar_machotes_v2.py
python3 scripts/validar_plantilla.py
python3 -m unittest discover -s tests -v
```

La documentación detallada está en [PIPELINE.md](PIPELINE.md), [METODOLOGIA.md](METODOLOGIA.md) y [ESTILO_REDACCION.md](ESTILO_REDACCION.md). El [diagrama editable](flujo_pipeline.drawio) describe el flujo y sus controles.
