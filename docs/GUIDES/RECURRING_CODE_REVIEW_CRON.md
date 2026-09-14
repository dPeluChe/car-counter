# Mejoras de detección y rutas cada cinco horas

El instalador está preparado, pero el cron no está activado. Este entorno rechazó incluso `crontab -l`. La consulta real de cuota tampoco pudo arrancar: Codex necesita escribir su estado en `~/.codex`, fuera de los permisos de esta sesión. No se modificó el crontab ni se inició otro agente.

## Activar desde la terminal del usuario

Desde la carpeta `labs-eps-carcounter`:

```bash
env/bin/python scripts/recurring_review.py check
env/bin/python scripts/recurring_review.py install
```

`check` comprueba cuota y disco sin iniciar trabajo del modelo. El código 2 indica que no hay disponibilidad verificada. `install` conserva las otras tareas del crontab, guarda una copia previa y verifica la entrada instalada. Requiere que Codex CLI ya tenga sesión ChatGPT iniciada; puedes comprobarlo con `codex login status`.

El inicio predeterminado es a las 22:00 de Ciudad de México del día de instalación. Si ya pasó esa hora, la siguiente comprobación ejecuta solamente el intervalo vigente. Para otro inicio usa `--start` con una fecha ISO 8601 y zona horaria.

El cron invoca un control ligero cada minuto. La consulta de cuota y el posible trabajo ocurren una vez cada cinco horas exactas: 22:00, 03:00, 08:00, 13:00, 18:00, 23:00… No usa `*/5` en las horas, que reiniciaría la secuencia cada medianoche. La computadora debe estar encendida y despierta; no se configura encendido ni se recuperan todas las ejecuciones perdidas.

## Condiciones de ejecución

- Consulta `account/rateLimits/read` mediante el [protocolo oficial de Codex](https://learn.chatgpt.com/docs/app-server). Usa la cuota de Codex disponible, no el horario supuesto de reinicio del plan.
- Requiere más de 5% restante en todas las ventanas informadas y al menos 2 GiB libres. Si falla la consulta, omite el intento y vuelve a comprobar en el siguiente intervalo.
- Ejecuta `codex exec` con sandbox `workspace-write`, aprobaciones `never` y el modelo configurado por el usuario. No compra créditos ni consume reinicios de cuota.
- Inicia una sesión nueva que lee el [objetivo y restricciones](RECURRING_CODE_REVIEW_PROMPT.md). No reabre automáticamente este chat.
- Un bloqueo de archivo impide solapar ejecuciones de este cron. No bloquea otras herramientas o agentes interactivos. Pausa el cron antes de trabajar simultáneamente sobre estos archivos.
- Cada trabajo tiene un límite de 45 minutos. Si lo alcanza, termina el proceso y conserva los cambios locales para revisión. Una comprobación inicial no garantiza que la cuota alcance para toda la ejecución.

## Revisar y pausar

```bash
env/bin/python scripts/recurring_review.py status
env/bin/python scripts/recurring_review.py pause
env/bin/python scripts/recurring_review.py resume
env/bin/python scripts/recurring_review.py uninstall
```

`pause` afecta futuras ejecuciones; no interrumpe una ya iniciada. `uninstall` retira únicamente el bloque de este proyecto. Los informes, errores y estado quedan en `output/recurring-review/`. `status` muestra el estado local; `crontab -l` permite comprobar la instalación del sistema.

Se probaron las decisiones de cuota, reserva, disco, exclusión mutua, intervalos entre días, conservación de otras tareas y lanzamiento simulado. La activación y una ejecución real del agente siguen pendientes de realizar desde una terminal con permisos.
