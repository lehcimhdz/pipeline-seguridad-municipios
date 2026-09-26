# Pipeline de seguridad municipal · contrato v2

## Alcance y fuentes

Se llena exclusivamente SEGURIDAD. Las entradas siguen siendo los cuatro DOCX
en `input/word/`, con el mismo prefijo municipal:

    {nombre_municipio} Anexo.docx
    {nombre_municipio} PAQUETE SEGURIDAD.docx
    {nombre_municipio} PAQUETE GOBIERNO ABIERTO Y BUEN GOBIERNO.docx
    {nombre_municipio} PAQUETE DESARROLLO URBANO SOSTENIBLE Y DERECHOS HUMANOS CONEXOS.docx

La carpeta es cambiante. El prefijo identifica el municipio y el contenido del
Anexo confirma identidad y estado. Se exige un archivo por sufijo; las cuatro
fuentes quedan identificadas con SHA-256 en el JSON. PAQUETE SEGURIDAD es la
fuente primaria de los 18 indicadores; el Anexo sirve de control cruzado. Los
otros dos paquetes aportan evidencia contextual, sin sustituir una observación
de seguridad. No se inventan datos para resolver discrepancias o faltantes.

## Machotes y migración

Los machotes generales recibidos son:

- `templates/Machote general medicion version final.docx`.
- `templates/Machote general anexos version final.docx`.

La migración normaliza sólo sus capítulos SEGURIDAD y deriva las bases
operativas `templates/seguridad_medicion.docx` y `templates/seguridad_anexo.docx`.
Las bases contienen portada, logo original de InstitutionWorks y SEGURIDAD.
El resto de los ejes de los originales se conserva. La plataforma electoral
queda fuera del pipeline.

La sección original de medición duplicaba el indicador de personal y omitía
Certificado Único Policial. Se corrige usando el catálogo de los 18 indicadores:
personal es el 4, evaluaciones el 5, instituto el 6 y CUP el 7. La corrección
se registra en el contrato. El calificativo IDEAL de la tabla general no
redefine la categoría EXCELENTE ni los umbrales de la metodología de seguridad.

Tras recibir una nueva revisión de los machotes generales:

    python3 scripts/migrar_machotes_v2.py
    python3 scripts/validar_plantilla.py

La migración actualiza ambas bases, el diccionario, las reglas y los hashes del
contrato. `normalizar_plantilla.py` y `contextualizar_variables.py` delegan en
ella por compatibilidad. Se debe revisar el diff editorial y metodológico antes
de aceptar una nueva versión. El pipeline de un municipio nunca modifica estos
activos de referencia.

## Contrato y variables

[config/contrato_documental.json](config/contrato_documental.json) registra
versiones, alcance, rutas, orden de indicadores y hashes de las bases,
diccionario, reglas, formato y fuentes. El JSON municipal incorpora esas
huellas. El renderizador rechaza resultados de versiones anteriores o activos
que cambien sin actualizar el contrato.

Los marcadores usan llaves simples: `{snake_case}`, con nombres ASCII y sin
espacios. El diccionario declara el tipo y las apariciones por documento:
116 variables y 137 apariciones entre medición y anexo. Se validan sobre el texto
de los párrafos, aun cuando Word fragmente un marcador en varios segmentos.

| Marcador | Tipo JSON | Uso |
| --- | --- | --- |
| `{municipio}`, `{estado}` | string | Identidad de ambos documentos. |
| `{calificacion_general}`, `{calificacion_ultimo_periodo}` | string | Categorías calculadas; PENDIENTE en borrador incompleto. |
| `{resumen_general}`, `{resumen_ultimo_periodo}` | string | Párrafos descriptivos por periodo. |
| `{analisis_indicador_01}`…`{analisis_indicador_18}` | string | Análisis específicos, con criterio, cobertura y evidencia. |
| `{cierre_indicador_01}`…`{cierre_indicador_18}` | string | Párrafo que cierra el análisis y las visualizaciones. |
| `{graficas_indicador_01}`…`{graficas_indicador_18}` | array | Especificaciones de gráficas nativas Word. |
| `{tablas_indicador_01}`…`{tablas_indicador_18}` | array | Tablas originales de ambos ámbitos en medición. |
| `{tablas_estatales_indicador_01}`…`{tablas_estatales_indicador_18}` | array | Tablas estatales del anexo. |
| `{tablas_municipales_indicador_01}`…`{tablas_municipales_indicador_18}` | array | Tablas municipales del anexo. |
| `{tabla_calificaciones}` | array | Puntajes de los 18 indicadores y ambos periodos, en el anexo. |
| `{bibliografia}` | string | Identificación de las fuentes efectivamente utilizadas. |

