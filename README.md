# Pipeline de seguridad municipal · v2.1

El pipeline transforma dos fuentes municipales en un diagnóstico de SEGURIDAD,
con análisis consultivo, tablas de evidencia y gráficas de los puntajes
calculables. Publica un solo Word, acompañado de su JSON fuente y un recibo de
renderizado.

Coloca en `input/word/` exactamente un archivo de cada tipo, con el mismo
prefijo municipal:

```text
{municipio} PAQUETE SEGURIDAD.docx
{municipio} Anexo.docx
```

PAQUETE SEGURIDAD aporta la evidencia principal; Anexo confirma identidad y
permite contrastar esa evidencia. Ambos archivos son entradas. La ejecución
utiliza exclusivamente esos dos documentos y no necesita API keys.

```sh
python3 -m pip install -r requirements.txt
python3 scripts/validar_plantilla.py
python3 scripts/ejecutar_pipeline.py
```

La única base de salida es
[seguridad_medicion.docx](templates/seguridad_medicion.docx), derivada del capítulo
SEGURIDAD de `templates/Machote general medicion version final.docx`. El original
se conserva intacto. Si se actualiza, regenera y valida la base antes de ejecutar:

```sh
python3 scripts/migrar_machotes_v2.py
python3 scripts/validar_plantilla.py
```

El [contrato documental](config/contrato_documental.json) vincula la base,
el [diccionario](diccionario_datos_diagnostico_seguridad_municipal.json), las
[reglas](reglas_calificacion.json), el [formato](config/formato_editorial.json)
y la [configuración de redacción](config/redaccion_consultoria.json).
La base tiene 81 variables únicas y 81 apariciones. Se conservan los 18
indicadores, 90 criterios y candados históricos. Un dato
faltante permanece como `null`; una calificación incompleta queda PENDIENTE.
El último periodo comprende una ventana común de dos años consecutivos al
cierre documental. Los vacíos no se rellenan con observaciones de otros años.

Las salidas tienen nombres estables; `{municipio}` usa minúsculas, sin acentos
y con guiones bajos:

```text
output/json/{municipio}_diagnostico_seguridad_municipal.json
output/word/{municipio}_seguridad_medicion_{modo}.docx
output/json/{municipio}_seguridad_medicion_{modo}_renderizado.json
```

Una corrida exitosa conserva esos tres archivos y limpia las salidas anteriores.
El modo predeterminado es `borrador`. Para volver a generar el Word a partir del
JSON vigente:

```sh
python3 scripts/renderizar_word.py output/json/{municipio}_diagnostico_seguridad_municipal.json --modo borrador
```

`--modo final` exige revisión concluida y cálculos completos y coherentes.
`--word ninguno` en el pipeline produce sólo el JSON y limpia los Word y recibos
anteriores. Las carpetas de salida están reservadas para artefactos del pipeline.

El formato sigue el manual de medición: tipografía Archivo incrustada, jerarquía
editorial y tablas legibles. El documento se entrega sin resaltado amarillo.
La prosa sigue [ESTILO_REDACCION.md](ESTILO_REDACCION.md): presenta hallazgos,
evidencia, implicaciones y prioridades, conservando la trazabilidad en el JSON.

Consulta [PIPELINE.md](PIPELINE.md) para el contrato, los periodos, la revisión
y la política de publicación. El [diagrama editable](flujo_pipeline.drawio)
describe la ejecución y el mantenimiento de la base documental.

```sh
python3 -m unittest discover -s tests -v
```
