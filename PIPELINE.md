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
                     +-- output/json/{municipio}_diagnostico_seguridad_municipal_{corrida}.json
                     +-- output/word/{municipio}_diagnostico_seguridad_municipal_{corrida}_{modo}_{id}.docx
                     +-- output/json/{municipio}_diagnostico_seguridad_municipal_{corrida}_renderizado.json

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

El modo `borrador` permite revisar resultados incompletos en un Word claramente
identificado. Se escribe «Pendiente» para un puntaje no calculado y se conserva
la explicación de su causa. Esta salida no cambia el estado `requiere_revision`
ni autoriza una calificación global parcial.

### Perfil editorial implementado

El perfil `diagnostico_desde_evidencia` utiliza los marcadores de resumen y
los 18 análisis específicos para componer prosa descriptiva a partir de los
resultados. Los bloques genéricos de alternativas se descartan en favor de
esa prosa. La selección queda registrada en `contenido_word.decision_editorial`.

La copia de salida incluye:

- Identidad y periodo documental, calificaciones general y reciente.
- Resumen de ambos periodos y hoja de cómputo completa.
- Las 18 secciones del documento base, sus benchmarks, puntajes y análisis.
- Tablas municipales y estatales originales, con ámbito y número de tabla.
- Pendientes de revisión en el borrador y el Anexo 1 metodológico.

Se excluyen la guía de captura, textos alternativos genéricos, variantes de
producto de gobierno/electoral, bancos de fuentes sugeridas y Anexo 2. La
exclusión es una decisión de alcance editorial, no una validación de referencias
o una resolución de las notas que contenían. La revisión de criterios y
referencias conservados en el Anexo 1 sigue siendo obligatoria antes del cierre.

`valores_plantilla` conserva las 62 claves del contrato: las variantes
descartadas pueden quedar en null y se enumeran en
`contenido_word.variables_no_aplicables`. Sólo las variables activas bloquean
el renderizado final. Los resúmenes y análisis automáticos describen puntajes,
criterios y evidencia; no deducen causalidad ni vigencia jurídica.

Se conserva la tipografía y el énfasis del contexto en las sustituciones. Los
párrafos compuestos y las tablas ajustan espaciado y alineación en la copia
para facilitar la lectura. El renderer soporta marcadores fragmentados entre
segmentos de Word, escapa caracteres XML y resalta todo texto nuevo procedente
del JSON, incluidas las celdas y sus encabezados. Los segmentos generados usan
el estilo `ContenidoJSON` y resaltado directo `yellow`; una reapertura del
DOCX comprueba esos atributos y la ausencia de marcadores pendientes.

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

    python3 -m pip install -r requirements.txt

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

El comando genera por defecto un Word de revisión (`--word borrador`).
`--word ninguno` conserva el uso de extracción y JSON sin cargar el renderizador.
Las corridas de extracción mantienen `requiere_revision` hasta resolver las
revisiones de evidencia, cobertura temporal y composición editorial.

Para renderizar nuevamente un JSON compuesto, sin repetir la extracción:

    python3 scripts/renderizar_word.py output/json/{archivo}.json --modo borrador

Para emitir la versión final desde un JSON revisado:

    python3 scripts/renderizar_word.py output/json/{archivo_validado}.json --modo final

El cierre requiere `estado_ejecucion: validado`, ausencia de validaciones de
nivel `bloqueante` o `revision`, 18 puntajes por periodo, ambas calificaciones
completas y variables activas resueltas. El renderizador recalcula la agregación
y contrasta la hoja de cómputo y los promedios; también exige que los hashes de
plantilla, diccionario y reglas correspondan al contrato actual. Cambiar sólo
el estado no habilita una versión final con puntajes faltantes.

La revisión debe corregir o resolver cada hallazgo en una nueva copia del JSON,
con evidencia y justificación conservadas; quitar una validación sin resolver
su causa no constituye una revisión. El sistema no verifica automáticamente
la suficiencia de esa justificación humana. Los ajustes metodológicos especiales
requieren extender primero el motor y su auditoría; el renderer no acepta
agregaciones que difieran del cálculo vigente.

