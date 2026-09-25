# Pipeline de seguridad municipal

Genera el diagnóstico municipal de seguridad a partir de cuatro documentos
Word por municipio.

Estado actual: extracción de tablas y cálculo de doce indicadores para ambos
periodos con los datos Word. Las 18 fichas y sus 90 criterios están en
[reglas_calificacion.json](reglas_calificacion.json). La composición del Word
final continúa pendiente.

Para ejecutar la extracción y los cálculos disponibles:

    python3 scripts/ejecutar_pipeline.py

Las equivalencias de temas, uniformes y equipo están versionadas en
[config/normalizaciones.json](config/normalizaciones.json). Las fuentes
externas requeridas y su formato están en
[config/fuentes_externas.json](config/fuentes_externas.json).

La especificación de entradas, extracción, validación, salidas y renderizado
está en [PIPELINE.md](PIPELINE.md).

El diccionario JSON es el contrato de datos del machote. Cada clave de
variables_documento usa el marcador canónico {{ clave_json }} y declara el
número de veces que debe aparecer en la plantilla.

La plantilla no se modifica durante una ejecución. Sus 62 variables canónicas
permiten insertar contenido específico por contexto. Cada ejecución genera un
JSON trazable en output/json/. El destino previsto del Word terminado es
output/word/; toda inserción desde JSON deberá llevar resaltado amarillo.

Para comprobar que el contrato entre el diccionario y el machote no se alteró:

    python3 scripts/validar_plantilla.py

Los marcadores entre corchetes que permanecen en el Word son instrucciones
editoriales, selectores de puntaje o notas de verificación. Están declarados en
marcadores_no_tratados_como_variables y no se sustituyen como datos.
