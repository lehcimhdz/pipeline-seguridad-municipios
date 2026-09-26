# Formato editorial — pipeline v3.3

## Alcance y decisiones autorizadas

El Word de salida aplica el manual de **Mediciones de Funcionamiento
Municipal** proporcionado por el usuario. Esta versión corrige el formato
de todo el documento, no sólo de los textos añadidos desde JSON. Incluye
contenido fijo, títulos, listas, notas, tablas, gráficas y bibliografía.
Los datos y la metodología de calificación no cambian.

El archivo original `Machote general medicion version final rzg investigación.docx`
permanece intacto. La copia parametrizada conserva 157 variables y 101
bloques de origen. La normalización y la portada se incorporan al renderizar
la salida y quedan declaradas en el contrato. No se reemplaza el documento
por una estructura inventada ni se pierde su contenido fijo.

Dos decisiones son explícitas:

- Se añade una portada con título y el logotipo InstitutionWorks existente,
  aunque no estuvieran en el original recibido.
- En capítulos y subcapítulos de 24 pt se usa **interlineado mínimo de 14 pt**,
  aprobado por el usuario para evitar recortes. No se usa altura exacta de
  14 pt, que podría cortar letras de 24 pt.

La configuración activa está en [config/formato_editorial.json](config/formato_editorial.json).
Los cambios de configuración requieren regenerar el contrato antes de
procesar de nuevo; no se aplican ignorando sus huellas SHA-256.

## Reglas del documento de medición

| Función | Fuente | Tamaño | Interlineado | Alineación y composición |
| --- | --- | --- | --- | --- |
| Título de portada | Archivo Regular | 26 pt | 40 pt exactos | Altas y bajas; centrado horizontal y verticalmente en la página. |
| Capítulo | Archivo Light | 24 pt | Mínimo 14 pt, excepción autorizada | Altas; centrado. |
| Subcapítulo | Archivo Light | 24 pt | Mínimo 14 pt, excepción autorizada | Altas y bajas; izquierda. |
| Cuerpo | Archivo Light | 12 pt | 16 pt exactos | Columna sencilla, justificado; sangría inicial 5 mm salvo el primer párrafo de cada bloque. |
| Calificación | Archivo Light | 9 pt | 10 pt exactos | Altas, centrado; conserva el color de su categoría. |
| Encabezado de tabla | Archivo Medium | 12 pt | 14 pt exactos | Altas y bajas; centrado. |
| Contenido de tabla | Archivo Light | 11 pt | 14 pt exactos | Altas y bajas; centrado. |
| Nota | Archivo Light | 9 pt | 11 pt exactos | Columna sencilla, izquierda. |
| Bibliografía | Archivo Light y Light Italic | 12 pt | 16 pt exactos | Columna sencilla, justificado; sangría inicial 5 mm salvo el primer párrafo. |

Los párrafos tienen espacio anterior y posterior de 0 pt. La sangría de
5 mm se expresa en unidades de Word con el redondeo técnico correspondiente;
no se simula mediante espacios. El primer párrafo de cada bloque usa sangría
inicial de 0. Las listas conservan su numeración y pertenencia al bloque;
no se convierten en texto plano para normalizar la tipografía.

Las siguientes excepciones mantienen la estructura sin introducir espacio
visible ni recortar elementos:

- Las listas usan sangría francesa de 5 mm, conservando sus identificadores
  de numeración; no siguen la sangría de primera línea del cuerpo corrido.
- Los párrafos vacíos originales se conservan ocultos a 1 pt. Así permanecen
  los bloques de origen sin añadir renglones de separación visibles.
- El párrafo que contiene una gráfica usa interlineado mínimo de 16 pt para
  permitir la altura del objeto; no modifica el interlineado del texto.
- La identidad bajo SEGURIDAD usa Archivo Light 12/16, centrada.

El cuerpo se justifica a ambos márgenes. El texto permanece en una columna;
centrar la columna no implica centrar cada línea del cuerpo. Los títulos,
notas y tablas siguen su alineación específica.

