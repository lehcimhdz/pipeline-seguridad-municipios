# Pipeline del Estudio de Seguridad · contrato v2.2

## Producto y documentos de referencia

La rama `pipeline-v2` genera un único estudio de SEGURIDAD: `{municipio} Estudio Seguridad.docx`. Llena el formato que la consultora pidió con una interpretación de las estadísticas y una valoración de su desempeño documentado.

El flujo distingue tres originales:

| Documento | Papel en la ejecución |
| --- | --- |
| `templates/Machote general medicion version final.docx` | Formato de la consultora: orden del capítulo y presentación del estudio. |
| `templates/Machote general medicion version final rzg investigación.docx` | Guía para interpretar los apartados y definir qué contenido recibe cada variable. |
| `templates/Machote_seguridad_general_con_calificacion.docx` | Benchmark para evaluar: fichas, criterios, dimensiones, escala y candados. |

`templates/seguridad_medicion.docx` es una base técnica derivada del formato de la consultora. Incluye su portada y logo, el capítulo SEGURIDAD con los 18 indicadores y la bibliografía. La migración conserva los tres originales. Las fichas internas, alternativas de redacción e instrucciones del benchmark no se insertan en el documento del cliente.

La guía contiene una duplicación de Personal que no altera el catálogo: Personal es el indicador 4, evaluaciones el 5, instituto el 6 y Certificado Único Policial el 7. Se conservan 18 indicadores únicos.

## Fuentes estadísticas

La entrada obligatoria es:

```text
input/word/{municipio} PAQUETE SEGURIDAD.docx
```

Puede agregarse `input/word/{municipio} Anexo.docx` como contraste documental y fuente de ilustraciones existentes. Es opcional; su ausencia queda registrada. Se exige un único archivo por tipo y el mismo prefijo municipal. Los archivos de bloqueo de Word se omiten.

El paquete aporta las tablas municipales y estatales de los 18 indicadores. Las unidades y las fechas deben ser compatibles antes de comparar territorios. La identidad del estado se verifica en la documentación o se declara mediante `--estado` cuando no se dispone del Anexo. La interpretación editorial debe corresponder a esa misma identidad.

No se utilizan otros paquetes, CSV, servicios externos ni información de otro municipio. La muestra editorial aporta estilo y estructura, no cifras, calificaciones ni conclusiones. Cada fuente incorporada queda vinculada por nombre y SHA-256.

## Contrato y variables

`config/contrato_documental.json` registra la versión, el alcance, las referencias documentales y las huellas. Vincula los tres originales, la base operativa, el diccionario, el benchmark transcrito, las reglas, las normalizaciones y la configuración editorial. La validación rechaza activos desactualizados.

`diccionario_datos_diagnostico_seguridad_municipal.json` define **25 variables de tipo string**, con nombres ASCII en `snake_case` y una aparición por variable:

| Variables | Contenido |
| --- | --- |
| `{municipio}`, `{estado}` | Identidad territorial. |
| `{calificacion_general}`, `{calificacion_ultimo_periodo}` | Categorías que devuelve la metodología seleccionada. |
| `{resumen_general}`, `{resumen_ultimo_periodo}` | Tres párrafos de síntesis por periodo, con cobertura del cálculo. |
| `{analisis_indicador_01}`…`{analisis_indicador_18}` | Hallazgos, comparación pertinente, consecuencias y recomendaciones sustentadas. |
| `{bibliografia}` | Fuentes efectivamente utilizadas en el estudio. |

Los saltos `\n\n` de los valores se convierten en párrafos reales. La base ya no solicita variables de tablas, gráficas calculadas o cierres repetidos. Las ilustraciones originales se seleccionan por separado y se sitúan junto al análisis correspondiente.

La composición utiliza versión `2.2` y perfil `estudio_seguridad`. Los valores publicables se conservan en `valores_plantilla`; las tablas extraídas, coordenadas, huellas, motivos de pendiente y cálculos permanecen como trazabilidad del JSON.

## Preparación e interpretación editorial

La escritura tiene una etapa explícita de interpretación. El programa prepara los datos y el agente editorial o la persona responsable redacta los análisis. No se sustituyen por párrafos seriados cuando falta esa interpretación.

```sh
python3 scripts/ejecutar_pipeline.py --preparar --estado "Nombre del estado"
```

