# Especificación del pipeline de seguridad municipal

## Propósito

Para un municipio, el pipeline recibe cuatro documentos Word, extrae evidencia
para los 18 indicadores de seguridad, construye un JSON trazable con base en
diccionario_datos_diagnostico_seguridad_municipal.json y genera el diagnóstico
terminado desde templates/Machote_seguridad_general_con_calificacion.docx.

El diccionario y el machote son activos de referencia: no se sobrescriben al
procesar un municipio.

## Entradas

Los cuatro archivos viven en input/word/ y comparten exactamente el mismo
prefijo de municipio:

    {nombre_municipio} Anexo.docx
    {nombre_municipio} PAQUETE SEGURIDAD.docx
    {nombre_municipio} PAQUETE GOBIERNO ABIERTO Y BUEN GOBIERNO.docx
    {nombre_municipio} PAQUETE DESARROLLO URBANO SOSTENIBLE Y DERECHOS HUMANOS CONEXOS.docx

La carpeta de entrada cambia en cada ejecución. El nombre del municipio se toma
del prefijo común; el estado se extrae del contenido, nunca se infiere del
nombre de archivo.

Antes de extraer, el agente debe detenerse con un error claro si falta un
archivo, existe más de un archivo para alguno de los cuatro sufijos, los
prefijos no coinciden o un archivo no es un DOCX legible.

### Prioridad de fuentes

| Fuente | Uso en el pipeline |
| --- | --- |
| PAQUETE SEGURIDAD | Fuente primaria para los 18 indicadores, sus series, calificaciones y comparaciones. |
| Anexo | Control cruzado de identidad municipal, periodo, calificaciones y resultados resumidos. |
| PAQUETE DESARROLLO URBANO… | Contexto para riesgos, desastres o protección civil; no sustituye un dato del paquete de seguridad. |
| PAQUETE GOBIERNO ABIERTO… | Contexto institucional; no sustituye un indicador de seguridad. |

Cuando haya una discrepancia, se conserva la evidencia de ambos documentos, se
prefiere el PAQUETE SEGURIDAD para el dato del indicador y se marca el caso
para revisión. El agente no debe inventar un valor para resolverla.

## Flujo

    input/word (4 DOCX)
            |
            +-- 1. Validar conjunto y detectar municipio
            +-- 2. Extraer párrafos, tablas, encabezados y evidencia
            +-- 3. Normalizar y calcular indicadores/calificaciones
            +-- 4. Validar contra el diccionario y la evidencia
            +-- 5. Escribir JSON trazable
            +-- 6. Componer y renderizar el Word final
                     |
                     +-- output/json/{municipio}_diagnostico_seguridad_municipal.json
                     +-- output/word/{municipio}_diagnostico_seguridad_municipal.docx

### 1. Extracción

El agente debe conservar, para cada dato usado, la fuente, el indicador, una
referencia localizable (página, tabla, encabezado o fragmento) y el texto o
valor original. Debe leer tablas además de párrafos. Si una gráfica o imagen
contiene el único dato disponible, se registra como evidencia visual y se
marca para revisión en lugar de estimar su valor.

### 2. Normalización y cálculo

Se aplican las reglas ya definidas en el diccionario:

- 18 indicadores y 3 dimensiones.
- Calificación general y del último periodo.
- Tratamiento de datos faltantes, candados y ajustes.
- Variables narrativas sólo cuando están respaldadas por evidencia.

Las elecciones de texto, por ejemplo comparacion_con_periodo_completo, deben
tomar uno de los valores permitidos en el diccionario. Si no hay evidencia
suficiente, el campo queda sin resolver y el estado de la ejecución es
requiere_revision; no se genera un Word final como si estuviera validado.

### 3. JSON de salida

El archivo en output/json/ es una instancia municipal del contrato, no una
modificación del diccionario base. Debe incluir, como mínimo:

    {
      "version": "1.0",
      "municipio": "{nombre_municipio}",
      "estado_ejecucion": "validado",
      "fuentes": [
        {
          "archivo": "{nombre_municipio} PAQUETE SEGURIDAD.docx",
          "sha256": "..."
        }
      ],
      "valores_plantilla": {
        "municipio": "{nombre_municipio}",
        "año_inicial": 2014,
        "comparacion_con_periodo_completo": "igual"
      },
      "indicadores": {},
      "calculos": {},
      "evidencia": {},
      "validaciones": []
    }

valores_plantilla contiene una clave por cada una de las 41 variables de
variables_documento; se usa directamente para sustituir {{ clave_json }}. Los
objetos indicadores, calculos, evidencia y validaciones conservan la
trazabilidad necesaria para auditar esas decisiones.

Antes de guardarlo, el pipeline valida tipos, opciones permitidas, campos
obligatorios, las 120 apariciones del machote y la ausencia de valores
inventados. El JSON se escribe de forma atómica para no dejar resultados
parciales.

### 4. Word de salida

El renderizador crea una copia del machote y sólo la copia se guarda en
output/word/. Sustituye los marcadores {{ clave_json }} usando
valores_plantilla.

El machote actual también contiene guía de calificación, textos alternativos e
instrucciones editoriales entre corchetes. Por ello el renderizado final tiene
dos partes:

1. Sustituir variables y conservar formato.
2. Seleccionar únicamente los textos que correspondan a la calificación y
   evidencia del municipio; eliminar instrucciones editoriales y alternativas
   no elegidas.

Un documento no se considera final mientras contenga un marcador {{ ... }},
una instrucción [borrar al finalizar], una nota [Verificar ...] sin resolver o
una variante incompatible con los datos. Esas condiciones deben quedar en
validaciones y bloquear la salida final.

## Controles operativos

- El proceso debe ejecutarse para un solo municipio por corrida.
- Las salidas nunca reemplazan otra corrida; se usa el nombre de municipio y,
  si hace falta, una marca de tiempo o identificador de ejecución.
- Cada archivo de entrada se identifica con SHA-256 en el JSON de salida.
- Los cambios al diccionario o al machote se validan con el comando siguiente:

      python3 scripts/validar_plantilla.py

- La revisión humana es obligatoria cuando hay conflicto de fuentes, datos
  faltantes relevantes, evidencia sólo visual, ajustes de puntuación o notas
  de verificación pendientes.

## Próximo entregable técnico

Implementar un comando único que reciba la carpeta input/word/, valide el
conjunto de cuatro archivos, produzca el JSON de salida y, sólo si su estado es
validado, genere el Word final. El comando debe registrar los errores sin
alterar el diccionario ni el machote.
