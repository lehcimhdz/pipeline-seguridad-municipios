# Metodología de calificación — pipeline v3.2

## Qué se califica y por qué

Se emite siempre una nota para los 18 indicadores y para cada periodo, pero
no se inventan datos para conseguirla. La nota publicada es una **calificación
documental interna**: mide lo acreditable frente a las fichas de este proyecto.
No es certificación oficial, prueba de cumplimiento legal, tasa delictiva ni
evaluación causal de una administración.

Se distinguen dos valores por indicador y periodo:

| Campo JSON | Significado |
| --- | --- |
| `puntaje` | Puntaje observado 1–5, sólo cuando hay evidencia válida y un criterio inequívoco; en otro caso `null`. |
| `puntaje_asignado` | Nota documental 1–5 siempre presente: copia el observado o asigna 1 cuando no puede acreditarse. |
| `base_calificacion` | `observado` o `no_acreditado`; permite distinguir dos notas numéricamente iguales. |
| `motivo_asignacion` | Criterio aplicado o razón específica de la no acreditación, sin borrar el motivo original. |

El piso 1 es una decisión normativa interna y conservadora: evita premiar
información no acreditada y mantiene los 18 indicadores en el denominador.
No significa que el valor real del indicador sea 1, que el municipio haya
incumplido ni que se haya negado a responder. Usar un 3 neutral, sustituir
con años anteriores o excluir faltantes mejoraría artificialmente una nota
sin nueva evidencia. Tampoco se aplica una penalización adicional por
falta de respuesta: ésta tendría que documentarse expresamente.

Las fichas históricas a veces incluyen “sin dato” en un nivel bajo. Desde
v3.2, una ausencia de dato no se reporta como desempeño observado. La
asignación documental permite emitir una calificación sin esa confusión.

Como referencia general para transparentar decisiones de construcción de
indicadores compuestos se utiliza el [manual OCDE/JRC](https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators-methodology-and-user-guide_9789264043466-en.html).
La selección del piso 1, los umbrales y los pesos de este proyecto son
decisiones internas, no estándares avalados por ese manual.

## Dónde se configura

[reglas_calificacion.json](reglas_calificacion.json) es el archivo activo:
contiene las 18 fichas, 90 criterios históricos, reglas ejecutables, las
tres dimensiones y `calificacion_documental`. Esta sección define:

| Parámetro | Valor predeterminado | Uso real |
| --- | --- | --- |
| `version` | `1.0` | Versión de esta política, independiente de la versión 3.2 del pipeline. |
| `piso_no_acreditado` | 1 | Nota asignada a puntajes observados `null`. El validador exige el extremo 1 de la escala. |
| `techo_sensibilidad` | 5 | Extremo superior del escenario de sensibilidad; el validador exige 5. |
| `pesos_dimension` | 1, 1, 1 | Pesos relativos positivos; se normalizan por su suma. |
| `escala_documental` | Mínimos 4.5, 3.5, 2.5, 1.5 y 1 | Clasificación del promedio, redondeado a dos decimales. |
| `candados.dimension_colapsada_minimo` | 1.5 | Activa un tope de ACREDITACIÓN PARCIAL cuando alguna dimensión queda debajo. |
| `candados.excelente_dimension_minimo` | 4 | Mínimo de cada dimensión para permitir ACREDITACIÓN MUY ALTA; además no puede haber ningún indicador con 1. |
| `candados.muy_bien_dimension_minimo` | 2.5 | Mínimo de cada dimensión para permitir ACREDITACIÓN ALTA. |
| `candados.falta_respuesta_umbral` | 10 | Sólo con falta de respuesta explícita y puntajes observados 1; nunca se deduce de un `null`. |

Cambiar pesos o umbrales es una decisión metodológica: registrar el motivo,
incrementar la versión de la política, revisar efectos en ambos periodos y
regenerar el contrato. La migración conserva los parámetros activos; no
los restablece desde [config/metodologia_seguridad.json](config/metodologia_seguridad.json),
que queda como referencia histórica.

    python3 scripts/migrar_machote_v3.py
    python3 scripts/validar_plantilla.py
    python3 -m unittest discover -s tests -v
    python3 scripts/ejecutar_pipeline.py --investigacion-json input/revision/investigacion_seguridad.json

