/*
 * Ejecutar en Earth Engine Code Editor con una cuenta/proyecto habilitado.
 * Crea cuatro tareas pendientes: A/B, 2022/2023, 100 km² por zona.
 * NO las inicia automáticamente. C no se incluye.
 * Conserva clases originales; no genera etiquetas binarias de bosque.
 * Fuente: https://github.com/mapbiomas/user-toolkit/blob/master/data/collections-lulc.js
 */
var asset = 'projects/mapbiomas-public/assets/chaco/lulc/collection5/mapbiomas_chaco_collection5_integration_v2';
var image = ee.Image(asset);
print('Verificar bandas antes de exportar', image.bandNames());

var zones = [
  {id: 'A_boqueron', left: 744980, top: 7591690, crs: 'EPSG:32720'},
  {id: 'B_alto_paraguay', left: 244250, top: 7752520, crs: 'EPSG:32721'}
];

zones.forEach(function(zone) {
  // Límites idénticos a configs/training_zones.geojson.
  var region = ee.Geometry.Rectangle(
    [zone.left, zone.top - 10000, zone.left + 10000, zone.top], zone.crs, false
  );
  Map.addLayer(region, {color: 'yellow'}, zone.id);
  [2022, 2023].forEach(function(year) {
    // Mantener 30 m: exportar a 10 m no crea detalle verdadero en las etiquetas.
    var layer = image.select('classification_' + year).toUint8();
    Export.image.toDrive({
      image: layer.unmask(255),
      description: zone.id + '_mapbiomas_c5_v2_' + year,
      folder: 'CHACO_PILOT_LABELS',
      fileNamePrefix: zone.id + '_mapbiomas_c5_v2_' + year,
      region: region,
      crs: zone.crs,
      // Alineación de origen con Sentinel, conservando píxeles de etiqueta de 30 m.
      crsTransform: [30, 0, zone.left, 0, -30, zone.top],
      maxPixels: 1000000,
      fileFormat: 'GeoTIFF',
      formatOptions: {cloudOptimized: true, noData: 255}
    });
  });
});
Map.centerObject(ee.Geometry.Point([-60.582, -21.806]), 11);