Este paso produce `output/json/{slug}_evidencia_seguridad.json`: evidencia ordenada, periodos, puntajes y catálogo de imágenes. No publica un nuevo Word. El archivo de redacción se guarda por defecto en `input/redaccion/{slug}.json`, o se indica mediante `--redaccion`.

El archivo editorial contiene:

- Identidad territorial y versión 2.2.
- Vínculos a fuentes, benchmark y reglas mediante SHA-256.
- Hechos que identifican indicador, tabla, fila, columna y valor observado.
- Operaciones editoriales comprobables cuando un párrafo utiliza diferencias o variaciones porcentuales.
- Dos resúmenes, 18 análisis y bibliografía, organizados en párrafos con referencias a esos hechos.
- Selección de ilustraciones originales y declaración de revisión y tipo de autor: `agente_editorial` o `persona`.

El control editorial comprueba fuentes, coincidencia de celdas, operaciones y cifras citadas. Una nueva fuente, una modificación del benchmark o reglas distintas invalidan la vinculación anterior y exigen revisar la interpretación. Ninguna clave de API es necesaria para ejecutar el pipeline.

La comprobación numérica no sustituye la lectura crítica: el autor debe revisar el significado, las unidades, las comparaciones, la causalidad y la pertinencia de las recomendaciones. El texto visible evita rutas, identificadores técnicos, instrucciones y referencias a versiones de trabajo. [ESTILO_REDACCION.md](ESTILO_REDACCION.md) explica el criterio de escritura.

## Calificaciones

La metodología está en [METODOLOGIA.md](METODOLOGIA.md). `scripts/estructurar_reglas.py` transcribe las 18 fichas y los 90 criterios del benchmark activo y registra su huella. Si cambió un criterio frente a su implementación, se detiene para que se revise la regla ejecutable.

El periodo general conserva las observaciones de cada indicador. El reciente utiliza las dos ediciones censales de cierre para 1–16 y los dos años calendario de cierre para 17–18. Una celda vacía no se omite ni se transforma en cero. Las etiquetas de las tablas no se reinterpretan automáticamente como el año de referencia de un censo.

Se ofrecen dos métodos:

| Opción | Resultado y alcance |
| --- | --- |
| `--calificacion evaluables` | Adaptación explícita sobre indicadores calificables. Exige al menos 2/3 por dimensión: 2 de 3, 5 de 7 y 6 de 8. Conserva igual peso para las dimensiones, declara cobertura y no permite EXCELENTE con pendientes. Es la opción predeterminada de la ejecución. |
| `--calificacion completo` | Aplica la agregación estricta del benchmark: los 18 puntajes son necesarios. Si falta alguno, la valoración conjunta queda pendiente y se bloquea la publicación del Word final. `--preparar` conserva la evidencia para su revisión. |

Los modos mantienen las mismas fichas individuales y la misma escala. La adaptación evaluable no atribuye puntajes a los pendientes ni equivale a un promedio completo. El JSON conserva un intervalo de sensibilidad de la evaluación completa; sus escenarios extremos no se publican como observaciones.

El documento final exige una calificación conjunta en ambos periodos. Este control también bloquea la publicación en modo `evaluables` si alguna dimensión no alcanza la cobertura mínima. Se puede ejecutar `--preparar --calificacion completo` para obtener la evidencia y sus pendientes sin reemplazar la entrega vigente.

Los candados, dependencias y redondeo se documentan en la metodología. No se aplican ajustes discrecionales automáticos. Las referencias jurídicas y académicas suministradas por el benchmark no se presentan como investigación externa realizada por esta ejecución.

## Reutilización de gráficas

`--graficas originales` importa exclusivamente ilustraciones que ya existen en las fuentes y que fueron seleccionadas en el archivo editorial. El catálogo identifica origen, parte interna, indicador y huella. El renderizado conserva los bytes de las imágenes elegidas y comprueba su identidad en el archivo final.

La selección requiere revisión del contenido: se omiten imágenes con etiquetas o series incompatibles con las tablas y las que no ayudan a explicar el argumento. No se traslada automáticamente todo el catálogo. En la primera selección editorial de esta versión se revisaron 30 imágenes del paquete y se eligieron 24; las seis restantes presentan errores o incongruencias. Esta cantidad no es una regla para otros municipios.

`--graficas ninguna` produce una versión exclusivamente textual con el mismo análisis. Ninguna de las opciones crea nuevas tablas, calcula gráficas de semáforos ni redibuja las series.

