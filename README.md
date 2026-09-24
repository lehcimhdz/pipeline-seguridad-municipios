# Pipeline de seguridad municipal

Genera el diagnóstico municipal de seguridad a partir de cuatro documentos
Word por municipio.

La especificación de entradas, extracción, validación, salidas y renderizado
está en [PIPELINE.md](PIPELINE.md).

El diccionario JSON es el contrato de datos del machote. Cada clave de
variables_documento usa el marcador canónico {{ clave_json }} y declara el
número de veces que debe aparecer en la plantilla.

La plantilla no se modifica durante una ejecución. Sus 62 variables canónicas
permiten insertar contenido específico por contexto. Para cada municipio se
genera un JSON trazable en output/json/ y un Word terminado en output/word/.

Para comprobar que el contrato entre el diccionario y el machote no se alteró:

    python3 scripts/validar_plantilla.py

Los marcadores entre corchetes que permanecen en el Word son instrucciones
editoriales, selectores de puntaje o notas de verificación. Están declarados en
marcadores_no_tratados_como_variables y no se sustituyen como datos.