La cursiva de la bibliografía usa Archivo Light Italic, sin convertir toda
la bibliografía en cursiva. No se emplea Calibri como sustituto del contenido
que heredaba esa familia desde el original.

## Portada y logotipo

La portada pertenece sólo a la salida y precede los 101 bloques de origen.
Su título usa Archivo Regular 26/40 y se centra horizontal y verticalmente.
Los tres párrafos —título, Seguridad e identidad municipal— comparten un
marco de texto `w:framePr` de altura automática, centrado en ambos ejes de la
página y limitado al ancho útil entre márgenes. Es una composición propia
de Word: los párrafos adyacentes con las mismas propiedades pertenecen al
mismo marco. [Referencia de Microsoft sobre `FrameProperties`](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.frameproperties?view=openxml-3.0.1).

El marco evita depender sólo de `w:vAlign` de la sección: la revisión visual
con LibreOffice 26.2 mostró que esa propiedad, por sí sola, dejaba el título
arriba. Se mantiene el centrado de sección y se añade el marco compatible;
no se posiciona el título mediante renglones vacíos ni espacios de relleno.
La auditoría exige las propiedades exactas del marco en los tres párrafos.

El logotipo InstitutionWorks se reutiliza desde los recursos del proyecto:
5 cm de ancho, altura proporcional y centrado en la parte baja de la página.
No se estira, redibuja ni sustituye por una marca generada.

La portada y su sección están declaradas como adición autorizada en la
auditoría de fidelidad. No cambian el catálogo de indicadores ni cuentan como
un bloque de evidencia del municipio. El contenido posterior conserva su
configuración de página según el contrato, salvo las propiedades editoriales
que se normalizan explícitamente. Se conserva el tamaño de papel y los
márgenes; la portada tiene centrado vertical y el cuerpo comienza en la
página siguiente con alineación vertical superior y una sola columna.

## Gráficas

Las gráficas son nativas de Word y conservan su condición de calificaciones
documentales, no de tasas de incidencia o tendencias de desempeño.

| Elemento | Fuente | Tamaño | Interlineado |
| --- | --- | --- | --- |
| Título | Archivo Medium | 12 pt | 14 pt explícitos |
| Ejes | Archivo Medium | 12 pt | 14 pt explícitos |
| Categorías | Archivo Medium | 9 pt | 10 pt explícitos |
| Datos dentro de la gráfica | Archivo Light | 9 pt | 10 pt explícitos |

La tipografía se escribe en las propiedades de texto de la gráfica; no se
confía únicamente en el tema predeterminado de Office. El interlineado se
declara mediante `a:lnSpc/a:spcPts`. Las referencias,
notas de cobertura y advertencias del gráfico se mantienen fuera de él con
el estilo de nota, sin modificar sus datos.

## Notas y bibliografía

Una nota al pie real de Word se identifica por su estructura de nota al pie
y se formatea a Archivo Light 9/11, a la izquierda y sin espacio entre
párrafos. Las notas del cuerpo o las fuentes de gráficas usan el mismo perfil
de nota cuando corresponde.

No se convierten todas las URLs o referencias en notas al pie, ni se crean
referencias que no existan. La bibliografía sigue siendo un bloque propio,
con sus fuentes deduplicadas y el perfil Light/Light Italic 12/16.

## Anexo: perfil conservado, salida no habilitada

La configuración conserva el manual de **ANEXO. Mediciones de Funcionamiento
Municipal**: portada 30/36, cuerpo 9/10, subcapítulos 18/16, tablas de títulos
11/14 y contenido 9/10, tablas de años y porcentajes 12/14, notas 9/10 y
bibliografía 12/16. Es un perfil separado, no se mezcla con el de medición.

Esta versión del pipeline sólo genera el documento de medición de SEGURIDAD.
Tener el perfil de anexo en la configuración no habilita ni demuestra la
generación de un Word de anexo. Esa salida requiere un alcance y pruebas
propios antes de activarse.

