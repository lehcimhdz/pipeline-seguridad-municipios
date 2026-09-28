# Escritura del estudio de seguridad · 2.3

El producto es una interpretación del funcionamiento municipal, organizada en
el formato de la consultora. Debe poder leerse como un estudio terminado:
explica qué ocurre, qué significan los cambios y qué decisiones permiten tomar.
La evidencia y las verificaciones técnicas se conservan por separado.

## Referencias y responsabilidades

`Muestra Estudio Seguridad.docx` orienta la escritura: síntesis con una posición
clara, comparaciones pertinentes y recomendaciones ligadas al hallazgo. Sus
datos, localidades, calificaciones y estándares no se trasladan a otro municipio.
La muestra se consultó fuera del repositorio; no es una fuente estadística.

Cada documento tiene una función distinta:

- `Machote general medicion version final.docx`: estructura del producto.
- `Machote general medicion version final rzg investigación.docx`: guía de
  interpretación y organización del razonamiento.
- `Machote_seguridad_general_con_calificacion.docx`: benchmark de evaluación.
- `{municipio} PAQUETE SEGURIDAD.docx`: evidencia municipal y referencia estatal.
- `{municipio} Anexo.docx`, cuando está disponible: contraste documental.

Las calificaciones las calcula el módulo metodológico. La redacción no cambia
puntajes ni resuelve faltantes mediante opiniones. El criterio de agregación y
su cobertura se explican brevemente junto a los resúmenes del estudio.

## Un argumento por párrafo

Los dos resúmenes contienen tres párrafos cada uno. El general organiza una
lectura conjunta de protección civil, personal y capacidades policiales; el
reciente identifica avances y asuntos de gestión en las últimas observaciones.
La síntesis elige hallazgos; no repite todas las cifras de los apartados.

Los dieciocho apartados conservan el orden del formato de la consultora. Cada
uno desarrolla un argumento propio: una situación municipal, las cifras
indispensables para comprenderla y su consecuencia para la gestión. La acción
propuesta debe responder al hallazgo, no ser un consejo genérico sobre el tema.
No existe una lista de frases que el programa combine para simular un análisis.

Seleccionar cifras también significa dejar fuera las que no ayudan a comprender
el problema. Una variación decisiva puede merecer un párrafo; el resto de una
serie puede describirse en una oración. Alternar el comienzo y la extensión
según el argumento evita que todos los apartados suenen a una misma ficha.

Las gráficas que se incluyan se reutilizan de la documentación original. No se
construyen gráficas de puntajes ni nuevas tablas. La selección editorial indica
qué figura corresponde a cada análisis y después de qué párrafo debe aparecer.
Las figuras con rótulos incompatibles o datos cuya interpretación no es fiable
se omiten y se registra el motivo en la trazabilidad.

## Interpretación verificable

Conservar territorio, año, unidad y universo de cada cifra. Comparar sólo
magnitudes equivalentes: un porcentaje de municipios no es un porcentaje de
policías; un total estatal no mide la cobertura de un municipio. Distinguir
variaciones en puntos porcentuales de variaciones relativas.

La ausencia de información no significa cero ni prueba mal desempeño. Un plan
existente no acredita su implementación; un equipo inventariado no demuestra
su funcionamiento; una remisión policial no equivale a un delito resuelto.
No sumar participantes de distintos cursos como personas únicas ni inferir
déficits por habitante sin denominadores compatibles.

Antes de escribir, leer las correspondencias del cálculo: distinguen cifras
reportadas, conceptos homologados y lecturas condicionales. Una homologación
automática no permite decir «se verificó» o «se comprobó» una situación que el
paquete sólo declara. El título de CUP vigente puede sustentar esa denominación;
un porcentaje de evaluaciones no permite añadir «aprobatorias vigentes» si el
estatus sigue sin conocerse.

La valoración provisional se explica como una limitación del argumento, no
como una etiqueta técnica repetida en cada apartado. Si la capacitación acredita
varios grupos, describir su alcance temático sin sumar asistentes de cursos
distintos. Si hay llamadas en dos cortes, señalar la continuidad de la serie,
sin atribuir la operación del servicio al municipio ni confundir más llamadas
con mejor atención. La incertidumbre debe quedar junto a la conclusión que
limita, sin referencias al archivo interno donde se conserva.

Una diferencia entre observaciones no demuestra una tendencia continua. Las
rupturas abruptas de una serie exigen verificar su comparabilidad antes de
atribuirlas a decisiones de gestión. Un porcentaje superior al total posible o
un desglose que contradice su agregado requiere una explicación cercana al
hallazgo. Evitar apéndices de advertencias genéricas al final del documento.

Las recomendaciones pueden proponer revisión de turnos, vigencias, atención o
funcionamiento cuando el dato sustenta esa prioridad. No atribuir intenciones,
causas políticas, incumplimientos legales o mejoras en la seguridad que la
documentación no demuestra. No incorporar estándares normativos nuevos como
si formaran parte del benchmark proporcionado.

