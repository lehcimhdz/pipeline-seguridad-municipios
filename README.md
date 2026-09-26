# Pipeline de seguridad municipal — v3.4

Genera una medición de SEGURIDAD desde los mismos cuatro Word por municipio.
Incorpora el machote **rzg investigación**, conserva los 18 indicadores y sus
90 criterios históricos y separa la investigación externa de los puntajes.
Emite siempre una **calificación documental**, sin inventar desempeño cuando
la evidencia no permite calcular un puntaje observado.

La base activa [seguridad_medicion_v3.docx](templates/seguridad_medicion_v3.docx)
parametriza una copia del original recibido en sus posiciones existentes:
**157 variables snake_case**, cuatro benchmarks, quince apartados de
investigación y tres mínimos de protección civil. Conserva los 101 bloques
de origen, texto fijo, títulos, listas y colores. La corrección
documentada del personal duplicado restituye CUP como indicador 7.
La identidad se incorpora bajo SEGURIDAD y las fuentes al final. La salida
añade una portada editorial con el logotipo InstitutionWorks existente y
normaliza el formato de todo el texto según el manual autorizado. El archivo
original permanece intacto; estas adaptaciones se auditan explícitamente.

## Ejecutar

Python 3.11+:

    python3 -m pip install -r requirements.txt
    python3 scripts/validar_plantilla.py
    python3 scripts/ejecutar_pipeline.py

Produce JSON trazable, Word **BORRADOR DE REVISIÓN** y recibo de renderizado.
El Word de salida no lleva resaltado amarillo, ni en el contenido incorporado
ni en las marcas heredadas del original. Todo el contenido usa tipografías
Archivo y el perfil editorial por función: títulos, cuerpo, notas, tablas,
gráficas y bibliografía. La auditoría comprueba estructura, posiciones,
formato editorial y ausencia de amarillo antes de publicar la salida.

La voz académico-consultiva y la separación entre texto publicable y
trazabilidad están en [ESTILO_REDACCION.md](ESTILO_REDACCION.md).
El control de redacción se aplica antes de guardar el JSON y antes de
publicar el Word. Los títulos documentales y las URL públicas permanecen en
la bibliografía; los archivos, códigos y SHA-256 se conservan sólo como
metadatos internos. Este control léxico no detecta autoría por IA ni
sustituye la revisión de calidad. No requiere un servicio de IA.

Las medidas, la portada y la excepción de interlineado mínimo de 14 pt en
títulos de 24 pt están en [FORMATO_EDITORIAL.md](FORMATO_EDITORIAL.md).
Pasar esta auditoría de formato no valida los datos ni sustituye la revisión humana.
El perfil del manual de anexo se conserva en la configuración; no se genera
un documento de anexo en este flujo.

Después de una ejecución exitosa, se eliminan las salidas anteriores de
`output/json/` y `output/word/`; sólo se conservan las vigentes.
No uses estas carpetas como archivo histórico.

Para incluir investigación previamente revisada:

    python3 scripts/ejecutar_pipeline.py --investigacion-json input/revision/investigacion_seguridad.json

Sin ese aporte, benchmarks, apartados y mínimos quedan pendientes. El pipeline
valida estructura y referencias declaradas, **no vigencia jurídica ni veracidad
de una investigación**. No necesita una API de IA.

El aporte local de prueba desarrolla los quince temas con veinte fuentes
primarias y mantiene pendiente la validación editorial humana. El comando
no consulta la web automáticamente ni reescribe el aporte silenciosamente.
Si sus textos contienen referencias técnicas no publicables, la ejecución
se detiene para que se corrija la redacción conservando el contenido y las URL.
La procedencia y las declaraciones de revisión se mantienen en la trazabilidad.
El municipio, estado y periodo declarados se contrastan con el resultado;
las revisiones pendientes del aporte se conservan íntegramente en el JSON y
se advierten de forma agrupada en el Word. La bibliografía elimina citas
idénticas; conserva referencias a una misma URL cuando difieren sus
localizadores u otros datos de la cita.

Los borradores explican los límites bajo «Alcance y aspectos por completar».
Los valores aún no desarrollados permanecen nulos y tienen una explicación
visible independiente, sin mostrar nombres de variables. La nueva redacción
no cambia los puntajes ni los cálculos.

Cada periodo tiene **18 de 18 notas documentales asignadas**. Con los datos
actuales hay 12 de 18 puntajes observados generales y 0 de 18 del último
periodo. El reciente es el intervalo común 2023–2024: falta 2023
en los indicadores 1–16 y los indicadores 17–18 requieren revisión metodológica.
No se sustituye 2023 por 2022. En el general siguen pendientes 4, 8, 9, 14,
17 y 18. El general recibe 3.12/5 — ACREDITACIÓN PARCIAL, con cobertura
observada 66.67 % y ponderada 73.21 %. El reciente recibe 1.00/5 — NO ACREDITADO, con cobertura observada
0 %; esto no significa desempeño catastrófico. Un documento final documental
puede conservar faltantes explicados, pero requiere revisión resuelta,
fuentes completas y declaración explícita de sus límites.

## Metodología y parámetros

[reglas_calificacion.json](reglas_calificacion.json) es la configuración
activa. Su sección `calificacion_documental` controla pesos de dimensiones,
escala y candados. Cada puntaje comprobable se conserva; los no comprobables
mantienen `puntaje=null` y reciben `puntaje_asignado=1` por no acreditación.
Se muestran cobertura simple, cobertura ponderada y sensibilidad, además
de las 36 calificaciones individuales y sus motivos en el Word.

La fórmula, sus límites, los requisitos de los 18 indicadores y el motivo
de cada decisión están en [METODOLOGIA_CALIFICACION.md](METODOLOGIA_CALIFICACION.md).
Esta nota es interna: no certifica cumplimiento legal ni aprobación oficial.

## Cuando cambie el machote

    python3 scripts/migrar_machote_v3.py
    python3 scripts/validar_plantilla.py
    python3 -m unittest discover -s tests -v
    python3 scripts/ejecutar_pipeline.py

La migración actualiza base, diccionario, reglas y contrato; conserva
101 bloques mediante controles de contenido y verifica su fidelidad.
El resultado se compara con la normalización editorial autorizada, no con
los estilos arbitrarios que pudiera traer el original.
Una modificación del original bloquea el pipeline hasta migrar.
Si cambia el inventario de indicadores, se exige revisar su correspondencia.
Los JSON anteriores deben regenerarse. Los 90 criterios históricos quedan
como referencia; la nueva capa documental no convierte sus faltantes en
desempeño observado. La migración conserva los parámetros activos de reglas;
si se cambian, hay que regenerar el contrato, probar y ejecutar de nuevo.

La población puede aportarse mediante CSV o INEGI opcional
(`--inegi-population`, secreto de entorno `INEGI_TOKEN`).
No se guardan tokens en salidas ni Git.

Detalles en [PIPELINE.md](PIPELINE.md).
Diagrama editable: [flujo_pipeline.drawio](flujo_pipeline.drawio).
