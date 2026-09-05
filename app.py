import json
import logging
import os
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request
from waitress import create_server

from checker import run_check
from history import HistoryStore


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")


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


# Der Check-Name ist gleichzeitig die eindeutige ID.
configured_check_names = []

# Letzter bekannter Zustand je Check.
previous_check_states = {}

# Wird nur gesetzt, wenn History aktiviert ist.
history_store = None

history_default_hours = 24
history_retention_days = 30


def load_config():
    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def validate_config(config):
    """
    Prüft grundlegende Konfigurationsfehler.

    Da der Check-Name gleichzeitig die ID ist,
    müssen alle Namen eindeutig sein.
    """

    checks = config.get("checks", [])

    seen_names = {}

    for index, check in enumerate(
        checks,
        start=1
    ):
        name = str(
            check.get("name", "")
        ).strip()

        if not name:
            raise ValueError(
                f"Check #{index} has no name"
            )

        normalized_name = name.casefold()

        if normalized_name in seen_names:
            raise ValueError(
                "Duplicate check name: "
                f"'{name}' conflicts with "
                f"'{seen_names[normalized_name]}'"
            )

        seen_names[normalized_name] = name


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

    try:
        max_size_mb = int(
            logging_config.get(
                "max_size_mb",
                5
            )
        )
    except (TypeError, ValueError):
        max_size_mb = 5

    try:
        backup_count = int(
            logging_config.get(
                "backup_count",
                5
            )
        )
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
        maxBytes=max_size_mb * 1024 * 1024,
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


def initialize_history(config):
    global history_store
    global history_default_hours
    global history_retention_days

    history_config = (
        config
        .get("settings", {})
        .get("history", {})
    )

    enabled = history_config.get(
        "enabled",
        True
    )

    try:
        history_retention_days = int(
            history_config.get(
                "retention_days",
                30
            )
        )
    except (TypeError, ValueError):
        history_retention_days = 30

    try:
        history_default_hours = int(
            history_config.get(
                "default_display_hours",
                24
            )
        )
    except (TypeError, ValueError):
        history_default_hours = 24

    if history_retention_days < 1:
        history_retention_days = 1

    if history_default_hours < 1:
        history_default_hours = 24

    if not enabled:
        history_store = None

        logging.info(
            "History disabled"
        )

        return

    history_store = HistoryStore(
        data_dir=DATA_DIR,
        filename="history.jsonl",
        retention_days=history_retention_days
    )

    history_store.cleanup(
        force=True
    )

    logging.info(
        "History initialized: "
        "retention=%s days default_display=%s hours",
        history_retention_days,
        history_default_hours
    )


def initialize_status(config):
    global current_status

    checks = []

    for check in config.get(
        "checks",
        []
    ):
        item = {
            "name": check["name"],
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

        checks.append(
            item
        )

    with status_lock:
        current_status = {
            "generated": None,
            "checks": checks
        }


def get_result_details(result):
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


def process_status_change(
    check,
    result
):
    """
    Behandelt Logging und History.

    History:
    - erster bekannter Zustand wird gespeichert
    - danach nur Statusänderungen

    Betriebslog:
    - initial UP wird nicht protokolliert
    - DOWN / UNKNOWN werden protokolliert
    - Wiederherstellung nach UP wird protokolliert
    """

    name = result.get(
        "name",
        check["name"]
    )

    new_status = result.get(
        "status",
        "unknown"
    )

    previous_status = (
        previous_check_states.get(
            name
        )
    )

    status_changed = (
        previous_status is None
        or previous_status != new_status
    )

    if status_changed:
        if history_store is not None:
            try:
                history_store.record(
                    check_name=name,
                    status=new_status
                )

            except Exception:
                logging.exception(
                    "Unable to write history for %s",
                    name
                )

        previous_check_states[name] = (
            new_status
        )

    details = get_result_details(
        result
    )

    check_type = result.get(
        "type",
        "unknown"
    )

    #
    # Erster jemals bekannter Zustand
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
                check["name"]
            )

            result = {
                "name": check["name"],
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

        process_status_change(
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
        current_status = new_status

    if history_store is not None:
        try:
            history_store.cleanup()

        except Exception:
            logging.exception(
                "Unable to clean history"
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
        "Checker started: interval=%s seconds",
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


@app.route("/api/history")
def api_history():
    if history_store is None:
        return jsonify({
            "enabled": False,
            "checks": {}
        })

    hours_raw = request.args.get(
        "hours",
        str(history_default_hours)
    )

    try:
        hours = int(
            hours_raw
        )
    except (TypeError, ValueError):
        return jsonify({
            "error": "Invalid hours parameter"
        }), 400

    if hours < 1:
        return jsonify({
            "error": "hours must be >= 1"
        }), 400

    max_hours = (
        history_retention_days * 24
    )

    if hours > max_hours:
        hours = max_hours

    try:
        history = history_store.get_history(
            check_names=configured_check_names,
            hours=hours
        )

    except Exception:
        logging.exception(
            "Unable to read history"
        )

        return jsonify({
            "error": "Unable to read history"
        }), 500

    history["enabled"] = True

    return jsonify(
        history
    )


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok"
    })


def run(stop_event=None):
    global configured_check_names
    global previous_check_states

    if not os.path.exists(
        CONFIG_FILE
    ):
        raise SystemExit(
            "config.json not found: "
            + CONFIG_FILE
        )

    config = load_config()

    try:
        validate_config(
            config
        )

    except ValueError as exc:
        raise SystemExit(
            f"Invalid configuration: {exc}"
        )

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

    configured_check_names = [
        check["name"]
        for check in checks
    ]

    logging.info(
        "Loaded %s checks",
        len(checks)
    )

    initialize_history(
        config
    )

    previous_check_states = {}

    if history_store is not None:
        try:
            previous_check_states.update(
                history_store.get_last_statuses(
                    configured_check_names
                )
            )

            logging.info(
                "Loaded %s previous check states "
                "from history",
                len(previous_check_states)
            )

        except Exception:
            logging.exception(
                "Unable to restore previous "
                "states from history"
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

    server_thread = threading.Thread(
        target=server.run,
        name="waitress",
        daemon=True
    )

    server_thread.start()

    try:
        while not stop_event.wait(
            1
        ):
            if not server_thread.is_alive():
                logging.error(
                    "Waitress server stopped unexpectedly"
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

            if task_dispatcher is not None:
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
