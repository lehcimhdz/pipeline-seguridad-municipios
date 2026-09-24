# Pipeline de seguridad municipal

El diccionario JSON es el contrato de datos de la plantilla Word. Cada clave en
`variables_documento` usa el marcador canónico `{{ clave_json }}` y declara el
número de veces que debe aparecer en el machote.

Para comprobar que el contrato se conserva después de editar la plantilla:

```sh
python3 scripts/validar_plantilla.py
```

Los marcadores entre corchetes que permanecen en el Word son instrucciones
editoriales, selectores de puntaje o notas de verificación. Están declarados en
`marcadores_no_tratados_como_variables` y no se sustituyen como datos.
