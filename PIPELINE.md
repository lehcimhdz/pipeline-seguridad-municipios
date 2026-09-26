# Pipeline de seguridad municipal — v3.1

## Alcance y origen

La fuente primaria sigue siendo el conjunto de cuatro Word de `input/word/`.
Sólo se completa SEGURIDAD. El nuevo origen es
`templates/Machote general medicion version final rzg investigación.docx`
(Unicode descompuesto en macOS). Se conserva intacto y se parametriza una
copia en [seguridad_medicion_v3.docx](templates/seguridad_medicion_v3.docx).
La copia conserva los 101 bloques de contenido originales, sus títulos,
listas, colores, espacios, márgenes y única sección. Cada bloque mantiene
su origen en un control de contenido Word (`w:sdt`); el documento no se
reconstruye desde cero.

El original añade investigación, no nuevos umbrales. Se conservan
**18 indicadores, 90 criterios, tres dimensiones de puntuación y dos periodos**.
Las cuatro líneas de investigación son bloques editoriales independientes
de las dimensiones. No se generan un anexo adicional ni una plataforma electoral.

Las orientaciones de gobierno y prioridades del machote se expresan con
evidencia disponible. Un puntaje interno no demuestra causalidad, cumplimiento
jurídico ni efectos sobre el delito.

## Entradas

Los cuatro DOCX deben compartir el prefijo municipal:

    {nombre_municipio} Anexo.docx
    {nombre_municipio} PAQUETE SEGURIDAD.docx
    {nombre_municipio} PAQUETE GOBIERNO ABIERTO Y BUEN GOBIERNO.docx
    {nombre_municipio} PAQUETE DESARROLLO URBANO SOSTENIBLE Y DERECHOS HUMANOS CONEXOS.docx

La carpeta cambia por municipio. El estado se extrae del contenido.
Se rechazan conjuntos incompletos, sufijos duplicados, prefijos diferentes
o DOCX ilegibles. PAQUETE SEGURIDAD es la fuente de indicadores y tablas;
Anexo permite control cruzado. Los otros paquetes conservan contexto y
procedencia, pero no sustituyen datos faltantes de seguridad.

La evidencia conserva archivo, SHA-256, párrafos, encabezados, tablas,
ámbito, coordenadas y valores originales. Las discrepancias quedan para
revisión; no se estiman cifras a partir de imágenes.

Los adaptadores existentes siguen disponibles:

- [config/normalizaciones.json](config/normalizaciones.json):
  temas, uniformes y equipo.
- [config/fuentes_externas.json](config/fuentes_externas.json):
  población e incidencia, opciones `--population-csv` y `--incidence-csv`.
- INEGI opcional: `--inegi-population` y `INEGI_TOKEN` desde entorno.
  No se interpola población ni se mezcla automáticamente con proyecciones;
  el secreto no aparece en procedencia, salidas ni Git.

Los adaptadores externos requieren ambas claves: `--cve-ent` y `--cve-mun`.
La población debe provenir de una sola opción: CSV o INEGI, no ambas.
Los CSV usan los campos declarados en la configuración, con años y claves
compatibles con las tablas municipales y estatales.

## Contrato y migración

[config/contrato_documental.json](config/contrato_documental.json) vincula con
SHA-256 original, base, diccionario, reglas, formato, investigación,
metodología histórica y tipografías. Incluye el manifiesto de fidelidad
con acciones y orden de los bloques originales.

    python3 scripts/migrar_machote_v3.py
    python3 scripts/validar_plantilla.py

La migración es explícita, nunca silenciosa durante la extracción.
Antes de procesar o renderizar se comprueban las huellas. Un cambio del
original bloquea la ejecución hasta migrar y revisar.
Un catálogo u orden desconocido también bloquea la migración.

El nuevo original duplica el indicador de personal y omite CUP.
La única corrección de catálogo traslada los bloques de origen 50/51
(segunda aparición de personal) después del bloque 55 (instituto de
formación), cambia ese título por CUP y completa allí el indicador 7.
Los 18 indicadores quedan en su orden canónico; el original no se modifica.
Los índices de bloques son base cero y la adaptación queda registrada.
Todas las instrucciones originales se conservan localizables por bloque en
[config/investigacion_seguridad.json](config/investigacion_seguridad.json).

[scripts/fidelidad_machote.py](scripts/fidelidad_machote.py) comprueba el
orden y la presencia de los 101 bloques, texto fijo, propiedades de
párrafo y listas, estilos originales, numeración, encabezados/pies y configuración de página.
Se valida al parametrizar, revisar la base y auditar el Word rellenado.
La base conserva los 35 párrafos con numeración/listas del original.
Se agregan únicamente identidad y aviso de borrador en sus posiciones
documentadas, desarrollo de cada campo y fuentes/pendientes al final.
No se incorpora portada ni logotipo ausentes en el nuevo machote.

