# Metodología del Estudio de Seguridad

La evaluación distingue cuatro documentos con funciones diferentes:

| Documento | Función |
| --- | --- |
| `templates/Machote general medicion version final.docx` | Formato de la consultora que recibe el texto final. |
| `templates/Machote general medicion version final rzg investigación.docx` | Guía de los apartados que deben interpretarse y sus variables. |
| `templates/Machote_seguridad_general_con_calificacion.docx` | Benchmark: 18 fichas, 90 criterios, escala, dimensiones y candados. |
| `input/word/{municipio} PAQUETE SEGURIDAD.docx` | Estadísticas municipales y estatales. El Anexo del mismo municipio permite un contraste adicional cuando está disponible. |

La muestra de estudio aportada por el usuario sirve para orientar la escritura. Sus cifras, conclusiones y calificaciones no se transfieren al municipio evaluado. El producto es `{municipio} Estudio Seguridad.docx`: una interpretación de las estadísticas dentro del formato de la consultora. Las fichas de cálculo, sus instrucciones y las referencias internas permanecen en los archivos de trabajo.

## Procedencia y reproducción de las reglas

`python3 scripts/estructurar_reglas.py` lee el benchmark activo y transcribe sus 18 fichas. Conserva el texto de los 90 criterios, su tabla y fila, los párrafos de aplicación y la huella SHA-256 del documento. Actualiza `config/metodologia_seguridad.json` y `reglas_calificacion.json` con la versión 2.2.

El programa comprueba que los criterios del documento coincidan con los que sustentan la lógica ejecutable. Si cambió un criterio, se detiene para revisar su implementación; no conserva silenciosamente una regla anterior. La migración documental debe regenerarse después para actualizar las huellas del contrato.

Las referencias académicas y normativas se reciben como parte del benchmark. Su inclusión no significa que el proceso haya consultado nuevamente esas obras, verificado la vigencia de una ley ni acreditado cumplimiento jurídico. La narración distingue entre lo declarado en las estadísticas, el parámetro de evaluación adoptado y las conclusiones que efectivamente pueden sostener los datos.

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
| 3 | Cobertura de seis grupos temáticos de protección civil; el máximo requiere al menos cinco e incluir análisis de riesgos. |
| 4 | Policías por cada mil habitantes: referencia superior de 1.8, con escalones de 1.2 y 0.8; máximo 4 para plantillas menores de 15. Requiere población documentada. |
| 5 y 7 | Promedio porcentual y mínimo observado; 5 exige promedio de al menos 95% y ninguna caída bajo 85%. |
| 8 | Prendas básicas diferentes y frecuencia; cinco o más grupos con entrega al menos anual para los niveles altos. |
| 9 | Chalecos por elemento, radios por elemento y equipo menos letal. La ficha fija referencias de 1 y 0.5 para chalecos, y 0.5 para radios. Requiere aclarar inventario frente a dotación. |
| 10 | Capacitación en grupos temáticos núcleo; dos o más con cobertura de al menos la mitad del personal para el máximo. |
| 14 | Cámaras por cada mil habitantes frente a la tasa estatal, continuidad y evolución. Requiere ambas poblaciones comparables. |
| 15 | Porcentajes de llamadas procedentes municipales y estatales comparables. No representa por sí solo eficacia ni tiempo de respuesta. |
| 17 | Fallecimientos, continuidad de los registros y, cuando corresponda, tasas comparables y eventos. Los porcentajes de egresos no sustituyen los conteos de muertes. |
| 18 | Puestas a disposición divididas entre incidencia delictiva y comparación estatal. El máximo también requiere revisión documentada de recomendaciones de derechos humanos. |

Las fichas completas y sus condiciones exactas están en `reglas_calificacion.json`. Los indicadores 4, 9, 14 y 18 conservan una revisión contextual cuando no se reúnen denominadores, definiciones o evidencia necesarios; esta versión no resuelve esas carencias con supuestos.

## Homologaciones que sí se realizan

En uniformes se cuentan seis grupos: camisola o camisa; pantalón; calzado; chamarra; fornitura o cinturón táctico; chaleco táctico. Dos prendas del mismo grupo no duplican la cobertura. Gorra, uniforme de gala o goggles no sustituyen los grupos básicos. Tanto anual como semestral satisfacen una entrega mínima anual. La dotación en una única edición se evalúa antes que la dotación incompleta. La información sobre tipos de prendas no demuestra que todos los policías las hayan recibido.

Los temas de capacitación se agrupan mediante equivalencias explícitas de `config/normalizaciones.json`. Una capacitación en derechos humanos con el prefijo «Proximidad social» no cuenta simultáneamente como derechos humanos y solución de problemas. Los cambios de rótulo entre ediciones no autorizan a sumar dos veces el mismo grupo.

