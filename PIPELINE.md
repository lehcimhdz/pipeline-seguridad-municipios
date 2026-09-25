# Especificación del pipeline de seguridad municipal

## Propósito

Para un municipio, el pipeline recibe cuatro documentos Word, extrae evidencia
para los 18 indicadores de seguridad, construye un JSON trazable con base en
diccionario_datos_diagnostico_seguridad_municipal.json y genera el diagnóstico
terminado desde templates/Machote_seguridad_general_con_calificacion.docx.

El diccionario y el machote son activos de referencia: no se sobrescriben al
procesar un municipio.

## Entradas

Los cuatro archivos viven en input/word/ y comparten exactamente el mismo
prefijo de municipio:

    {nombre_municipio} Anexo.docx
    {nombre_municipio} PAQUETE SEGURIDAD.docx
    {nombre_municipio} PAQUETE GOBIERNO ABIERTO Y BUEN GOBIERNO.docx
    {nombre_municipio} PAQUETE DESARROLLO URBANO SOSTENIBLE Y DERECHOS HUMANOS CONEXOS.docx

La carpeta de entrada cambia en cada ejecución. El nombre del municipio se toma
del prefijo común; el estado se extrae del contenido, nunca se infiere del
nombre de archivo.

Antes de extraer, el agente debe detenerse con un error claro si falta un
archivo, existe más de un archivo para alguno de los cuatro sufijos, los
prefijos no coinciden o un archivo no es un DOCX legible.

### Prioridad de fuentes

| Fuente | Uso en el pipeline |
| --- | --- |
| PAQUETE SEGURIDAD | Fuente primaria para los 18 indicadores, sus series, calificaciones y comparaciones. |
| Anexo | Control cruzado de identidad municipal, periodo, calificaciones y resultados resumidos. |
| PAQUETE DESARROLLO URBANO… | Contexto para riesgos, desastres o protección civil; no sustituye un dato del paquete de seguridad. |
| PAQUETE GOBIERNO ABIERTO… | Contexto institucional; no sustituye un indicador de seguridad. |

Cuando haya una discrepancia, se conserva la evidencia de ambos documentos, se
prefiere el PAQUETE SEGURIDAD para el dato del indicador y se marca el caso
para revisión. El agente no debe inventar un valor para resolverla.

## Flujo

    input/word (4 DOCX)
            |
            +-- 1. Validar conjunto y detectar municipio
            +-- 2. Extraer párrafos, tablas, encabezados y evidencia
            +-- 3. Normalizar y calcular indicadores/calificaciones
            +-- 4. Validar contra el diccionario y la evidencia
            +-- 5. Escribir JSON trazable
            +-- 6. Componer y renderizar el Word final
                     |
                     +-- output/json/{municipio}_diagnostico_seguridad_municipal.json
                     +-- output/word/{municipio}_diagnostico_seguridad_municipal.docx

### 1. Extracción

El agente debe conservar, para cada dato usado, la fuente, el indicador, una
referencia localizable (página, tabla, encabezado o fragmento) y el texto o
valor original. Debe leer tablas además de párrafos. Si una gráfica o imagen
contiene el único dato disponible, se registra como evidencia visual y se
marca para revisión en lugar de estimar su valor.

### 2. Normalización y cálculo

Se aplican las reglas ya definidas en el diccionario:

- 18 indicadores y 3 dimensiones.
- Calificación general y del último periodo.
- Tratamiento de datos faltantes, candados y ajustes.
- Variables narrativas sólo cuando están respaldadas por evidencia.

Las elecciones de texto, por ejemplo comparacion_con_periodo_completo, deben
tomar uno de los valores permitidos en el diccionario. Si no hay evidencia
suficiente, el campo queda sin resolver y el estado de la ejecución es
requiere_revision; no se genera un Word final como si estuviera validado.

### 3. JSON de salida

