import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify
from waitress import serve

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


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def configure_logging():
    os.makedirs(LOG_DIR, exist_ok=True)

    logfile = os.path.join(
        LOG_DIR,
        "status-monitor.log"
    )

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(message)s"
        ),
        handlers=[
            logging.FileHandler(
                logfile,
                encoding="utf-8"
            ),
            logging.StreamHandler()
        ]
    )


def perform_checks(config):
    global current_status

    default_timeout = config["settings"].get(
        "default_timeout",
        3
    )

    results = []

    logging.info("Starting check cycle")

    for check in config.get("checks", []):
        result = run_check(
            check,
            default_timeout
        )

        results.append(result)

        logging.info(
            "%s [%s] %s",
            result["name"],
            result["type"],
            result["status"].upper()
        )

    new_status = {
        "generated": datetime.now(
            timezone.utc
        ).isoformat(),
        "checks": results
    }

    with status_lock:
        current_status = new_status


def check_loop(config):
    interval = config["settings"].get(
        "check_interval",
        30
    )

    while True:
        try:
            perform_checks(config)
        except Exception:
            logging.exception(
                "Error during check cycle"
            )

        time.sleep(interval)


@app.route("/")
def index():
    return app.send_static_file(
        "index.html"
    )


@app.route("/api/status")
def api_status():
    with status_lock:
        return jsonify(current_status)


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok"
    })


def main():
    configure_logging()

    logging.info(
        "Starting VW-Statusmonitor"
    )

    if not os.path.exists(CONFIG_FILE):
        logging.error(
            "config.json not found"
        )
        raise SystemExit(1)

    config = load_config()

    worker = threading.Thread(
        target=check_loop,
        args=(config,),
        daemon=True
    )

    worker.start()

    listen_address = config["settings"].get(
        "listen_address",
        "0.0.0.0"
    )

    listen_port = config["settings"].get(
        "listen_port",
        8080
    )

    logging.info(
        "Listening on %s:%s",
        listen_address,
        listen_port
    )

    serve(
        app,
        host=listen_address,
        port=listen_port,
        threads=4
    )


if __name__ == "__main__":
    main()
