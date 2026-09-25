# Fuentes externas normalizadas

Deposita aquí copias CSV descargadas de las fuentes oficiales, sin alterar sus
valores. La normalización de encabezados se hace en una copia de trabajo o
mediante un adaptador reproducible; el CSV entregado al pipeline debe tener
estos campos.

Para población: cve_ent, cve_mun, año, poblacion.

Para incidencia delictiva: cve_ent, cve_mun, año, delitos_fuero_comun.

Cada año y combinación de claves debe aparecer sólo una vez. La población
estatal y la incidencia estatal se calculan como suma de las filas municipales
de la misma entidad y año. Usa cve_mun 000 solamente si la fuente lo requiere,
pero no lo combines con filas municipales para evitar doble conteo.

Los CSV de datos se ignoran en Git. El JSON de salida conserva su hash,
proveedor y campos utilizados.

## API de INEGI para población

Como alternativa al CSV de CONAPO, el pipeline puede consultar el indicador
INEGI 1002000001, Población total, para el municipio y su entidad. Define el
token sólo en el entorno y ejecuta:

    export INEGI_TOKEN
    python3 scripts/ejecutar_pipeline.py --inegi-population --cve-ent 00 --cve-mun 000

La corrida guarda las respuestas JSON originales, con fecha y hash, en esta
carpeta. Estos archivos están ignorados por Git. El JSON del diagnóstico sólo
registra URL con token redactado, metadatos, años y hashes. No se acepta un
token como argumento de línea de comandos, archivo de configuración ni dato
de salida.

La serie de Población total puede tener únicamente años censales. Se usan
exclusivamente los años que INEGI entrega; no se interpolan años faltantes ni
se combinan automáticamente con las proyecciones de CONAPO. Si los años de un
indicador no están cubiertos, dicho indicador permanece pendiente de revisión.
