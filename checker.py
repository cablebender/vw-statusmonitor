import platform
import socket
import subprocess
import time
import urllib.error
import urllib.request
import ssl


def check_ping(target, timeout=3):
    start = time.perf_counter()

    if platform.system().lower() == "windows":
        command = [
            "ping",
            "-n", "1",
            "-w", str(timeout * 1000),
            target
        ]
    else:
        command = [
            "ping",
            "-c", "1",
            "-W", str(timeout),
            target
        ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 1
        )

        elapsed = round((time.perf_counter() - start) * 1000, 1)

        return {
            "status": "up" if result.returncode == 0 else "down",
            "response_ms": elapsed
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "down",
            "error": "timeout"
        }


def check_tcp(target, port, timeout=3):
    start = time.perf_counter()

    try:
        with socket.create_connection(
            (target, port),
            timeout=timeout
        ):
            elapsed = round(
                (time.perf_counter() - start) * 1000,
                1
            )

            return {
                "status": "up",
                "response_ms": elapsed
            }

    except Exception as exc:
        return {
            "status": "down",
            "error": str(exc)
        }


def check_http(
    target,
    timeout=3,
    expected_status=200,
    verify_tls=True
):
    start = time.perf_counter()

    context = None

    if target.lower().startswith("https://") and not verify_tls:
        context = ssl._create_unverified_context()

    try:
        request = urllib.request.Request(
            target,
            headers={
                "User-Agent": "VW-Statusmonitor/0.1"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=timeout,
            context=context
        ) as response:

            elapsed = round(
                (time.perf_counter() - start) * 1000,
                1
            )

            http_status = response.status

            return {
                "status": (
                    "up"
                    if http_status == expected_status
                    else "down"
                ),
                "http_status": http_status,
                "response_ms": elapsed
            }

    except urllib.error.HTTPError as exc:
        return {
            "status": "down",
            "http_status": exc.code,
            "error": str(exc)
        }

    except Exception as exc:
        return {
            "status": "down",
            "error": str(exc)
        }


def run_check(check, default_timeout=3):
    check_type = check.get("type")
    timeout = check.get("timeout", default_timeout)

    if check_type == "ping":
        result = check_ping(
            check["target"],
            timeout
        )

    elif check_type == "tcp":
        result = check_tcp(
            check["target"],
            check["port"],
            timeout
        )

    elif check_type in ("http", "https"):
        result = check_http(
            check["target"],
            timeout,
            check.get("expected_status", 200),
            check.get("verify_tls", True)
        )

    else:
        result = {
            "status": "down",
            "error": f"Unknown check type: {check_type}"
        }

    result["name"] = check.get("name", check["target"])
    result["description"] = check.get("description", "")
    result["type"] = check_type
    result["target"] = check["target"]

    if "port" in check:
        result["port"] = check["port"]

    return result
