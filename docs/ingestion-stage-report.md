# Ingesta A/B: resultados, verificación y pendientes

Etapa cerrada para imágenes Sentinel-2 al 26 de octubre de 2026. A, Boquerón, y B, Alto Paraguay, están aprobadas; C, Presidente Hayes, se mantiene como reserva sin nuevas descargas en esta etapa.

La demo principal usará el par histórico 2022/2023 y el reciente será una prueba de estabilidad y falsas alertas. Este encuadre fue aprobado por el equipo, pero todavía no por la cátedra; no se presentará como cumplimiento confirmado del requisito literal de “últimos meses”.

## Qué quedó preparado

- **Paquete demo/control:** ocho recortes, cuatro fechas por zona; pares histórico y reciente, en la extensión aprobada de aproximadamente 15 km² por zona. El futuro visor limitará cada solicitud a un máximo inicial de 4 km².
- **Insumos históricos ampliados:** cuatro recortes de 100 km², dos fechas para cada zona, con grilla de 1000 × 1000 píxeles a 10 m. Son imágenes para construir el dataset después, no un dataset etiquetado.
- **Canales:** B02, B03, B04, B08 y NDVI, en ese orden; float32 y nodata −9999 en el stack.
- **Calidad:** SCL remuestreada por vecino más cercano, máscara de observabilidad, huella del polígono y máscara de píxeles válidos en ambas fechas.
- **Trazabilidad:** originales DN recortados, IDs STAC, fecha efectiva, URLs de assets, radiometría aplicada, proyección, transformada, checksums y código/configuración identificados por hash.
- **Repositorio:** implementación, pruebas, configuraciones y manifiestos pequeños; los paquetes de imágenes quedan fuera del historial Git.

Los 12 recortes de salida provienen de ocho adquisiciones: las cuatro históricas se procesaron tanto para el área de demo como para las ventanas ampliadas. No son 12 fechas independientes.

## Controles y resultados medidos

Las fechas de una misma zona comparten proyección, transformada, dimensiones y tamaño de píxel. A utiliza EPSG:32720 y B EPSG:32721; el recorte de B de mayo de 2026 venía de otra tesela/zona UTM y se alineó explícitamente, no por coincidencia de tamaño.

| Paquete / zona | Primera fecha | Segunda fecha | Área válida en ambas fechas |
|---|---|---|---:|
| Demo A, histórico | 21/10/2022 | 21/09/2023 | 100,0000% |
| Demo B, histórico | 01/10/2022 | 16/09/2023 | 99,9867% |
| Control A, reciente | 05/05/2026 | 20/09/2026 | 100,0000% |
| Control B, reciente | 05/05/2026 | 02/09/2026 | 99,9533% |
| Entrenamiento A, insumos históricos | 21/10/2022 | 21/09/2023 | 99,9572% |
| Entrenamiento B, insumos históricos | 01/10/2022 | 16/09/2023 | 99,9728% |

Estos porcentajes se calculan dentro de la huella del área, con SCL 4/5/6, exclusión de nubes/sombras y margen de dos píxeles, reflectancias válidas y NDVI definido. Son cobertura observable según el control implementado, no accuracy del modelo ni prueba de ausencia absoluta de nubes.

Pasaron **22 pruebas unitarias** y la verificación de **106 checksums de raster** entre ambos paquetes. También se verificaron orden de canales, rangos, correspondencia de NDVI, nodata, grillas iguales por zona y máscaras de intersección; no se ejecutó todavía una evaluación de segmentación.

### Incidencia radiométrica detectada y resuelta

La primera ejecución aplicaba el offset declarado a todos los assets y descartaba casi toda la imagen de 2022 por reflectancias negativas. La comprobación de propiedades mostró que esas escenas ya tenían el offset aplicado; se corrigió el código y se regeneraron las salidas, siguiendo la distinción documentada por el proveedor ([Earth Search](https://github.com/Element84/earth-search/issues/41)).

Las escenas antiguas con `earthsearch:boa_offset_applied=true` usan offset efectivo 0; las C1 de 2023/2026 usan −0,1, ambas con escala 0,0001. El manifiesto conserva el metadato original y la interpretación efectiva; no se resolvió recortando a cero las reflectancias negativas.

## Qué verificar en la laptop

Desde el repositorio, instalar el entorno indicado en el README. Descomprimir los dos paquetes de imágenes dentro de `data/interim/`; después se puede apagar Wi-Fi para verificar los archivos locales.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_ingestion.py data/interim/pilot-v1
.\.venv\Scripts\python.exe scripts/verify_ingestion.py data/interim/historical-inputs-v1
```

Se espera `22 passed` y `status: passed` para ambos paquetes, con ocho y cuatro registros respectivamente. Las verificaciones de archivos no consultan servicios remotos; la instalación inicial de dependencias sí necesita conectividad o paquetes previamente descargados.

Revisar además las miniaturas `pilot_preview.jpg` y, si tienen QGIS, abrir `stack.tif` como RGB usando bandas 3/2/1 y NDVI como banda 5. El gris indica píxeles excluidos; no significa desmonte.

## Qué falta y por qué no se avanzó a entrenar

- **MapBiomas:** asset y exportador listos; faltan autenticación/proyecto habilitado y los cuatro TIFF de etiquetas. Seguir `mapbiomas-export.md`.
- **Máscaras:** definir correspondencia bosque/no bosque, revisar fechas y bordes, anotar una muestra y separar referencia de test. La máscara `valid.tif` actual no es una máscara de bosque.
- **Dataset:** particiones espaciales, parches, estadísticas de normalización calculadas únicamente sobre train y documentación final. Todavía no se congeló un dataset.
- **Modelo y métricas:** baseline, U-Net, evaluación e inferencia en la ASUS pendientes. Los segundos de preparación registrados en el manifiesto no son tiempos de inferencia ni resultados de la laptop.
- **Aplicación:** API, visor y Docker se implementarán tras cerrar las fases correspondientes; no hay una demo ejecutable todavía.

La fecha límite para resolver MapBiomas es el 28 de octubre. Si no se logra, se aplicará la alternativa Hansen autorizada con las limitaciones documentadas, sin inventar porcentajes de ruido ni convertir ausencia de pérdida en bosque.

## Cambios que dependen del profesor

- **Zonas preparadas:** si exige áreas arbitrarias, el modo online dejaría de ser opcional y habría que renegociar alcance/tiempo; no se ha supuesto esa aprobación.
- **Fechas recientes:** si exige un caso reciente positivo, el histórico no lo sustituye. Haría falta buscar y revisar otro recorte/intervalo, sin etiquetar estacionalidad como desmonte.
- **Tres páginas IEEE:** mantenemos la hipótesis de que referencias cuentan dentro de las tres páginas hasta recibir la plantilla o aclaración.

El siguiente paso es resolver las etiquetas y aprobar las reglas de máscaras y separación espacial. Esta entrega termina la preparación de imágenes y deja visible ese bloqueo; no avanza automáticamente al entrenamiento.
