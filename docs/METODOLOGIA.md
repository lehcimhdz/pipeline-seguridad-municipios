# Metodología del Estudio de Seguridad · integración 2.3

La evaluación distingue cuatro documentos con funciones diferentes:

| Documento | Función |
| --- | --- |
| `templates/Machote general medicion version final.docx` | Formato de la consultora que recibe el texto final. |
| `templates/Machote general medicion version final rzg investigación.docx` | Guía de los apartados que deben interpretarse y sus variables. |
| `templates/Machote_seguridad_general_con_calificacion.docx` | Benchmark: 18 fichas, 90 criterios, escala, dimensiones y candados. |
| `input/word/{municipio} PAQUETE SEGURIDAD.docx` | Estadísticas municipales y estatales. El Anexo del mismo municipio permite un contraste adicional cuando está disponible. |

La muestra de estudio aportada por el usuario sirve para orientar la escritura. Sus cifras, conclusiones y calificaciones no se transfieren al municipio evaluado. El producto es `{municipio} Estudio Seguridad.docx`: una interpretación de las estadísticas dentro del formato de la consultora. Las fichas de cálculo, sus instrucciones y las referencias internas permanecen en los archivos de trabajo.

## Procedencia y reproducción de las reglas

`python3 scripts/estructurar_reglas.py` lee el benchmark activo y conserva la transcripción histórica de sus 18 fichas y 90 criterios, coordenadas y huella SHA-256. Integra `config/ponderacion.json` y `config/definiciones_cngmd.json` en `config/metodologia_seguridad.json` y `config/reglas_calificacion.json`, versión 2.3.

El documento remitido como benchmark revisado no contenía cambios textuales en las fichas. Por ello `scripts/actualizar_benchmark_v23.py` incorpora un anexo interno explícito e idempotente. Ese anexo, las escalas operativas y las definiciones revisadas prevalecen sobre formulaciones históricas incompatibles, en particular «no hay dato = 1», cobertura temática y llamadas. Las fórmulas y convenciones añadidas no se atribuyen a una validación externa ni a una aprobación adicional del asesor. El formato de la consultora no se modifica.

El programa comprueba que los criterios del documento coincidan con los que sustentan la lógica ejecutable. Si cambió un criterio, se detiene para revisar su implementación; no conserva silenciosamente una regla anterior. La migración documental debe regenerarse después para actualizar las huellas del contrato.

Las referencias académicas y normativas se reciben como parte del benchmark. Para el breve marco público se cotejaron los textos oficiales del Marco de Sendai, la Ley General de Protección Civil y la Ley General del Sistema Nacional de Seguridad Pública vigente desde 2025; sus referencias APA están en `config/redaccion_consultoria.json`. Esto no equivale a verificar todas las obras del benchmark ni a acreditar cumplimiento jurídico. La ley de 2025 sirve como contexto actual y no se aplica retroactivamente para declarar cumplimiento en observaciones anteriores. La narración distingue entre las estadísticas, el parámetro de evaluación adoptado y las conclusiones que efectivamente pueden sostener los datos.

## Periodos de evaluación

La calificación general utiliza las observaciones documentadas de cada indicador. Una variable que comienza después que otra conserva su periodo propio; no se atribuye automáticamente la ausencia de años anteriores a falta de respuesta municipal.

El periodo reciente sigue la periodicidad del benchmark:

- Indicadores 1–16: las dos ediciones censales más recientes del conjunto de información, aunque sus etiquetas no sean años consecutivos.
- Indicadores 17–18: los dos años calendario más recientes de las series anuales.

Por ejemplo, una evaluación puede utilizar 2022 y 2024 para los indicadores censales y 2023–2024 para las series anuales. En ese caso no debe presentarse todo el cálculo como si correspondiera exclusivamente a 2023–2024.

Los objetivos recientes son comunes dentro de cada periodicidad. Si un indicador termina antes, no se reemplaza el cierre por sus dos observaciones anteriores. Una celda vacía tampoco se omite al seleccionar el periodo. En fallecimientos, los años ausentes entre inicio y cierre permanecen en el denominador temporal.

La frase «todas las ediciones» se aplica a las dos ediciones seleccionadas cuando se evalúa el periodo reciente. Por tanto, cumplir ambos cierres puede obtener 5; no existe una penalización automática por ser una evaluación reciente.