## Fidelidad y ausencia de amarillo

La fidelidad de la base se verifica contra el original. Para la salida se
compara contra la transformación editorial determinista autorizada: se
conservan los 101 bloques, texto fijo, orden y listas; se permiten la portada,
el ajuste editorial de propiedades y las adaptaciones ya documentadas.

No se conserva un formato incorrecto sólo porque estuviera en el original.
Tampoco se admite que normalizar estilos borre texto, cambie un indicador o
reordene bloques fuera de las adaptaciones del contrato.

El Word de salida no lleva resaltado amarillo en texto, celdas ni fondo de
gráficas. Se retiran también las marcas amarillas heredadas del original,
sin tocar ese archivo. Los colores de texto del machote y de las categorías
se conservan cuando no son resaltados amarillos; no se convierte todo a negro.
La trazabilidad técnica de los valores incorporados desde JSON permanece.

## Validación y operación

La auditoría editorial se ejecuta sobre el Word temporal antes de publicar
la salida y rechaza
propiedades incompatibles con el perfil: tipografía, tamaño, interlineado,
alineación y sangría, además de las verificaciones de portada y gráficas.
No basta con que exista un estilo cuyo nombre sea Archivo: se comprueban
las propiedades que efectivamente se aplican al contenido.

Los estilos de párrafo `Editorial_` identifican la función de cada bloque.
La auditoría comprueba también las propiedades de párrafos y fragmentos de
texto, para detectar formatos directos incompatibles que pudieran anular
el estilo. La fidelidad del contenido y la auditoría editorial son
comprobaciones complementarias: aprobar una no permite omitir la otra.

Para regenerar y verificar:

    python3 scripts/migrar_machote_v3.py
    python3 scripts/validar_plantilla.py
    python3 -m unittest discover -s tests -v
    python3 scripts/ejecutar_pipeline.py --investigacion-json input/revision/investigacion_seguridad.json

Se incrustan las tipografías Archivo disponibles en [assets/fonts](assets/fonts)
con sus licencias. La comprobación XML no garantiza paginación idéntica
entre Word y otros visores; la revisión visual sigue siendo pertinente para
detectar saltos de página, legibilidad y composición del documento final.

En la previsualización local con LibreOffice 26.2.0.3 para macOS se detectó
una limitación concreta: su PDF usa Archivo Regular donde el DOCX pide
Archivo Medium, aun estando incrustado el TTF correcto. Los experimentos
aislados apuntan a la resolución de familias/pesos de ese visor, no a una
fuente corrupta; no se ha demostrado el mismo comportamiento en Microsoft
Word. No se alteran las fuentes oficiales ni se usa Bold para compensarlo.
Por tanto, la comprobación XML aprobada no permite certificar el peso Medium
en ese PDF de previsualización. La revisión final en Word debe corroborarlo.
El diagnóstico está en [assets/fonts/README.md](assets/fonts/README.md).

Comprobación local del 26 de septiembre de 2026: 135 pruebas automatizadas
aprobadas, 157 variables resueltas, 101 bloques de origen conservados,
42 tablas y 18 gráficas verificadas. La salida no contiene marcadores
pendientes ni resaltado amarillo. Las huellas de cálculos, indicadores y
valores de plantilla coinciden con la ejecución anterior al ajuste editorial;
el original también conserva su SHA-256. La vista previa consta de 67 páginas,
con portada centrada y logotipo inferior; esa paginación no se impone a Word.

Pasar la auditoría de formato no valida la evidencia. Las notas de la
prueba local siguen siendo 3.12/5 — ACREDITACIÓN PARCIAL en el general y
1.00/5 — NO ACREDITADO en el reciente, con las mismas coberturas y límites.
Un final documental requiere las revisiones declaradas resueltas y fuentes
completas; el software no certifica que una revisión humana ocurrió.
La metodología se explica por separado en
[METODOLOGIA_CALIFICACION.md](METODOLOGIA_CALIFICACION.md).
