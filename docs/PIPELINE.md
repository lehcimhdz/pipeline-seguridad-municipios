# Pipeline del Estudio de Seguridad · rama v2, contrato 2.3

## Producto y documentos de referencia

La rama `pipeline-v2` genera `{municipio} Estudio Seguridad.docx`. Con `--plataforma-electoral` genera también `{municipio} Plataforma Electoral Seguridad.docx`, limitado a los dos incisos de Seguridad del machote electoral recibido. El estudio llena el formato de medición de la consultora con una interpretación de las estadísticas y una valoración de su desempeño documentado.

El flujo distingue tres originales:

| Documento | Papel en la ejecución |
| --- | --- |
| `templates/Machote general medicion version final.docx` | Formato de la consultora: orden del capítulo y presentación del estudio. |
| `templates/Machote general medicion version final rzg investigación.docx` | Guía para interpretar los apartados y definir qué contenido recibe cada variable. |
| `templates/Machote_seguridad_general_con_calificacion.docx` | Benchmark para evaluar: fichas, criterios, dimensiones, escala y candados. |

`templates/seguridad_medicion.docx` es una base técnica derivada del formato de la consultora. Incluye portada y logo, capítulo SEGURIDAD con los 18 indicadores y bibliografía. La migración no altera sus documentos de referencia. Una operación separada y reproducible añade al benchmark interno el anexo metodológico 2.3; el formato y la guía originales no cambian. Las fichas internas e instrucciones no se insertan en el documento del cliente.

`templates/PLATAFORMA ELECTORAL MACHOTE.docx` es el original del segundo producto. `scripts/crear_plantilla_electoral.py` deriva `templates/seguridad_plataforma_electoral.docx`: portada, introducción de Seguridad y cinco campos para cada inciso, «a. Protección Civil» y «b. Seguridad». Añade al final «Fuentes clave» para las referencias realmente citadas. La base conserva la presentación del Word recibido. El PDF de Cuernavaca orienta únicamente la organización y el tono; sus cifras y propuestas no se transfieren.

La guía contiene una duplicación de Personal que no altera el catálogo: Personal es el indicador 4, evaluaciones el 5, instituto el 6 y Certificado Único Policial el 7. Se conservan 18 indicadores únicos.

## Fuentes estadísticas

La entrada obligatoria es:

```text
input/word/{municipio} PAQUETE SEGURIDAD.docx
```

Puede agregarse `input/word/{municipio} Anexo.docx` como contraste documental y fuente de ilustraciones existentes. Es opcional; su ausencia queda registrada. Se exige un único archivo por tipo y el mismo prefijo municipal. Los archivos de bloqueo de Word se omiten.

El paquete aporta las tablas municipales y estatales de los 18 indicadores. Las unidades y las fechas deben ser compatibles antes de comparar territorios. La identidad del estado se verifica en la documentación o se declara mediante `--estado` cuando no se dispone del Anexo. La interpretación editorial debe corresponder a esa misma identidad.

El paquete sigue siendo la fuente estadística principal. Todos los datos municipales proceden de `input/`. El material del asesor recibido en `new-elements`, fuera del repositorio, aporta parámetros generales que se integran en `config/`; no se consulta como una fuente de cifras del municipio. La muestra editorial aporta estilo, no cifras ni conclusiones.

Primero se resuelven las correspondencias que permiten los títulos, columnas y valores del paquete, junto con los títulos de las gráficas de Seguridad del paquete y del Anexo. Los complementos revisados son opcionales: pueden aportar población o aclarar los universos que sigan pendientes, sin repetir lo ya reconocido. Se incorporan expresamente mediante `--complemento`, nunca mediante búsquedas automáticas. Cada observación complementaria exige archivo conservado, SHA-256, año, localizador y revisión. Véase [RECOLECCION_DATOS.md](RECOLECCION_DATOS.md).

Si se incorpora un complemento municipal, debe conservarse en `input/complementos/{slug}.json` junto a sus fuentes descargadas en `input/fuentes/`. Los porcentajes de evaluaciones aprobatorias vigentes se distinguen de la mera aprobación, y el personal policial se separa del total institucional. Una población censal anterior sólo puede utilizarse como base fija explícita para tasas posteriores, nunca como población observada en esos años. El complemento se indica mediante `--complemento`: no se carga automáticamente.

