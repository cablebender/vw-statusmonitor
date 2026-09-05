import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone


VALID_STATUSES = {
    "up",
    "down",
    "unknown"
}


class HistoryStore:
    def __init__(
        self,
        data_dir,
        filename="history.jsonl",
        retention_days=30
    ):
        self.data_dir = data_dir
        self.filename = filename
        self.retention_days = max(
            1,
            int(retention_days)
        )

        self.path = os.path.join(
            self.data_dir,
            self.filename
        )

        self.lock = threading.RLock()

        self.last_cleanup = 0.0

        # Maximal einmal pro Stunde aufräumen.
        self.cleanup_interval = 3600

        os.makedirs(
            self.data_dir,
            exist_ok=True
        )


    @staticmethod
    def _now():
        return datetime.now(
            timezone.utc
        )


    @staticmethod
    def _format_time(timestamp):
        return timestamp.astimezone(
            timezone.utc
        ).isoformat()


    @staticmethod
    def _parse_time(value):
        if not isinstance(
            value,
            str
        ):
            return None

        try:
            if value.endswith("Z"):
                value = (
                    value[:-1]
                    + "+00:00"
                )

            timestamp = (
                datetime.fromisoformat(
                    value
                )
            )

            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(
                    tzinfo=timezone.utc
                )

            return timestamp.astimezone(
                timezone.utc
            )

        except (
            TypeError,
            ValueError
        ):
            return None


    def record(
        self,
        check_name,
        status,
        timestamp=None
    ):
        if status not in VALID_STATUSES:
            status = "unknown"

        if timestamp is None:
            timestamp = self._now()

        record = {
            "time": self._format_time(
                timestamp
            ),
            "check": str(
                check_name
            ),
            "status": status
        }

        line = json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":")
        )

        with self.lock:
            with open(
                self.path,
                "a",
                encoding="utf-8"
            ) as file:
                file.write(
                    line + "\n"
                )


    def _load_events_unlocked(self):
        if not os.path.exists(
            self.path
        ):
            return []

        events = []

        try:
            with open(
                self.path,
                "r",
                encoding="utf-8"
            ) as file:
                for line_number, line in enumerate(
                    file,
                    start=1
                ):
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        record = json.loads(
                            line
                        )

                    except json.JSONDecodeError:
                        logging.warning(
                            "Ignoring malformed history "
                            "line %s",
                            line_number
                        )

                        continue

                    check_name = record.get(
                        "check"
                    )

                    status = record.get(
                        "status"
                    )

                    timestamp = self._parse_time(
                        record.get(
                            "time"
                        )
                    )

                    if (
                        not check_name
                        or status not in VALID_STATUSES
                        or timestamp is None
                    ):
                        logging.warning(
                            "Ignoring invalid history "
                            "line %s",
                            line_number
                        )

                        continue

                    events.append({
                        "time": timestamp,
                        "check": str(
                            check_name
                        ),
                        "status": status
                    })

        except FileNotFoundError:
            return []

        events.sort(
            key=lambda event: event["time"]
        )

        return events


    def get_last_statuses(
        self,
        check_names=None
    ):
        with self.lock:
            events = (
                self._load_events_unlocked()
            )

        allowed = None

        if check_names is not None:
            allowed = set(
                check_names
            )

        result = {}

        for event in events:
            name = event["check"]

            if (
                allowed is not None
                and name not in allowed
            ):
                continue

            result[name] = (
                event["status"]
            )

        return result


    def get_history(
        self,
        check_names,
        hours=24
    ):
        hours = max(
            1,
            int(hours)
        )

        end = self._now()

        start = end - timedelta(
            hours=hours
        )

        with self.lock:
            events = (
                self._load_events_unlocked()
            )

        events_by_check = {
            name: []
            for name in check_names
        }

        for event in events:
            name = event["check"]

            if name in events_by_check:
                events_by_check[
                    name
                ].append(
                    event
                )

        result = {}

        for name in check_names:
            check_events = (
                events_by_check.get(
                    name,
                    []
                )
            )

            state_at_start = "unknown"

            relevant_events = []

            for event in check_events:
                event_time = event["time"]

                if event_time <= start:
                    state_at_start = (
                        event["status"]
                    )

                elif event_time <= end:
                    relevant_events.append(
                        event
                    )

                else:
                    break

            intervals = []

            current_status = (
                state_at_start
            )

            current_start = start

            for event in relevant_events:
                event_time = event["time"]

                if event_time > current_start:
                    intervals.append({
                        "from": self._format_time(
                            current_start
                        ),
                        "to": self._format_time(
                            event_time
                        ),
                        "status": current_status
                    })

                current_status = (
                    event["status"]
                )

                current_start = (
                    event_time
                )

            if current_start < end:
                intervals.append({
                    "from": self._format_time(
                        current_start
                    ),
                    "to": self._format_time(
                        end
                    ),
                    "status": current_status
                })

            result[name] = intervals

        return {
            "hours": hours,
            "from": self._format_time(
                start
            ),
            "to": self._format_time(
                end
            ),
            "checks": result
        }


    def cleanup(
        self,
        force=False
    ):
        """
        Entfernt alte History-Einträge.

        Wichtig:
        Pro Check bleibt der letzte Status VOR
        der Retention-Grenze erhalten.

        Dadurch kann der Zustand am Beginn
        des Zeitfensters weiterhin rekonstruiert
        werden.
        """

        now_monotonic = (
            time.monotonic()
        )

        if (
            not force
            and (
                now_monotonic
                - self.last_cleanup
            ) < self.cleanup_interval
        ):
            return

        self.last_cleanup = (
            now_monotonic
        )

        cutoff = (
            self._now()
            - timedelta(
                days=self.retention_days
            )
        )

        with self.lock:
            events = (
                self._load_events_unlocked()
            )

            if not events:
                return

            last_before_cutoff = {}

            retained_events = []

            for event in events:
                if event["time"] < cutoff:
                    last_before_cutoff[
                        event["check"]
                    ] = event

                else:
                    retained_events.append(
                        event
                    )

            retained_events.extend(
                last_before_cutoff.values()
            )

            retained_events.sort(
                key=lambda event: event["time"]
            )

            temp_path = (
                self.path + ".tmp"
            )

            with open(
                temp_path,
                "w",
                encoding="utf-8"
            ) as file:
                for event in retained_events:
                    record = {
                        "time": self._format_time(
                            event["time"]
                        ),
                        "check": event["check"],
                        "status": event["status"]
                    }

                    file.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                            separators=(",", ":")
                        )
                        + "\n"
                    )

            os.replace(
                temp_path,
                self.path
            )
