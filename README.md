# Pipeline de seguridad municipal

Genera el diagnóstico municipal de seguridad a partir de cuatro documentos
Word por municipio.

Estado actual: extracción de tablas y cálculo de doce indicadores para ambos
periodos con los datos Word y generación de un Word de revisión con el contenido
del JSON resaltado en amarillo. Las 18 fichas y sus 90 criterios están en
[reglas_calificacion.json](reglas_calificacion.json). La versión final requiere
datos completos y revisión editorial resuelta.

Instala la dependencia del renderizador (Python 3.11+):

    python3 -m pip install -r requirements.txt

Para ejecutar extracción, cálculos, JSON y Word de revisión:

    python3 scripts/ejecutar_pipeline.py

El comando genera archivos nuevos en `output/json/` y `output/word/`. El Word
lleva la leyenda **BORRADOR DE REVISIÓN**, incluye las tablas fuente de los
18 indicadores y señala las puntuaciones pendientes sin inventarlas. Un
recibo JSON vincula ambos archivos mediante SHA-256 y registra la comprobación
del resaltado amarillo. Usa `--word ninguno` para obtener sólo el JSON.

Para renderizar un JSON existente, ya compuesto por la versión actual:

    python3 scripts/renderizar_word.py output/json/{archivo}.json --modo borrador

Tras resolver los pendientes y validar el JSON, `--modo final` exige ambas
calificaciones completas, coherencia de cálculos y ninguna revisión abierta.
El renderizador rechaza JSON antiguos sin `contenido_word`; deben regenerarse.

Las equivalencias de temas, uniformes y equipo están versionadas en
[config/normalizaciones.json](config/normalizaciones.json). Las fuentes
externas requeridas y su formato están en
[config/fuentes_externas.json](config/fuentes_externas.json).

La población para los indicadores 4 y 14 puede ingresarse como CSV de CONAPO
o consultarse desde la API oficial del Banco de Indicadores de INEGI. Esta
segunda vía se activa sólo con `--inegi-population` y el secreto de entorno
`INEGI_TOKEN`; el token nunca se guarda ni se muestra en las salidas. La API
aporta únicamente los años que publica: el pipeline no interpola ni mezcla
esa serie con proyecciones.

La especificación de entradas, extracción, validación, salidas y renderizado
está en [PIPELINE.md](PIPELINE.md).

El diccionario JSON es el contrato de datos del machote. Cada clave de
variables_documento usa el marcador canónico {{ clave_json }} y declara el
número de veces que debe aparecer en la plantilla.

La plantilla no se modifica durante una ejecución. Sus 62 variables canónicas
permiten insertar contenido específico por contexto. Cada ejecución genera un
JSON trazable en output/json/. El Word se guarda en output/word/; toda inserción
desde JSON lleva resaltado amarillo, verificado al volver a abrir el DOCX.

Para comprobar que el contrato entre el diccionario y el machote no se alteró:

    python3 scripts/validar_plantilla.py

Los marcadores entre corchetes de la plantilla están declarados en
marcadores_no_tratados_como_variables. En la copia de salida se completan los
selectores de puntaje y se excluye el material editorial del perfil elegido;
no se considera resuelta una verificación por haber excluido su texto.
