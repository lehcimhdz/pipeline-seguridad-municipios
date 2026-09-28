# Evidencia complementaria de la integración 2.3

El paquete municipal sigue siendo la fuente principal. El complemento es
opcional: aclara lo que no pueda resolverse en el paquete y aporta denominadores
comprobables. No sustituye los datos recibidos ni convierte el manual censal en
una observación municipal. Todos los datos de cada municipio están en `input/`;
el material de `new-elements` aporta parámetros generales para el pipeline.

## Antes de solicitar más información

Ejecutar primero `--preparar` sin complemento y leer las `correspondencias` y
los motivos de pendiente en `indicadores[].evaluaciones`. Revisar también
`lecturas_graficas`: el programa reconoce títulos, columnas y texto incrustado
en las gráficas de Seguridad del paquete y del Anexo bajo las reglas adoptadas. No hay que transcribir
esas correspondencias en un archivo de confirmaciones ni declarar
`revision: "verificada"` para habilitar cada ficha.

El título de CUP vigente permite homologar su porcentaje bajo la definición
censal adoptada. Un encabezado genérico de control de confianza, en cambio, no
identifica aprobación y vigencia. Si el título de la gráfica dice que los
elementos aprobaron las evaluaciones, queda aclarada la aprobación; todavía
debe comprobarse vigencia. «Cámaras en funcionamiento» permite reconocer
equipos en servicio en los ámbitos y años indicados, sin aportar población.
En capacitación, «servidores públicos» no prueba por
sí solo pertenencia a la unidad ni un conteo único. El complemento debe atender
esas diferencias concretas, no confirmar en bloque todas las estadísticas.

La lectura de imágenes requiere Tesseract local; véase la instalación en
[README.md](README.md). Si no está disponible o falla una lectura, el aviso no
demuestra que el documento carezca de esa aclaración. Revisar la imagen y
resolver la lectura antes de solicitar información adicional. No extraer
cifras mediante OCR para reemplazar las tablas ni extender la definición a
años que no cubra el título. La procedencia y las lecturas se comprueban de
nuevo antes de renderizar.

## Archivo y ejecución

Guardar el complemento revisado en `input/complementos/{slug}.json`. Conservar
sus fuentes en `input/fuentes/`: PDF, CSV, XLSX o DOCX quedan fuera de Git. Usar
fuentes oficiales o aclaraciones documentadas del productor del paquete.
El complemento puede provenir del CNGMD (datos abiertos CSV sin token) o de la API del Banco de Indicadores del INEGI. El token de esta última se lee sólo desde `.env`, nunca se copia al complemento, a las fuentes conservadas ni a Git. Para la ficha 18, el CNGMD y el SESNSP son fuentes distintas y deben conservarse por separado.

```sh
python3 scripts/ejecutar_pipeline.py --preparar --estado "Nombre del estado" --complemento input/complementos/{slug}.json
```

Cuando la cobertura y la redacción revisada lo permitan, ejecutar el mismo
comando sin `--preparar`. Hay que indicar de nuevo `--complemento`: no se carga
silenciosamente un archivo municipal encontrado por nombre.

Objeto inicial, todavía sin datos:

```json
{
  "version": "1.0",
  "municipio": "Nombre del municipio",
  "estado": "Nombre del estado",
  "fuentes": [],
  "poblacion": [],
  "observaciones": {}
}
```

Cada elemento de `fuentes` declara `id`, `titulo`, `archivo` y `sha256`.
`archivo` puede ser absoluto o relativo al repositorio; la huella se comprueba
contra sus bytes al preparar y antes de renderizar. Conviene conservar además
URL oficial, fecha de descarga y edición, sin secretos de acceso.

Cada población u observación añadida mediante el complemento requiere `fuente` (id anterior), `localizador`
(hoja/fila/columna, reactivo y edición o página) y `revision: "verificada"`.
Esta última es una declaración del revisor: el programa comprueba procedencia
e integridad, no interpreta por sí mismo que un PDF respalde el dato. No marcar
como verificada una correspondencia pendiente. No subir estos archivos a Git.

Si una observación combina fuentes, usar además `evidencias_campos`: un objeto con una entrada por **cada campo de dato** de la observación. Cada entrada incluye `fuente`, `localizador` y `revision: "verificada"`. Esto impide atribuir el denominador del SESNSP al CNGMD o viceversa. La procedencia general de la observación también se mantiene.

