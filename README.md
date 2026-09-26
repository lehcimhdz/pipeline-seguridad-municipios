# Pipeline de seguridad municipal · v2

Los cuatro Word de `input/word/` siguen siendo las fuentes. El pipeline llena
exclusivamente SEGURIDAD y publica dos documentos: medición y anexo.

    python3 -m pip install -r requirements.txt
    python3 scripts/validar_plantilla.py
    python3 scripts/ejecutar_pipeline.py

Las bases operativas son [seguridad_medicion.docx](templates/seguridad_medicion.docx)
y [seguridad_anexo.docx](templates/seguridad_anexo.docx), derivadas de los nuevos
machotes generales. Las variables usan llaves simples y `snake_case` ASCII:
`{municipio}`, `{estado}`, `{analisis_indicador_01}`, `{graficas_indicador_01}`
y `{tablas_indicador_01}`. Hay 116 variables y 137 apariciones entre ambas bases.

El [contrato documental](config/contrato_documental.json) vincula las plantillas,
el [diccionario](diccionario_datos_diagnostico_seguridad_municipal.json), las
[reglas](reglas_calificacion.json), el [formato editorial](config/formato_editorial.json)
y las fuentes Archivo mediante SHA-256. Las reglas conservan los 18 indicadores,
90 criterios y candados de la metodología anterior: los nuevos Word no contienen
fichas de puntuación ni cambian esos umbrales.

La salida contiene un JSON fuente, dos DOCX de nombre estable y dos recibos.
Cada ejecución exitosa elimina los artefactos anteriores. Las tablas conservan
la evidencia municipal y estatal; las gráficas nativas de Word muestran los
puntajes calculados de ambos periodos, sin convertir un pendiente en cero.
Todo texto insertado desde JSON queda resaltado en amarillo.

El formato aplica Archivo Regular/Light/Medium, tamaños, colores, interlineados,
sangrías y tablas conforme al manual. Las fuentes oficiales se incrustan en
los DOCX. Los interlineados de títulos inferiores a su tamaño de letra se
aplican como mínimos para evitar superposición o recorte.

Para repetir el renderizado sin extraer otra vez:

    python3 scripts/renderizar_word.py output/json/{archivo}.json --modo borrador

`--documento medicion` o `--documento anexo` genera sólo ese documento;
por defecto genera ambos. `--modo final` exige revisión humana concluida,
todos los puntajes, cálculos coherentes y ninguna validación abierta.
`--word ninguno` en el pipeline genera sólo el JSON y limpia las salidas anteriores.
Los JSON v1 deben regenerarse.

La población opcional puede ingresarse como CSV o con `--inegi-population`,
usando `INEGI_TOKEN` desde el entorno. La ejecución habitual con los cuatro
Word no necesita API key. Las claves y respuestas de fuentes externas nunca
se incorporan al repositorio.

Consulta [PIPELINE.md](PIPELINE.md) para el contrato de variables, el manual
editorial, la migración de nuevos machotes y las limitaciones pendientes.

    python3 -m unittest discover -s tests -v
