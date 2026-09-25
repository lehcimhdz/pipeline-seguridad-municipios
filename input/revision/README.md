# Decisiones de revisión por municipio

Este directorio admite un archivo JSON por municipio cuando una fuente presenta
celdas vacías, datos dudosos o una ambigüedad que no puede resolver el código.
El archivo no debe contener estimaciones sin evidencia.

La estructura incluye municipio, decisiones, indicador, año, clasificación,
justificación y evidencia. Las clasificaciones permitidas son
sin_respuesta_municipal, variable_no_existente_en_edicion, dato_dudoso,
no_aplicable y pendiente_de_captura.

La evidencia debe señalar archivo, tabla y fila. Por ejemplo, una decisión
para el indicador 17 en 2022 puede clasificar una celda vacía como
pendiente_de_captura hasta contar con soporte documental.