La búsqueda opcional de incidencia en el catálogo de datos.gob.mx utiliza `open-data-mexico` únicamente para localizar los CSV del SESNSP. No necesita token; se instala aparte y no forma parte de la preparación ordinaria:

```sh
python3 -m pip install -r requirements-discovery.txt
python3 scripts/incidencia_sesnsp.py --descubrir
python3 scripts/incidencia_sesnsp.py --descubrir --descargar
```

Si el servidor de descargas no permite el acceso, obtener los CSV municipal y estatal de la **misma edición** por el canal oficial y auditarlos localmente:

```sh
python3 scripts/incidencia_sesnsp.py --municipal input/fuentes/sesnsp_incidencia_municipal.csv --estatal input/fuentes/sesnsp_incidencia_estatal.csv --entidad 19 --municipio 19006 --anios 2023 2024
```

El resultado suma las doce columnas mensuales de las filas del territorio y año indicados, rechaza celdas no numéricas, no convierte ausencias en cero y muestra la huella SHA-256. Es una cifra **candidata**, no se incorpora automáticamente al complemento ni habilita `incidencia_comparable`. Verificar edición, cobertura, ámbito y definición antes de usarla; la incidencia del SESNSP cuenta presuntos delitos en carpetas de investigación, no personas remitidas.

## Población

Cada registro de `poblacion` contiene:

- `ambito`: `municipal` o `estatal`; la identidad corresponde al encabezado del archivo.
- `anio`, `valor` positivo, `serie`, `fecha_referencia` ISO (`AAAA-MM-DD`).
- `metodo`: `reconstruccion`, `proyeccion`, `censo`, `encuesta`, `interpolacion_geometrica` o `censo_base_fija`.
- Fuente, localizador y revisión, como se explicó arriba.

Se admite una sola serie por ámbito. Las tasas comparadas exigen la misma serie,
método y fecha en ambos ámbitos. Preferir una serie anual consistente; distinguir
el año de referencia del dato del año de edición censal. En las tablas del
paquete esa correspondencia debe confirmarse, no inferirse.

Si se decide usar el Censo de Población 2020 como denominador fijo para una tasa de 2022 o 2024, declarar `metodo: "censo_base_fija"`, `fecha_referencia: "2020-03-15"`, `anio_referencia_poblacion: 2020` y `uso_como_base_fija: true` en ambos ámbitos. `anio` indica el año del numerador, **no** el año en que se observó esa población. Esto permite una tasa de referencia con base 2020, no una estimación de habitantes de 2022 o 2024. No aplicar el censo 2020 retrospectivamente a años anteriores. El estudio deberá decir que la base es fija y que el crecimiento demográfico posterior no está incorporado.

La consulta para Apodaca recuperó 656 464 habitantes en el municipio y 5 784 442 en Nuevo León, ambos observados en 2020. Los CSV municipales del CNGMD permitieron cotejar 877 de 920 evaluaciones aprobatorias vigentes en 2022 y 662 de 736 en 2024. El censo de gobiernos no reemplaza el paquete municipal: sus filas se usan sólo donde coinciden ámbito, concepto y periodo. La tabla de capacitación y difusión de protección civil clasifica participantes de eventos; no acredita por sí sola personas únicas capacitadas dentro de la Unidad Municipal, por lo que no habilita la ficha 2.

Una interpolación exige `anclajes`, exactamente dos registros con `anio`,
`valor`, fuente, localizador y revisión. El año interpolado debe estar dentro
del intervalo y el valor coincidir con `P0*(P1/P0)^((año-año0)/(año1-año0))`,
con tolerancia de una persona por redondeo. No extrapolar.

## Observaciones por ficha

`observaciones` tiene claves de indicador (`"1"`…`"18"`) y dentro claves de año
(`"2024"`, por ejemplo). Sólo se agregan los campos que necesiten aclaración.
Cada entrada conserva la procedencia; los requisitos por ficha son:

| Ficha | Confirmación o datos requeridos |
| --- | --- |
| 2 | `universo: "personal_unidad_pc"`, `conteo_personas: "unico"`. Acreditar que no son cursos de difusión a población ni suma de participantes repetidos. |
| 3 | `grupos_captados`: claves de grupos en `config/definiciones_cngmd.json`; `catalogo_completo: true`. Si no se impartió ningún núcleo, `ausencia_temas_acreditada: true`; un tema no homologado no demuestra ausencia. |
| 4 | `personal_policial`: conteo sin administrativos; población del año. `institucion_propia: false` sólo cuando su ausencia esté documentada, no por mando único. Una ausencia afecta a los rubros policiales del periodo. |
| 5 | `universo: "corporaciones_policiales"`, `definicion: "aprobatorias_vigentes"`: no basta saber cuántas personas fueron evaluadas. Una gráfica que explicita aprobación resuelve esa parte; aclarar la vigencia y el universo si siguen pendientes. |
| 7 | Mismo universo; `definicion: "cup_vigente"`. No requiere complemento cuando el título y la columna ya permiten la homologación adoptada. Aclarar encabezados distintos o contradicciones. No inferir inconsistencia automáticamente por CUP cero y controles aprobados positivos. |
| 9 | `personal_policial`, `chalecos`, `radios`, `menos_letal` (conteos), `naturaleza_del_dato: "asignado_al_cierre"`. No confundir compras o entregas anuales con disponibilidad. |
| 10 | Mismo universo policial; `definicion: "capacitacion_sin_profesionalizacion"`. Confirmar denominador de porcentajes y no sumar personas entre cursos. |
| 14 | `universo: "camaras_en_servicio"` sólo si no queda reconocido mediante títulos explícitos para los ámbitos y años correspondientes; los conteos salen del paquete. Poblaciones municipal y estatal compatibles. |
| 15 | `registro_municipal: true` indica competencia del registro, no existencia automática del centro. Población y conteos de llamadas del paquete. Para 5: `meta_respuesta` documentada y `meta_respuesta_cumplida: true` en cada año. `ausencia_registro_acreditada` distingue inexistencia comprobada de vacío; `dato_dudoso` limita a 3. |
| 18 | `personas_mp`, `delitos_municipales`, `personas_mp_estatal`, `delitos_estatales`; `incidencia_comparable: true` sólo tras conciliación. Para 5: `revision_derechos: "sin_recomendaciones_documentada"` y `control_uso_fuerza: "revisado"`. Las personas ante el MP provienen del CNGMD; la incidencia delictiva, del SESNSP. Documentar cada componente con `evidencias_campos`; no usar el total de puestas a disposición ni sumar municipios con datos faltantes para estimar el estado. |

En el complemento local de Apodaca ya constan 3 083 y 2 994 probables personas responsables registradas en puestas a disposición ante el Ministerio Público (2023 y 2024), localizadas en `m3s2p19` del CNGMD 2025. Esos numeradores municipales **no** completan la ficha 18: faltan denominadores de incidencia municipal y estatal, un numerador estatal íntegro y la conciliación de comparabilidad. Los códigos `NA` y `NSS` del CNGMD estatal no son ceros. Hasta resolverlos, la ficha permanece sin calificación.

Confirmar una definición no modifica silenciosamente las celdas del paquete.
Si el paquete está equivocado, solicitar su corrección y volver a preparar con
la nueva fuente; las huellas invalidarán la redacción anterior. Un complemento
que contradiga un campo explícito reconocido deja la evaluación pendiente de
conciliación: no sirve para imponer un valor distinto sin explicarlo.

Un nivel provisional no elimina la necesidad del dato faltante. Los grupos
temáticos positivos permiten describir capacitación sin inventar personas
únicas. Dos conteos recientes de llamadas permiten una lectura condicional de
continuidad, pero no prueban competencia municipal ni completan la población.
La condición y su evidencia quedan registradas y no cuentan para el promedio.

Para cualquier ficha, `sin_respuesta_municipal_acreditada: true` exige
documentación explícita de esa causa en todos los años del periodo. Sólo si no
hay puntaje y no es un universo no aplicable permite asignar 1 por falta de
respuesta. No usarlo para forzar cobertura ni cuando falte un denominador.
Si las celdas contienen una respuesta, incluso cero o «No», el sistema no la
reclasifica como falta de respuesta para activar esos candados.

## Revisión antes de entregar

Revisar `indicadores[].evaluaciones` y `calculos` en la preparación. Se necesitan
2/3, 5/7 y 6/8 evaluables por dimensión y seis de los ocho prioritarios. Un
provisional no cuenta. Si no se alcanza esa cobertura, el pipeline conserva la
entrega anterior y no imprime una nota conjunta inventada.

Actualizar la interpretación editorial a 2.3 sólo después de leer los nuevos
resultados. Las huellas de ponderación, definiciones, textos y complemento deben
corresponder a la evidencia revisada. Los datos internos y las instrucciones
de recolección no se trasladan al documento para la consultora.