Cada renderizado crea un DOCX nuevo sin sobrescribir la plantilla ni salidas
anteriores. Su recibo `*_renderizado.json` registra el hash del JSON fuente
exacto, el del Word, modo, perfil, plantilla y auditoría de resaltado. El JSON
fuente conserva `salida_word.modo_solicitado` y la ruta del recibo esperado;
el recibo sólo existe al completar el Word correctamente. En el comando
independiente el recibo usa el nombre único del Word y se informa en consola.
Esto evita modificar el JSON después de calcular su hash. Los JSON de versiones
anteriores sin `contenido_word` deben regenerarse con el pipeline actual.

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
La composición descriptiva ya está implementada. La explicación causal de
divergencias entre periodos continúa siendo una revisión editorial respaldada
por evidencia.

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

## Fuentes externas y decisiones de revisión

Los indicadores 4 y 14 requieren población; el 18 requiere incidencia
delictiva. Sus contratos se encuentran en config/fuentes_externas.json. La
población puede provenir de un CSV trazable de CONAPO o, de forma explícita,
de la API oficial del Banco de Indicadores de INEGI. La incidencia delictiva
continúa teniendo como fuente primaria al SESNSP.

Para CSV, se deposita la descarga original normalizada en
input/datos_externos/ y se pasa en la corrida:

    python3 scripts/ejecutar_pipeline.py \
      --population-csv input/datos_externos/poblacion_municipal.csv \
      --incidence-csv input/datos_externos/incidencia_delictiva_municipal.csv \
      --cve-ent 00 --cve-mun 000

Cada CSV debe tener los campos de su contrato. El JSON final registra
proveedor, página oficial, ruta local, hash y campos utilizados. Las fuentes
son CONAPO para población municipal y SESNSP para incidencia delictiva.

### Población mediante la API de INEGI

La alternativa INEGI consulta la serie histórica de `1002000001` (Población
total) para la clave municipal de cinco dígitos y para su entidad. El token es
un secreto de entorno, no un parámetro del comando ni un archivo del proyecto:

    export INEGI_TOKEN
    python3 scripts/ejecutar_pipeline.py \
      --inegi-population \
      --cve-ent 00 --cve-mun 000

Cada respuesta original se conserva en `input/datos_externos/`, carpeta
ignorada por Git. El JSON de salida registra indicador, área geográfica,
metadatos de serie, fecha, años y SHA-256; la URL se conserva con el token
redactado. Una corrida rechaza combinar `--inegi-population` y
`--population-csv`, pues mezclar una serie censal con proyecciones requiere
una conciliación metodológica documentada.

La API puede devolver sólo años censales. El motor usa únicamente años
publicados por INEGI y no interpola ni proyecta; por tanto, los indicadores 4
y 14 siguen pendientes cuando faltan años que aparecen en sus tablas fuente.

Las celdas vacías, datos dudosos y excepciones se resuelven sólo mediante el
archivo JSON descrito en input/revision/README.md. Una decisión debe señalar
indicador, año, clasificación, justificación y coordenadas de evidencia. Sin
esa decisión una celda vacía sigue bloqueando el indicador.

## Siguiente paso técnico

Completar los indicadores 4, 14 y 18 al ingresar sus CSV externos; completar
el 8 y 9 con una decisión explícita sobre cobertura de la dotación e
inventario; y resolver los vacíos de fallecimientos del 17 mediante revisión.
No se declara ausente un dato sólo porque su extracción aún no esté implementada.

Después corresponde resolver la revisión de evidencia y referencias para
cerrar los diagnósticos finales. La composición descriptiva y el renderizador
con resaltado amarillo ya permiten revisar el flujo completo mediante un
borrador. Las variables de variantes descartadas no se exigen como campos
obligatorios del informe final.
