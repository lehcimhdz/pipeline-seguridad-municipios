# Pipeline de seguridad municipal — v3

Genera una medición de SEGURIDAD desde los mismos cuatro Word por municipio.
Incorpora el machote **rzg investigación**, conserva los 18 indicadores y sus
90 criterios y separa la investigación externa de los puntajes.

La base activa [seguridad_medicion_v3.docx](templates/seguridad_medicion_v3.docx)
tiene **97 variables snake_case**, cuatro benchmarks y tres mínimos de
protección civil. El original recibido se conserva sin editar.
No se genera un anexo adicional ni una plataforma electoral.

## Ejecutar

Python 3.11+:

    python3 -m pip install -r requirements.txt
    python3 scripts/validar_plantilla.py
    python3 scripts/ejecutar_pipeline.py

Produce JSON trazable, Word **BORRADOR DE REVISIÓN** y recibo de renderizado.
Texto, tablas y gráficas insertados desde JSON llevan amarillo. Se aplica el
manual editorial y se incrustan las tipografías Archivo.

Después de una ejecución exitosa, se eliminan las salidas anteriores de
`output/json/` y `output/word/`; sólo se conservan las vigentes.
No uses estas carpetas como archivo histórico.

Para incluir investigación previamente revisada:

    python3 scripts/ejecutar_pipeline.py --investigacion-json input/revision/investigacion_seguridad.json

Sin ese aporte, los benchmarks y mínimos quedan pendientes. El pipeline
valida estructura y referencias declaradas, **no vigencia jurídica ni veracidad
de una investigación**. No necesita una API de IA.

Los datos actuales permiten calcular 12 de 18 indicadores por periodo.
Siguen pendientes 4, 8, 9, 14, 17 y 18, además de la nueva investigación.
La versión final requiere datos completos y revisión resuelta.

## Cuando cambie el machote

    python3 scripts/migrar_machote_v3.py
    python3 scripts/validar_plantilla.py
    python3 -m unittest discover -s tests -v
    python3 scripts/ejecutar_pipeline.py

La migración actualiza base, diccionario, reglas y contrato.
Una modificación del original bloquea el pipeline hasta migrar.
Si cambia el inventario de indicadores, se exige revisar su correspondencia.
Los JSON anteriores deben regenerarse.

La población puede aportarse mediante CSV o INEGI opcional
(`--inegi-population`, secreto de entorno `INEGI_TOKEN`).
No se guardan tokens en salidas ni Git.

Detalles en [PIPELINE.md](PIPELINE.md).
Diagrama editable: [flujo_pipeline.drawio](flujo_pipeline.drawio).