El archivo en output/json/ es una instancia municipal del contrato, no una
modificación del diccionario base. Debe incluir, como mínimo:

    {
      "version": "1.0",
      "municipio": "{nombre_municipio}",
      "estado_ejecucion": "validado",
      "fuentes": [
        {
          "archivo": "{nombre_municipio} PAQUETE SEGURIDAD.docx",
          "sha256": "..."
        }
      ],
      "valores_plantilla": {
        "municipio": "{nombre_municipio}",
        "año_inicial": 2014,
        "comparacion_con_periodo_completo": "igual"
      },
      "indicadores": {},
      "calculos": {},
      "evidencia": {},
      "validaciones": []
    }

valores_plantilla contiene una clave por cada una de las 62 variables de
variables_documento; se usa directamente para sustituir {{ clave_json }}. Los
objetos indicadores, calculos, evidencia y validaciones conservan la
trazabilidad necesaria para auditar esas decisiones.

Antes de guardarlo, el pipeline valida tipos, opciones permitidas, campos
obligatorios, las 120 apariciones del machote y la ausencia de valores
inventados. El JSON se escribe de forma atómica para no dejar resultados
parciales.

### 4. Word de salida

El renderizador crea una copia del machote y sólo la copia se guarda en
output/word/. Sustituye los marcadores {{ clave_json }} usando
valores_plantilla. Todo texto, cifra, tabla o bloque que se incorpore desde el
JSON debe conservar el formato tipográfico circundante y llevar resaltado
amarillo. El resaltado identifica con claridad el contenido generado para su
revisión editorial; no se aplica al texto preexistente del machote.

El machote actual también contiene guía de calificación, textos alternativos e
instrucciones editoriales entre corchetes. Por ello el renderizado final tiene
dos partes:

1. Sustituir variables y conservar formato.
2. Seleccionar únicamente los textos que correspondan a la calificación y
   evidencia del municipio; eliminar instrucciones editoriales y alternativas
   no elegidas.

Un documento no se considera final mientras contenga un marcador {{ ... }},
una instrucción [borrar al finalizar], una nota [Verificar ...] sin resolver,
una variante incompatible con los datos o contenido incorporado desde el JSON
sin resaltado amarillo. Esas condiciones deben quedar en validaciones y
bloquear la salida final.

## Controles operativos

- El proceso debe ejecutarse para un solo municipio por corrida.
- Las salidas nunca reemplazan otra corrida; se usa el nombre de municipio y,
  si hace falta, una marca de tiempo o identificador de ejecución.
- Cada archivo de entrada se identifica con SHA-256 en el JSON de salida.
- Los cambios al diccionario o al machote se validan con el comando siguiente:

      python3 scripts/validar_plantilla.py

- La revisión humana es obligatoria cuando hay conflicto de fuentes, datos
  faltantes relevantes, evidencia sólo visual, ajustes de puntuación o notas
  de verificación pendientes.

## Ejecución disponible

El comando de prevalidación y extracción inicial recibe la carpeta input/word/
por defecto:

    python3 scripts/ejecutar_pipeline.py

Valida los cuatro DOCX, identifica municipio y estado, registra las huellas
SHA-256 y conserva párrafos y tablas con coordenadas de bloque, tabla y fila.
Extrae los 18 indicadores, compara sus tablas con el Anexo y calcula por
separado el periodo general y el reciente en los casos implementados.

Cada corrida escribe un archivo nuevo con municipio e identificador de
ejecución; conserva las salidas anteriores. Los años se extraen de las tablas
y se registra la cobertura de cada indicador. Las calificaciones reportadas
en la fuente se conservan separadas de las calculadas. La ausencia de una
calificación reciente en la fuente no constituye un bloqueo: se calcula a
partir de los datos cuando el criterio lo permite.

El JSON incluye las tablas originales de los cuatro documentos para auditar
la extracción. Todavía no extrae contenido exclusivo de imágenes o gráficas.

El renderizador todavía está pendiente de implementación. Su contrato exige
JSON validado y resaltado amarillo para toda inserción, conforme a la sección
Word de salida. Las corridas actuales conservan estado requiere_revision.

## Reglas de calificación versionadas

