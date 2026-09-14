# Analisis del conteo vehicular, 6 de septiembre de 2026

El conteo por linea ya funciona en una muestra del video normal con VisDrone y
recorte de inferencia. La precision de las rutas completas de la glorieta sigue
sin validarse. No existe un conteo humano en `data/validation/route_truth.json`.

## Evidencia del problema

El proyecto usa Python, OpenCV, Ultralytics y trackers persistentes. La ejecucion
principal pasa por `main.py`, `runtime.py`, `detection.py` y `counting.py`.
El repositorio estaba limpio en `main`, commit `332b79b`, antes de esta revision.

Se reprodujo el pipeline anterior con YOLO11L, ByteTrack, imagen de 1920 pixeles,
sin SAHI y con la configuracion local de zonas:

```bash
env/bin/python main.py --config config/config.json \
  --model models/yolo/yolov11l.pt --video assets/glorieta_fast.MP4 \
  --no-sahi --headless --no-save --max-frames 475 --benchmark \
  --output-json output/audit_baseline.json \
  --output-tracks-csv output/audit_baseline_tracks.csv
```

Resultado: 475 frames, 920 IDs, cero rutas, 582 segundos y 0.82 FPS en CPU.
Los resultados anteriores guardados tambien tenian cero rutas. Los 920 IDs
son fragmentos de tracking, no un aforo de 920 autos. El CSV anterior conservaba
solo 697 de esos IDs porque borraba los tracks retirados antes de exportarlos.

## Causas encontradas

| Hallazgo | Evidencia | Consecuencia |
|---|---|---|
| Continuidad temporal insuficiente en el clip rapido | En los primeros dos frames, el percentil 99 del desplazamiento de puntos visuales fue 53.84 px, frente a 1.17 px en el clip normal de un minuto | El tracking por solapamiento pierde asociaciones; cambiar solo el contador no recupera esos recorridos |
| El detector general falla en esta vista | YOLO11L encontro cero cajas de vehiculos en el recorte del primer frame del video normal incluso con confianza 0.03; VisDrone encontro cajas con confianza superior a 0.9 | Se necesita evaluar el modelo sobre la vista real antes de ajustar rutas |
| Cruces con confirmacion incompatibles | Se exigia cambio de lado respecto al frame anterior y varias observaciones ya confirmadas del mismo lado | El modo por lineas perdia cruces normales con el valor predeterminado de dos frames |
| Origen y destino mal confirmados | Un cambio directo a otra zona no reemplazaba un origen sin confirmar; `min_dest_frames=1` requeria otro frame | Se perdian rutas o se mantenia un origen equivocado |
| IDs inventados sin tracker | El fallback asignaba `i + 1` segun el orden de las detecciones en cada frame | Autos distintos podian compartir una supuesta trayectoria |
| Configuracion espacial incompleta | La configuracion local cubre cuatro zonas y omite accesos visibles; los videos normal y rapido tienen encuadres distintos | Las mismas zonas no sirven para ambos videos ni representan todas las rutas |
| Modelo con ruta rota | `config/config.json` apuntaba a la ubicacion anterior del repositorio | La ejecucion predeterminada no podia cargar ese archivo |

El desplazamiento de puntos incluye movimiento de camara, objetos y posibles
errores de flujo optico. Es evidencia de discontinuidad; no mide velocidad de
vehiculos ni determina el factor exacto de aceleracion del video.

## Cambios implementados

- El cruce conserva el lado de origen y confirma la llegada al otro lado. Verifica
  la interseccion con el segmento real, incluyendo el paso por encima de la linea
  y los casos con bounding boxes. No cuenta pasar alrededor de un extremo.
- Las lineas verticales distinguen izquierda y derecha. Cada ID cuenta una vez
  por linea y sentido. Los saltos de observaciones reinician la confirmacion.
- Las zonas aceptan destinos de un frame cuando se configura asi y reemplazan
  origenes que no llegaron a confirmarse.
- La falta de tracker detiene el proceso en vez de fabricar IDs. Cuando SAHI usa
  SORT, el reporte indica el tracker efectivo.
- `settings.inference_roi` recorta el area de deteccion. Las coordenadas de las
  lineas, exclusiones y salidas siguen referidas al video original.
- Los CSV conservan los tracks retirados y registran el primer frame, numero de
  observaciones, destino y frame del conteo. La posicion inicial ya no cambia al
  agotarse el historial de dibujo.