No todos los criterios narrativos son parámetros automáticos. Las fichas de
existencia, cursos y porcentajes consumen `reglas_ejecutables`; los adaptadores
de temas, personal, cámaras, llamadas y puestas a disposición tienen lógica
explícita en [scripts/calificar.py](scripts/calificar.py). Cambiar sólo el
texto de un umbral de esas fichas no cambia el cálculo: exige modificar su
adaptador y sus pruebas. Uniformes, equipamiento y fallecimientos todavía
requieren revisión contextual; no se simula una automatización inexistente.

## Fórmula, pesos y redondeo

Para cada indicador `i`, sea `s_i` el puntaje observado o `null`:

    a_i = s_i, si s_i es verificable
    a_i = 1,   si s_i es null

Se calcula la media de las notas asignadas dentro de cada dimensión `d`:

    D_d = suma(a_i de la dimensión d) / cantidad de indicadores de d
    M   = suma(peso_d × D_d) / suma(peso_d)

Las dimensiones son:

| Dimensión | Indicadores | Peso predeterminado | Peso efectivo de cada indicador |
| --- | --- | --- | --- |
| Protección civil | 1–3 | 1/3 | 1/9 |
| Condiciones del personal | 4–10 | 1/3 | 1/21 |
| Inteligencia y eficiencia policial | 11–18 | 1/3 | 1/24 |

Por ello, igual peso entre dimensiones no significa igual peso entre los
18 indicadores. La fórmula conserva esa estructura del modelo histórico.
Todos los pesos deben ser positivos; las dimensiones deben contener los
18 indicadores exactamente una vez. No se excluyen faltantes.

La precisión interna usa `Decimal`. Sólo para clasificar y mostrar se
aplica `ROUND_HALF_UP` a dos decimales; no se redondean datos fuente para
forzar su entrada en un intervalo de una ficha.

| Promedio redondeado | Categoría documental preliminar |
| --- | --- |
| 4.50–5.00 | ACREDITACIÓN MUY ALTA |
| 3.50–4.49 | ACREDITACIÓN ALTA |
| 2.50–3.49 | ACREDITACIÓN PARCIAL |
| 1.50–2.49 | ACREDITACIÓN BAJA |
| 1.00–1.49 | NO ACREDITADO |

Los candados se aplican en el orden 1–4 de la configuración y sólo pueden
reducir la categoría, no mejorarla. Son cautelas operativas heredadas de la
agregación histórica. El Word conserva el promedio numérico y la categoría
después de candados; por eso ambos pueden no corresponder al mismo tramo
preliminar. El JSON registra cada candado y si modificó la categoría.

La categoría histórica EXCELENTE / MUY BIEN / REGULAR / MAL / CATASTRÓFICO
sólo aparece en `categoria_desempeno` cuando los 18 puntajes son observados,
mediante la agregación histórica. No se obtiene sustituyendo faltantes.
Si se cambian los pesos documentales, esa categoría histórica sigue siendo
un resultado distinto calculado con la metodología histórica.

## Periodos y faltantes

El periodo general utiliza las observaciones documentadas de cada indicador,
no una imputación anual continua. El reciente utiliza los mismos dos años
calendario consecutivos para los 18 indicadores, terminando en el último
año municipal documentado. Una observación anterior no sustituye un año
ausente. Debe revisarse la correspondencia entre edición censal y año de
referencia antes de cerrar un diagnóstico.

Se mantiene `puntaje=null`, con asignación documental 1, si falta un año
requerido, un denominador comparable o la homologación necesaria; si hay
datos inválidos, duplicados no conciliados o una combinación no cubierta
por la ficha. No se completan huecos entre umbrales: por ejemplo 84.95 puede
quedar entre tramos históricos y requiere revisión, no redondeo oportunista.
Un tema vacío no significa que no hubo capacitación. Una celda en blanco
no se convierte en cero. Una referencia estatal igual a cero no se divide.

