# Standup 2026-09-15: listo para pruebas manuales

Continúa [STANDUP_260914.md](STANDUP_260914.md).

## Qué se cerró

| PR | Resultado |
|---|---|
| #11 | Tramos de cámara estable (`make segment-video`) y `main.py --start-frame` |
| #12 | Reporte de tracks incompletos y posibles cambios de ID (`make review-tracks`), simplify, revisión de código y ajustes de preparación para pruebas manuales |

## Hallazgos del día

- **Fragmentación:** en el replay de 300 frames, 150 de 282 tracks tienen 10 observaciones o menos.
- **Cambios de ID:** hay 83 candidatos y 38 cambian de clase (car ↔ van).
  - Causa probable: YOLO hace NMS por clase y deja dos cajas sobre el mismo auto (TODO-030).
- **CSV de tracks:** ahora trae la caja real del primer y último frame, si el origen se confirmó y los votos de clase.
- **Video de validación:** `glorieta_test1min.mp4`. Su frame 1 es el 5396 del video completo, así que el frame del reproductor es el frame del evento.
- **Validador:** avisa si una ruta de la referencia no aparece en la salida (nombres sin flecha fallaban en silencio).

## Revisiones

- **Código (PR #12):** sin errores altos ni medios. Se corrigieron los dos bajos: CSV viejo sin columnas nuevas y recorte fuera del frame.
- **Preparación:** PRUEBA-01, `make review-tracks` y la validación por grupos funcionan hoy. El bloqueo principal es que no hay perfil de zonas de toda la glorieta (TODO-031).

## Orden de pruebas manuales

1. PRUEBA-01: replay de 300 frames, confirmar los 6 eventos.
2. PRUEBA-03 parcial: `make review-tracks` sobre ese replay y revisar los primeros candidatos en el video.
3. PRUEBA-04: contar a mano `Anillo oeste ↓` en los frames 1-300 con `events_truth.example.json` y validar con `--events --by-group`.
4. PRUEBA-02: extraer, preetiquetar, corregir en LabelMe y evaluar dentro de la ROI.
5. PRUEBA-05: configurador en escritorio sobre `glorieta_test1min.mp4`, guardar y reabrir.
6. PRUEBA-07: `audit_camera_motion.py --max-frames 1799` sobre el clip.
7. Marcaje de zonas de todos los accesos (TODO-031), con 10 px de margen.
8. Grabar una vez la caché de 1799 frames con ese perfil.
9. PRUEBA-06: variantes de zonas con replay, `make review-tracks` con origen confirmado y referencia de 1799 frames.
10. PRUEBA-08: registro de incidencias desde el paso 1.

## Cierre del día: pulido del flujo de UI (PR #13)

Antes de empezar las pruebas se revisó el flujo completo de UI, que no se había tocado. Salió en dos tandas: fase A (defectos de pérdida de datos, dibujo, autosave y lanzamiento) y ronda 2 sobre los cuatro reportes de simplify, con dos agentes en worktrees y los commits desde la sesión coordinadora.

### Qué cambió

- **Configurador:** ROI de inferencia editable desde la GUI (antes solo a mano en el JSON, y una zona fuera de la ROI contaba cero sin avisar); `--model` explícito ya no lo pisa el perfil; un perfil sin `sahi.enabled` ya no enciende SAHI; los valores por defecto de tracker y SAHI salen del esquema; `conf_per_class` solo escribe clases que el modelo puede emitir.
- **Wizard:** "Ejecutar" valida el perfil antes de gastar una corrida; sin perfil preseleccionado; resumen de perfil en el Paso 3; "Cancelar" también cierra un configurador colgado.
- **Compartido:** `carcounter/process_utils.py` con cierre por grupo de procesos, usado también por el cron.

### Hallazgos

- **Preview congelado:** la inferencia corría en el hilo de Tk, 1186 a 1653 ms por tick. Ahora corre en un hilo y el tick baja a 3.6 ms; las cajas van uno o dos segundos atrasadas, que es el precio aceptado.
- **Costo de SAHI:** reescala cada tile a `imgsz` (1600), 73.6 s por el tramo de 300 frames. Bajarlo a 640 corre 3.7x más rápido pero reasigna clases y el aforo pasa de 3 ligeros y 2 pesados a 5 y 1. No se cambió el default; queda en TODO-038 con [informe](../RESEARCH/SAHI_IMAGE_SIZE_2026_09_15.md).
- **Corrección a lo anotado arriba:** el NMS por clase solo aplica a la ruta sin SAHI. Con SAHI, `geometry.apply_nms` suprime por IoU sin mirar la clase, así que ese duplicado no sobrevive por ahí.

### Estado

Suite en 395 pruebas y probe de ventana oculta 16 de 16. La verificación en escritorio sigue pendiente y es el paso 5 de la lista de arriba, ahora con los puntos de la ronda 2 añadidos en TODO-033.