## Puntajes y parámetros

Cada ficha asigna un entero entre 1 y 5. Se aplica el primer criterio satisfecho en el orden explícito de la lógica ejecutable. La escala es:

| Puntaje agregado | Categoría |
| --- | --- |
| 4.50–5.00 | EXCELENTE |
| 3.50–4.49 | MUY BIEN |
| 2.50–3.49 | REGULAR |
| 1.50–2.49 | MAL |
| 1.00–1.49 | CATASTRÓFICO |

Los parámetros proceden del benchmark, no de las calificaciones impresas en el paquete. Estas últimas se conservan únicamente para contraste.

| Indicadores | Parámetro de evaluación |
| --- | --- |
| 1, 6, 11, 12, 13 y 16 | Existencia y continuidad declaradas; una respuesta positiva no acredita calidad ni funcionamiento. |
| 2 | Continuidad de cursos y personal capacitado; umbrales de la mitad y tres cuartas partes de las ediciones. |
| 3 | Cobertura sobre los grupos efectivamente captados por edición; promedio de proporciones anuales. El máximo exige al menos 80% e incluir análisis de riesgos en cada observación evaluada. |
| 4 | Policías por cada mil habitantes: referencia superior de 1.8, con escalones de 1.2 y 0.8; máximo 4 para plantillas menores de 15. Requiere población documentada. |
| 5 y 7 | Promedio porcentual y mínimo observado; 5 exige promedio de al menos 95% y ninguna caída bajo 85%. |
| 8 | Prendas básicas diferentes y frecuencia; cinco o más grupos con entrega al menos anual para los niveles altos. |
| 9 | Chalecos por elemento, radios por elemento y equipo menos letal. La ficha fija referencias de 1 y 0.5 para chalecos, y 0.5 para radios. Requiere aclarar inventario frente a dotación. |
| 10 | Capacitación en grupos temáticos núcleo; dos o más con cobertura de al menos la mitad del personal para el máximo. |
| 14 | Cámaras por cada mil habitantes frente a la tasa estatal, continuidad y evolución. Requiere ambas poblaciones comparables. |
| 15 | Continuidad de un registro de competencia municipal y tasas descriptivas calculables. Sin evidencia de respuesta no supera 4; un porcentaje de 100% limita a 3 y exige revisión. No se premia el crecimiento de llamadas. |
| 17 | Fallecimientos, continuidad de los registros y, cuando corresponda, tasas comparables y eventos. Los porcentajes de egresos no sustituyen los conteos de muertes. |
| 18 | Personas ante el Ministerio Público por cada 100 000 habitantes, comparadas con la tasa estatal del mismo universo y año. La incidencia delictiva sólo aporta contexto. Sin población o numerador estatal homólogo, el puntaje es `null`. El máximo exige además revisión documentada de derechos humanos y uso de la fuerza. |

Las fichas históricas, sus revisiones y condiciones ejecutables están en `config/reglas_calificacion.json`. Las definiciones y los requisitos de cada indicador se resuelven por año, primero con el paquete y después, si hace falta, con evidencia complementaria. No existe una exigencia general de revisión manual para todas las fichas. Los faltantes se calculan dinámicamente y señalan el requisito pendiente, no la mera ausencia de un archivo auxiliar. Los campos necesarios y su contrato están en [RECOLECCION_DATOS.md](RECOLECCION_DATOS.md).

### Prioridad del último corte

La misma regla rige para todos los municipios. En las fichas porcentuales 5
(control de confianza) y 7 (CUP vigente), cuando ambas ediciones recientes
son comparables, están acreditadas y el porcentaje final supera al anterior,
la calificación **del periodo reciente** utiliza:

`promedio_reciente = (porcentaje_anterior + 2 × porcentaje_último) / 3`.

Si no hay mejora acreditada, se conserva la media ordinaria. La calificación
general mantiene su serie completa. Sigue vigente el mínimo de cada año para
obtener 5, así como los candados y la declaración de cobertura parcial. Un
avance de un rubro no borra un retroceso observado en otro. La convención 1:2
es una decisión metodológica del equipo, no una ponderación estimada por una
fuente externa; su efecto y los dos valores utilizados se registran en el JSON.
Otros indicadores ya distinguen continuidad y último corte mediante sus
propias fichas; no se aplica la fórmula porcentual a existencias, equipos,
llamadas, fallecimientos ni remisiones, donde “más” no siempre es “mejor”.

