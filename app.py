import json
import logging
import os
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify
from waitress import create_server

from checker import run_check


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")
LOG_DIR = os.path.join(BASE_DIR, "logs")


app = Flask(
    __name__,
    static_folder=STATIC_DIR,
    static_url_path=""
)


status_lock = threading.Lock()

current_status = {
    "generated": None,
    "checks": []
}


# Letzter tatsächlich gemessener Status.
# Wird für die zustandsbasierte Protokollierung verwendet.
previous_check_states = {}


def load_config():
    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def configure_logging(config):
    os.makedirs(
        LOG_DIR,
        exist_ok=True
    )

    logging_config = (
        config
        .get("settings", {})
        .get("logging", {})
    )

    log_level_name = str(
        logging_config.get(
            "level",
            "INFO"
        )
    ).upper()

    log_level = getattr(
        logging,
        log_level_name,
        logging.INFO
    )

    max_size_mb = logging_config.get(
        "max_size_mb",
        5
    )

    backup_count = logging_config.get(
        "backup_count",
        5
    )

    try:
        max_size_mb = int(max_size_mb)
    except (TypeError, ValueError):
        max_size_mb = 5

    try:
        backup_count = int(backup_count)
    except (TypeError, ValueError):
        backup_count = 5

    if max_size_mb < 1:
        max_size_mb = 1

    if backup_count < 0:
        backup_count = 0

    logfile = os.path.join(
        LOG_DIR,
        "status-monitor.log"
    )

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"
    )

    file_handler = RotatingFileHandler(
        logfile,
        maxBytes=(
            max_size_mb
            * 1024
            * 1024
        ),
        backupCount=backup_count,
        encoding="utf-8"
    )

    file_handler.setFormatter(
        formatter
    )

    console_handler = (
        logging.StreamHandler()
    )

    console_handler.setFormatter(
        formatter
    )

    root_logger = logging.getLogger()

    root_logger.setLevel(
        log_level
    )

    # Verhindert doppelte Handler, falls die
    # Logging-Konfiguration erneut geladen wird.
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(
            handler
        )

        try:
            handler.close()
        except Exception:
            pass

    root_logger.addHandler(
        file_handler
    )

    root_logger.addHandler(
        console_handler
    )

    logging.info(
        "Logging initialized: "
        "level=%s max_size=%sMB backups=%s",
        log_level_name,
        max_size_mb,
        backup_count
    )


def initialize_status(config):
    global current_status

    checks = []

    for check in config.get(
        "checks",
        []
    ):
        item = {
            "name": check.get(
                "name",
                check.get(
                    "target",
                    "Unknown"
                )
            ),
            "description": check.get(
                "description",
                ""
            ),
            "type": check.get(
                "type",
                "unknown"
            ),
            "target": check.get(
                "target",
                ""
            ),
            "status": "unknown"
        }

        if "port" in check:
            item["port"] = check["port"]

        checks.append(item)

    with status_lock:
        current_status = {
            "generated": None,
            "checks": checks
        }


def get_check_key(check):
    """
    Erzeugt eine eindeutige interne ID für einen Check.

    Name alleine reicht nicht unbedingt aus,
    weil mehrere Checks denselben Namen besitzen könnten.
    """

    return (
        str(
            check.get(
                "name",
                ""
            )
        ),
        str(
            check.get(
                "type",
                ""
            )
        ),
        str(
            check.get(
                "target",
                ""
            )
        ),
        str(
            check.get(
                "port",
                ""
            )
        )
    )


def get_result_details(result):
    """
    Erzeugt eine kurze Beschreibung für das Log.
    """

    details = []

    if result.get(
        "http_status"
    ) is not None:
        details.append(
            f"HTTP {result['http_status']}"
        )

    if result.get(
        "response_ms"
    ) is not None:
        details.append(
            f"{result['response_ms']} ms"
        )

    if result.get(
        "port"
    ) is not None:
        details.append(
            f"port {result['port']}"
        )

    if result.get(
        "error"
    ):
        details.append(
            str(result["error"])
        )

    if not details:
        return ""

    return " - " + " | ".join(
        details
    )


def log_status_change(
    check,
    result
):
    """
    Protokolliert nur relevante Ereignisse:

    - erster erfolgreicher UP-Check:
      kein Logeintrag

    - erster DOWN/UNKNOWN-Check:
      WARNING

    - Wechsel nach DOWN/UNKNOWN:
      WARNING

    - Wiederherstellung nach UP:
      INFO

    - unveränderter Zustand:
      kein Logeintrag
    """

    key = get_check_key(
        check
    )

    new_status = result.get(
        "status",
        "unknown"
    )

    previous_status = (
        previous_check_states.get(
            key
        )
    )

    previous_check_states[key] = (
        new_status
    )

    name = result.get(
        "name",
        "Unknown"
    )

    check_type = result.get(
        "type",
        "unknown"
    )

    details = get_result_details(
        result
    )

    #
    # Erster Check
    #
    if previous_status is None:
        if new_status == "down":
            logging.warning(
                "%s [%s] DOWN%s",
                name,
                check_type,
                details
            )

        elif new_status == "unknown":
            logging.warning(
                "%s [%s] UNKNOWN%s",
                name,
                check_type,
                details
            )

        # Ein initialer UP-Status wird absichtlich
        # nicht protokolliert.
        return

    #
    # Keine Änderung
    #
    if previous_status == new_status:
        return

    #
    # Statusänderung
    #
    if new_status == "up":
        logging.info(
            "%s [%s] %s -> UP%s",
            name,
            check_type,
            previous_status.upper(),
            details
        )

    elif new_status == "down":
        logging.warning(
            "%s [%s] %s -> DOWN%s",
            name,
            check_type,
            previous_status.upper(),
            details
        )

    elif new_status == "unknown":
        logging.warning(
            "%s [%s] %s -> UNKNOWN%s",
            name,
            check_type,
            previous_status.upper(),
            details
        )

    else:
        logging.warning(
            "%s [%s] %s -> %s%s",
            name,
            check_type,
            previous_status.upper(),
            str(new_status).upper(),
            details
        )


