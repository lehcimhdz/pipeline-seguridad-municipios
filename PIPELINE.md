# Pipeline de seguridad municipal · contrato v2.1

## Alcance y entradas

La rama `pipeline-v2` genera un diagnóstico de SEGURIDAD en un único Word.
Las únicas fuentes de una corrida son los dos DOCX de `input/word/`:

```text
{municipio} PAQUETE SEGURIDAD.docx
{municipio} Anexo.docx
```

Se exige un archivo por sufijo y un prefijo municipal común. PAQUETE SEGURIDAD
aporta las tablas y observaciones de los 18 indicadores; Anexo permite confirmar
municipio y estado y contrastar las tablas y calificaciones reportadas. La
evidencia estatal incluida en esos documentos sirve de contexto cuando sus
unidades y años permiten compararla con la municipal.

Cada fuente queda identificada con su nombre y SHA-256. Las diferencias entre
ambas generan una revisión documentada. La falta de un dato conserva su estado
desconocido. La ejecución completa funciona con estas dos fuentes, sin claves
de acceso ni consultas a servicios externos.

## Machote y base operativa

El original es `templates/Machote general medicion version final.docx`.
La migración deriva `templates/seguridad_medicion.docx`, que contiene portada,
logo original, introducción, capítulo SEGURIDAD, conclusiones y bibliografía.
El archivo original se conserva intacto. El Anexo municipal es una entrada de
contraste; no es un segundo documento de salida.

La base conserva los 95 bloques del capítulo original y su orden de 18
indicadores. Personal es el indicador 4, evaluaciones el 5, instituto el 6 y
Certificado Único Policial el 7. La categoría histórica EXCELENTE conserva
sus umbrales. La migración exige que títulos y marcadores coincidan con el
catálogo; un cambio de estructura requiere revisar esa correspondencia.

Después de recibir una revisión del machote:

```sh
python3 scripts/migrar_machotes_v2.py
python3 scripts/validar_plantilla.py
```

La migración actualiza la base, el diccionario y las referencias del contrato.
`normalizar_plantilla.py` y `contextualizar_variables.py` delegan en esta operación
por compatibilidad. Se debe revisar el cambio editorial y metodológico antes de
usar la nueva base. La corrida municipal sólo lee estos activos de referencia.

## Contrato y contenido

[config/contrato_documental.json](config/contrato_documental.json) registra la
versión, el alcance, las rutas, el orden de indicadores y las huellas SHA-256.
El JSON municipal conserva esas referencias para vincular evidencia, reglas,
formato, redacción y base de salida. El renderizador rechaza un contrato o
contenido incompatible con la versión vigente.

La validación comprueba las huellas del original, la base, la transcripción
metodológica, las reglas, el diccionario, el formato, la configuración de
redacción y las fuentes tipográficas. Si cambia el original, se debe ejecutar
y revisar la migración antes de continuar.

Los marcadores usan llaves simples y nombres ASCII en `snake_case`.
El [diccionario](diccionario_datos_diagnostico_seguridad_municipal.json) declara
81 variables únicas y 81 apariciones: nueve globales y cuatro por cada uno de
los 18 indicadores. Registra su tipo y obligatoriedad. La validación reconstruye
el texto de cada párrafo para reconocer marcadores que Word haya dividido en
varios segmentos.

| Marcador | Tipo JSON | Uso |
| --- | --- | --- |
| `{municipio}`, `{estado}` | string | Identidad territorial. |
| `{introduccion_seguridad}` | string | Propósito, alcance documental y lectura del diagnóstico. |
| `{calificacion_general}`, `{calificacion_ultimo_periodo}` | string | Categorías calculadas; PENDIENTE cuando falta evidencia suficiente. |
| `{resumen_general}`, `{resumen_ultimo_periodo}` | string | Síntesis de hallazgos por periodo. |
| `{analisis_indicador_01}`…`{analisis_indicador_18}` | string | Evidencia, comparación pertinente e implicaciones de cada indicador. |
| `{graficas_indicador_01}`…`{graficas_indicador_18}` | array | Especificaciones de gráficas nativas de Word. |
| `{tablas_indicador_01}`…`{tablas_indicador_18}` | array | Tablas de evidencia municipal y estatal. |
| `{cierre_indicador_01}`…`{cierre_indicador_18}` | string | Prioridad de gestión y límite de interpretación. |
| `{conclusiones_seguridad}` | string | Prioridades sustentadas y asuntos que requieren verificación. |
| `{bibliografia}` | string | Identificación de las dos fuentes utilizadas. |