Las dependencias particulares se aplican al puntaje observado antes de la
capa documental: 2→3, 10→6 y 11→12. El piso asignado a un faltante no se usa
para inferir una condición observada en otro indicador.

## Cobertura y sensibilidad

Se publican juntos la nota, los faltantes y estas dos coberturas:

    cobertura_simple = indicadores con puntaje observado / 18 × 100
    cobertura_ponderada = suma(peso_d × observados_d / cantidad_d) / suma(peso_d) × 100

`asignados=18` no significa `observados=18`. Las coberturas no miden certeza,
calidad estadística ni proporción de años o celdas completos. El general
puede tener puntaje observado sobre una serie documental más corta.

La sensibilidad mantiene fijos los puntajes observados y reemplaza sólo
los no observados por 1 en el escenario mínimo y 5 en el máximo. Se aplica
la misma agregación, antes de candados. No se usa para asignar una categoría
optimista ni para estimar cómo serán los datos futuros. No es un intervalo
de confianza, y no incluye otras fuentes de incertidumbre o cambios de pesos.

## Parámetros y evidencia de los 18 indicadores

Los umbrales siguientes describen las fichas internas, no obligaciones
legales ni estándares oficiales verificados. Una mayor cifra no siempre
significa mejor seguridad; las notas no sustituyen el análisis contextual.

| ID | Indicador y método | Datos o condiciones relevantes |
| --- | --- | --- |
| 1 | Plan de protección civil; existencia | Respuesta reconocible por edición; continuidad e intermitencia. La existencia reportada no prueba vigencia o implementación. |
| 2 | Capacitación de protección civil; cursos | Cursos y personal capacitado no negativos; continuidad, 75 % y 50 % de ediciones, y observaciones recientes. No sumar personas como individuos únicos. |
| 3 | Temas de protección civil; homologación | Temas núcleo únicos; 5 o más y análisis de riesgos para el máximo, 4 para nivel 4, 2–3 para nivel 3, 1 para nivel 2. Cinco sin riesgos no tienen criterio inequívoco. |
| 4 | Personal de seguridad; tasa | Personal/población × 1000, mismo año y municipio. Umbrales históricos 1.8, 1.2 y 0.8; no interpolar población ni ocultar huecos 1.79–1.8 o 1.19–1.2. |
| 5 | Control de confianza; porcentaje | Valores 0–100; promedio 95 y mínimo 85 para máximo, tramos 85–94.9, 70–84.9, 50–69.9. Evaluación no implica aprobación ni vigencia. |
| 6 | Instituto de formación; existencia | Serie de existencia; dependencia del indicador 10 para formación externa. No inventar convenios. |
| 7 | Certificado Único Policial; porcentaje | Vigencia identificada, porcentajes y umbrales como ficha 5; revisar consistencia con control de confianza. |
| 8 | Uniformes; revisión contextual | Prendas básicas homologadas, al menos 5 para niveles altos, frecuencia anual o una sola vez, dotación y cobertura. El nombre de una prenda no prueba periodicidad. |
| 9 | Equipamiento; revisión contextual | Chalecos/personal ≥ 1 y radios/personal ≥ 0.5 más equipo menos letal; límite inferior de chalecos 0.5. Distinguir inventario de dotación del año y usar personal compatible. |
| 10 | Capacitación policial; homologación | Temas núcleo, total y porcentaje válido por año; ≥ 50 % en al menos 2 temas para niveles altos. No sumar porcentajes de participantes superpuestos. |
| 11 | Georreferenciación; existencia | Existencia identificada por edición; no inferir uso operativo a partir de coordenadas sin justificación. |
| 12 | Patrullajes estratégicos; existencia | Continuidad y respuesta reconocible; máximo 3 si indicador 11 observado=1. No inferir focalización eficaz sólo por existencia. |
| 13 | Problemas comunitarios; existencia | Serie de atención reportada; no equivale automáticamente a solución de problemas o metodología demostrada. |
| 14 | Cámaras; tasas comparables | Cámaras/población × 1000 municipal y estatal por año; referencia estatal, continuidad y retrocesos. No prueba funcionamiento ni monitoreo. |
| 15 | Llamadas procedentes; comparación | Porcentajes 0–100 completos y comparables frente al estado; vacíos no son puntajes observados 1 o 2. No deduce calidad o tiempo de respuesta. |
| 16 | Informe anual; existencia | Existencia por edición y tipo de informe; no equiparar publicación con rendición de cuentas efectiva. |
| 17 | Personal, egresos y fallecimientos; revisión contextual | Totales de muertes, años completos, tasa por personal y referencia estatal; conciliar desgloses, bases de porcentajes y series. No sumar categorías superpuestas ni interpretar un vacío como ausencia de muertes. |
| 18 | Puestas a disposición; razones | Personas/incidencia comparable municipal y estatal; referencias relativas 1 y 0.75. Requiere distinguir destinos MP/juez cívico. Máximo 5 exige estabilidad y revisión documentada de derechos humanos; el adaptador automático no lo otorga. |

