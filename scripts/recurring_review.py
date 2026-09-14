import argparse
from datetime import datetime
import fcntl
import json
import math
import os
from pathlib import Path
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import time
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "output" / "recurring-review"
PROMPT = ROOT / "docs/GUIDES/RECURRING_CODE_REVIEW_PROMPT.md"
BEGIN = "# BEGIN carcounter-recurring-review"
END = "# END carcounter-recurring-review"
INTERVAL = 5 * 3600


def save_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else {}


def next_slot(start, now):
    return start if now < start else start + (int((now - start) // INTERVAL) + 1) * INTERVAL


def quota_decision(payload, reserve=5):
    buckets = payload.get("rateLimitsByLimitId") or {}
    snapshot = buckets.get("codex", payload.get("rateLimits"))
    if not isinstance(snapshot, dict):
        return dict(ready=False, reason="Cuota desconocida")
    if snapshot.get("rateLimitReachedType") or snapshot.get("spendControlReached"):
        return dict(ready=False, reason="Límite de cuenta alcanzado")
    windows = [snapshot[key] for key in ("primary", "secondary") if snapshot.get(key) is not None]
    if not windows:
        return dict(ready=False, reason="Sin ventanas de cuota verificables")
    remaining = []
    for window in windows:
        used = window.get("usedPercent") if isinstance(window, dict) else None
        if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used) or used < 0:
            return dict(ready=False, reason="Respuesta de cuota inválida")
        remaining.append(max(0, 100 - used))
    individual = snapshot.get("individualLimit")
    if individual is not None:
        value = individual.get("remainingPercent")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            return dict(ready=False, reason="Límite individual desconocido")
        remaining.append(value)
    available = min(remaining)
    return dict(ready=available > reserve, remaining_percent=available,
                reason="Cuota disponible" if available > reserve else "Cuota agotada o en reserva")


def stop_process(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def execution_environment(codex):
    folders = [str(ROOT / "env/bin"), str(Path(codex).parent),
               str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin",
               os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")]
    return dict(os.environ, PATH=os.pathsep.join(folders))


def read_quota(codex):
    process = subprocess.Popen([codex, "app-server", "--stdio"], cwd=ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True,
                               env=execution_environment(codex))
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    buffer = b""
    deadline = time.monotonic() + 30

    def send(message):
        process.stdin.write((json.dumps(message) + "\n").encode())
        process.stdin.flush()

    def request(number, method, params=None):
        nonlocal buffer
        send(dict(id=number, method=method, params=params or {}))
        while True:
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                message = json.loads(line)
                if message.get("id") == number:
                    if "error" in message:
                        raise RuntimeError(f"Consulta {method} rechazada; revisar sesión y conexión de Codex")
                    return message["result"]
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise TimeoutError("La consulta de cuota excedió 30 segundos")
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError("Codex cerró la consulta de cuota")
            buffer += chunk
            if len(buffer) > 2_000_000:
                raise RuntimeError("Respuesta de cuota demasiado grande")

    try:
        request(1, "initialize", {"clientInfo": {"name": "carcounter_cron", "version": "1.0"}})
        send({"method": "initialized"})
        account = request(2, "account/read", {"refreshToken": False}).get("account")
        if not account or account.get("type") != "chatgpt":
            raise RuntimeError("Se requiere sesión ChatGPT en Codex CLI")
        return quota_decision(request(3, "account/rateLimits/read"))
    finally:
        selector.close()
        stop_process(process)
        process.stdin.close()
        process.stdout.close()


def preflight(settings):
    free = shutil.disk_usage(ROOT).free
    if free < 2 * 1024 ** 3:
        return dict(ready=False, reason="Menos de 2 GiB libres", free_bytes=free)
    try:
        result = read_quota(settings["codex"])
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        result = dict(ready=False, reason=str(error))
    return dict(result, free_bytes=free)


def run_due(settings, directory=STATE_DIR, now=None):
    now = time.time() if now is None else now
    with (directory / "lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return dict(status="busy")
        if (directory / "PAUSED").exists():
            return dict(status="paused")
        state = read_json(directory / "state.json")
        if now < max(settings["start"], state.get("next_run", 0)):
            return dict(status="waiting")
        state = dict(status="checking", checked_at=now, next_run=next_slot(settings["start"], now))
        save_json(directory / "state.json", state)
        check = preflight(settings)
        state.update(check=check, status="skipped")
        save_json(directory / "state.json", state)
        if not check["ready"]:
            return state
        stamp = datetime.fromtimestamp(now, ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
        report = directory / f"{stamp}.md"
        command = [settings["codex"], "-a", "never", "-s", "workspace-write", "exec",
                   "-C", str(ROOT), "--color", "never", "-o", str(report), "-"]
        state.update(status="running", report=str(report))
        save_json(directory / "state.json", state)
        with (directory / f"{stamp}.log").open("x") as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=log,
                                       cwd=ROOT, start_new_session=True, pass_fds=(lock.fileno(),),
                                       env=execution_environment(settings["codex"]))
            try:
                process.communicate(PROMPT.read_bytes(), timeout=45 * 60)
                state.update(status="finished" if process.returncode == 0 else "failed",
                             exit_code=process.returncode)
            except subprocess.TimeoutExpired:
                state.update(status="timeout")
            finally:
                stop_process(process)
                state["finished_at"] = time.time()
                save_json(directory / "state.json", state)
        return state


def managed_crontab(existing, entry):
    lines = existing.splitlines()
    if lines.count(BEGIN) != lines.count(END) or lines.count(BEGIN) > 1:
        raise ValueError("Bloque de cron inconsistente; no se modificó")
    if BEGIN in lines:
        first, last = lines.index(BEGIN), lines.index(END)
        if last < first:
            raise ValueError("Bloque de cron invertido; no se modificó")
        lines = lines[:first] + lines[last + 1:]
    if entry:
        lines += [BEGIN, entry, END]
    return "\n".join(lines) + ("\n" if lines else "")


def install(settings, remove=False):
    current = subprocess.run(["/usr/bin/crontab", "-l"], capture_output=True, text=True)
    if current.returncode and not (current.returncode == 1 and "no crontab for" in current.stderr.lower()):
        raise RuntimeError("No se pudo leer crontab; instalación cancelada sin reemplazar tareas")
    command = shlex.join([str(ROOT / "env/bin/python"), str(Path(__file__).resolve()), "run"])
    if "\n" in command or "\r" in command:
        raise ValueError("Ruta no compatible con cron")
    entry = "* * * * * " + command.replace("%", "\\%") + " >/dev/null 2>&1"
    updated = managed_crontab(current.stdout, None if remove else entry)
    if not remove:
        if not Path(settings["codex"]).is_file() or not os.access(settings["codex"], os.X_OK):
            raise ValueError("Ejecutable Codex no disponible")
        save_json(STATE_DIR / "settings.json", settings)
    stamp = time.time_ns()
    (STATE_DIR / f"crontab-before-{stamp}.txt").write_text(current.stdout)
    subprocess.run(["/usr/bin/crontab", "-"], input=updated, text=True, check=True)
    actual = subprocess.run(["/usr/bin/crontab", "-l"], capture_output=True, text=True, check=True)
    if actual.stdout != updated:
        raise RuntimeError("La verificación del crontab no coincide; revisar manualmente")
    return dict(status="uninstalled" if remove else "installed")


def main():
    parser = argparse.ArgumentParser(description="Mejoras de detección y rutas cada cinco horas")
    parser.add_argument("action", choices=["install", "uninstall", "check", "run", "status", "pause", "resume"])
    parser.add_argument("--start", help="Inicio ISO 8601 con zona horaria")
    parser.add_argument("--codex", default=shutil.which("codex") or str(Path.home() / ".superset/bin/codex"))
    args = parser.parse_args()
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.umask(0o077)
    settings = read_json(STATE_DIR / "settings.json") or dict(codex=args.codex)
    if args.action == "install":
        default = datetime.now(ZoneInfo("America/Mexico_City")).replace(hour=22, minute=0, second=0, microsecond=0)
        start = datetime.fromisoformat(args.start) if args.start else default
        if start.utcoffset() is None:
            parser.error("--start requiere zona horaria")
        settings.update(codex=args.codex, start=start.timestamp())
        result = install(settings)
    elif args.action == "uninstall":
        result = install(settings, remove=True)
    elif args.action == "check":
        result = preflight(settings)
    elif args.action == "run":
        if "start" not in settings:
            raise RuntimeError("Primero instala el cron desde tu terminal")
        result = run_due(settings)
    elif args.action == "status":
        result = dict(settings=settings, state=read_json(STATE_DIR / "state.json"),
                      paused=(STATE_DIR / "PAUSED").exists())
    elif args.action == "pause":
        (STATE_DIR / "PAUSED").touch()
        result = dict(status="paused")
    else:
        (STATE_DIR / "PAUSED").unlink(missing_ok=True)
        result = dict(status="resumed")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.action == "check" and not result["ready"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        if STATE_DIR.exists():
            save_json(STATE_DIR / "last_error.json", dict(at=time.time(), error=str(error)))
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
