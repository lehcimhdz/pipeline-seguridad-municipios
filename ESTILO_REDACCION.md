# Estilo de redacción — pipeline v3.4

## Propósito y alcance

El diagnóstico se redacta con una voz académico-consultiva: sobria, precisa
y accesible para quienes toman decisiones de gestión municipal. El texto
explica qué se observa, hasta dónde permite concluir la información y qué
requiere revisión. No narra los procedimientos informáticos que produjeron
el documento.

La configuración está en
[config/redaccion_consultoria.json](config/redaccion_consultoria.json) y su
aplicación en [scripts/redaccion_consultoria.py](scripts/redaccion_consultoria.py).
El análisis descriptivo se compone en
[scripts/analisis_evidencia.py](scripts/analisis_evidencia.py). Esta capa no
requiere un servicio de modelos de lenguaje ni una API de IA; aplica reglas
de composición y comprobaciones deterministas.

El estilo no modifica las fuentes, las cifras, los cálculos ni la metodología
de calificación. Los 18 indicadores, los periodos de evaluación y la
distinción entre puntaje observado y nota documental asignada permanecen.

## Cómo construir cada apartado

1. **Hallazgo.** Abrir con el resultado concreto, no con una fórmula de
   presentación como «la evidencia muestra lo siguiente».
2. **Alcance.** Precisar ámbito municipal o estatal, años, cifras y unidad
   cuando la fuente la establece. Las diferencias de porcentajes se expresan
   en puntos porcentuales. Un encabezado ambiguo, como «Total», no autoriza
   a inventar una unidad de personas, equipos o recursos monetarios.
3. **Implicación o límite.** Explicar qué permite interpretar la comparación
   y qué requiere completar. No atribuir causas, efectividad, cumplimiento
   normativo ni mejoras en seguridad sin evidencia suficiente.

La conclusión no debe copiar literalmente el análisis: puede concentrarse
en la observación más reciente, distinguirla del balance entre extremos y
señalar la condición necesaria para evaluar el periodo completo. No se
agregan recomendaciones específicas sólo para completar una estructura.

Las declaraciones de existencia no acreditan funcionamiento efectivo. Los
datos faltantes no se convierten en ceros; las categorías potencialmente
superpuestas no se suman. Las cifras estatales no se presentan como cambios
municipales ni como una clasificación de desempeño entre territorios.

## Ejemplos de reformulación

Son **paráfrasis ilustrativas** de formulaciones y cifras utilizadas en las
pruebas del proyecto, no citas de las fuentes ni una promesa de reproducción
literal en cada documento.

| Formulación que se evita | Redacción orientada al lector |
| --- | --- |
| «Para este indicador, la evidencia muestra lo siguiente: Total, variación de +16 unidades del campo.» | «El total reportado es 177 en 2024, frente a 161 en 2022; la diferencia es de 16. La comparación describe la dotación declarada, no acredita su funcionamiento.» |
| «Existencia: Sí; por tanto, opera adecuadamente.» | «Se declara su existencia en 2024. Esta respuesta no permite determinar su funcionamiento efectivo.» |
| «Hay celdas vacías en 2022.» | «No se dispone de información para 2022; esta ausencia no equivale a un valor de cero.» |
| «El puntaje es null y se asignó el piso del sistema.» | «La nota documental de 1/5 corresponde a información insuficiente; no expresa un desempeño observado.» |
| «Fuente: Municipio PAQUETE SEGURIDAD.docx, SHA-256…» | «Información municipal, cuadro 14.» En la bibliografía: «Compendio de seguridad municipal. Documentación proporcionada para el diagnóstico.» |
| «PENDIENTE: minimos_proteccion_civil.» | «La determinación de los requisitos aplicables queda sujeta a la revisión de las fuentes normativas.» |

La mejora de estilo no convierte una asociación en causalidad ni una nota
por información insuficiente en evidencia de mal desempeño.

## Texto publicable y trazabilidad interna

Se conservan dos planos complementarios:

- El informe presenta hallazgos, cifras, calificaciones y límites; identifica
  documentos e instituciones mediante títulos legibles y conserva las URL
  públicas de las referencias.
- La instancia de datos y el recibo mantienen nombres de archivos, huellas
  SHA-256, códigos de validación, coordenadas de tablas y demás metadatos
  necesarios para reproducir y auditar el resultado.

La bibliografía del Word no incluye rutas locales, nombres de archivo
informáticos ni huellas digitales. Esta separación no elimina las fuentes
ni su trazabilidad: cambia qué información se presenta al lector y cuál
permanece en la documentación técnica.

En borrador, los límites se reúnen bajo **«Alcance y aspectos por completar»**
y se explican con lenguaje sustantivo. Una variable sin contenido conserva
`None` en memoria —`null` en el JSON—; su explicación visible se proporciona
por separado mediante `contenido_word.textos_pendientes`. No se escribe un
código de variable en el párrafo pendiente ni se inventa contenido para
simular que el apartado está completo.

## Control previo a la publicación

El control se ejecuta antes de guardar la instancia JSON y vuelve a
comprobarse antes de publicar el Word. Revisa los textos destinados al
lector, no los metadatos internos que legítimamente contienen referencias
técnicas. Rechaza rutas locales, extensiones de archivos, identificadores
internos, huellas digitales y las expresiones técnicas o autorreferenciales
definidas en la configuración. Las URL públicas se conservan.

La comprobación incluye los textos de las celdas de las tablas de evidencia.
No los reescribe ni depura: si una celda contiene una referencia técnica
no publicable, se detiene la publicación para revisar el insumo. Los valores
y textos originales permanecen intactos; no se elimina información de una
tabla para superar el control.

Es un **control léxico acotado**. No es un detector de textos escritos por
IA, no certifica autoría humana y no evalúa por sí mismo calidad literaria,
veracidad, vigencia normativa ni solidez de una recomendación. La revisión
humana debe comprobar claridad, pertinencia, ausencia de repeticiones,
consistencia de cifras, referencias y límites de interpretación.

### Investigación aportada

La investigación incorporada no se reescribe ni se depura silenciosamente.
Si un texto destinado al informe contiene términos o referencias técnicas
no publicables, el proceso se detiene y solicita corregir el aporte. Debe
revisarse su redacción conservando el contenido sustantivo, las referencias
y sus URL; después se ejecuta de nuevo el flujo.

No se borran atribuciones ni se modifica un aporte para aparentar una
revisión humana que no ha ocurrido. La procedencia y las declaraciones de
revisión permanecen en la trazabilidad; los pendientes sólo se cierran
mediante una revisión real y explícita.

## Verificación de la entrega

Una entrega requiere tres comprobaciones independientes: integridad de los
datos y la calificación, redacción sustantiva revisada y cumplimiento del
[formato editorial](FORMATO_EDITORIAL.md). Aprobar el control léxico o el
formato de Word no sustituye las otras comprobaciones ni habilita por sí
solo el estado final.