## Contrato y variables

`config/contrato_documental.json` registra la versión, el alcance, las referencias documentales y las huellas. Vincula los tres originales, la base operativa, el diccionario, el benchmark transcrito, las reglas, las normalizaciones y la configuración editorial. La validación rechaza activos desactualizados.

`config/diccionario_datos_diagnostico_seguridad_municipal.json` define **25 variables de tipo string**, con nombres ASCII en `snake_case` y una aparición por variable:

| Variables | Contenido |
| --- | --- |
| `{municipio}`, `{estado}` | Identidad territorial. |
| `{calificacion_general}`, `{calificacion_ultimo_periodo}` | Categorías que devuelve la metodología seleccionada. |
| `{resumen_general}`, `{resumen_ultimo_periodo}` | Tres párrafos de síntesis por periodo, con cobertura del cálculo. |
| `{analisis_indicador_01}`…`{analisis_indicador_18}` | Hallazgos, comparación pertinente, consecuencias y recomendaciones sustentadas. |
| `{bibliografia}` | Fuentes efectivamente utilizadas en el estudio. |

Los saltos `\n\n` de los valores se convierten en párrafos reales. La base ya no solicita variables de tablas, gráficas calculadas o cierres repetidos. Las ilustraciones originales se seleccionan por separado y se sitúan junto al análisis correspondiente.

La composición utiliza versión `2.3` y perfil `estudio_seguridad`. Los valores publicables se conservan en `valores_plantilla`; las tablas extraídas, coordenadas, huellas, motivos de pendiente y cálculos permanecen como trazabilidad del JSON. El contrato incluye ponderación, definiciones censales y catálogo editorial; una modificación exige regenerarlo y revisar el texto.

## Preparación e interpretación editorial

La escritura tiene una etapa explícita de interpretación. El programa prepara los datos y el agente editorial o la persona responsable redacta los análisis. No se sustituyen por párrafos seriados cuando falta esa interpretación.

```sh
python3 scripts/ejecutar_pipeline.py --preparar --estado "Nombre del estado"
```

Este paso produce `output/json/{slug}_evidencia_seguridad.json`: evidencia ordenada, periodos, puntajes, valoraciones provisionales y catálogo de imágenes. Las `correspondencias` de cada evaluación registran el campo reconocido, el tipo de decisión, la regla aplicada y sus evidencias por indicador y año, con tabla, fila y columna cuando provienen de celdas. Una homologación automática no se marca como revisión humana ni como nueva comprobación externa. Los faltantes explican el requisito concreto que no pudo resolverse; un complemento vacío no es, por sí solo, motivo de bloqueo.

La preparación también realiza lectura óptica local de las gráficas de Seguridad mediante Tesseract. `lecturas_graficas` conserva el texto completo reconocido, el título, el estado de lectura, idioma y motor, junto con el archivo, la imagen y su SHA-256. Estas lecturas se vinculan al indicador correspondiente. Los años del título delimitan el alcance de cada aclaración; no se extrapola a otras ediciones. Las cifras calculables siguen procediendo de las tablas, no del reconocimiento de números en una imagen.

Para habilitar esta lectura, instalar `tesseract` y sus datos de español: `brew install tesseract tesseract-lang` en macOS o `sudo apt-get install tesseract-ocr tesseract-ocr-spa` en Debian/Ubuntu. Se prefiere español; si no está disponible, se utiliza inglés. El motor y las imágenes permanecen en el equipo. Sin motor, idioma utilizable o lectura válida se registra el problema y se conservan los pendientes correspondientes; no se completan títulos por conjetura.

Preparar no publica un nuevo Word. El archivo de redacción se guarda por defecto en `input/redaccion/{slug}.json`, o se indica mediante `--redaccion`.

El archivo editorial contiene:

- Identidad territorial y versión 2.3.
- Vínculos a fuentes, benchmark, reglas, ponderación, definiciones, catálogo narrativo y evidencia complementaria mediante SHA-256.
- `seleccion_editorial`: encuadre de cada indicador, revisión semántica y consecuencia específica revisada. No equivale a insertar un párrafo prefabricado.
- Hechos que identifican indicador, tabla, fila, columna y valor observado.
- Operaciones editoriales comprobables cuando un párrafo utiliza diferencias o variaciones porcentuales.
- Dos resúmenes, 18 análisis y bibliografía, organizados en párrafos con referencias a esos hechos.
- Un encuadre general breve basado en el Marco de Sendai y las leyes generales de protección civil y seguridad pública se agrega a la síntesis. Sus fuentes verificadas se incorporan a la bibliografía en APA; no sustituyen las fuentes estadísticas municipales ni implican una evaluación jurídica de cumplimiento.
- Selección de ilustraciones originales y declaración de revisión y tipo de autor: `agente_editorial` o `persona`.

El archivo electoral independiente se guarda en `input/redaccion_electoral/{slug}.json`. Sus once campos de contenido, definidos en `config/variables_plataforma_electoral_seguridad.json`, citan indicadores de la misma evaluación. Cada campo puede declarar `referencias` con IDs de `config/fuentes_plataforma_electoral_seguridad.json`; la cita debe aparecer en ese argumento. El programa construye la bibliografía APA sólo con los IDs citados y conserva la huella del catálogo de fuentes. Declara municipio, estado, fuentes municipales y huella de la evaluación, y requiere revisión editorial. Si cambian las entradas o el cálculo, se revisan de nuevo las propuestas. No se publican marcadores, citas huérfanas ni cifras sin vinculación factual explícita. Las leyes se usan como referentes vigentes para propuestas, sin juzgar retroactivamente series anteriores; Sendai es un marco no vinculante y la literatura comparada no prueba efectos locales.

El control editorial comprueba fuentes, coincidencia de celdas, operaciones y cifras citadas. Una nueva fuente, una modificación del benchmark o reglas distintas invalidan la vinculación anterior y exigen revisar la interpretación. Ninguna clave de API es necesaria para ejecutar el pipeline.

La comprobación numérica no sustituye la lectura crítica: el autor debe revisar el significado, las unidades, las comparaciones, la causalidad y la pertinencia de las recomendaciones. El texto visible evita rutas, identificadores técnicos, instrucciones y referencias a versiones de trabajo. [ESTILO_REDACCION.md](ESTILO_REDACCION.md) explica el criterio de escritura.

## Calificaciones

La metodología está en [METODOLOGIA.md](METODOLOGIA.md). `scripts/estructurar_reglas.py` conserva la transcripción de las 18 fichas históricas y añade ponderación y definiciones revisadas. El anexo de integración 2.3 declara su precedencia sobre los criterios incompatibles; las fichas 3 y 15 tienen escalas operativas explícitas. Un cambio en los criterios históricos exige revisar la implementación.

El periodo general conserva las observaciones de cada indicador. El reciente utiliza las dos ediciones censales de cierre para 1–16 y los dos años calendario de cierre para 17–18. Una celda vacía no se omite ni se transforma en cero. Las etiquetas de las tablas no se reinterpretan automáticamente como el año de referencia de un censo.