[config/metodologia_seguridad.json](config/metodologia_seguridad.json) conserva
los criterios históricos. [reglas_calificacion.json](reglas_calificacion.json)
pasa a v3.1 sin cambiar los 90 criterios, sus umbrales, dimensiones ni
agregación. Se corrige la selección del último periodo: dos años calendario
consecutivos, comunes a todos los indicadores, terminados en el último año
municipal documentado. Si falta cualquiera de esos años, el puntaje queda
pendiente; una observación anterior no reemplaza al año faltante.
`investigacion_modifica_puntajes=false`: un benchmark no cambia puntajes
automáticamente. Una modificación metodológica requiere decisión explícita.

`normalizar_plantilla.py` y `contextualizar_variables.py` remiten a la
migración v3.1. Repetirla con el mismo original produce la misma base y contrato.

## Variables y composición

El [diccionario](diccionario_datos_diagnostico_seguridad_municipal.json)
declara **116 variables y 116 apariciones**, con llaves simples y snake_case ASCII:

- `{municipio}`, `{estado}`, calificaciones y resúmenes por periodo.
- Bienes a proteger, comparación estatal/municipal, avances y resúmenes
  de dimensiones.
- Tendencia, recomendaciones, fortalezas, áreas de mejora y prioridades.
- Cuatro `{benchmark_*}` y tres `{minimos_indicador_XX}`.
- Quince `{investigacion_<linea>_<apartado>}`, uno por tema del machote,
  inmediatamente después de la instrucción temática conservada.
- Por cada indicador: `{analisis_indicador_XX}`,
  `{graficas_indicador_XX}`, `{tablas_indicador_XX}`,
  `{cierre_indicador_XX}`.
- `{bibliografia}`.

Los análisis identifican periodo, criterio, puntaje y pendientes.
[scripts/analisis_evidencia.py](scripts/analisis_evidencia.py) interpreta
valores y cambios de las tablas documentales con sus unidades y ámbitos.
Los cierres explican hallazgos y límites específicos de cada indicador,
en lugar de repetir un mismo párrafo. No atribuyen causas por una variación
de conteos ni confunden bajas de personal con letalidad policial.
Las tablas son estructuras de filas/celdas. Las gráficas nativas de Word
comparan puntajes internos de ambos periodos: **no son series de incidencia
ni benchmarks**. Los puntos pendientes se omiten, nunca se dibujan como cero.

El JSON conserva hoja de cómputo y promedios para auditoría.
`periodos_evaluacion` documenta el intervalo común reciente; las evaluaciones
conservan años observados, evaluados y faltantes por ámbito cuando corresponde.
Falta de datos no equivale a desempeño deficiente; no se presenta un promedio
parcial como calificación final. Las narrativas requieren revisión editorial.

## Investigación revisada

| Línea | Indicadores | Materias |
| --- | --- | --- |
| Protección civil | 1–3 | Leyes, tratados, desastres, Naciones Unidas y mínimos aplicables. |
| Condiciones del personal | 4–10 | Legislación, UNODC y revisiones sistemáticas. |
| Inteligencia policial | 11–16 | Patrullaje, hotspots, policía comunitaria, evaluación, derechos humanos, CCTV y mediación. |
| Eficiencia policial | 17–18 | Derechos humanos, sistema interamericano, letalidad, detenciones, cifra negra y abuso. |

Los cuatro Word no garantizan investigación normativa o científica suficiente.
Sin aporte revisado, benchmarks, apartados y mínimos quedan `null`; el
borrador muestra los pendientes y no inventa estándares. Cada tema tiene
un campo propio; una síntesis general no sustituye sus desarrollos.

    python3 scripts/ejecutar_pipeline.py --investigacion-json input/revision/investigacion_seguridad.json

Estructura del aporte (ejemplo esquemático, no evidencia):

    {
      "version": "1.0",
      "lineas": [
        {
          "id": "proteccion_civil",
          "estado": "verificado",
          "analisis": "Texto revisado que cite https://fuente-oficial.example/documento",
          "apartados": {
            "tratados_leyes": "Desarrollo con cita https://fuente-oficial.example/documento",
            "recomendaciones_onu": "Desarrollo con cita https://fuente-oficial.example/documento"
          },
          "referencias": [
            {
              "titulo": "Título de la fuente primaria",
              "url": "https://fuente-oficial.example/documento",
              "fecha_consulta": "2026-09-26",
              "localizador": "Artículo, sección o página",
              "aplicabilidad": "Municipio, jurisdicción y periodo pertinentes",
              "revisado_por": "Responsable de la revisión"
            }
          ]
        }
      ],
      "minimos_indicadores": {
        "01": {
          "texto": "Mínimo revisado; cita https://fuente-oficial.example/documento",
          "referencias": ["https://fuente-oficial.example/documento"]
        }
      }
    }

