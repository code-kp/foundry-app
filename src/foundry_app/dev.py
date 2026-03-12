from __future__ import annotations

import argparse
import os
import signal
import subprocess
import time


DEFAULT_PORT = 8000
STOP_RETRIES = 20
STOP_WAIT_SECONDS = 0.25


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Helpers for local Foundry App development."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop the process currently listening on the app port.",
    )
    stop_parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="TCP port to clear before starting the app again.",
    )

    args = parser.parse_args(argv)
    if args.command == "stop":
        return stop_port(int(args.port))
    return 1


def stop_port(port: int) -> int:
    pids = find_listening_pids(port)
    if not pids:
        print("[stop] No listening process found on port {port}.".format(port=port))
        return 0

    targets = expand_process_tree(pids)
    print(
        "[stop] Stopping processes on port {port}: {pids}".format(
            port=port,
            pids=", ".join(str(pid) for pid in sorted(targets)),
        )
    )
    terminate_processes(targets, force=False)
    remaining = wait_for_exit(targets)
    if remaining:
        terminate_processes(remaining, force=True)
        remaining = wait_for_exit(remaining)

    if remaining:
        print(
            "[stop] Some processes are still running: {pids}".format(
                pids=", ".join(str(pid) for pid in sorted(remaining))
            )
        )
        return 1

    print("[stop] Port {port} is clear.".format(port=port))
    return 0


def find_listening_pids(port: int) -> list[int]:
    if os.name == "nt":
        return _find_windows_listening_pids(port)
    return _find_unix_listening_pids(port)


def expand_process_tree(pids: list[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    pending = [pid for pid in pids if pid > 0]

    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        ordered.append(pid)
        pending.extend(_child_pids(pid))

    # Stop children before parents.
    return list(reversed(ordered))


def terminate_processes(pids: list[int], *, force: bool) -> None:
    for pid in pids:
        if os.name == "nt":
            command = ["taskkill", "/PID", str(pid), "/T"]
            if force:
                command.append("/F")
            subprocess.run(command, capture_output=True, text=True, check=False)
            continue

        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            continue


def wait_for_exit(pids: list[int]) -> list[int]:
    remaining = [pid for pid in pids if _pid_running(pid)]
    for _ in range(STOP_RETRIES):
        if not remaining:
            return []
        time.sleep(STOP_WAIT_SECONDS)
        remaining = [pid for pid in remaining if _pid_running(pid)]
    return remaining


def _find_unix_listening_pids(port: int) -> list[int]:
    result = subprocess.run(
        ["lsof", "-nP", "-tiTCP:{port}".format(port=port), "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "Failed to inspect listening ports.")

    pids = []
    for raw_line in result.stdout.splitlines():
        value = raw_line.strip()
        if value.isdigit():
            pids.append(int(value))
    return sorted(set(pids))


def _find_windows_listening_pids(port: int) -> list[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to inspect listening ports.")

    pids = []
    needle = ":{port}".format(port=port)
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address = parts[1]
        pid = parts[-1]
        if not local_address.endswith(needle):
            continue
        if pid.isdigit():
            pids.append(int(pid))
    return sorted(set(pids))


def _child_pids(pid: int) -> list[int]:
    if os.name == "nt":
        return []

    result = subprocess.run(
        ["pgrep", "-P", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        return []

    children = []
    for raw_line in result.stdout.splitlines():
        value = raw_line.strip()
        if value.isdigit():
            children.append(int(value))
    return children


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", "PID eq {pid}".format(pid=pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


if __name__ == "__main__":
    raise SystemExit(main())
