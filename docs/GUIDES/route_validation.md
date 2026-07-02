# Validacion end-to-end del conteo de rutas (origen -> destino)

Mide el resultado real del producto: **cuantos autos completaron cada ruta A->B**,
comparado contra un conteo humano del mismo clip. Complementa a
[validation_workflow.md](validation_workflow.md), que solo mide deteccion por frame.

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

JSON plano `{ "ruta": conteo }`. El separador puede ser `->` o `→` (se normaliza):

```json
{
  "Norte -> Este": 40,
  "Sur -> Oeste": 18
}
```

Las claves deben usar los mismos nombres de zona que dibujaste en `make setup`.

## Que reporta

Por cada ruta: `pred` (pipeline), `real` (humano), `err` (|pred-real|) y `acc`
(`1 - err/real`). Marca **rutas fantasma** (el pipeline invento una que no ocurrio)
y **rutas faltantes** (ocurrio pero el pipeline no la conto). Al final: MAE por ruta,
accuracy media por ruta y accuracy sobre el total.

## Interpretar los errores

- **Faltan autos en una ruta (undercount):** revisa deteccion (autos chicos del dron
  no detectados -> [validation_workflow.md](validation_workflow.md)) o tracking
  (ID switch a media glorieta pierde el origen).
- **Rutas fantasma:** tracks que cruzan zonas de forma espuria, o autos que dan varias
  vueltas antes de salir. Sube `min_origin_frames`/`min_dest_frames`.
- **Destino equivocado:** un auto que circula la glorieta pasando por varias salidas
  antes de la real; el conteo fija la primera salida distinta al origen.