Las instrucciones `[INSERTAR ANÁLISIS E INTERCALAR GRÁFICAS Y/O TABLAS]` se
descomponen en párrafos separados con análisis, gráficas, tablas y cierre del
indicador correspondiente. No se reutiliza una variable genérica `{analisis}`
en 18 contextos diferentes. Los saltos reales de párrafo se almacenan como
`\n\n` en el JSON; no se inserta la cadena literal `/n`.

Las tablas son listas de objetos con `titulo`, `filas`, `ambito` y
`tabla_fuente`. El renderizador comprueba que sus filas y ámbitos coincidan con
la evidencia. Las gráficas contienen `tipo: puntajes`, `titulo`, `categorias`,
`valores` y `fuente`; sus valores deben coincidir con las evaluaciones. Un valor
null se omite de la gráfica y se explica como pendiente, nunca como cero. Si
ningún periodo tiene puntaje, la lista de gráficas está vacía. Esta versión no
genera automáticamente series de datos brutos: categorías, unidades y campos
comparables deben definirse antes de añadir otro tipo de gráfica.

## Flujo y salidas

El diagrama editable está en [flujo_pipeline.drawio](flujo_pipeline.drawio).

    4 Word → validar identidad → extraer evidencia → normalizar y calificar
           → componer variables → JSON municipal → medición + anexo
           → auditar formato y amarillo → recibos → limpiar salidas anteriores

    output/json/{municipio}_diagnostico_seguridad_municipal_{corrida}.json
    output/word/{municipio}_seguridad_medicion_{modo}.docx
    output/word/{municipio}_seguridad_anexo_{modo}.docx
    output/json/{municipio}_seguridad_medicion_{modo}_renderizado.json
    output/json/{municipio}_seguridad_anexo_{modo}_renderizado.json

La composición queda registrada en `contenido_word`, perfil `seguridad_v2`.
Incluye la hoja de cómputo y promedios auditables en JSON, sin reintroducir las
antiguas fichas como contenido editorial de los nuevos documentos.

Después de publicar las salidas solicitadas, se conservan únicamente el JSON
fuente vigente, los Word y sus recibos. Se eliminan permanentemente los JSON y
DOCX previos de esas carpetas, que son destinos exclusivos del pipeline. Un
error antes de completar el renderizado impide la limpieza. Las publicaciones
individuales son atómicas; el conjunto de dos Word y dos recibos no es una
transacción indivisible: si falla el segundo documento, se conserva el JSON y
se informa el error. Los bloqueos temporales `~$` se omiten y Word los administra.
No se admiten ejecuciones simultáneas sobre la misma carpeta de salida.

Los recibos vinculan JSON, Word, modo, perfil y contrato mediante SHA-256 y
registran la auditoría de las inserciones. Las salidas y entradas municipales
están ignoradas por Git.

## Manual editorial

[config/formato_editorial.json](config/formato_editorial.json) define los dos
perfiles. Archivo Regular corresponde a la familia `Archivo`, estilo regular.
Los cuatro TTF oficiales se incluyen con licencia OFL en `assets/fonts/` y se
incrustan completos en los DOCX. Un visor que ignore incrustaciones necesita
tener instaladas las fuentes para reproducir el diseño exactamente.

| Elemento | Medición: fuente / tamaño / interlineado | Anexo: fuente / tamaño / interlineado |
| --- | --- | --- |
| Título principal | Archivo Regular · 26 / 40 pt | Archivo Regular · 30 / 36 pt |
| Capítulo o rubro | Archivo Light · 24 / 14 pt | Archivo Light · 24 / 14 pt |
| Subcapítulo o indicador | Archivo Light · 24 / 14 pt | Archivo Light · 18 / 16 pt |
| Cuerpo | Archivo Light · 12 / 16 pt | Archivo Light · 9 / 10 pt |
| Calificación | Archivo Light · 9 / 10 pt | Archivo Light · 9 / 10 pt |
| Encabezado de tabla | Archivo Medium · 12 / 14 pt | Archivo Medium · 11 / 14 pt |
| Contenido de tabla | Archivo Light · 11 / 14 pt | Archivo Light · 9 / 10 pt |
| Tabla de años y porcentajes | Formato de tabla de medición | Medium/Light · 12 / 14 pt |
| Notas | Archivo Light · 9 / 11 pt | Archivo Light · 9 / 10 pt |
| Bibliografía | Archivo Light/Italic · 12 / 16 pt | Archivo Light/Italic · 12 / 16 pt |

