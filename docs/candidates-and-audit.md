# Tres zonas candidatas y revisión exploratoria de etiquetas

Consulta y revisión realizadas el 26 de octubre de 2026. Las zonas son **candidatas, no una selección definitiva**; se eligieron por pérdida histórica detectada en GFC y se inspeccionaron con Sentinel-2.

## Coordenadas y evidencia de selección

Coordenadas WGS84, en grados decimales; en la tabla el centro se expresa como latitud/longitud. En los archivos GeoJSON y bounding boxes se usa longitud/latitud, como exige ese formato.

| Candidata | Centro aproximado (latitud, longitud) | Bbox [oeste, sur, este, norte] | Área de prospección | Píxeles GFC con pérdida 2022/2023 |
|---|---|---|---:|---:|
| A, Boquerón | -21.806, -60.582 | [-60.600, -21.824, -60.564, -21.788] | 14,84 km² | 10.711 |
| B, Alto Paraguay | -20.354, -59.402 | [-59.420, -20.372, -59.384, -20.336] | 14,98 km² | 12.481 |
| C, Presidente Hayes | -23.334, -59.194 | [-59.212, -23.352, -59.176, -23.316] | 14,68 km² | 4.372 |

Los conteos se calcularon directamente sobre los tiles `lossyear` de GFC 2025 v1.13 publicados por Hansen; no son hectáreas ni estimaciones de pérdida reciente ([archivo oficial](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/download.html)). La pertenencia completa de los tres rectángulos a sus departamentos se contrastó con geoBoundaries PRY ADM1, cuya geometría representa 2012 ([metadatos](https://www.geoboundaries.org/api/current/gbOpen/PRY/ADM1/)).

### Por qué estas zonas

- **A, Boquerón:** el par histórico muestra una transformación geométrica clara a lotes rectangulares, mientras conserva una masa boscosa continua al este. Es mi primera opción para explicar segmentación, límites y transición temporal.
- **B, Alto Paraguay:** el par histórico muestra ampliación de lotes y franjas conservadas; aporta ejemplos difíciles de bordes y mosaico. Lo propongo como segundo candidato preferente o reserva si se necesita simplificar.
- **C, Presidente Hayes:** contiene un desmonte histórico y coberturas más heterogéneas, caminos y áreas naturalmente abiertas. Es útil como prueba difícil, pero exige mayor cuidado para no equiparar vegetación natural no arbórea con desmonte.

Estas interpretaciones corresponden a una revisión visual exploratoria de las miniaturas incluidas; no son constataciones de campo ni conclusiones sobre titularidad, legalidad o causa. Las áreas de prospección de unos 15 km² se reducirán para la demo: cada solicitud empezará limitada a 4 km².

## Escenas verificadas con baja nubosidad

Se consultó el catálogo STAC, se leyeron los recortes RGB y SCL y se conservaron los IDs completos en `evidence/selected_scenes.csv`. Los porcentajes de la tabla son `eo:cloud_cover` de la escena, no del polígono; se muestran con cuatro decimales cuando hace falta.

| Candidata | Histórico anterior | Histórico posterior | Reciente anterior | Reciente posterior |
|---|---|---|---|---|
| A | 21/10/2022; 0,0046% | 21/09/2023; 0,0031% | 05/05/2026; 0,0104% | 20/09/2026; 0,0016% |
| B | 01/10/2022; 0,0042% | 16/09/2023; 0,0034% | 05/05/2026; 0,0024% | 02/09/2026; 0,0022% |
| C | 23/10/2022; 0,0045% | 03/10/2023; 0,2412% | 05/05/2026; 0,0026% | 27/09/2026; 0,0017% |

En la grilla reducida de inspección de 512 × 512, la suma SCL de sombras/nubes/cirros fue 0% para once recortes y 0,077% para C en 2022. Este control se repetirá a resolución nativa y con la máscara conservadora definitiva: SCL no es una garantía de ausencia absoluta de nubes o sombras.

Se encontraron escenas de distintas teselas/zonas UTM para algunas fechas de B y C. Antes de inferir se reproyectarán todas las fechas a una misma grilla; no se restarán matrices sólo porque tienen igual tamaño.

### Interpretación temporal importante

**En las tres zonas, el caso positivo visualmente claro es histórico.** Entre mayo y septiembre de 2026 predominan diferencias de verdor de lotes ya abiertos y no identifiqué un nuevo desmonte inequívoco en estas miniaturas.

Por tanto, las fechas recientes sirven para probar estabilidad y falsas alertas, no para prometer una cantidad positiva de hectáreas. Si se exige una demo reciente positiva, falta una búsqueda acotada de otro recorte/intervalo; no se ha ocultado ese pendiente ni se pintarán diferencias de NDVI como deforestación.

## Muestra visual de pseudoetiquetas: qué se pudo medir

La auditoría realizada aquí es de **Hansen**, no de MapBiomas. No pudimos exportar el raster de MapBiomas en esta fase y, por tanto, no existe todavía un porcentaje de ruido medido para las etiquetas propuestas de entrenamiento.

### Diseño de la revisión piloto

- Se generaron 12 puntos por candidata con semilla 42: seis etiquetados por Hansen como pérdida 2022 y seis como pérdida 2023.
- Para el resumen de compatibilidad se usaron sólo los 18 puntos de pérdida 2023: el par de imágenes comienza a fines de 2022 y no permite auditar correctamente todo el año 2022.
- Se inspeccionó el centro marcado en rojo y su contexto en las cuatro columnas de cada lámina: 2022, 2023, mayo de 2026 y septiembre de 2026.
- Es una selección exploratoria condicionada a pérdida registrada, en zonas elegidas por cambio, con pocos puntos y dependencia espacial. No estima precisión global, recall ni proporción regional de etiquetas erróneas.
- No hubo segunda anotadora independiente ni verificación de campo; las clasificaciones del asistente deben ser revisadas por las integrantes antes de usarse en un informe.

### Resultado exploratorio

| Zona | Compatibles visualmente con remoción | Dudosos/mixtos, requieren revisión | Total |
|---|---:|---:|---:|
| A | 2 | 4 | 6 |
| B | 3 | 3 | 6 |
| C | 3 | 3 | 6 |
| Total | 8 | 10 | 18 |

**10/18 = 55,6% de los puntos de este piloto requieren revisión o exclusión**, principalmente por coincidir con franjas conservadas, caminos, bordes o cambio no inequívoco. Eso no significa “55,6% de error de Hansen”, mucho menos de MapBiomas o del futuro dataset; algunos son píxeles mixtos legítimos a la resolución de origen y otros requieren más fechas.

El registro punto por punto se conserva en `evidence/audit_decisions.csv`. Los puntos 2022 siguen sin evaluación de compatibilidad anual; en particular, una remoción ocurrida antes de octubre de 2022 no puede validarse restando las imágenes de octubre de 2022 y septiembre de 2023.

### Qué haremos antes de entrenar

Exportar las pseudoetiquetas efectivamente elegidas, emparejarlas temporalmente y tomar una muestra estratificada de ambas clases, incluyendo interiores y bordes. Propuesta reducida: 60 puntos, 30 por zona, con dos revisiones independientes y categorías “compatible”, “aparente error” e “incierto”.

El informe distinguirá porcentaje de aparentes errores del porcentaje de incertidumbre y reportará tamaño, diseño y desacuerdo entre revisoras. Los puntos utilizados para corregir entrenamiento no podrán reutilizarse como referencia de test.

## Lectura de las láminas

Las láminas `*_overview.jpg` muestran arriba el par histórico y abajo el reciente. Las láminas `*_audit.jpg` contienen los 12 puntos por candidata; sólo las filas 07–12 se incluyeron en el resumen anterior.

Las miniaturas son imágenes de inspección, no inputs de entrenamiento. Contienen datos Copernicus Sentinel modificados de 2022, 2023 y 2026; la fuente de puntos es Hansen/UMD/Google/USGS/NASA.