## Correspondencias entre datos y criterios

Las definiciones integradas 2.5 mantienen la ponderación 2.3 y hacen explícita la lectura automática del paquete y las gráficas de Seguridad del Anexo. Los archivos de `new-elements` aportan parámetros generales: no son datos de un municipio ni sustituyen a `input/`. El reconocimiento distingue tres operaciones:

- Recuperar un dato explícito de su título o celda, conservando indicador, año, tabla, fila y columna según corresponda.
- Homologar ese concepto con una definición o grupo temático ya adoptado, dejando identificada la regla.
- Formular una lectura condicional cuando sigue faltando una comprobación sustantiva. No convertirla en un puntaje acreditado.

Estas decisiones quedan en `correspondencias` dentro de cada evaluación, junto con sus evidencias. No reciben una marca ficticia de revisión humana. El renderizador vuelve a calcularlas a partir de las fuentes y las reglas; modificar sólo el JSON no cambia el resultado válido. Una observación complementaria documentada puede resolver una ambigüedad, pero una contradicción con información explícita exige conciliación.

Los títulos incrustados en imágenes forman parte de la evidencia documental. La lectura óptica local conserva el texto reconocido, su estado, idioma, motor y huella de la imagen en `lecturas_graficas`; el renderizador la reproduce antes de admitir sus correspondencias. Se utiliza el título completo y su intervalo de años para precisar un concepto. Los números de las tablas siguen sustentando los cálculos. Una imagen ilegible o una lectura no disponible deja el requisito pendiente; no autoriza a completar palabras o años por semejanza con otro municipio.

El título «Certificado Único Policial vigente», unido a una columna porcentual municipal, permite aplicar la definición censal adoptada para ese certificado y su universo policial. Es una homologación metodológica del dato reportado, no prueba de que se haya auditado nuevamente el levantamiento o reconstruido el denominador. El título genérico «Evaluaciones de control de confianza» no identifica el estatus aprobatorio vigente. Una gráfica que especifica «aprobó las evaluaciones» sí permite recuperar la aprobación; la vigencia sigue pendiente si no se declara. Tampoco «servidores públicos capacitados» identifica por sí solo personal exclusivo de protección civil ni acredita un conteo único, y «elementos de seguridad pública» no confirma un total exclusivamente policial sin administrativos.

En cámaras, la expresión «en funcionamiento» permite reconocer equipos en servicio para los ámbitos y años que identifique el título. Esa precisión evita pedir nuevamente un dato ya expresado en la gráfica. El puntaje definitivo todavía requiere poblaciones municipal y estatal comparables; la aclaración del concepto no aporta esos denominadores.

La homologación reconoce conceptos; no aporta cantidades inexistentes. No obtiene población a partir del tamaño de la plantilla, no transforma personal total en policías y no deduce un catálogo completo de capacitación sólo de los temas que aparecen impartidos.

Cuando se emplea `censo_base_fija`, el denominador es la población censal observada el 15 de marzo de 2020 para el municipio y el estado. Los numeradores de 2022 o 2024 se dividen por esa misma base; el resultado es una tasa **con base censal 2020**, no una tasa por habitantes efectivamente observados en esos años. La comparación entre municipios y periodos queda condicionada por el crecimiento demográfico no incorporado. La fuente, el año del numerador y el año de la base se conservan en el complemento. Esta opción no autoriza atribuir una población 2024 al INEGI ni aplicar la base 2020 a 2014–2018.

## Homologaciones que sí se realizan

En uniformes se cuentan seis grupos: camisola o camisa; pantalón; calzado; chamarra; fornitura o cinturón táctico; chaleco táctico. Dos prendas del mismo grupo no duplican la cobertura. Gorra, uniforme de gala o goggles no sustituyen los grupos básicos. Tanto anual como semestral satisfacen una entrega mínima anual. La dotación en una única edición se evalúa antes que la dotación incompleta. La información sobre tipos de prendas no demuestra que todos los policías las hayan recibido.

Los temas de capacitación se agrupan mediante equivalencias explícitas de `config/normalizaciones.json`. Una capacitación en derechos humanos con el prefijo «Proximidad social» no cuenta simultáneamente como derechos humanos y solución de problemas. Los cambios de rótulo entre ediciones no autorizan a sumar dos veces el mismo grupo.

