# Fuentes editoriales

Archivo Regular, Light, Medium, Light Italic y Bold, obtenidas de los archivos TTF
oficiales de [Omnibus-Type/Archivo](https://github.com/Omnibus-Type/Archivo/tree/master/fonts/ttf).
Se redistribuyen sin modificar bajo la licencia [SIL OFL](OFL.txt).
El contrato registra sus SHA-256.

El pipeline incrusta los cinco archivos completos en las bases operativas y
salidas DOCX. En Word, Archivo Regular corresponde a la familia `Archivo` con
estilo regular; Light y Medium usan las familias `Archivo Light` y `Archivo Medium`.
La bibliografía puede usar la variante italic de `Archivo Light`.
Bold conserva la compatibilidad con la negrita histórica de las bases,
incluida su combinación con `Archivo Medium`; se declara en las dos familias
sin cambiar el documento original. Hay seis relaciones de incrustación para
cinco archivos. Desde v3.3 la salida normalizada no aplica negrita al texto
editorial ni a las gráficas: conservar la fuente incrustada no obliga a usarla.

Los visores que ignoran fuentes incrustadas necesitan instalar estos TTF para
previsualizar exactamente la composición editorial.

## Límite de la previsualización con LibreOffice

En la prueba local con LibreOffice 26.2.0.3 para macOS, la exportación a PDF
resolvió `Archivo Medium` como `Archivo-Regular`, aunque el DOCX declara
`Archivo Medium` y contiene su TTF completo. La desofuscación de cada una de
las seis incrustaciones coincide byte por byte con los archivos oficiales;
no se detectó pérdida ni corrupción de la fuente.

Una prueba reducida reprodujo la sustitución con un párrafo explícito de
12 pt, sin negrita ni cursiva. Retirar las relaciones de Bold no la corrigió.
Los nombres internos del TTF Medium son familia heredada `Archivo Medium`
(`nameID 1`) y familia tipográfica `Archivo`, estilo `Medium` (`nameID 16/17`).
Los experimentos temporales apuntan a la resolución de esa familia/peso en
LibreOffice; no demuestran un fallo equivalente en Microsoft Word.

No se modifican los TTF oficiales ni se sustituye Medium por Bold para
compensar al visor. La auditoría del DOCX verifica las fuentes declaradas;
la previsualización de LibreOffice no certifica el peso visual Medium.
Conviene comprobarlo también en Microsoft Word antes de la aprobación
editorial final. Véase [FORMATO_EDITORIAL.md](../../FORMATO_EDITORIAL.md).
