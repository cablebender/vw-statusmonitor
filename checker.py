import platform
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request


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

        elapsed = round(
            (
                time.perf_counter()
                - start
            ) * 1000,
            1
        )

        if result.returncode == 0:
            return {
                "status": "up",
                "response_ms": elapsed
            }

        return {
            "status": "down",
            "response_ms": elapsed,
            "error": (
                "Ping returned exit code "
                f"{result.returncode}"
            )
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "down",
            "error": "Ping timeout"
        }

    except FileNotFoundError:
        return {
            "status": "unknown",
            "error": "ping executable not found"
        }

    except Exception as exc:
        return {
            "status": "unknown",
            "error": str(exc)
        }


def check_tcp(target, port, timeout=3):
    start = time.perf_counter()

    try:
        with socket.create_connection(
            (target, port),
            timeout=timeout
        ):
            elapsed = round(
                (
                    time.perf_counter()
                    - start
                ) * 1000,
                1
            )

            return {
                "status": "up",
                "response_ms": elapsed
            }

    except (
        socket.timeout,
        ConnectionRefusedError,
        ConnectionResetError,
        OSError
    ) as exc:
        return {
            "status": "down",
            "error": str(exc)
        }

    except Exception as exc:
        return {
            "status": "unknown",
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

    if (
        target.lower().startswith("https://")
        and not verify_tls
    ):
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
                (
                    time.perf_counter()
                    - start
                ) * 1000,
                1
            )

            http_status = response.status

            result = {
                "status": (
                    "up"
                    if http_status == expected_status
                    else "down"
                ),
                "http_status": http_status,
                "response_ms": elapsed
            }

            if http_status != expected_status:
                result["error"] = (
                    f"Expected HTTP {expected_status}, "
                    f"received HTTP {http_status}"
                )

            return result

    except urllib.error.HTTPError as exc:
        elapsed = round(
            (
                time.perf_counter()
                - start
            ) * 1000,
            1
        )

        http_status = exc.code

        result = {
            "status": (
                "up"
                if http_status == expected_status
                else "down"
            ),
            "http_status": http_status,
            "response_ms": elapsed
        }

        if http_status != expected_status:
            result["error"] = str(
                exc
            )

        return result

    except (
        urllib.error.URLError,
        TimeoutError,
        socket.timeout
    ) as exc:
        return {
            "status": "down",
            "error": str(exc)
        }

    except ValueError as exc:
        return {
            "status": "unknown",
            "error": (
                "Invalid URL: "
                + str(exc)
            )
        }

    except Exception as exc:
        return {
            "status": "unknown",
            "error": str(exc)
        }


def run_check(
    check,
    default_timeout=3
):
    check_type = check.get(
        "type"
    )

    target = check.get(
        "target"
    )

    timeout = check.get(
        "timeout",
        default_timeout
    )

    if not check_type:
        result = {
            "status": "unknown",
            "error": "Check type missing"
        }

    elif not target:
        result = {
            "status": "unknown",
            "error": "Check target missing"
        }

    elif check_type == "ping":
        result = check_ping(
            target,
            timeout
        )

    elif check_type == "tcp":
        if "port" not in check:
            result = {
                "status": "unknown",
                "error": "TCP port missing"
            }

        else:
            result = check_tcp(
                target,
                check["port"],
                timeout
            )

    elif check_type in (
        "http",
        "https"
    ):
        result = check_http(
            target,
            timeout,
            check.get(
                "expected_status",
                200
            ),
            check.get(
                "verify_tls",
                True
            )
        )

    else:
        result = {
            "status": "unknown",
            "error": (
                "Unknown check type: "
                f"{check_type}"
            )
        }

    result["name"] = check.get(
        "name",
        target or "Unknown"
    )

    result["description"] = (
        check.get(
            "description",
            ""
        )
    )

    result["type"] = (
        check_type
        or "unknown"
    )

    result["target"] = (
        target
        or ""
    )

    result["depends_on"] = (
        check.get(
            "depends_on",
            []
        )
    )

    if "port" in check:
        result["port"] = (
            check["port"]
        )

    return result