Cuando control de confianza (5) o CUP vigente (7) mejora entre dos porcentajes
recientes comparables, el último recibe peso doble en el promedio de su ficha.
No es una bonificación general: si el último corte empeora o falta evidencia,
se mantiene el criterio ordinario. Los candados siguen vigentes. Véase
[METODOLOGIA.md](METODOLOGIA.md#prioridad-del-último-corte).

Se ofrecen dos métodos:

| Opción | Resultado y alcance |
| --- | --- |
| `--calificacion disponibles` | Opción predeterminada. Calcula con los puntajes acreditados si existe al menos uno por dimensión y uno prioritario. Mantiene los pesos 25/35/40 y los candados; con pendientes publica la categoría como «COBERTURA PARCIAL», el número evaluado y una advertencia de sensibilidad. No imputa faltantes. |
| `--calificacion evaluables` | Exige 2 de 3, 5 de 7 y 6 de 8 por dimensión y al menos 6 de los 8 prioritarios para asignar categoría. Usa ponderación 25/35/40, declara cobertura y no permite EXCELENTE con pendientes. |
| `--calificacion completo` | Aplica la agregación estricta del benchmark: los 18 puntajes son necesarios para asignar categoría. Si falta alguno, la valoración conjunta queda pendiente, pero el estudio interpretativo puede publicarse con el alcance declarado. |

Los modos mantienen las mismas fichas individuales y la misma escala. La adaptación evaluable no atribuye puntajes a los pendientes ni equivale a un promedio completo. El JSON conserva un intervalo de sensibilidad de la evaluación completa; sus escenarios extremos no se publican como observaciones.

Las definiciones integradas 2.5 incorporan correspondencias automáticas y lecturas condicionales dentro del contrato de ponderación 2.3. Un CUP explícitamente vigente puede evaluarse con el porcentaje reportado bajo la homologación censal adoptada. El título de una gráfica puede acreditar que las evaluaciones fueron aprobadas o que las cámaras estaban en funcionamiento, dentro del periodo expresado. Aprobar no equivale a tener una evaluación vigente; mencionar elementos de seguridad pública no permite descontar administrativos. Una contradicción entre un campo explícito y un complemento exige conciliación; no se impone silenciosamente una de las versiones.

Las valoraciones provisionales conservan `puntaje: null` y no cuentan para cobertura ni promedio. En capacitación policial se reconocen grupos núcleo del último año disponible, sin sumar asistentes entre cursos. En llamadas, dos cortes municipales recientes permiten una lectura condicional de continuidad de la serie; no prueban quién opera el servicio ni su eficacia. El renderizador vuelve a leer las imágenes y recalcula las correspondencias y las evaluaciones antes de aceptar el JSON; rechaza lecturas editadas o que no puedan reproducirse con las fuentes.

El documento puede publicarse aunque no exista calificación en alguno de los periodos, siempre que la interpretación editorial esté revisada y vinculada a la evidencia vigente. En ese caso muestra «SIN VALORACIÓN CONJUNTA». En modo `disponibles`, la categoría surge sólo de los puntajes acreditados y se identifica visiblemente como parcial; no equivale a la nota de los 18 indicadores y puede cambiar al resolver pendientes. Si falta toda una dimensión, no hay prioritarios acreditados o existe un universo no comparable, no se asigna categoría. No se rebajan los criterios individuales ni se transforma un pendiente en cero o uno. `--preparar` conserva evidencia y pendientes sin reemplazar la entrega vigente.

`--esquema dimensiones_iguales` permite comparar el promedio aritmético histórico, pero conserva los controles 2.3: no reproduce íntegramente una evaluación 2.2. `--esquema global` pondera directamente los indicadores. Cada resultado conserva sus coeficientes efectivos; con cobertura parcial cambian los pesos relativos dentro de la dimensión.

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
| Títulos de tabla, si se incorporan | Archivo Medium | 12 / 14 pt |
| Contenido de tabla, si se incorpora | Archivo Light | 11 / 14 pt |
| Título y ejes de gráfica, si se incorporan | Archivo Medium | 12 / 14 pt |
| Categorías y datos de gráfica, si se incorporan | Archivo Medium / Archivo Light | 9 pt |

La portada centra el título y conserva el logo InstitutionWorks a 5 cm de ancho, con altura proporcional y ubicado en la zona inferior. Los capítulos se centran y los subcapítulos se alinean a la izquierda. El cuerpo es de una columna, sin espacio adicional entre párrafos y con sangría de 5 mm salvo el inicial. La bibliografía usa la misma regla de sangría; las notas se alinean a la izquierda.

La plataforma electoral derivada aplica el mismo perfil de medición a su portada, capítulo, incisos, cuerpo y bibliografía. La portada lleva el logo original en el pie de la primera página; el capítulo empieza en la página siguiente. Las referencias se distribuyen en párrafos separados, alineados a la izquierda para evitar grandes espacios entre palabras, y sus títulos correspondientes llevan Archivo Light Italic. El apartado electoral no contiene notas al pie, tablas ni gráficas: los estilos previstos para esos elementos no justifican agregarlos. El machote electoral recibido permanece intacto.

El interlineado de los títulos se aplica como mínimo para que una letra de 24 pt no quede recortada dentro de una altura exacta de 14 pt. No se utiliza resaltado amarillo. La auditoría comprueba variables resueltas, tipografía de las inserciones, ausencia de nuevas tablas o gráficas e integridad de las imágenes originales.

## Ejecución y publicación

```text
Paquete Seguridad + Anexo opcional
  → comprobar identidad, originales y contrato
  → extraer evidencia y catalogar gráficas existentes
  → leer títulos de las gráficas de Seguridad y delimitar sus años
  → reconocer correspondencias y aclarar sólo los faltantes específicos
  → aplicar benchmark y declarar cobertura
  → redactar y revisar la interpretación vinculada a los hechos
  → llenar las 25 variables y reutilizar las imágenes seleccionadas
  → auditar Word y publicar JSON, Word y recibo
  → limpiar salidas anteriores
```

```sh
python3 scripts/ejecutar_pipeline.py --estado "Nombre del estado"
python3 scripts/ejecutar_pipeline.py --estado "Nombre del estado" --plataforma-electoral
python3 scripts/ejecutar_pipeline.py --calificacion completo --graficas ninguna --estado "Nombre del estado"
```

`--input` y `--output` permiten elegir las carpetas. `--redaccion` selecciona otro archivo editorial. El renderizador independiente permite regenerar desde el JSON vigente:

`--plataforma-electoral` activa la segunda salida y `--redaccion-electoral` permite seleccionar su texto revisado. Ambas salidas se validan en el área temporal antes de sustituir los entregables vigentes.

```sh
python3 scripts/renderizar_word.py output/json/{slug}_diagnostico_seguridad_municipal.json
```

Las salidas estables son:

```text
output/word/{municipio} Estudio Seguridad.docx
output/word/{municipio} Plataforma Electoral Seguridad.docx  (opcional)
output/json/{slug}_diagnostico_seguridad_municipal.json
output/json/{slug}_estudio_seguridad_renderizado.json
output/json/{slug}_plataforma_electoral_seguridad.json  (opcional)
output/json/{slug}_plataforma_electoral_renderizado.json  (opcional)
```

El nombre del Word conserva el municipio legible. El slug del JSON usa minúsculas, sin acentos y con guiones bajos. El identificador de corrida queda dentro del JSON. El recibo vincula los artefactos mediante SHA-256 y conserva los resultados de la auditoría.

La publicación prepara los artefactos en un área temporal, los valida y después sustituye la entrega vigente. Si falla antes de publicar, la anterior permanece. Si falla uno de los reemplazos, se intenta restaurar el conjunto previo; si la restauración también falla, se conserva una carpeta de recuperación y se informa su ubicación. Cada reemplazo es atómico, pero el conjunto no es una transacción indivisible frente a una interrupción del equipo.

Sólo tras la publicación exitosa se limpian los JSON y DOCX anteriores de las carpetas de salida, reservadas al pipeline. Preparar evidencia no equivale a publicar una nueva entrega. No deben ejecutarse corridas simultáneas sobre las mismas salidas. Los bloqueos `~$` son administrados por Word. Entradas, redacción por municipio y resultados quedan fuera del seguimiento de Git.

## Mantenimiento y pruebas

Al recibir cambios en los documentos de referencia:

```sh
python3 scripts/actualizar_benchmark_v23.py
python3 scripts/estructurar_reglas.py
python3 scripts/migrar_machotes_v2.py
python3 scripts/validar_plantilla.py
python3 -m unittest discover -s tests -v
```

La migración actualiza la base operativa, el diccionario y las referencias del contrato. Después de un cambio metodológico o de fuentes debe revisarse también la interpretación editorial. El [diagrama editable](diagramas/flujo_pipeline.drawio) representa esta separación entre fuentes estadísticas, benchmark, guía y formato de entrega.