Los 18 bloques separan análisis, gráficas, tablas y cierre. Cada marcador
pertenece a un indicador concreto. Los saltos de párrafo se representan con
`\n\n` en el JSON y se convierten en párrafos reales de Word.

Las tablas son listas de objetos con `titulo`, `filas`, `ambito` y
`tabla_fuente`. Sus filas y ámbitos deben corresponder con la evidencia extraída.
Las gráficas contienen `tipo: puntajes`, `titulo`, `categorias`, `valores` y
`fuente`; los valores deben coincidir con las evaluaciones calculadas.
Un puntaje `null` queda fuera de la gráfica. Si no hay un puntaje disponible,
la lista de gráficas queda vacía. Las series originales se consultan en las
tablas de evidencia.

La composición se registra en `contenido_word`, versión `2.1`, perfil
`seguridad_medicion_v2`. La prosa se rige por
[config/redaccion_consultoria.json](config/redaccion_consultoria.json), perfil
`diagnostico_consultivo`, y por [ESTILO_REDACCION.md](ESTILO_REDACCION.md).
Las coordenadas de origen, controles cruzados y motivos técnicos permanecen
disponibles en el JSON para la revisión.

## Metodología y periodos

La transcripción histórica de las reglas está en
[config/metodologia_seguridad.json](config/metodologia_seguridad.json).
Sus coordenadas remiten al documento indicado en `fuente_historica`, conservado
en el historial Git. `reglas_calificacion.json` vincula esa transcripción con
su hash. Se mantienen 18 indicadores, 90 criterios, tres dimensiones, umbrales,
dependencias y candados. Esta conservación no acredita vigencia normativa externa.

El periodo general usa las observaciones documentales admitidas por cada
criterio. El último periodo tiene una ventana común de dos años consecutivos
al cierre documental; por ejemplo, 2023–2024. Una pareja de observaciones de
2022 y 2024 no equivale a esa ventana. Los años se conservan como etiquetas de
las tablas: su relación con la edición de una fuente requiere revisión.
No se completan años intermedios ni se arrastran valores de años anteriores.

`scripts/calificar.py` calcula los criterios implementados mediante
`config/normalizaciones.json` y aplica las dependencias 3→2, 6→10 y 12→11.
La evidencia insuficiente produce `None` en Python y `null` en JSON, con su
motivo de revisión. Un cero requiere evidencia de ese valor; una celda vacía
o una leyenda de falta de información conserva su carácter de dato desconocido.

Si falta cualquier puntaje necesario, la calificación global permanece
pendiente. Los indicadores que requieren población, incidencia, cobertura o
clasificación de eventos quedan pendientes cuando las dos fuentes no aportan
lo necesario. La composición puede explicar los datos disponibles y su límite,
pero no completar el cálculo mediante inferencias editoriales.

Para regenerar las reglas transcritas y sus referencias:

```sh
python3 scripts/estructurar_reglas.py
python3 scripts/migrar_machotes_v2.py
```

Cada decisión de revisión se registra en la trazabilidad técnica del JSON con:

- La validación o el indicador revisado y el periodo al que corresponde.
- La evidencia precisa dentro de PAQUETE SEGURIDAD o Anexo: documento, tabla,
  fila, columna o párrafo que permita localizarla.
- El motivo de la decisión, la discrepancia o el faltante resuelto y su efecto
  en la evaluación, conservando la regla histórica aplicable.
- El responsable de la revisión y su fecha.

Si las dos fuentes no permiten resolver el caso, se conserva el pendiente.
La revisión debe comprobar también los cálculos y la correspondencia del texto
con la evidencia. Editar sólo el estado de ejecución, borrar una validación o
asignar un puntaje para forzar la completitud no constituye una resolución.

## Formato y redacción

[config/formato_editorial.json](config/formato_editorial.json) contiene el
manual de medición. Archivo Regular corresponde a la familia `Archivo`,
estilo regular. Las tipografías oficiales se incluyen con licencia OFL en
`assets/fonts/` y se incrustan en el Word. Un visor que ignore las fuentes
incrustadas requiere tenerlas instaladas para reproducir el diseño.

