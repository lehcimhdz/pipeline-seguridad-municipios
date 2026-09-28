# Evidencia complementaria de la integración 2.3

El paquete municipal sigue siendo la fuente principal. El complemento es
opcional: aclara lo que no pueda resolverse en el paquete y aporta denominadores
comprobables. No sustituye los datos recibidos ni convierte el manual censal en
una observación municipal. Todos los datos de cada municipio están en `input/`;
el material de `new-elements` aporta parámetros generales para el pipeline.

## Antes de solicitar más información

Ejecutar primero `--preparar` sin complemento y leer las `correspondencias` y
los motivos de pendiente en `indicadores[].evaluaciones`. El programa reconoce
títulos, columnas y conceptos bajo las reglas adoptadas. No hay que transcribir
esas correspondencias en un archivo de confirmaciones ni declarar
`revision: "verificada"` para habilitar cada ficha.

El título de CUP vigente permite homologar su porcentaje bajo la definición
censal adoptada. Un encabezado genérico de control de confianza, en cambio, no
identifica aprobación y vigencia. En capacitación, «servidores» no prueba por
sí solo pertenencia a la unidad ni un conteo único. El complemento debe atender
esas diferencias concretas, no confirmar en bloque todas las estadísticas.

## Archivo y ejecución

Guardar el complemento revisado en `input/complementos/{slug}.json`. Conservar
sus fuentes en `input/fuentes/`: PDF, CSV, XLSX o DOCX quedan fuera de Git. Usar
fuentes oficiales o aclaraciones documentadas del productor del paquete.
No se requieren tokens ni servicios de IA.

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

## Población

Cada registro de `poblacion` contiene:

- `ambito`: `municipal` o `estatal`; la identidad corresponde al encabezado del archivo.
- `anio`, `valor` positivo, `serie`, `fecha_referencia` ISO (`AAAA-MM-DD`).
- `metodo`: `reconstruccion`, `proyeccion`, `censo`, `encuesta` o `interpolacion_geometrica`.
- Fuente, localizador y revisión, como se explicó arriba.

Se admite una sola serie por ámbito. Las tasas comparadas exigen la misma serie,
método y fecha en ambos ámbitos. Preferir una serie anual consistente; distinguir
el año de referencia del dato del año de edición censal. En las tablas del
paquete esa correspondencia debe confirmarse, no inferirse.

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
| 5 | `universo: "corporaciones_policiales"`, `definicion: "aprobatorias_vigentes"`: no basta saber cuántas personas fueron evaluadas. |
| 7 | Mismo universo; `definicion: "cup_vigente"`. No requiere complemento cuando el título y la columna ya permiten la homologación adoptada. Aclarar encabezados distintos o contradicciones. No inferir inconsistencia automáticamente por CUP cero y controles aprobados positivos. |
| 9 | `personal_policial`, `chalecos`, `radios`, `menos_letal` (conteos), `naturaleza_del_dato: "asignado_al_cierre"`. No confundir compras o entregas anuales con disponibilidad. |
| 10 | Mismo universo policial; `definicion: "capacitacion_sin_profesionalizacion"`. Confirmar denominador de porcentajes y no sumar personas entre cursos. |
| 14 | `universo: "camaras_en_servicio"`; los conteos salen del paquete. Poblaciones municipal y estatal compatibles. |
| 15 | `registro_municipal: true` indica competencia del registro, no existencia automática del centro. Población y conteos de llamadas del paquete. Para 5: `meta_respuesta` documentada y `meta_respuesta_cumplida: true` en cada año. `ausencia_registro_acreditada` distingue inexistencia comprobada de vacío; `dato_dudoso` limita a 3. |
| 18 | `personas_mp`, `delitos_municipales`, `personas_mp_estatal`, `delitos_estatales`; `incidencia_comparable: true`. Para 5: `revision_derechos: "sin_recomendaciones_documentada"` y `control_uso_fuerza: "revisado"`. La fuente y localizador deben respaldar todos los componentes; si procede, conservar un expediente de conciliación con las referencias de cada uno. |

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