[reglas_calificacion.json](reglas_calificacion.json) contiene las 18 fichas y
los 90 criterios de puntuación transcritos del Anexo 1, con coordenadas en el
DOCX, datos requeridos, precauciones y hash del documento fuente. Estas reglas
reproducen la metodología interna; no acreditan vigencia normativa externa.

Para regenerarlo tras una revisión del documento base:

    python3 scripts/estructurar_reglas.py

El motor de scripts/calificar.py interpreta las condiciones estructuradas
del JSON. Automatiza existencia (1, 6, 11, 12, 13 y 16), cursos (2),
temas de protección civil (3), porcentajes de evaluación y CUP (5 y 7),
temas de capacitación policial (10) y llamadas procedentes (15). Las
dependencias 3→2, 6→10 y 12→11 se aplican antes de agregar resultados.

Las equivalencias están en config/normalizaciones.json: temas núcleo,
prendas básicas, categorías de equipamiento y frecuencias. Cada patrón puede
revisarse y cambiarse sin editar el motor. Para preservar evidencia, el JSON
de salida registra temas o comparaciones que llevaron al puntaje.

La agregación exige los 18 puntajes: promedia por dimensión y después entre
las tres dimensiones, aplicando los candados generales 1–4. Los ajustes por
dato dudoso son decisiones del evaluador y no se aplican automáticamente.
La composición narrativa y su comprobación de divergencia entre periodos
siguen pendientes.

Criterios operativos explícitos de esta implementación:

- Se conserva precisión decimal interna y se clasifica el promedio agregado
  con redondeo ROUND_HALF_UP a dos decimales. Es una concreción técnica de la
  propuesta de redondeo del diccionario y debe constar al revisar el método.
- Los rangos individuales se interpretan literalmente. No se rellenan huecos
  entre umbrales ni se decide un puntaje cuando ninguna condición coincide.
- En los indicadores binarios, existencia anterior con ausencia en las dos
  observaciones recientes aplica el criterio 2 antes del de intermitencia.
- Una celda vacía requiere clasificar la causa; no equivale automáticamente
  a cero, falta de respuesta o inexistencia de la variable.
- Se seleccionan las dos etiquetas temporales más recientes observadas sin
  saltar vacíos. Debe confirmarse la relación entre edición y año de referencia,
  así como la cobertura de las ediciones ausentes, antes de cerrar el informe.

Pruebas reproducibles de umbrales, faltantes, dependencias, fuentes externas
y candados:

    python3 -m unittest discover -s tests -v

## Siguiente paso técnico

## Fuentes externas y decisiones de revisión

Los indicadores 4 y 14 requieren población; el 18 requiere incidencia
delictiva. Sus contratos se encuentran en config/fuentes_externas.json.
El proceso no descarga silenciosamente ni transforma una base oficial: se
deposita la descarga original normalizada en input/datos_externos/ y se pasa
en la corrida:

    python3 scripts/ejecutar_pipeline.py \
      --population-csv input/datos_externos/poblacion_municipal.csv \
      --incidence-csv input/datos_externos/incidencia_delictiva_municipal.csv \
      --cve-ent 00 --cve-mun 000

Cada CSV debe tener los campos de su contrato. El JSON final registra
proveedor, página oficial, ruta local, hash y campos utilizados. Las fuentes
son CONAPO para población municipal y SESNSP para incidencia delictiva.

Las celdas vacías, datos dudosos y excepciones se resuelven sólo mediante el
archivo JSON descrito en input/revision/README.md. Una decisión debe señalar
indicador, año, clasificación, justificación y coordenadas de evidencia. Sin
esa decisión una celda vacía sigue bloqueando el indicador.

## Siguiente paso técnico

Completar los indicadores 4, 14 y 18 al ingresar sus CSV externos; completar
el 8 y 9 con una decisión explícita sobre cobertura de la dotación e
inventario; y resolver los vacíos de fallecimientos del 17 mediante revisión.
No se declara ausente un dato sólo porque su extracción aún no esté implementada.

Después corresponde componer los análisis con evidencia, seleccionar las
variantes narrativas y completar el renderizador con verificación del resaltado
amarillo. Las variables de variantes descartadas no deben exigirse como si
fueran campos obligatorios del informe final.
