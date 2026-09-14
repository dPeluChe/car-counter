# Validacion end-to-end del conteo de rutas (origen -> destino)

Mide el resultado real del producto: **cuantos autos completaron cada ruta A->B**,
comparado contra un conteo humano del mismo clip. Complementa a
[validation_workflow.md](validation_workflow.md), que solo mide deteccion por frame.

Para empezar con el material real y salidas separadas, sigue el [protocolo manual](MANUAL_VALIDATION.md). El perfil de ejemplo actual está en modo `lines` y no configura rutas completas. Los comandos `make setup/run` usan por defecto otro video (`glorieta_fast.MP4`) y `config/config.json`; no mezclarlos con las referencias del video normal sin ajustar `VIDEO` y `CONFIG`.

## Requisitos

- `config/config.json` con zonas dibujadas (`make setup`).
- Modo de conteo `zones` (default) — solo ese modo produce rutas A->B.

## Flujo

```bash
# 1. Dibuja las zonas de la glorieta (una por bocacalle: Norte, Sur, Este, Oeste)
make setup

# 2. Corre el pipeline sobre un clip corto (por defecto 1500 frames)
make run                 # -> output/results.json  (+ output/od_matrix.csv)

# 3. Ve ese mismo clip y cuenta a mano cada ruta. Crea el ground truth:
#    data/validation/route_truth.json
#    (plantilla en docs/GUIDES/route_truth.example.json)

# 4. Compara pipeline vs humano
make validate-routes     # usa TRUTH=data/validation/route_truth.json
```

## Formato del conteo humano

JSON plano `{ "ruta": conteo }`. El separador puede ser `->` o `→` (se normaliza). El siguiente ejemplo es ficticio y muestra solamente el formato; no es un conteo medido:

```json
{
  "Norte -> Este": 40,
  "Sur -> Oeste": 18
}
```

Las claves deben usar los mismos nombres de zona que dibujaste en `make setup`.

Este formato agregado no incorpora hash, límites del tramo ni un campo de revisión humana: debes comprobarlos al registrar la prueba. Para una comparación con esas verificaciones usa [eventos individuales](ROUTE_EVENT_REVIEW.md).

## Que reporta

Por cada ruta: `pred` (pipeline), `real` (humano), `err` (|pred-real|) y `acc`
(`1 - err/real`). Marca **rutas fantasma** (el pipeline invento una que no ocurrio)
y **rutas faltantes** (ocurrio pero el pipeline no la conto). Al final: MAE por ruta,
accuracy media por ruta y accuracy sobre el total.

La accuracy ponderada por ruta es `max(0, 1 - suma(|pred-real|) / max(total_real, 1))`.
Penaliza los errores de origen/destino aunque el total de autos coincida. Un total
correcto puede esconder rutas intercambiadas.

Para exigir un umbral, por ejemplo 95%:

```bash
env/bin/python scripts/validate_routes.py \
  --results output/results.json \
  --truth data/validation/route_truth.json \
  --min-accuracy 0.95 --output output/validation_report.json
```

El comando termina con codigo 1 si no alcanza el umbral o no hay autos en la
referencia. El 95% es un ejemplo; el criterio del proyecto debe acordarse con EPS.
Los conteos deben ser enteros no negativos. La referencia debe cubrir las mismas
rutas y los mismos frames del video procesado.

Para procesar sin ventana ni video de salida y conservar el JSON:

```bash
env/bin/python main.py --config config/config.json --no-sahi \
  --headless --no-save --output-tracks-csv output/tracks.csv
```

El CSV conserva los tracks retirados de memoria activa, su posicion inicial,
`first_seen_frame`, `observed_frames`, `destination` y `counted_frame`.
Los IDs representan trayectorias del tracker; un cambio de ID puede dividir un
auto en varias trayectorias. El numero de IDs no equivale al aforo.

En modo `lines`, se confirma el cambio de lado durante `min_crossing_frames`
observaciones consecutivas. El recorrido entre frames debe cruzar el segmento
dibujado. Con bounding boxes, la caja debe terminar de pasar la linea. La distancia
del centro a la linea ya no descarta cruces. El campo antiguo `tolerance` se acepta
por compatibilidad, pero ya no limita el conteo.
Las lineas principalmente horizontales usan `↑/↓`; las verticales usan `←/→`.
Cada ID cuenta una vez por linea y sentido.

## Interpretar los errores

- **Faltan autos en una ruta (undercount):** revisa deteccion (autos chicos del dron
  no detectados -> [validation_workflow.md](validation_workflow.md)) o tracking
  (ID switch a media glorieta pierde el origen).
- **Rutas fantasma:** revisar geometría, asociaciones incorrectas y observaciones de entrada/salida. Cambiar `min_origin_frames`/`min_dest_frames` es un experimento que también puede perder autos rápidos, no una solución garantizada.
- **Destino equivocado:** un auto que circula la glorieta pasando por varias salidas
  antes de la real; el conteo fija la primera salida distinta al origen.

## Evidencia de aceptación

Guarda perfil, comando, video/hash, intervalo, referencia humana y reporte. Un total correcto puede ocultar un auto omitido y otro contado dos veces dentro de la misma ruta; la evaluación agregada no identifica esos casos. El emparejamiento temporal de eventos aporta esa comprobación, pero tampoco prueba identidad física cuando varios autos pasan muy próximos.
