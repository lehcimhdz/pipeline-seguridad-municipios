# Redacción del diagnóstico de seguridad · v2.1

## Propósito y referencia

El documento debe ayudar a comprender el funcionamiento de la seguridad
municipal y a reconocer prioridades de gestión a partir de evidencia concreta.
La voz es consultiva: explica qué muestran los datos, por qué importa y qué
conviene revisar o fortalecer.

La referencia editorial es `Muestra Estudio Seguridad.docx`, consultada fuera
del repositorio. Se retoma su organización mediante síntesis, comparación
territorial y temporal, e implicaciones para la gestión. Sus cifras, localidades,
calificaciones, estándares y juicios no son insumos del diagnóstico. El archivo
no se incorpora al repositorio ni se consulta durante la ejecución.

Las únicas fuentes factuales son `{municipio} PAQUETE SEGURIDAD.docx` y
`{municipio} Anexo.docx`. Las calificaciones proceden de las reglas históricas
versionadas. Las pautas operativas están en
[config/redaccion_consultoria.json](config/redaccion_consultoria.json), perfil
`diagnostico_consultivo`.

## Organización del documento

La introducción explica el propósito del diagnóstico, su alcance en SEGURIDAD,
las dos fuentes y el periodo documental. Presenta una lectura accesible de las
calificaciones y de las limitaciones de información. Debe permitir comprender
el documento sin conocer el pipeline.

La síntesis general selecciona los hallazgos más relevantes para la gestión.
La síntesis del último periodo identifica el cierre documental y sus límites.
Ambas deben corresponder a las evaluaciones calculadas y a la cobertura real
de las fuentes.

Cada indicador desarrolla una secuencia reconocible:

1. **Hallazgo.** Expone la situación municipal observada con una frase concreta.
2. **Evidencia.** Identifica magnitud, unidad, territorio y año; compara sólo
   cuando las observaciones son equivalentes.
3. **Implicación.** Explica la relación con la capacidad o función municipal,
   manteniendo la incertidumbre que la evidencia requiera.
4. **Prioridad.** Propone una acción proporcionada al hallazgo o una verificación
   precisa cuando falte información.

Las tablas conservan la evidencia y las gráficas muestran puntajes calculables.
Los párrafos conectan los resultados con su significado, evitando enumerar
todas las celdas. El cierre de cada indicador concentra la prioridad de gestión.
Las conclusiones reúnen las prioridades sustentadas y los asuntos que siguen
abiertos, sin introducir hechos nuevos.

## Voz y precisión

Usa oraciones directas y párrafos breves, cada uno con una idea principal.
Nombra al municipio o al ámbito estatal cuando pueda haber ambigüedad. Alterna
la estructura de los párrafos conforme al tipo de evidencia; evita repetir
un preámbulo idéntico en los 18 indicadores.

Prefiere verbos descriptivos y verificables: «reporta», «registra», «aumentó»,
«disminuyó», «se mantuvo» o «no permite determinar». Usa «sugiere» cuando la
relación sea una interpretación prudente. Las recomendaciones pueden comenzar
con «Conviene revisar», «La prioridad es» o «Se requiere verificar», seguidas
de un objeto específico.

Cada cifra debe conservar su unidad y año. Un porcentaje de municipios no
describe el porcentaje de policías del municipio. El promedio estatal y el
total municipal requieren una explicación de sus respectivas unidades antes
de compararse. Cuando se citan dos extremos de una serie, se identifican los
años de ambos valores.

Los siguientes patrones ilustran la forma de redacción; los campos entre
corchetes deben reemplazarse exclusivamente con evidencia validada:

> En [municipio], [indicador] pasó de [valor y unidad] en [año inicial] a
> [valor y unidad] en [año final]. Este cambio hace pertinente revisar
> [proceso directamente relacionado con el indicador].

> La fuente reporta [hallazgo verificable]. Para determinar [aspecto no
> resuelto] se requiere [dato preciso faltante]. La prioridad es completar
> esa verificación antes de establecer una meta de cobertura.

## Límites de interpretación

Un faltante permanece como `null` en el JSON y se explica en la prosa.
«No se reporta información» describe una limitación documental; no demuestra
ausencia de personal, equipo, servicio o actividad. Un cero se usa únicamente
cuando está reportado y validado como tal. La calificación PENDIENTE conserva
esa condición hasta resolver la evidencia necesaria.

El periodo general y la ventana común de dos años consecutivos del último
periodo se aplican según [PIPELINE.md](PIPELINE.md). Se deben distinguir los
años efectivamente observados de los años sin información. Una variación entre
dos observaciones no demuestra una tendencia continua en los años intermedios.

La cantidad de cursos o registros de participantes no permite inferir personas
únicas capacitadas. Las categorías que puedan superponerse no se suman como
si fueran excluyentes. Una razón de cobertura requiere numerador, denominador,
unidad y periodo compatibles; sin población suficiente, no se declara déficit
o suficiencia por habitante.

Las relaciones observadas no prueban causalidad. Los datos sobre recursos,
procesos y resultados deben describirse conforme a lo que miden. La existencia
de un plan no acredita su implementación; la adquisición de equipo no prueba
su funcionamiento ni su cobertura. No se atribuyen causas políticas, delitos,
intenciones o responsabilidades que las fuentes no establezcan.

Las recomendaciones deben responder al hallazgo documentado. Se pueden
proponer verificación de cobertura, seguimiento de vigencias o revisión de
procesos cuando corresponda. No se agregan metas numéricas, estándares nuevos
ni afirmaciones de cumplimiento legal que no formen parte de la evidencia y
de las reglas aplicables.

## Presentación y revisión

El Word conserva lenguaje para quien toma decisiones municipales. Las
coordenadas de celdas, hashes, nombres de variables, códigos de validación y
trazas de cálculo se consultan en el JSON y el recibo. Una limitación que afecta
la interpretación sí debe explicarse en el texto con palabras comprensibles.

La entrega usa el manual de medición y tipografía Archivo, sin resaltado
amarillo. Antes de cerrar la revisión se comprueba que cada afirmación tenga
respaldo en las dos fuentes, que las cifras conserven unidad y periodo, que los
faltantes sigan visibles y que las conclusiones coincidan con el cuerpo del
diagnóstico. La revisión editorial no modifica puntajes ni criterios.