Las portadas centran título e identidad; el logo original se coloca centrado en
la parte baja, con 5 cm de ancho y altura proporcional. Capítulos y categorías
usan altas; cuerpo y subcapítulos conservan altas y bajas. El contenido usa una
columna, cero separación entre párrafos y sangría de 5 mm salvo el párrafo
inicial. Las notas se alinean a la izquierda, las tablas se centran y las
calificaciones aplican el color de su categoría.

Los interlineados inferiores al tamaño de la fuente en títulos se interpretan
como mínimos (por ejemplo, título 24 pt con mínimo de 14 pt) para evitar
superposición y recorte. Cuerpo, notas y tablas mantienen el interlineado fijo
del manual. Las gráficas tienen espacio propio que puede crecer con el objeto.
Sus títulos y ejes usan Archivo Medium 12 pt, categorías Medium 9 pt y datos
Archivo Light 9 pt. Los valores pendientes no aparecen como barras de altura cero.

Cada inserción textual desde JSON lleva estilo `ContenidoJSON`, resaltado
`yellow` y sombreado `FFFF00`, incluidos encabezados y celdas de tablas. Las
gráficas usan texto DrawingML y fondo amarillo para marcar el objeto completo. El contenido fijo del machote
conserva su formato. Se reabre el DOCX para comprobar marcadores pendientes,
fuentes editoriales y resaltado.

## Ejecución y revisión

    python3 scripts/ejecutar_pipeline.py
    python3 scripts/renderizar_word.py output/json/{archivo}.json --modo borrador

El pipeline genera ambos documentos por defecto. El renderizador independiente
permite `--documento medicion`, `--documento anexo` o `--documento ambos`.
Cada comando conserva sólo las salidas solicitadas de esa ejecución.
`--word ninguno` produce sólo JSON y elimina los Word y recibos anteriores.

El borrador indica `requiere_revision`, explica faltantes y muestra PENDIENTE
sin asignar una calificación global parcial. Para `--modo final`, se exige
`estado_ejecucion: validado`, los 18 puntajes en ambos periodos, agregaciones
coherentes, todas las variables requeridas y ausencia de validaciones
bloqueantes o de revisión. Cambiar sólo el estado no basta. Quitar una
validación sin resolver su evidencia no constituye revisión; el sistema no
acredita automáticamente la suficiencia de una justificación humana.

    python3 -m unittest discover -s tests -v

## Reglas de calificación y fuentes externas

Los nuevos machotes no contienen fichas ni criterios numéricos. La transcripción
histórica se conserva en `config/metodologia_seguridad.json`; sus coordenadas
remiten al antiguo documento indicado en `fuente_historica`, disponible en el
historial Git. `reglas_calificacion.json` registra el hash de esa transcripción.
Se mantienen 18 fichas, 90 criterios, tres dimensiones, ambos periodos, umbrales,
dependencias y candados. Su preservación no acredita vigencia normativa externa.

    python3 scripts/estructurar_reglas.py
    python3 scripts/migrar_machotes_v2.py

`scripts/calificar.py` calcula existencia, cursos, temas, porcentajes de
evaluación/CUP y llamadas, usando `config/normalizaciones.json`. Aplica las
dependencias 3→2, 6→10 y 12→11; no interpola huecos ni confunde una celda vacía
con ausencia de respuesta municipal. Los ajustes discrecionales requieren
revisión y una extensión metodológica explícita.

Los indicadores 4 y 14 requieren población; el 18, incidencia delictiva. Los
contratos externos siguen en `config/fuentes_externas.json`. CSV normalizados
pueden aportarse desde `input/datos_externos/`:

    python3 scripts/ejecutar_pipeline.py \
      --population-csv input/datos_externos/poblacion_municipal.csv \
      --incidence-csv input/datos_externos/incidencia_delictiva_municipal.csv \
      --cve-ent 00 --cve-mun 000

La población puede consultarse opcionalmente a INEGI (indicador 1002000001):

    export INEGI_TOKEN
    python3 scripts/ejecutar_pipeline.py --inegi-population --cve-ent 00 --cve-mun 000

El token sólo se lee del entorno, se oculta de la procedencia y nunca se guarda
en Git. Las respuestas originales quedan en la carpeta ignorada de datos
externos. No se combinan CSV de población y API en una corrida; sólo se usan
años publicados sin interpolar. La ejecución con los cuatro Word funciona sin
token. Las fuentes externas mantienen proveedor, huella y campos usados.

Pueden seguir pendientes 4, 8, 9, 14, 17 y 18 según la evidencia recibida.
Uniformes/equipo requieren resolver cobertura; fallecimientos vacíos necesitan
clasificación explícita. Las decisiones humanas siguen el formato de
`input/revision/README.md`. El cambio de machotes no resuelve esos faltantes.