Los otros IDs son `condiciones_personal`, `inteligencia_policial` y
`eficiencia_policial`. Se admiten aportes parciales para borradores.
Cada línea aportada exige análisis, referencias HTTPS sin credenciales,
fecha ISO, localizador, aplicabilidad y revisor. Todas las URLs declaradas
deben aparecer en el conjunto de análisis y apartados de su línea; no es
necesario repetir una lista de referencias en cada síntesis. Los mínimos
01–03 sólo pueden citar fuentes declaradas en
protección civil y deben incluirlas en el texto.

Claves de `apartados` por línea:

| Línea | Claves |
| --- | --- |
| `proteccion_civil` | `tratados_leyes`, `recomendaciones_onu` |
| `condiciones_personal` | `leyes_nacionales`, `reportes_unodc`, `revisiones_laborales` |
| `inteligencia_policial` | `patrullaje`, `hotspots`, `policia_comunitaria`, `evaluacion_policial`, `derechos_humanos`, `cctv`, `mediacion` |
| `eficiencia_policial` | `derechos_humanos`, `letalidad`, `detenciones_seguridad` |

Cada apartado aportado debe incluir al menos una URL de las referencias de
su línea. Un apartado ausente sigue pendiente aunque el benchmark exista.

El pipeline valida **estructura y procedencia declarada**, no comprueba
vigencia, autoridad ni veracidad externa. Sí comprueba la correspondencia
de claves con los quince temas y marca desarrollos faltantes.
El agente o responsable debe consultar fuentes primarias, verificar
jurisdicción y periodo y revisar el contenido antes de declarar
`estado=verificado`. Tener una URL no acredita esa verificación.

El aporte local preparado para la prueba contiene cuatro líneas, quince
apartados y veinte fuentes primarias únicas. Fue consultado y redactado
mediante revisión documental asistida por IA; sus referencias conservan
esa atribución y la validación editorial humana queda pendiente. El valor
`verificado` declara revisión documental del aportante, no aprobación final.
Se distinguen leyes aplicables al periodo de cierre, recomendaciones
internacionales no vinculantes y evidencia científica con límites de
transferencia. No se aplican retroactivamente reformas posteriores ni se
trasladan cifras nacionales a un municipio. Las fuentes municipales siguen
siendo los cuatro Word.

El aporte se identifica con SHA-256. Si declara municipio, estado o periodo,
se comprueba su correspondencia con el resultado; no se reutiliza un aporte
de otra localidad o cobertura temporal. Las referencias pasan a la
bibliografía final sin duplicados por URL y `pendientes_revision` se incorpora
a las revisiones del resultado y del Word.
No modifica los criterios ni resuelve automáticamente indicadores faltantes.
No requiere API de IA ni ejecuta investigación web automática.

## Ejecución y salidas

    python3 -m pip install -r requirements.txt
    python3 scripts/ejecutar_pipeline.py

Flujo: validar contrato y base → validar cuatro Word → extraer →
fijar intervalos comunes y calificar → componer análisis específicos e
integrar investigación por tema → JSON → rellenar las posiciones del
machote y auditar fidelidad/amarillo → recibo → limpiar.
Diagrama editable: [flujo_pipeline.drawio](flujo_pipeline.drawio).

    output/json/{municipio}_diagnostico_seguridad_municipal_{corrida}.json
    output/word/{municipio}_seguridad_medicion_borrador.docx
    output/json/{municipio}_seguridad_medicion_borrador_renderizado.json

El JSON es una instancia municipal, no una copia del diccionario:
contiene evidencia, cálculos, validaciones, investigación, contrato y
`valores_plantilla`. El recibo vincula SHA-256 de JSON/Word y registra
las auditorías de resaltado y fidelidad. El nombre del Word es estable por municipio,
documento y modo; el ID de corrida sólo aparece en el JSON trazable.

El modo predeterminado es borrador. `--word ninguno` genera únicamente JSON.
Para renderizar una instancia compatible:

    python3 scripts/renderizar_word.py output/json/{archivo}.json --modo borrador

Los JSON anteriores no se renderizan contra el nuevo contrato:
deben regenerarse desde la evidencia.

## Formato editorial y amarillo

[config/formato_editorial.json](config/formato_editorial.json) conserva el
perfil del manual de Mediciones de Funcionamiento Municipal. En v3.1,
el texto que sustituye una variable hereda la sangría, lista, color y
formato local de su posición en el original. Los títulos y contenido fijo
se conservan; los párrafos adicionales, tablas y gráficas usan el perfil
editorial correspondiente. La configuración de referencia incluye:

- Portada: Archivo Regular 26 pt / 40 pt, centrada; este machote no
  contiene portada y esta opción no añade una.
- Capítulos: Light 24 pt / 14 pt, altas y centrados.
- Subcapítulos: Light 24 pt / 14 pt, izquierda.
- Cuerpo: Light 12 pt / 16 pt, columna sencilla, justificado;
  sangría 5 mm excepto al inicio y sin espacio entre párrafos.
- Calificaciones: Light 9 pt / 10 pt, centradas y con color por grado.
- Tablas: Medium 12 pt / 14 pt en títulos, Light 11 pt / 14 pt en contenido.
- Gráficas: títulos/ejes Medium 12 pt, categorías Medium 9 pt,
  datos Light 9 pt.
- Notas: Light 9 pt / 11 pt. Bibliografía: Light 12 pt / 16 pt,
  sangría 5 mm excepto al inicio.

Si el interlineado de un título es menor que su fuente se usa como mínimo,
no como altura exacta que recorte las letras. Se incrustan Regular, Light,
Medium, Light Italic y Bold, con licencia OFL en [assets/fonts](assets/fonts).
Bold permite representar la negrita del original sin sustituirla por una
familia serif; cinco archivos se vinculan mediante seis relaciones de fuentes.

El nuevo original no contiene logo. No se introduce uno ni se crea una
portada; los recursos históricos de `assets/` no alteran la estructura activa.
La fidelidad es estructural: la paginación final puede crecer al incorporar
análisis, investigación, tablas y gráficas.

Todo contenido agregado desde JSON lleva amarillo: texto con
`w:highlight` y sombreado `FFFF00`, celdas y fondo de gráficas.
La auditoría reabre el DOCX y rechaza inserciones sin resaltado, bloques
perdidos/reordenados fuera de la adaptación declarada o cambios de formato
fijo y configuración de página.
La plantilla original no se modifica al procesar municipios.

## Revisión, final y limpieza

Un final exige `estado_ejecucion=validado`, ninguna revisión/bloqueo,
18 puntajes por periodo, ambas calificaciones, cuatro benchmarks revisados,
quince apartados y tres mínimos. Se comprueban tipos, identidad, contrato,
intervalo reciente común, fidelidad, tablas frente a evidencia, gráficas
frente a puntajes, hoja de cómputo y agregados.
Cambiar sólo el estado o borrar las validaciones no basta.

Con el conjunto local disponible, el periodo general tiene 12 de 18
indicadores calculables; siguen pendientes 4, 8, 9, 14, 17 y 18.
El último periodo común es 2023–2024 y tiene 0 de 18 calculables: falta
2023 en los indicadores 1–16 y los indicadores 17–18 mantienen sus
pendientes metodológicos. La selección anterior de las dos observaciones
disponibles podía usar 2022–2024; esa sustitución dejó de admitirse.
Los pendientes no equivalen a cero ni prueban desempeño deficiente.

| Indicador | Evidencia o revisión requerida |
| --- | --- |
| 4 | Población comparable por año y ámbito para la tasa de personal. |
| 8 | Homologación y cobertura de la dotación de uniformes. |
| 9 | Homologación y alcance de la dotación de equipo. |
| 14 | Población comparable para la tasa de cámaras. |
| 17 | Interpretación de cambios de personal, egresos y fallecimientos conforme a la ficha. |
| 18 | Incidencia delictiva comparable y revisión de las puestas a disposición. |

La tabla anterior describe los pendientes generales. Para el periodo
reciente también debe completarse el intervalo 2023–2024 en cada ámbito
requerido. Incorporar investigación desarrolla los temas del machote,
pero no suple datos faltantes ni cierra la revisión editorial.

Después de una ejecución exitosa se eliminan permanentemente JSON y DOCX
anteriores, incluidos productos obsoletos de v2. Sólo se conserva el
JSON, Word y recibo vigente. Con `--word ninguno` queda sólo el JSON.
La limpieza no toca entradas, plantillas, ocultos ni subcarpetas.
Una falla de renderizado no dispara la limpieza de salidas anteriores.
Un histórico debe copiarse fuera de estas carpetas.

Los Word y JSON de `input/` y `output/` están excluidos de Git.
La investigación puede guardarse en `input/revision/`; no versionar tokens.

## Pruebas

    python3 scripts/validar_plantilla.py
    python3 -m unittest discover -s tests -v

Cubren reglas, limpieza, contrato y cambios del original, conservación
de bloques/formato/listas/sección, alteraciones de fidelidad, selección
del intervalo reciente, análisis de evidencia, tablas/gráficas, tipografías,
amarillo, apartados de investigación y rechazo de finales incompletos.