En fallecimientos se identifica la tabla municipal de conteos y se preservan sus vacíos. Cuando ya hay casos positivos en más de la mitad de todos los años del periodo, el criterio 1 queda acreditado aunque algunos años sigan desconocidos. La razón es la frecuencia de fallecimientos, no una supuesta falta de respuesta municipal. Cero registrado y conteo desconocido son estados distintos. No se suman desgloses al total ni se calcula un índice de letalidad a partir de estos datos.

## Información insuficiente y ambigüedades

La falta de respuesta del municipio, una variable no incluida en una edición, un dato dudoso y un denominador ausente requieren tratamientos distintos. Una celda vacía no demuestra ninguna de esas causas por sí sola.

Se conserva `null` cuando falta evidencia para aplicar un criterio. Tampoco se rellenan huecos no resueltos entre umbrales: por ejemplo, promedio de certificación mayor o igual a 95% con una caída bajo 85%. La integración explicita los escalones revisados de protección civil y llamadas, descritos más abajo. Una revisión documental que acredite ausencia de respuesta municipal en todo el periodo puede asignar 1 con esa causa; una celda vacía nunca la acredita por sí sola.

Ausencia de institución municipal propia y mando único no son equivalentes. La primera se registra como `no_aplicable` para los rubros policiales del periodo y bloquea la agregación hasta definir un universo específico, sin penalización. El segundo no elimina automáticamente la institución ni sus obligaciones.

Las siguientes dependencias sí están expresadas en el benchmark:

- Indicador 2 con puntaje 1: el 3 también recibe 1, salvo que la evaluación reciente carezca de cobertura temporal para aplicarlo.
- Indicador 6 inferior a 3, con formación del indicador 10 de al menos 3: el 6 recibe un mínimo de 3.
- Indicador 11 con puntaje 1: el 12 no puede superar 3.

Si falta el indicador requerido para una dependencia que puede cambiar el resultado, no se inventa su valor.

## Agregación completa y valoraciones de cobertura parcial

El modo `completo` requiere los 18 puntajes. En la integración 2.3 el esquema principal calcula la media ponderada de cada dimensión y luego aplica estos pesos:

| Dimensión | Indicadores | Peso final |
| --- | --- | --- |
| Protección civil | 1–3 | 25% |
| Condiciones del personal | 4–10 | 35% |
| Inteligencia y eficiencia policial | 11–18 | 40% |

Los prioritarios son 2, 4, 5, 10, 11, 12, 13 y 14, con peso 2; los restantes pesan 1. Las sumas completas son 4, 10 y 12 por dimensión. Esta elección es una convención explícita del equipo, no una estimación estadística de importancia causal.

El modo `evaluables` exige 2 de 3, 5 de 7 y 6 de 8 por dimensión y al menos seis de los ocho prioritarios. Calcula medias ponderadas sólo sobre los puntajes acreditados y conserva el peso 25/35/40 de las dimensiones. No incorpora pendientes como ceros, unos ni estimaciones. Los coeficientes efectivos se registran: con cobertura parcial cambian los pesos internos. La razón máxima de efecto entre prioritarios es 1.875 con cobertura completa, pero puede superar 2 al faltar secundarios; no se promete el mismo límite para coberturas parciales.

El modo `disponibles`, predeterminado para generar el estudio, relaja **sólo la cobertura mínima de la agregación**: exige al menos un puntaje acreditado en cada dimensión y uno de los ocho prioritarios. Mantiene las definiciones de las fichas, los pesos 25/35/40, los candados y el tope MUY BIEN cuando hay pendientes. Repondera únicamente dentro de cada dimensión sobre los indicadores calificados; no asigna puntajes a los ausentes. Su resultado se denomina «categoría de cobertura parcial», nunca evaluación completa de los 18 indicadores. El Word informa cobertura total, por dimensión y prioritaria, y advierte que la categoría puede cambiar. Si falta toda una dimensión, no hay prioritarios acreditados o existe un universo no aplicable, no se asigna categoría.