- El guardado de configuracion conserva los umbrales de confirmacion y el recorte.
- `--headless --no-save` evita el dibujo cuando no hay consumidor de imagen.
  `--no-save` conserva la exportacion JSON; `--no-output-json` la desactiva.
- El benchmark usa el ultimo promedio acumulado y los frames procesados para
  calcular los porcentajes. Antes dividia por la cantidad de muestras del reporte.
- El validador de rutas tiene `--min-accuracy` y penaliza errores por ruta aunque
  los totales coincidan. Rechaza valores negativos, fracciones y rutas duplicadas.

## Pruebas y mediciones

La suite original pasaba 204 pruebas y omitia 15 por dependencias opcionales.
Se reprodujeron 13 fallos en una primera bateria de 15 casos de regresion antes
de corregir el contador. Las pruebas agregadas cubren tambien recortes,
persistencia de configuracion, exportacion y el criterio de aceptacion por ruta.
Resultado final: 251 pruebas aprobadas y 15 omitidas por dependencias opcionales.
Tambien pasaron la compilacion de Python y `git diff --check`.

En una prueba aislada de 120 frames de 1920x1080 con 96 tracks simulados, el
procesamiento sin imagen paso de 7.24 a 0.186 ms por frame. Esto excluye inferencia
real: no representa una aceleracion equivalente del pipeline completo. La
deteccion de la ejecucion original tardaba aproximadamente 1,183 ms por frame.

Con el video normal, VisDrone, ByteTrack, recorte `[680,350,960,750]`, confianza
0.25 y resolucion 960, se procesaron 300 frames y se registraron seis cruces
descendentes en la linea del anillo oeste: un bus y cinco autos. Los IDs contados
fueron 1, 31, 57, 64, 86 y 136, con 222-300 observaciones cada uno. El procesamiento
tardo 153.92 segundos, aproximadamente 1.95 FPS en CPU.

Esta prueba mide una linea durante unos diez segundos. No es comparable con el
total de rutas del clip rapido y no demuestra la precision de toda la glorieta.
Los resultados y el video estan en `output/audit_visdrone_roi*`.

La comparacion de resoluciones en los frames 0, 150 y 299 recupero con 640 pixeles
257 de las 258 cajas producidas a 960, usando IoU >= 0.5. Cada inferencia a 640
tardo aproximadamente 0.20 segundos. Esta comparacion entre modelos no sustituye
anotaciones humanas; pueden compartir errores.

La ejecucion completa de los mismos 300 frames a 640 pixeles produjo los mismos
seis cruces, un bus y cinco autos, en 89.05 segundos: 3.37 FPS y 42% menos tiempo.
Los seis IDs contados tuvieron 222-300 observaciones. El total de IDs del recorte
subio de 197 a 282; conservar el total de cruces no demuestra por si solo igual
precision del detector. El video final se reviso visualmente y sus resultados
estan en `output/aerial_demo*`.

## Ejecucion reproducible

```bash
make run-aerial
```

Usa `docs/GUIDES/aerial_counting.example.json` y genera `output/aerial_demo.mp4`,
`output/aerial_demo.json` y `output/aerial_demo_tracks.csv`. Requiere los archivos
locales `assets/glorieta_test1min.mp4` y `models/yolo/yolov8l-visdrone.pt`.
La configuracion de ejemplo usa resolucion 640. La configuracion original de
zonas se conserva; solo se corrigio su ruta al modelo.

## Trabajo necesario para aceptar el aforo completo

1. Delimitar las entradas y salidas solicitadas por EPS en el video original.
   El recorte debe abarcar todo el recorrido para contar rutas A->B.
2. Revisar movimiento de camara y ajustar o estabilizar las zonas sobre un tramo
   mas largo. Un recorte fijo no estabiliza el video.
3. Anotar los cruces o rutas de ese mismo tramo, con los mismos limites temporales.
   Separar autos, buses y otras clases segun el alcance acordado.
4. Ejecutar el validador con el umbral acordado y revisar cada diferencia. La
   [guia de validacion](../GUIDES/ROUTE_VALIDATION.md) incluye el comando.

No se entreno un modelo nuevo ni se modificaron los pesos. No se hicieron commits,
PRs ni despliegues. Las pruebas de CPU no establecen rendimiento en GPU.

## Continuación

La [segunda revisión](DETECTION_IMPROVEMENTS_2026_09_07.md) documenta la calibración compartida, ByteTrack con SAHI, caché de detecciones y correcciones del evaluador. Sustituye el fallback obligatorio a SORT descrito en la primera etapa.