En fallecimientos se identifica la tabla municipal de conteos y se preservan sus vacíos. Cuando ya hay casos positivos en más de la mitad de todos los años del periodo, el criterio 1 queda acreditado aunque algunos años sigan desconocidos. La razón es la frecuencia de fallecimientos, no una supuesta falta de respuesta municipal. Cero registrado y conteo desconocido son estados distintos. No se suman desgloses al total ni se calcula un índice de letalidad a partir de estos datos.

## Información insuficiente y ambigüedades

La falta de respuesta del municipio, una variable no incluida en una edición, un dato dudoso y un denominador ausente requieren tratamientos distintos. Una celda vacía no demuestra ninguna de esas causas por sí sola.

Se conserva `null` cuando falta evidencia para aplicar un criterio. Tampoco se rellenan huecos entre umbrales de las fichas: por ejemplo, promedio de certificación mayor o igual a 95% con una caída bajo 85%, o cinco temas de protección civil sin análisis de riesgos. La política puede revisarse por el equipo responsable, pero cualquier resolución debe quedar documentada antes de automatizarse.

Las siguientes dependencias sí están expresadas en el benchmark:

- Indicador 2 con puntaje 1: el 3 también recibe 1, salvo que la evaluación reciente carezca de cobertura temporal para aplicarlo.
- Indicador 6 inferior a 3, con formación del indicador 10 de al menos 3: el 6 recibe un mínimo de 3.
- Indicador 11 con puntaje 1: el 12 no puede superar 3.

Si falta el indicador requerido para una dependencia que puede cambiar el resultado, no se inventa su valor.

## Agregación completa y adaptación sobre indicadores evaluables

El modo `completo` reproduce la agregación del benchmark. Requiere los 18 puntajes; calcula un promedio simple por dimensión y después el promedio simple de las tres dimensiones:

| Dimensión | Indicadores | Peso final |
| --- | --- | --- |
| Protección civil | 1–3 | 1/3 |
| Condiciones del personal | 4–10 | 1/3 |
| Inteligencia y eficiencia policial | 11–18 | 1/3 |

El modo `evaluables` es una adaptación explícita para producir una valoración de la información disponible. No equivale a la evaluación completa del benchmark. Exige al menos dos tercios de los indicadores en cada dimensión, redondeados hacia arriba: 2 de 3, 5 de 7 y 6 de 8. Calcula el promedio de los indicadores evaluables dentro de cada dimensión y conserva el peso de un tercio para cada dimensión. No incorpora los pendientes como ceros, unos ni promedios estimados.

Cuando existen pendientes, este modo devuelve `calculado_parcial`, declara la cobertura total y por dimensión y limita la categoría máxima a MUY BIEN. La narración debe identificar el alcance, por ejemplo: «La valoración de los 14 indicadores evaluables es MUY BIEN; cuatro rubros no cuentan con elementos suficientes para asignarles puntaje». El archivo puede ser una entrega editorial final y, al mismo tiempo, declarar honestamente el alcance de su evaluación.

El cálculo conserva también un intervalo de sensibilidad de la evaluación completa: asigna hipotéticamente 1 y 5 a los pendientes únicamente para obtener límites inferior y superior. Esos escenarios no sustituyen los puntajes `null` ni se presentan como observaciones. Si las categorías extremas difieren, la categoría completa sigue siendo indeterminada.

La API `agregar(..., modo='completo')` mantiene el modo estricto como predeterminado. El flujo que utilice `evaluables` debe elegirlo expresamente y registrar esa selección.

La publicación del Word final exige una calificación conjunta en ambos periodos. En modo `completo`, cualquier indicador sin puntaje bloquea esa publicación; en modo `evaluables`, la bloquea una cobertura inferior al mínimo de alguna dimensión. `--preparar` permite conservar la evidencia con calificaciones pendientes para revisarla, sin publicar un nuevo documento ni sustituir la entrega vigente.

## Candados y precisión

Se conserva precisión decimal interna. Sólo para clasificar se redondea a dos decimales con `ROUND_HALF_UP`.

Después del promedio se aplican los límites del benchmark: una dimensión inferior a 1.50 impide superar REGULAR; EXCELENTE requiere todas las dimensiones de al menos 4 y ningún indicador con 1; MUY BIEN requiere todas las dimensiones de al menos 2.50. Diez o más indicadores con 1 por falta de respuesta municipal acreditada llevan a CATASTRÓFICO. En el modo evaluable los límites se revisan sobre la evidencia disponible, además del tope por cobertura parcial.

El benchmark permite un máximo de tres ajustes justificados de un punto por evaluación. Esta implementación no aplica ajustes discrecionales automáticos. Una diferencia de dos categorías entre periodos debe explicarse con evidencia; no autoriza a atribuir el cambio a una administración, subsidio o decisión presupuestal sin documentación.

## Verificación

`python3 -m unittest discover -s tests -p test_calificacion.py -v` comprueba reproducción de las reglas, huella del benchmark, periodicidades, ausencia de imputación, homologaciones, dependencias, agregación, cobertura y límites. Estas pruebas validan la implementación de la metodología; no validan la exactitud externa de las estadísticas recibidas.