Cuando existen pendientes, este modo devuelve `calculado_parcial`, declara la cobertura total y por dimensión y limita la categoría máxima a MUY BIEN. La narración debe identificar el alcance, por ejemplo: «La valoración de los 14 indicadores evaluables es MUY BIEN; cuatro rubros no cuentan con elementos suficientes para asignarles puntaje». El archivo puede ser una entrega editorial final y, al mismo tiempo, declarar honestamente el alcance de su evaluación.

El cálculo conserva también un intervalo de sensibilidad de la evaluación completa: asigna hipotéticamente 1 y 5 a los pendientes únicamente para obtener límites inferior y superior. Esos escenarios no sustituyen los puntajes `null` ni se presentan como observaciones. Si las categorías extremas difieren, la categoría completa sigue siendo indeterminada.

La API activa es `ponderacion.agregar_ponderado(..., modo='completo')`; la CLI elige `disponibles` por defecto y registra la selección. `calificar.agregar` permanece para comparación histórica y pruebas, no es el agregador del documento final. `dimensiones_iguales` usa pesos individuales 1 y tercios por dimensión; reproduce el promedio histórico, pero conserva candados nuevos. `global` divide la suma de productos puntaje × peso entre pesos evaluables. Ninguna comparación cambia automáticamente el esquema elegido.

La categoría completa exige cobertura suficiente en ambos periodos. En modo `completo`, cualquier pendiente impide asignarla; en `evaluables`, la impide una cobertura insuficiente por dimensión o prioridad. El modo `disponibles` permite una categoría **parcial**, con su etiqueta y nota de alcance visibles. Un universo no aplicable impide la agregación ordinaria. La falta de categoría **no bloquea la publicación del estudio**: el Word dice «SIN VALORACIÓN CONJUNTA» y añade cobertura efectiva. Una interpretación editorial revisada y vinculada a la evidencia sigue siendo obligatoria. `--preparar` conserva la evidencia para revisión sin publicar ni sustituir la entrega vigente.

## Candados y precisión

Se conserva precisión decimal interna. Sólo para clasificar se redondea a dos decimales con `ROUND_HALF_UP`.

Después del promedio se aplican los límites del benchmark: una dimensión inferior a 1.50 impide superar REGULAR; EXCELENTE requiere todas las dimensiones de al menos 4 y ningún indicador con 1; MUY BIEN requiere todas las dimensiones de al menos 2.50. Diez o más indicadores con 1 por falta de respuesta municipal acreditada llevan a CATASTRÓFICO. En el modo evaluable los límites se revisan sobre la evidencia disponible, además del tope por cobertura parcial.

Se añaden los candados 7–9: EXCELENTE requiere los ocho prioritarios con al menos 4; MUY BIEN requiere media ponderada de prioritarios de al menos 3 y ninguno con 1; cuatro prioritarios con 1 por falta de respuesta acreditada limitan a MAL. No cambian los puntajes individuales. Un 1 por un resultado observado sí activa el candado 8, pero no prueba falta de respuesta para el 9.

El benchmark permite un máximo de tres ajustes justificados de un punto por evaluación. Esta implementación no aplica ajustes discrecionales automáticos. Una diferencia de dos categorías entre periodos debe explicarse con evidencia; no autoriza a atribuir el cambio a una administración, subsidio o decisión presupuestal sin documentación.

## Verificación

`python3 -m unittest discover -s tests -v` comprueba reglas base, integración 2.3, huellas, periodicidades, no imputación, cobertura, ponderación, candados, evidencia complementaria, redacción y publicación del Word. Las pruebas validan la implementación; no demuestran la exactitud externa de las estadísticas ni sustituyen la revisión editorial.

## Convenciones nuevas de las fichas 3 y 15

La propuesta no especificó todos los escalones inferiores de protección civil. La convención incorporada, pendiente de ratificación sustantiva del equipo, usa la media anual de grupos acreditados/grupos captados: 5 desde 80% con riesgos en todas las observaciones; 4 desde 2/3; 3 desde 1/3; 2 si es positiva; 1 si es cero y la ausencia está acreditada. Sin riesgos el máximo es 4. Sin catálogo de la edición o sin homologación verificable no puntúa. No se acumulan temas de diferentes años para simular cobertura simultánea ni se suman participantes por tema como personas únicas.

