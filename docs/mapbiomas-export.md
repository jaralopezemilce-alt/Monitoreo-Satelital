# Exportar las etiquetas de MapBiomas para A y B

El raster todavía no fue exportado en este entorno. El asset y su forma de carga están verificados en el toolkit oficial, pero un asset público de Earth Engine no equivale a una URL GeoTIFF anónima ([toolkit de MapBiomas](https://github.com/mapbiomas/user-toolkit)).

## Qué está listo

El script `scripts/export_mapbiomas_pilot.js` prepara cuatro tareas para las ventanas históricas ampliadas de A y B, años 2022 y 2023. Su nombre conserva “pilot” por continuidad, pero exporta los 100 km² completos de cada zona; no activa C ni convierte categorías a bosque/no bosque.

La fuente es Colección 5.0, integración v2, asset:

```text
projects/mapbiomas-public/assets/chaco/lulc/collection5/mapbiomas_chaco_collection5_integration_v2
```

Ese identificador, los años disponibles y el producto están publicados en la [configuración oficial](https://github.com/mapbiomas/user-toolkit/blob/master/data/collections-lulc.js). Se mantienen 30 m y las clases originales, con nodata 255; el remuestreo posterior a 10 m usará vecino más cercano y no se interpretará como nueva precisión.

## Acción necesaria de una integrante

Earth Engine requiere una cuenta autenticada y un proyecto de Google Cloud habilitado/registrado; el Code Editor maneja la autenticación del usuario ([guía oficial](https://developers.google.com/earth-engine/guides/auth)). No necesitan compartir contraseñas ni tokens en el chat.

1. Abrir el Code Editor de Earth Engine con una cuenta y proyecto habilitados.
2. Copiar `scripts/export_mapbiomas_pilot.js` y ejecutarlo.
3. Comprobar en Console que existen `classification_2022` y `classification_2023`. Si aparece error de acceso, detenerse y compartir el texto del error sin credenciales.
4. En Tasks, iniciar las cuatro tareas; elegir Google Drive y conservar los parámetros del script.
5. Descargar los cuatro TIFF de la carpeta `CHACO_PILOT_LABELS` y adjuntarlos en esta conversación.

La exportación a Drive es una tarea por lotes; `crsTransform` controla la grilla y no se combina con `scale`, según la [documentación de exportación](https://developers.google.com/earth-engine/apidocs/export-image-todrive). El script sólo se validó sintácticamente aquí: no se afirma que estas tareas se hayan ejecutado ni terminado.

Archivos esperados:

```text
A_boqueron_mapbiomas_c5_v2_2022.tif
A_boqueron_mapbiomas_c5_v2_2023.tif
B_alto_paraguay_mapbiomas_c5_v2_2022.tif
B_alto_paraguay_mapbiomas_c5_v2_2023.tif
```

La fuente declara CC BY 4.0 y debe atribuirse a MapBiomas Chaco ([portal oficial](https://chaco.mapbiomas.org/)). Guardaremos versión, año, grilla, checksum y regla de conversión junto a los datos; todavía falta auditar estos raster contra las fechas concretas de Sentinel.

## Límite de decisión y alternativa autorizada

La fecha de decisión es **28 de octubre de 2026**. No se necesita esperar pasivamente: mientras se resuelve el acceso, las imágenes y verificaciones ya están listas; el cambio de fuente quedará registrado cuando corresponda, no como una tarea automática que supuestamente está corriendo.

Si la exportación no se logra en ese plazo, la alternativa autorizada es Hansen como fuente principal de pseudoetiquetas, con revisión manual. Usaremos la cobertura arbórea base y pérdida anual junto con evidencia contemporánea: `lossyear=0` no significa bosque, una pérdida antigua puede haber regenerado y un evento del año de la imagen puede ser posterior a su fecha.

No se llamará “verdad de terreno” a esa reconstrucción. Los casos ambiguos se marcarán como ignorados, se conservarán correcciones revisadas y se separará una referencia de test; los umbrales y la regla exacta se aprobarán en la fase de máscaras.
