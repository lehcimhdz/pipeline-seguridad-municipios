# Estudio de seguridad municipal · v2 / metodología 2.3

El pipeline llena el capítulo SEGURIDAD del formato de la consultora con una interpretación escrita de las estadísticas municipales. Produce **`{municipio} Estudio Seguridad.docx`** y, mediante `--plataforma-electoral`, también **`{municipio} Plataforma Electoral Seguridad.docx`**. La redacción relaciona los hallazgos con sus implicaciones y recomendaciones; las calificaciones se sustentan en el benchmark del proyecto.

Los tres documentos de referencia tienen funciones distintas:

| Documento en `templates/` | Función |
| --- | --- |
| `Machote general medicion version final.docx` | Formato de la consultora y orden del estudio final. |
| `Machote general medicion version final rzg investigación.docx` | Guía para interpretar los apartados y definir las variables. |
| `Machote_seguridad_general_con_calificacion.docx` | Benchmark de evaluación: 18 fichas, 90 criterios, escala y candados. |

La base operativa [seguridad_medicion.docx](templates/seguridad_medicion.docx) se deriva de esos documentos y tiene **25 variables de texto**. Se conservan el formato y la guía de la consultora. El benchmark interno incorpora un anexo de integración 2.3 que declara los cambios respecto de las fichas históricas. No se entrega al cliente ese documento interno.

El apartado 2. Seguridad de la plataforma electoral se deriva del [machote electoral recibido](templates/PLATAFORMA%20ELECTORAL%20MACHOTE.docx) en una [base separada](templates/seguridad_plataforma_electoral.docx). Tiene [once variables de contenido](config/variables_plataforma_electoral_seguridad.json): introducción y cinco campos para cada inciso, «a. Protección Civil» y «b. Seguridad», además de reutilizar municipio y estado. La base añade «Fuentes clave» al final, construidas sólo con las referencias efectivamente citadas del [catálogo verificado](config/fuentes_plataforma_electoral_seguridad.json). El PDF de Cuernavaca es una referencia de estructura y tono, no una fuente de cifras o propuestas para otros municipios.

Para reconstruir la base electoral desde el Word original: `python3 scripts/crear_plantilla_electoral.py`. El generador comprueba la huella del machote recibido y la presencia y orden de ambos incisos.

## Preparar un municipio

En `input/word/` se requiere `{municipio} PAQUETE SEGURIDAD.docx`. Puede acompañarse de `{municipio} Anexo.docx`, que permite contrastar información e incorporar sus gráficas originales cuando esté disponible. El municipio debe coincidir en ambos nombres.

```sh
python3 -m pip install -r requirements.txt
python3 scripts/validar_plantilla.py
python3 scripts/ejecutar_pipeline.py --preparar --estado "Nombre del estado"
```