## Preparación editorial sin una API key

Un agente o una persona redacta y revisa la interpretación en
`input/redaccion/{municipio_normalizado}.json`. La ejecución no llama a un
servicio de IA. Conserva ese texto y comprueba su correspondencia con las
fuentes y los criterios vigentes. Si falta el archivo o quedó desactualizado,
se detiene antes de publicar el Word: no lo sustituye por prosa automática.

El archivo editorial contiene:

- `version`, `municipio` y `estado`.
- `vinculos`: nombres exactos y SHA-256 de fuentes, benchmark, reglas,
  ponderación, definiciones, textos narrativos y evidencia complementaria.
  Al cambiar la evidencia o la metodología se requiere revisar el texto
  antes de actualizar sus vínculos; no se deben renovar las huellas a ciegas.
  `evaluacion_sha256` vincula también los resultados, cobertura y periodos: si
  cambia el esquema o la evaluación, hay que revisar nuevamente la prosa.
- `revision`: estado `revisada`, tipo de autor `agente_editorial` o `persona` y
  alcance de la revisión. El primero no significa aprobación humana.
- `hechos`: referencias a indicador, tabla, fila, columna y valor literal. La
  fila se cuenta desde cero, incluida la cabecera; las observaciones empiezan
  en uno. Se admiten restas y variaciones porcentuales con operandos, precisión
  decimal y resultado declarados.
  Un hecho del complemento usa `origen: "complemento"`, `indicador`, `anio`,
  `campo` y `valor` exacto. Para población, `campo: "poblacion"` y `ambito`.
  No se admiten valores declarados que difieran de la evidencia conservada.
- `bloques`: tres párrafos por resumen, los dieciocho análisis y la bibliografía.
  Cada párrafo contiene `texto` y una lista `evidencia` con los hechos que usa.
- `seleccion_editorial`: claves `1` a `18`, cada una con `encuadre_id` igual a
  su clave, `revision_semantica: true` y `consecuencia_revisada` específica.
  Esa declaración deja rastro de la lectura; no prueba automáticamente que la
  interpretación sea correcta. Los resúmenes deben citar hechos de al menos dos
  indicadores y no omitir prioritarios con puntaje 1 o 2.
- `ilustraciones`: fuente, parte del documento, indicador y posición del
  párrafo, contada desde cero. `ilustraciones_excluidas` conserva los motivos de
  omisión, que no se imprimen como instrucciones al lector.

Los archivos editoriales municipales se mantienen fuera de Git, igual que los
insumos y las salidas. Su contenido y su huella se incorporan al resultado para
permitir reconstruir exactamente la interpretación usada.

## Qué comprueba el programa y qué debe revisar el autor

La validación comprueba identidad, nombres y huellas de las fuentes, versión del
criterio, integridad de los bloques, coincidencia de las celdas y operaciones
declaradas. Cada número escrito debe existir en los hechos citados o en sus
años, o ser resultado de una operación declarada. Los conteos de cobertura y
las etiquetas de calificación se agregan directamente desde el cálculo vigente.

El control numérico no demuestra por sí solo la verdad de una interpretación.

## Uso del material narrativo del asesor

`config/textos_narrativos.json` conserva encuadres, impactos, variantes y ejemplos
como material de consulta. El texto municipal sigue siendo escrito y revisado;
el programa no concatena frases según el semáforo. No se recibieron los 144
cierres anunciados ni un bloque `apartados`: no se presentan como disponibles.
Las propuestas electorales del catálogo no generan un segundo producto.

El razonamiento enlaza contexto, dato y consecuencia sin repetir una fórmula
literal. Hay que verificar que cada encuadre corresponda al universo observado,
que una comparación tenga años y denominadores compatibles y que la recomendación
responda al hallazgo. Un mayor volumen de llamadas no demuestra mejor atención;
el número de remisiones no equivale a delitos esclarecidos. No copiar inferencias
causales del catálogo sin respaldo. Los marcadores pendientes, incluso `{AÑOS}`,
bloquean la publicación.

Si el rubro conserva puntaje pendiente, se explica qué se sabe y qué información
falta, sin llamarlo fracaso ni presentar una valoración provisional como nota
oficial. La metodología y el alcance se expresan al lector en términos del estudio,
no mediante nombres de archivos, rutas, JSON o instrucciones de operación.
El autor debe comprobar que cada cifra se atribuye al concepto, territorio y
año correctos, que las comparaciones son válidas y que la consecuencia propuesta
no excede la evidencia. El programa tampoco certifica calidad literaria.

Antes de generar el Word se rechazan rutas, identificadores técnicos, nombres
de archivos locales y expresiones como «borrador», «machote» o «plantilla» en el
texto público. El documento utiliza Archivo, conserva el formato editorial de
medición y no resalta en amarillo el contenido incorporado.
