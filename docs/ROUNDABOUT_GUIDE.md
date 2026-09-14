# Configuración de rutas en una glorieta

El motor implementa rutas entre zonas, pero la demo actual usa una sola línea y una ROI parcial. Consulta el [estado verificado](GUIDES/VERIFIED_STATE.md) y ejecuta PRUEBA-05/06 del [protocolo manual](GUIDES/MANUAL_VALIDATION.md) antes de presentar rutas completas.

## Definir el alcance antes de dibujar

Identifica video, tramo y bocacalles que se revisarán. Acuerda las clases incluidas y el tratamiento de autos ya dentro del encuadre al inicio, salidas después del final, retornos y vueltas múltiples. Usa una copia del perfil y salidas nuevas.

La región de inferencia debe cubrir suficientes observaciones de origen, tránsito y destino. Dibujar una zona fuera de la ROI no amplía la detección. Si cambia la ROI, hace falta inferencia nueva; la caché de 300 frames del ejemplo no acredita otro encuadre ni el minuto completo.

## Configurador

Desde el repositorio, abre el configurador con la copia creada por el protocolo manual:

```bash
env/bin/python setup.py --config "$CARCOUNTER_REVIEW_DIR/profile.json"
```

Ese argumento indica archivo de entrada y salida. Confirma visualmente el video y el modelo cargados antes de dibujar. No se ha comprobado la apertura de Tk en esta sesión; cualquier fallo debe registrarse con mensaje y entorno, no atribuirse al detector sin revisar.

En calibración, prueba el perfil real sobre muestras de varios frames. La vista global muestra predicciones; sin anotaciones humanas completas no mide recall. Los filtros derivados de muestras requieren una acción explícita desde cinco muestras. Al cambiar de modelo revisa las clases disponibles y vuelve a comprobar las muestras.

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

Usa preview para comprobar correspondencia de zonas, movimiento y cajas. Guarda, cierra y reabre la copia para verificar persistencia. Si la cámara cambia de encuadre, revisa la geometría contra el frame de referencia; el monitor de deriva no estabiliza la imagen.

Ejemplo para el video de referencia completo, después de guardar un perfil de zonas apropiado:

```bash
env/bin/python main.py --config "$CARCOUNTER_REVIEW_DIR/profile.json" \
  --headless --demo-mode --device cpu --max-frames 1799 \
  --output "$CARCOUNTER_REVIEW_DIR/routes.mp4" \
  --output-json "$CARCOUNTER_REVIEW_DIR/routes.json" \
  --output-tracks-csv "$CARCOUNTER_REVIEW_DIR/routes_tracks.csv" \
  --output-od-csv "$CARCOUNTER_REVIEW_DIR/routes_od.csv"
```

El comando ejecuta inferencia, no utiliza la caché parcial anterior. Revisa el log para confirmar video, modo y tracker efectivos. Si el JSON del perfil sigue en modo `lines`, la salida seguirá siendo aforo por línea.

La matriz OD solo corresponde a `zones`. `directions` clasifica desplazamiento por vector y `lines` cuenta cruces por línea/sentido; ninguno equivale a rutas completas entre bocacalles.

## Validación para presentar

Sigue autos humanos completos y compara eventos, no solo el total de IDs. Conserva también omisiones, duplicaciones, destinos erróneos y casos incompletos. Usa [validación de eventos](GUIDES/ROUTE_EVENT_REVIEW.md) para ruta/clase/tiempo y [totales por ruta](GUIDES/route_validation.md) como resumen complementario.

La presentación debe identificar las rutas revisadas, intervalo, clases, referencia humana y errores medidos. No usar porcentajes de exactitud que provengan de otra cámara, modelo o prueba sintética.
