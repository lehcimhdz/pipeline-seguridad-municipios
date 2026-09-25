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