def perform_checks(config):
    global current_status

    default_timeout = (
        config
        .get("settings", {})
        .get(
            "default_timeout",
            3
        )
    )

    results = []

    # Checkzyklen werden nur auf DEBUG
    # protokolliert.
    logging.debug(
        "Starting check cycle"
    )

    for check in config.get(
        "checks",
        []
    ):
        try:
            result = run_check(
                check,
                default_timeout
            )

        except Exception as exc:
            logging.exception(
                "Internal error while checking %s",
                check.get(
                    "name",
                    check.get(
                        "target",
                        "Unknown"
                    )
                )
            )

            result = {
                "name": check.get(
                    "name",
                    check.get(
                        "target",
                        "Unknown"
                    )
                ),
                "description": check.get(
                    "description",
                    ""
                ),
                "type": check.get(
                    "type",
                    "unknown"
                ),
                "target": check.get(
                    "target",
                    ""
                ),
                "status": "unknown",
                "error": (
                    "Internal checker error: "
                    f"{exc}"
                )
            }

            if "port" in check:
                result["port"] = (
                    check["port"]
                )

        results.append(
            result
        )

        log_status_change(
            check,
            result
        )

    new_status = {
        "generated": datetime.now(
            timezone.utc
        ).isoformat(),
        "checks": results
    }

    with status_lock:
        current_status = (
            new_status
        )


def check_loop(
    config,
    stop_event
):
    interval = (
        config
        .get("settings", {})
        .get(
            "check_interval",
            30
        )
    )

    logging.info(
        "Checker started: "
        "interval=%s seconds",
        interval
    )

    while not stop_event.is_set():
        try:
            perform_checks(
                config
            )

        except Exception:
            logging.exception(
                "Error during check cycle"
            )

        if stop_event.wait(
            interval
        ):
            break

    logging.info(
        "Checker thread stopped"
    )


@app.route("/")
def index():
    return app.send_static_file(
        "index.html"
    )


@app.route("/api/status")
def api_status():
    with status_lock:
        return jsonify(
            current_status
        )


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok"
    })


def run(stop_event=None):
    if not os.path.exists(
        CONFIG_FILE
    ):
        raise SystemExit(
            "config.json not found: "
            + CONFIG_FILE
        )

    config = load_config()

    configure_logging(
        config
    )

    logging.info(
        "Starting VW-Statusmonitor"
    )

    checks = config.get(
        "checks",
        []
    )

    logging.info(
        "Loaded %s checks",
        len(checks)
    )

    initialize_status(
        config
    )

    if stop_event is None:
        stop_event = (
            threading.Event()
        )

    worker = threading.Thread(
        target=check_loop,
        args=(
            config,
            stop_event
        ),
        name="status-checker",
        daemon=True
    )

    worker.start()

    listen_address = (
        config
        .get("settings", {})
        .get(
            "listen_address",
            "0.0.0.0"
        )
    )

    listen_port = (
        config
        .get("settings", {})
        .get(
            "listen_port",
            8080
        )
    )

    logging.info(
        "Listening on %s:%s",
        listen_address,
        listen_port
    )

    server = create_server(
        app,
        host=listen_address,
        port=listen_port,
        threads=4
    )

    server_thread = (
        threading.Thread(
            target=server.run,
            name="waitress",
            daemon=True
        )
    )

    server_thread.start()

    try:
        while not stop_event.wait(
            1
        ):
            if not server_thread.is_alive():
                logging.error(
                    "Waitress server "
                    "stopped unexpectedly"
                )

                break

    except KeyboardInterrupt:
        logging.info(
            "Keyboard interrupt received"
        )

        stop_event.set()

    finally:
        logging.info(
            "Stopping VW-Statusmonitor"
        )

        stop_event.set()

        try:
            server.close()

        except Exception:
            logging.exception(
                "Error while closing "
                "Waitress server"
            )

        try:
            task_dispatcher = getattr(
                server,
                "task_dispatcher",
                None
            )

            if (
                task_dispatcher
                is not None
            ):
                task_dispatcher.shutdown()

        except Exception:
            logging.exception(
                "Error while stopping "
                "Waitress task dispatcher"
            )

        server_thread.join(
            timeout=10
        )

        worker.join(
            timeout=10
        )

        logging.info(
            "VW-Statusmonitor stopped"
        )


def main():
    run()


if __name__ == "__main__":
    main()
