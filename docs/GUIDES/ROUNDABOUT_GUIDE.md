# Configuración de rutas en una glorieta

Cómo dibujar zonas origen/destino y qué hace el contador con ellas. Las rutas completas no están validadas todavía ([VERIFIED_STATE.md](VERIFIED_STATE.md)); ejecuta PRUEBA-05/06 del [protocolo manual](MANUAL_VALIDATION.md) antes de presentarlas.

## Definir el alcance antes de dibujar

Identifica video, tramo y bocacalles que se revisarán. Acuerda las clases incluidas y el tratamiento de autos ya dentro del encuadre al inicio, salidas después del final, retornos y vueltas múltiples. Usa una copia del perfil y salidas nuevas.

La región de inferencia debe cubrir suficientes observaciones de origen, tránsito y destino. Dibujar una zona fuera de la ROI no amplía la detección. Si cambia la ROI hace falta otra caché ([detalle](DETECTION_TUNING.md#grabar-una-vez-y-repetir-sin-inferencia)).

## Configurador

Desde el repositorio, abre el configurador con la copia creada por el protocolo manual:

```bash
env/bin/python setup.py --config "$CARCOUNTER_REVIEW_DIR/profile.json"
```

Ese argumento es archivo de entrada y salida. Confirma el video y el modelo cargados antes de dibujar; si Tk falla, registra mensaje y entorno.

Para calibrar detector y filtros sigue [DETECTION_TUNING.md](DETECTION_TUNING.md#calibrar-en-el-configurador). Al cambiar de modelo revisa las clases disponibles y vuelve a comprobar las muestras.

## Ubicar zonas de origen y destino

Selecciona modo `zones` y al menos dos zonas de entrada/salida. Los puntos están en coordenadas del video original, también cuando se infiere un recorte. Evita que una zona de salida invada el anillo por donde circulan autos que no están saliendo.

El comportamiento actual de `VehicleCounter` es:

1. Confirmar una zona de origen durante `min_origin_frames` observaciones.
2. Esperar tránsito o una zona diferente.
3. Confirmar como destino la primera zona distinta al origen que cumpla `min_dest_frames`.
4. Registrar una ruta y terminar el conteo de ese ID.

Una zona mal colocada puede producir un destino prematuro. Subir la permanencia sin revisar la geometría también puede perder autos rápidos. No hay una política implementada de múltiples rutas completas por ID ni una garantía de recuperar el mismo vehículo después de cambiar de ID.

Las exclusiones descartan detecciones por su centro. Un auto estacionado sigue siendo un vehículo detectable; excluirlo solo es válido si queda fuera del alcance acordado. No recortes estacionamientos que también cubren un acceso que debes contar.

## Revisar, guardar y ejecutar

Antes de guardar o ejecutar, el perfil se valida. **Bloquea** (el texto dice qué corregir) un elemento que nunca puede contar: sin ningún punto dentro de la ROI de inferencia, cubierto por las exclusiones, o dos zonas que se solapan 50 % o más de la menor. **Avisa** sin bloquear un elemento parcialmente fuera de la ROI, excluido en 50 % o más, o dos zonas con solape de 5 % a 50 %. Los porcentajes son aproximados.

Usa preview para comprobar correspondencia de zonas, movimiento y cajas. Guarda, cierra y reabre la copia para verificar persistencia. Si la cámara cambia de encuadre, revisa la geometría contra el frame de referencia; el monitor de deriva no estabiliza la imagen.

Ejemplo para el video de referencia completo, después de guardar un perfil de zonas apropiado:

```bash
env/bin/python main.py --config "$CARCOUNTER_REVIEW_DIR/profile.json" \
  --headless --demo-mode --device cpu --max-frames 1799 \
  --output "$CARCOUNTER_REVIEW_DIR/routes.mp4" \
  --output-json "$CARCOUNTER_REVIEW_DIR/routes.json" \
  --output-tracks-csv "$CARCOUNTER_REVIEW_DIR/routes_tracks.csv" \
  --output-od-csv "$CARCOUNTER_REVIEW_DIR/routes_od.csv" \
  --output-od-group-csv "$CARCOUNTER_REVIEW_DIR/routes_od_by_group.csv"
```

El comando ejecuta inferencia, no utiliza la caché parcial anterior. Revisa el log para confirmar video, modo y tracker efectivos. Si el JSON del perfil sigue en modo `lines`, la salida seguirá siendo aforo por línea.

La matriz OD solo corresponde a `zones`. `--output-od-group-csv` la desglosa por grupo EPS en formato largo (`origen,destino,grupo,conteo`) con los mismos eventos que `routes_by_group` del JSON; sin rutas de zonas solo escribe el encabezado. `directions` clasifica desplazamiento por vector y `lines` cuenta cruces por línea/sentido; ninguno equivale a rutas completas entre bocacalles.

## Validación para presentar

Sigue autos humanos completos y compara eventos, no solo el total de IDs. Conserva también omisiones, duplicaciones, destinos erróneos y casos incompletos. Procedimiento en [ROUTE_VALIDATION.md](ROUTE_VALIDATION.md): eventos por ruta/clase/tiempo como método principal y totales por ruta como resumen.

La presentación debe identificar las rutas revisadas, intervalo, clases, referencia humana y errores medidos. No usar porcentajes de exactitud que provengan de otra cámara, modelo o prueba sintética.


## Entradas y salidas explícitas por acceso

En Paso 2, dibuja polígonos separados para cada carril de entrada y salida. Usa **Definir entradas y salidas por acceso** para asignar a cada zona su rol y acceso. Por ejemplo, las zonas `Norte entrada` y `Norte salida` comparten acceso `Norte`, con roles distintos.

El perfil guarda `zone_roles`, un objeto por nombre de zona con `role` (`entry` o `exit`) y `access`. Debe incluir todas las zonas y al menos una entrada y una salida. Una entrada confirmada inicia la ruta; únicamente una salida confirmada la termina. Visitar otra entrada durante el tránsito no completa ni cambia el origen. Dos polígonos del mismo acceso permiten contar `Norte → Norte`. Cada ID completa como máximo una ruta; una vuelta interna sin salida no cuenta como retorno.

La confirmación sigue usando `min_origin_frames` y `min_dest_frames`; huecos de observación reinician confirmaciones pendientes. La geometría debe separar carriles y evitar solapamientos: el motor aún escoge la primera zona que contiene el centro. Un polígono mal colocado puede producir un destino prematuro; la semántica no sustituye revisar el encuadre.

Perfiles sin `zone_roles` conservan la regla anterior: cualquier zona distinta del origen puede completar el destino. **Usar zonas sin roles** vuelve a ese comportamiento. Los eventos explícitos conservan `origin_zone` y `destination_zone`, mientras la matriz OD usa los nombres de acceso.