La lectura del texto incrustado en las gráficas utiliza Tesseract instalado en el equipo. En macOS: `brew install tesseract tesseract-lang`; en Debian/Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-spa`. Se prefiere español y se usa inglés si español no está disponible. Si falta el motor o una imagen no puede leerse, la preparación registra el aviso y conserva las tablas; las aclaraciones que dependan de esa imagen quedan pendientes.

`--preparar` genera `output/json/{slug}_evidencia_seguridad.json` con estadísticas, correspondencias documentadas, calificaciones y un catálogo de gráficas existentes. El estado debe quedar identificado por la documentación o declararse expresamente cuando falte el Anexo.

Cuando un municipio requiere evidencia adicional, preparar con `--complemento input/complementos/{slug}.json`. Las fuentes descargadas y el complemento permanecen en `input/`, fuera de Git. Si se utiliza población censal de 2020 como base fija para tasas recientes, debe declararse expresamente: no es población observada en cada año posterior. El token opcional de la API permanece en `.env`, también ignorado por Git.

La ficha 18 exige personas ante el Ministerio Público del mismo universo y año en municipio y estado, y poblaciones comparables para calcular tasas por cien mil habitantes. La incidencia delictiva del SESNSP sólo sirve de contexto: no es el denominador del puntaje. El descubrimiento y la auditoría opcionales de CSV están descritos en [recolección de datos](docs/RECOLECCION_DATOS.md); no se consultan ni incorporan cifras externas durante la ejecución ordinaria.

El programa reconoce lo que los títulos, las columnas y el texto de las gráficas de Seguridad permiten establecer y lo relaciona con los parámetros generales. La lectura de imágenes conserva texto, procedencia y huella; aclara conceptos sin sustituir las cifras de las tablas ni ampliar los años indicados en el título. No exige una confirmación manual para cada celda. Los datos de cada municipio proceden de `input/`; el material recibido en `new-elements`, fuera del repositorio, aporta criterios generales, no estadísticas municipales. Sus reglas incorporadas se conservan en `config/`.

Un agente editorial o una persona redacta y revisa `input/redaccion/{slug}.json`. Este archivo contiene los dos resúmenes, los 18 análisis, la bibliografía y la selección de ilustraciones. Cada párrafo remite a hechos verificables; las fuentes y el benchmark quedan vinculados por sus huellas. No se necesita una API key. Un nuevo municipio o una fuente modificada requiere una nueva interpretación revisada.

Para producir también la plataforma electoral, redactar y revisar `input/redaccion_electoral/{slug}.json` con las once variables del apartado, los indicadores que respaldan cada una, las huellas de los Word municipales y la huella de la evaluación. Cada argumento que use una norma, un marco internacional o investigación debe declarar sus IDs en `referencias` e incluir su cita en el texto; el programa añade las referencias APA al final. Comprueba esos vínculos y rechaza citas no declaradas, marcadores o cifras no acreditadas. El Marco de Sendai se identifica como referente internacional, no como tratado; las investigaciones sobre patrullaje o cámaras no se presentan como prueba de resultados municipales. La plataforma se publica junto con el estudio sólo si ambos documentos pasan sus comprobaciones.

```sh
python3 scripts/ejecutar_pipeline.py --estado "Nombre del estado"
python3 scripts/ejecutar_pipeline.py --estado "Nombre del estado" --plataforma-electoral
```

Opciones principales:

- `--input` y `--output`: carpetas de entradas y salidas.
- `--redaccion`: ubicación alternativa de la interpretación editorial.
- `--complemento input/complementos/{slug}.json`: evidencia opcional para resolver denominadores y ambigüedades que no aclara el paquete; véase [recolección](docs/RECOLECCION_DATOS.md). No requiere volver a declarar lo ya reconocido ni autoriza buscar cifras externas automáticamente.
- `--esquema dimensiones_ponderadas|dimensiones_iguales|global`: ponderación principal o comparación explícita; la principal es 25/35/40.
- `--calificacion disponibles|evaluables|completo`: valoración con los puntajes acreditados, umbrales de cobertura mayores o evaluación estricta de los 18 indicadores.
- `--graficas originales|ninguna`: reutilizar las ilustraciones seleccionadas de los documentos fuente o entregar sólo texto.
- `--plataforma-electoral`: producir además el apartado electoral de Seguridad; `--redaccion-electoral` permite indicar otro archivo de interpretación revisada.

Los valores predeterminados son `disponibles` y `originales`. Las gráficas se importan sin redibujarlas; no se agregan tablas ni se construyen nuevas gráficas. Una selección editorial omite imágenes incoherentes con las tablas o innecesarias para la explicación.

## Evaluación y presentación

La [metodología](docs/METODOLOGIA.md) distingue las dos ediciones censales recientes para los indicadores 1–16 de los dos años recientes para 17–18. Los datos desconocidos conservan `null`.

El modo predeterminado `disponibles` calcula una categoría con los indicadores que sí tienen puntaje acreditado: exige al menos uno por dimensión y uno prioritario, conserva pesos y candados, y muestra «COBERTURA PARCIAL» cuando hay pendientes. Una valoración provisional no entra al promedio; los faltantes siguen en `null`. La nota del Word declara la cobertura y advierte que la categoría puede cambiar. `evaluables` mantiene el umbral más exigente de 2/3, 5/7 y 6/8 por dimensión y seis de los ocho prioritarios; `completo` exige 18 puntajes. Si ni siquiera el modo disponible tiene cobertura básica, el estudio se publica sin categoría conjunta. `--preparar` permite revisar la evidencia sin sustituir el Word anterior.

Las definiciones integradas 2.5, dentro de la ponderación 2.3, distinguen dato explícito, homologación y lectura condicional. Por ejemplo, el título «Certificado Único Policial vigente» permite reconocer ese porcentaje bajo la definición adoptada. Una gráfica que dice «aprobó las evaluaciones» aclara la aprobación, aunque no acredita vigencia; «cámaras en funcionamiento» aclara el estado de los equipos, aunque sigue haciendo falta población para calcular tasas. Las valoraciones provisionales de capacitación o continuidad de llamadas describen lo disponible, sin completar artificialmente la cobertura. Cada decisión conserva sus referencias; las lecturas de imágenes y las evaluaciones se recalculan antes de renderizar.

La interpretación editorial debe actualizarse a 2.3 y revisarse de nuevo: cambiar sólo sus huellas no basta. El catálogo recibido aporta encuadres y ejemplos, no análisis municipales terminados ni los 144 cierres anunciados. No se requiere un servicio de IA. La consulta opcional al Banco de Indicadores del INEGI sí requiere el token local; la preparación ordinaria usa los archivos conservados y no hace llamadas de red.

La entrega usa Archivo, el logo de la consultora, el formato editorial solicitado y ningún resaltado amarillo. Los títulos de 24 pt tienen interlineado mínimo de 14 pt para evitar recortes. Las gráficas originales conservan los textos y tipografías incrustados en sus imágenes; cambiarlos exigiría redibujarlas. El documento visible no contiene instrucciones, nombres de archivos internos ni referencias a una versión de trabajo.

## Salidas y mantenimiento

```text
output/word/{municipio} Estudio Seguridad.docx
output/word/{municipio} Plataforma Electoral Seguridad.docx  (con --plataforma-electoral)
output/json/{slug}_diagnostico_seguridad_municipal.json
output/json/{slug}_estudio_seguridad_renderizado.json
output/json/{slug}_plataforma_electoral_seguridad.json  (con --plataforma-electoral)
output/json/{slug}_plataforma_electoral_renderizado.json  (con --plataforma-electoral)
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

La documentación detallada está en [PIPELINE.md](docs/PIPELINE.md), [METODOLOGIA.md](docs/METODOLOGIA.md) y [ESTILO_REDACCION.md](docs/ESTILO_REDACCION.md). El [diagrama editable](docs/diagramas/flujo_pipeline.drawio) describe el flujo y sus controles.

## Organización del repositorio

- `docs/`: uso del pipeline, metodología, escritura, recolección y diagrama.
- `config/`: contrato, reglas, diccionario de datos y parámetros generales.
- `templates/`: originales de consulta y base operativa del Word; sus rutas no cambian.
- `scripts/` y `tests/`: implementación y pruebas automatizadas.
- `input/` y `output/`: evidencia municipal y entregables, excluidos de Git.
- `assets/fonts/`: tipografías Archivo y su licencia.

Los comandos de esta guía se ejecutan desde la raíz del repositorio.