El código reconoce datos negativos, porcentajes imposibles y ciertos vacíos;
esa validación técnica no resuelve por sí sola incompatibilidades de universo,
clasificación o finalidad. Los indicadores 8, 9 y 17 siguen sin regla contextual
automática que convierta toda evidencia en desempeño observado.

## Variables y trazabilidad en el machote

La copia parametrizada mantiene la estructura del original y añade 41
variables a las 116 previas, para un total de 157:

- 36 campos: `{calificacion_indicador_01_general}` a
  `{calificacion_indicador_18_general}` y sus equivalentes `_ultimo_periodo`.
- `{metodologia_calificacion}`.
- `{cobertura_general}` y `{cobertura_ultimo_periodo}`.
- `{sensibilidad_general}` y `{sensibilidad_ultimo_periodo}`.

Las calificaciones globales incluyen promedio/5 y categoría documental.
Los análisis explican el criterio o el motivo de la nota por indicador;
gráficas y hoja de cómputo usan `puntaje_asignado` identificado como documental.
El JSON mantiene tablas originales, procedencia, SHA-256 y puntajes observados.
Antes de renderizar se recomputan asignaciones y agregados para rechazar
alteraciones inconsistentes.

El amarillo se elimina del Word de salida, incluidas las marcas heredadas
del original. No se elimina la trazabilidad del JSON ni se altera el archivo
original. El contrato documenta esa excepción de fidelidad.

Siempre emitir nota no significa siempre emitir un documento final. El
borrador conserva pendientes técnicos y revisión humana. Un final documental
puede mantener puntajes observados `null` si declara sus límites, completa
las fuentes exigidas y resuelve explícitamente las revisiones; no se convierte
por ello en una validación del desempeño faltante. El software verifica
coherencia, estado y revisiones declaradas, no puede certificar que una revisión
humana realmente ocurrió. Poner `estado_ejecucion=validado` o borrar avisos
no sustituye esa revisión.

## Resultado de la prueba local

Con la evidencia local usada al introducir v3.2:

| Periodo | Nota documental | Observados | Cobertura ponderada | Sensibilidad antes de candados |
| --- | --- | --- | --- | --- |
| General | 3.12/5 — ACREDITACIÓN PARCIAL | 12/18 (66.67 %) | 73.21 % | 3.12–4.19/5 |
| Reciente 2023–2024 | 1.00/5 — NO ACREDITADO | 0/18 (0 %) | 0 % | 1.00–5.00/5 |

En ambos hay 18/18 notas asignadas. Los pendientes generales son 4, 8, 9,
14, 17 y 18. En el reciente falta 2023 para 1–16 y se mantienen las revisiones
de 17–18. La diferencia entre notas no demuestra deterioro municipal: refleja
también distinta cobertura, que debe mostrarse siempre junto a la calificación.
