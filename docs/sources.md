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

**Estado (26 oct, tarde): acceso a Earth Engine resuelto; exportación pendiente de ejecutar.** El equipo comparte un proyecto de Google Cloud con Earth Engine habilitado (variable `GEE_PROJECT`). `scripts/fase2_export_mapbiomas.py` reproduce desde Python la exportación de `scripts/export_mapbiomas_pilot.js` (misma grilla de 30 m, clases originales, nodata 255) sin pasar por Drive. Hasta que se ejecute y se revise `manifests/mapbiomas-labels-v1.json`, MapBiomas sigue sin auditar.

Códigos de clase de la leyenda `mapbiomas-chaco` del toolkit oficial ([legends.js](https://github.com/mapbiomas/user-toolkit/blob/master/data/legends.js)): 3 leñosas cerradas, 4 leñosas abiertas, 6 leñosas inundables, 45 leñosas dispersas, 12 pastizal, 15 pastura, 18/19 agricultura, 26/33 agua, 0/27 no observado. La asignación propuesta a bosque/no bosque está en `src/chaco_monitor/labels.py` y `docs/fase2-dataset.md`, pendiente de aprobación del equipo.

## Fuentes de contraste

- **ESA WorldCover:** años 2020/2021, resolución 10 m, CC BY 4.0; los algoritmos de ambas versiones difieren, por lo que su resta no es una referencia válida de cambio ([acceso y condiciones](https://esa-worldcover.org/en/data-access)). Alternativa de etiquetado para un experimento de 2021, no para 2023/2026 sin revisión.
- **Dynamic World:** predicciones por imagen y probabilidades desde 2015, resolución 10 m, CC BY 4.0 y atribución específica ([catálogo](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1)). Sólo apoyo, no verdad de terreno ni test independiente.
- **geoBoundaries:** límites departamentales PRY ADM1, representativos de 2012, licencia CC BY 4.0, ID `PRY-ADM1-63826900` ([metadatos oficiales](https://www.geoboundaries.org/api/current/gbOpen/PRY/ADM1/)). Se comprobó que cada rectángulo completo está dentro del departamento indicado; esto no certifica límites catastrales actuales.
