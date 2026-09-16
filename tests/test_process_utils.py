"""Cierre de subprocesos: cae todo el grupo, no solo el proceso lanzado."""

import os
import subprocess
import sys
import time

from carcounter.process_utils import stop_process, terminate_group

IGNORA_SIGTERM = ("import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                  "print('listo', flush=True); time.sleep(60)")
CON_HIJO = ("import subprocess, sys, time; "
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
            "print(child.pid, flush=True); time.sleep(60)")


def _alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_process_that_ignores_sigterm_is_killed():
    process = subprocess.Popen([sys.executable, "-c", IGNORA_SIGTERM],
                               start_new_session=True, stdout=subprocess.PIPE)
    process.stdout.readline()
    stop_process(process, timeout=1)
    process.stdout.close()
    assert process.poll() is not None


def test_child_of_the_subprocess_does_not_survive():
    process = subprocess.Popen([sys.executable, "-c", CON_HIJO],
                               start_new_session=True, stdout=subprocess.PIPE)
    child = int(process.stdout.readline())
    stop_process(process, timeout=5)
    process.stdout.close()
    deadline = time.monotonic() + 5
    while _alive(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(child)


def test_without_own_group_falls_back_to_terminate():
    class Fake:
        terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    fake = Fake()
    terminate_group(fake)
    assert fake.terminated