Como las ilustraciones son imágenes, sus textos y fuentes tipográficas quedan incrustados. Se conserva su presentación original; el manual Archivo se aplica al texto y al entorno del documento. No se afirma haber cambiado a Archivo las letras que forman parte de una imagen.

## Formato editorial

El cuerpo sigue `config/formato_editorial.json`. Las fuentes Archivo se incluyen con licencia OFL en `assets/fonts/` y se incrustan en Word. Un visor que no utilice fuentes incrustadas necesita tenerlas instaladas.

| Elemento | Fuente | Tamaño / interlineado |
| --- | --- | --- |
| Título principal | Archivo Regular | 26 / 40 pt |
| Capítulo | Archivo Light, altas | 24 / mínimo 14 pt |
| Subcapítulo | Archivo Light | 24 / mínimo 14 pt |
| Cuerpo | Archivo Light | 12 / 16 pt |
| Notas al pie | Archivo Light | 9 / 11 pt |
| Bibliografía | Archivo Light y Light Italic | 12 / 16 pt |

La portada centra el título y conserva el logo InstitutionWorks a 5 cm de ancho, con altura proporcional y ubicado en la zona inferior. Los capítulos se centran y los subcapítulos se alinean a la izquierda. El cuerpo es de una columna, sin espacio adicional entre párrafos y con sangría de 5 mm salvo el inicial. La bibliografía usa la misma regla de sangría; las notas se alinean a la izquierda.

El interlineado de los títulos se aplica como mínimo para que una letra de 24 pt no quede recortada dentro de una altura exacta de 14 pt. No se utiliza resaltado amarillo. La auditoría comprueba variables resueltas, tipografía de las inserciones, ausencia de nuevas tablas o gráficas e integridad de las imágenes originales.

## Ejecución y publicación

```text
Paquete Seguridad + Anexo opcional
  → comprobar identidad, originales y contrato
  → extraer evidencia y catalogar gráficas existentes
  → aplicar benchmark y declarar cobertura
  → redactar y revisar la interpretación vinculada a los hechos
  → llenar las 25 variables y reutilizar las imágenes seleccionadas
  → auditar Word y publicar JSON, Word y recibo
  → limpiar salidas anteriores
```

```sh
python3 scripts/ejecutar_pipeline.py --estado "Nombre del estado"
python3 scripts/ejecutar_pipeline.py --calificacion completo --graficas ninguna --estado "Nombre del estado"
```

`--input` y `--output` permiten elegir las carpetas. `--redaccion` selecciona otro archivo editorial. El renderizador independiente permite regenerar desde el JSON vigente:

```sh
python3 scripts/renderizar_word.py output/json/{slug}_diagnostico_seguridad_municipal.json
```

Las salidas estables son:

```text
output/word/{municipio} Estudio Seguridad.docx
output/json/{slug}_diagnostico_seguridad_municipal.json
output/json/{slug}_estudio_seguridad_renderizado.json
```

El nombre del Word conserva el municipio legible. El slug del JSON usa minúsculas, sin acentos y con guiones bajos. El identificador de corrida queda dentro del JSON. El recibo vincula los artefactos mediante SHA-256 y conserva los resultados de la auditoría.

La publicación prepara los artefactos en un área temporal, los valida y después sustituye la entrega vigente. Si falla antes de publicar, la anterior permanece. Si falla uno de los reemplazos, se intenta restaurar el conjunto previo; si la restauración también falla, se conserva una carpeta de recuperación y se informa su ubicación. Cada reemplazo es atómico, pero el conjunto no es una transacción indivisible frente a una interrupción del equipo.

Sólo tras la publicación exitosa se limpian los JSON y DOCX anteriores de las carpetas de salida, reservadas al pipeline. Preparar evidencia no equivale a publicar una nueva entrega. No deben ejecutarse corridas simultáneas sobre las mismas salidas. Los bloqueos `~$` son administrados por Word. Entradas, redacción por municipio y resultados quedan fuera del seguimiento de Git.

## Mantenimiento y pruebas

Al recibir cambios en los documentos de referencia:

```sh
python3 scripts/estructurar_reglas.py
python3 scripts/migrar_machotes_v2.py
python3 scripts/validar_plantilla.py
python3 -m unittest discover -s tests -v
```

La migración actualiza la base operativa, el diccionario y las referencias del contrato. Después de un cambio metodológico o de fuentes debe revisarse también la interpretación editorial. El [diagrama editable](flujo_pipeline.drawio) representa esta separación entre fuentes estadísticas, benchmark, guía y formato de entrega.
