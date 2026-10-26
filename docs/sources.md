# Fuentes, versiones y condiciones

Revisión del 26 de octubre de 2026. Separar disponibilidad documental, consulta exitosa y descarga real evita llamar “dataset listo” a una colección que todavía no pudimos exportar.

## Sentinel-2

Earth Search publica un catálogo STAC con Sentinel-2 L2A y assets de bandas/visualización; es una vía de acceso, no el productor de las imágenes ([documentación del servicio](https://element84.com/earth-search/)). Consultamos directamente el catálogo y leímos recortes RGB y SCL, conservando los IDs y URLs originales en `docs/evidence/selected_scenes.csv`.

La prospección utilizó `sentinel-2-l2a` para 2022 y `sentinel-2-c1-l2a` para 2023/2026. Se encontró que la segunda no devolvía las escenas antiguas de 2022 en estas consultas; por eso el script hace explícita la selección de colección por período.

Antes de entrenar, hay que leer las escalas, offsets y metadatos de cada asset y llevar todas las bandas a reflectancia comparable. No suponer que los DN de estos archivos son directamente equivalentes a la colección armonizada de Earth Engine, cuya corrección radiométrica está documentada por separado ([catálogo armonizado](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED)).

En la ingesta se comprobó que los items de 2022 llevan `earthsearch:boa_offset_applied=true`: se aplica escala 0,0001 y offset efectivo 0. Para los items C1 de 2023/2026 se aplica la escala 0,0001 y offset −0,1; esta diferencia entre colecciones está explicada por el proveedor ([aclaración de Earth Search](https://github.com/Element84/earth-search/issues/41)).

El primer ensayo que aplicaba el offset declarado a todos los archivos produjo valores negativos y fue descartado; se corrigió la regla y se regeneraron todas las salidas. El manifiesto conserva tanto el metadato original como la radiometría efectiva y las pruebas incluyen esta regresión.

Las miniaturas RGB se usaron sólo para inspección. El modelo debe consumir reflectancia multiespectral, no JPEG ni RGB de visualización.

La licencia de datos Sentinel permite acceso libre y abierto y exige atribución de los derivados mediante “Contains modified Copernicus Sentinel data [Year]” ([aviso legal](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice)). Las miniaturas incluidas contienen datos Sentinel modificados de 2022, 2023 y 2026.

## Hansen / Global Forest Change

Usamos **GFC 2025 v1.13**, banda `lossyear`, valores 1–25 para años 2001–2025 y 0 para ausencia de pérdida registrada; su licencia es CC BY 4.0 ([documentación y descarga](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/download.html)). Los tiles descargados fueron `20S_070W` y `20S_060W`, cuyas direcciones están publicadas en la [lista oficial de archivos](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/lossyear.txt).

El script divide tres ventanas iniciales en bloques de 144 × 144 píxeles y selecciona, en cada una, el bloque con más píxeles de pérdida 2022/2023. Por eso los candidatos están sesgados hacia cambios conocidos: sirven para seleccionar estudios de caso, no para estimar la deforestación regional.

No utilizar `lossyear == 0` como etiqueta de bosque: sólo significa ausencia de pérdida detectada en esa capa. Tampoco usar `lossyear > 0` como máscara actual de no bosque sin considerar año, regeneración y definición de cobertura.

Crédito: Hansen/UMD/Google/USGS/NASA. Las cantidades guardadas en `candidates.json` son conteos de píxeles de prospección, no hectáreas oficiales.

## MapBiomas Chaco

La configuración oficial identifica **Colección 5.0, integración v2**, años 1985–2023, y una capa de calidad v1 ([configuración oficial del toolkit](https://github.com/mapbiomas/user-toolkit/blob/master/data/collections-lulc.js)). Los asset IDs son:

```text
projects/mapbiomas-public/assets/chaco/lulc/collection5/mapbiomas_chaco_collection5_integration_v2
projects/mapbiomas-public/assets/chaco/lulc/collection5/mapbiomas_chaco_collection5_quality_v1
```

El portal declara CC BY 4.0 y exige reconocer la fuente ([MapBiomas Chaco](https://chaco.mapbiomas.org/)); la leyenda distingue vegetación leñosa cerrada, abierta, dispersa e inundable e incluye árboles y arbustos ([leyenda](https://chaco.mapbiomas.org/wp-content/uploads/sites/2/2024/08/MB-Chaco-Col-5-pdf-Legend-Descript-ES.pdf)). Por ello no se asignarán automáticamente todas las clases leñosas a bosque.

**Estado: fuente identificada, raster todavía no exportado ni auditado.** El portal interactivo no permitió completar la revisión en esta sesión y el toolkit proporciona assets de Earth Engine, no enlaces públicos directos a GeoTIFF. No hay autorización de Earth Engine en este entorno; no se fabricaron URLs ni una estimación de ruido de MapBiomas.

Siguiente paso propuesto: exportar recortes 2022/2023 desde una cuenta de Earth Engine habilitada y revisar la correspondencia temporal con Sentinel. Si el acceso no se resuelve en el primer día de ingesta, no bloquear todo el proyecto: pasar a una alternativa histórica documentada y a anotación manual acotada, previa aprobación.

## Fuentes de contraste

- **ESA WorldCover:** años 2020/2021, resolución 10 m, CC BY 4.0; los algoritmos de ambas versiones difieren, por lo que su resta no es una referencia válida de cambio ([acceso y condiciones](https://esa-worldcover.org/en/data-access)). Alternativa de etiquetado para un experimento de 2021, no para 2023/2026 sin revisión.
- **Dynamic World:** predicciones por imagen y probabilidades desde 2015, resolución 10 m, CC BY 4.0 y atribución específica ([catálogo](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1)). Sólo apoyo, no verdad de terreno ni test independiente.
- **geoBoundaries:** límites departamentales PRY ADM1, representativos de 2012, licencia CC BY 4.0, ID `PRY-ADM1-63826900` ([metadatos oficiales](https://www.geoboundaries.org/api/current/gbOpen/PRY/ADM1/)). Se comprobó que cada rectángulo completo está dentro del departamento indicado; esto no certifica límites catastrales actuales.
