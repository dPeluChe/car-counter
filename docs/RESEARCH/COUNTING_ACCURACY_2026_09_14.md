# Margen de error en aforos por video, 14 de septiembre de 2026

Pregunta: ¿qué margen de error es realista para un conteo origen/destino por video en una glorieta, y cómo definirlo para aceptar resultados? Resultado aplicado: [COUNTING_SCOPE.md](../GUIDES/COUNTING_SCOPE.md#criterio-de-aceptación-propuesta).

## Evidencia encontrada

| Fuente | Tipo | Dato |
|---|---|---|
| NASEM (2025), *Leveraging Existing Traffic Signal Assets to Obtain Quality Traffic Counts*, cap. 3, resultados de NCHRP 03-144. doi:10.17226/29214 | Guía técnica (EE.UU.) | Volúmenes motorizados de sistemas de video comerciales: **WMAPE 1.4 % a 33.7 %** según fabricante, equipo e intersección. Los giros (TMC) tienen menor precisión que los movimientos de paso. No motorizados: WMAPE 3.6 % a 93.7 %. Recomienda validaciones manuales de 15 a 30 minutos. |
| Wang, Ho y Wang (2023), *Journal of Intelligent and Connected Vehicles* 6(3):149-160. doi:10.26599/JICV.2023.9210014 | Artículo revisado por pares | Conteo de giros desde video de dron con tracking multiobjeto: **91.93 %** de precisión global, mejor caso sobre 98 %. **Causa principal de error: cambios de ID** por oclusión del fondo. |
| Miovision, *Traffic Data Accuracy Definition* (2021) | Garantía comercial | Regla 5/95 por clase en periodos de 15 min: **±5 vehículos** hasta 100, **95 %** arriba de 100. En glorietas multicámara los giros son "aproximados". Bicicletas: ±5 hasta 50 por 15 min. |
| *Automating the Estimation of Turning Movement Rates at Multilane Roundabouts*, ScienceDirect (2025), S2773153725000908 | Artículo | Resumen: 97 % de precisión verificada con conteo manual. **Solo se leyó el resumen** (el texto completo bloqueó la descarga). |
| SCT, Datos Viales, introducción | Oficial (México) | Simbología de composición vehicular: M, A, B, C2, C3, T3S2. Se leyó solo el fragmento de búsqueda. |

No se pudieron descargar el estudio de precisión de conteos manuales desde video (Majumder y Wilmot, 2023, *Journal of Transportation Technologies* 13(4)) ni los manuales de Alberta y NYSDOT; no se citan cifras de ellos.

## Lectura para este proyecto

1. **±20 % es un objetivo inicial razonable, no un estándar.** Queda dentro del rango observado en sistemas comerciales (hasta 33.7 % de WMAPE) y es más laxo que el error del estudio con dron (cerca de 8 %) y que la garantía comercial (5 %). Sirve para un prototipo; no para presentar como precisión de producto.
2. **El error dominante en glorietas son los cambios de ID**, no la detección. Cada cambio en el anillo pierde un origen. Por eso TODO-030 va antes que afinar detección.
3. **Los porcentajes solo son estables con volumen.** Las referencias definen precisión sobre bloques de 15 minutos o con una tolerancia absoluta en conteos chicos. Un minuto de glorieta deja pocas unidades por ruta: con 5 vehículos, un solo error es 20 %. De ahí la regla `max(2 vehículos, 20 %)` por celda.
4. **La referencia humana también tiene error.** Las guías piden validaciones manuales repetibles; conviene que el conteo humano de eventos se haga en dos pasadas o por dos personas y se reconcilien diferencias antes de marcar `reviewed=true`.
5. **Bicicletas y motos se detectan peor** (NCHRP: error mucho mayor en no motorizados). Esperar más error en `dos_ruedas` que en `ligeros`.

## Siguiente paso

Contar a mano el tramo acordado con grupos EPS, correr `validate_routes.py --events --by-group` y calcular la tabla de aceptación. Con ese resultado se confirma o ajusta el ±20 % y se decide si ampliar a 15 minutos.