| Elemento | Fuente | Tamaño / interlineado |
| --- | --- | --- |
| Título principal | Archivo Regular | 26 / 40 pt |
| Capítulo | Archivo Light | 24 / 14 pt |
| Subcapítulo o indicador | Archivo Light | 24 / 14 pt |
| Cuerpo | Archivo Light | 12 / 16 pt |
| Calificación | Archivo Light | 9 / 10 pt |
| Encabezado de tabla | Archivo Medium | 12 / 14 pt |
| Contenido de tabla | Archivo Light | 11 / 14 pt |
| Notas | Archivo Light | 9 / 11 pt |
| Bibliografía | Archivo Light/Italic | 12 / 16 pt |

La portada centra título e identidad. El logo conserva su proporción con
5 cm de ancho. El contenido tiene una columna, cero separación entre párrafos
y sangría de 5 mm salvo el párrafo inicial. Las notas se alinean a la izquierda,
las tablas se centran y las calificaciones conservan el color de su categoría.

Los interlineados de títulos inferiores al tamaño de la letra se aplican como
mínimos para evitar recortes. Cuerpo, notas y tablas conservan el interlineado
fijo del manual. Las gráficas disponen de espacio propio y sus títulos, ejes,
categorías y valores usan Archivo conforme a la configuración editorial.

El resultado se entrega sin resaltado amarillo en texto, tablas o gráficas.
La auditoría reabre el Word para comprobar los marcadores, las inserciones,
la tipografía y el formato. El recibo conserva el resultado de esa auditoría.

La redacción presenta un hallazgo, los datos que lo sustentan y su relevancia
para la gestión municipal. La muestra consultada es una referencia de tono y
organización; sus cifras, juicios y conclusiones no forman parte de las fuentes
ni de las reglas del diagnóstico.

## Ejecución y publicación

El [diagrama editable](flujo_pipeline.drawio) muestra la ejecución vigente y
el mantenimiento de la base documental.

```text
2 Word → validar identidad y contrato → extraer y contrastar evidencia
       → normalizar y calificar → componer y validar contenido
       → JSON fuente → Word de medición → auditoría y recibo
       → limpiar salidas anteriores
```

```sh
python3 scripts/ejecutar_pipeline.py
python3 scripts/renderizar_word.py output/json/{municipio}_diagnostico_seguridad_municipal.json --modo borrador
```

El pipeline usa `--word borrador` de forma predeterminada; también admite
`--word final` y `--word ninguno`. El renderizador independiente admite
`--modo borrador` o `--modo final`; `--documento medicion` es el único perfil
documental y puede omitirse.

Las salidas usan el municipio normalizado a minúsculas, sin acentos y con
guiones bajos. El identificador de ejecución se conserva dentro del JSON;
los nombres de archivo son estables:

```text
output/json/{municipio}_diagnostico_seguridad_municipal.json
output/word/{municipio}_seguridad_medicion_{modo}.docx
output/json/{municipio}_seguridad_medicion_{modo}_renderizado.json
```

El borrador conserva `requiere_revision`, señala faltantes y presenta
PENDIENTE cuando corresponde. El modo final requiere
`estado_ejecucion: validado`, los puntajes exigidos de los 18 indicadores en ambos periodos,
agregaciones coherentes, variables completas y ninguna validación bloqueante
o de revisión abierta. Ambos modos validan la coherencia del contenido antes
de publicarlo.

Tras completar satisfactoriamente la generación del Word y el recibo, se
conservan únicamente el JSON fuente vigente y esos dos artefactos. Se eliminan
permanentemente los JSON y DOCX anteriores de las carpetas de salida, que
están reservadas al pipeline. `--word ninguno` conserva sólo el JSON y elimina
los Word y recibos anteriores. No se ejecuta la limpieza cuando falla la
generación. Los archivos temporales de bloqueo `~$` quedan a cargo de Word.

El recibo vincula JSON, Word, modo y contrato mediante SHA-256 y registra la
auditoría de inserciones. El pipeline prepara el JSON, el Word y el recibo en
un área temporal antes de reemplazar la entrega vigente. Si falla la validación
o el renderizado durante esa preparación, la entrega anterior se conserva.
Después de superar los controles se publican los artefactos y se limpian las
salidas anteriores. El pipeline guarda copias temporales de la entrega anterior
y las restaura si falla alguno de los reemplazos. Si también falla la
restauración, conserva los archivos en una carpeta `.recuperacion-*` e informa
su ubicación. La sustitución de cada archivo es atómica; el conjunto no es una
transacción indivisible ante la interrupción del proceso o del equipo.
No se deben ejecutar corridas
simultáneas sobre las mismas carpetas de salida. Las entradas municipales y
las salidas están ignoradas por Git.

```sh
python3 -m unittest discover -s tests -v
```