Llamadas: 5 requiere registro completo, tasas calculables y meta documentada de respuesta/despacho cumplida en todo el periodo; 4, registro y tasas sin acreditar esa meta; 3, continuidad parcial con ambos cortes recientes y ausencia acreditada de los otros, o señal de dato dudoso; 2, registro previo con ausencia acreditada en ambos cierres recientes; 1, ausencia acreditada en todos los cortes aplicables. Un vacío no aclarado conserva `null`. El porcentaje de procedencia puede contextualizar la demanda, pero no mide eficacia; 100% limita a 3 aun cuando se acrediten otros requisitos. Estas escalas operativas se identifican como integración, no como transcripción literal de los archivos del asesor.

## Valoraciones provisionales

Se conserva `valoracion_provisional` junto a un puntaje `null`: nivel indicativo o null, evidencia usada, confianza, dato faltante y `computa_en_agregacion: false`. No es una manera de completar los ocho prioritarios. Las cifras absolutas de personal no se convierten en un nivel sin denominador; el listado de cursos no se transforma en personas capacitadas.

En capacitación policial, la presencia positiva de dos o más grupos núcleo en el último año observado permite nivel indicativo 3; un grupo permite 2. Los rótulos equivalentes cuentan una sola vez. Se identifica expresamente ese año para no presentar la lectura reciente como cobertura de todo el periodo. No se suman participantes repetidos ni se supone que un tema no listado equivale a cero; el nivel 1 requiere acreditar la ausencia, no una homologación fallida. Profesionalización y capacitación permanecen diferenciadas.

En llamadas, dos cortes municipales recientes con conteos permiten nivel indicativo 3, de confianza baja, como lectura condicional de continuidad de la serie reportada. Si se desconoce quién opera el servicio, esa incertidumbre permanece: no se declara competencia municipal ni se asigna el puntaje definitivo. Esta convención de integración recoge la lectura de continuidad propuesta por el asesor sin atribuirle una validación adicional; reemplaza el bloqueo automático de toda interpretación por falta de confirmación del operador. Los conteos no prueban tiempos de atención, resolución ni desempeño. Un vacío tampoco basta para asignar nivel 2 por supuesto registro incompleto.

En cámaras, los conteos pueden sostener una lectura provisional de presencia y evolución aun sin poblaciones comparables; no acreditan por sí mismos que los equipos funcionen. Si el título de la gráfica especifica funcionamiento y cubre los años evaluados, esa condición queda documentada, mientras permanecen pendientes los denominadores que falten. Cada valoración declara su base y qué evidencia falta para aplicar la ficha definitiva.

Cuando todos los pendientes admiten nivel provisional, se calcula un escenario intermedio separado. Los extremos que asignan 1 y 5 permanecen intactos; el escenario no los estrecha ni pasa por resultado observado. Sin evidencia sustituta suficiente se declara `no_estimable`. Una institución no aplicable no se somete a esos escenarios como si fuera un dato desconocido ordinario.

## Fuentes y decisiones pendientes

Se prefiere una serie anual CONAPO consistente y documentada. Las tasas requieren año y fecha de referencia; comparaciones municipales y estatales exigen la misma serie, método y fecha. No se mezclan censos, proyecciones e interpolaciones silenciosamente. Una interpolación geométrica exige dos anclajes documentados, año interior y reproducción del valor; no autoriza extrapolar.

Las precisiones censales del material recibido deben cotejarse contra la edición usada en cada tabla, especialmente catálogos de protección civil y universo policial. Fuentes de consulta: [CNGMD 2023, seguridad pública](https://www.inegi.org.mx/contenidos/programas/cngmd/2023/doc/cngmd_2023_m3s1.pdf), [ejercicio de la función policial](https://www.inegi.org.mx/contenidos/programas/cngmd/2023/doc/cngmd_2023_m3s2.pdf) y [protección civil](https://www.inegi.org.mx/contenidos/programas/cngmd/2023/doc/cngmd_2023_m4.pdf). Consultar esos cuestionarios no completa por sí solo las cifras municipales faltantes. La numeración de reactivos no se traslada automáticamente a otra edición.

El catálogo narrativo recibido no contiene los 144 cierres anunciados. Sus encuadres son referencias que requieren revisión semántica. La plataforma electoral opcional usa el mismo cálculo municipal como contexto, pero requiere propuestas redactadas para ese municipio. No se trasladan causalidades, recomendaciones ni cifras de ejemplo al estudio o a la plataforma.
