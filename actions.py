import logging
import os
import shutil
import subprocess
import threading
import time


class ActionManager:
    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(
            base_dir
        )

        self.lock = threading.RLock()

        # Laufzeitzustand je Check:
        #
        # {
        #   "Cisco-VPN": {
        #       "down_since": 123456.78,
        #       "running": False
        #   }
        # }
        self.states = {}


    def process_result(
        self,
        check,
        result
    ):
        """
        Wird nach jedem Check aufgerufen.

        Wenn ein Check mit konfigurierter Aktion
        länger als "down_for" Sekunden DOWN ist,
        wird die Aktion gestartet.

        Nach dem Start der Aktion beginnt der
        DOWN-Timer erneut.
        """

        action = check.get(
            "action"
        )

        if not action:
            return

        if not action.get(
            "enabled",
            True
        ):
            return

        check_name = check.get(
            "name",
            "Unknown"
        )

        status = result.get(
            "status",
            "unknown"
        )

        now = time.monotonic()

        with self.lock:
            state = self.states.setdefault(
                check_name,
                {
                    "down_since": None,
                    "running": False
                }
            )

            #
            # Sobald der Check nicht mehr DOWN ist,
            # wird der Timer vollständig zurückgesetzt.
            #
            if status != "down":
                state["down_since"] = None
                return

            #
            # Beginn eines neuen DOWN-Zeitraums.
            #
            if state["down_since"] is None:
                state["down_since"] = now

                logging.info(
                    "%s action timer started",
                    check_name
                )

                return

            try:
                down_for = int(
                    action.get(
                        "down_for",
                        900
                    )
                )

            except (
                TypeError,
                ValueError
            ):
                logging.error(
                    "%s has invalid "
                    "action.down_for value",
                    check_name
                )

                return

            if down_for < 1:
                logging.error(
                    "%s has invalid "
                    "action.down_for value: %s",
                    check_name,
                    down_for
                )

                return

            elapsed = (
                now
                - state["down_since"]
            )

            #
            # Noch nicht lange genug DOWN.
            #
            if elapsed < down_for:
                return

            #
            # Eine Aktion für diesen Check läuft
            # bereits.
            #
            if state["running"]:
                return

            #
            # WICHTIG:
            #
            # Timer bereits jetzt zurücksetzen.
            # Dadurch wird die Aktion nicht beim
            # nächsten 30-Sekunden-Check erneut
            # gestartet.
            #
            state["down_since"] = now
            state["running"] = True

        logging.warning(
            "%s has been DOWN for %s seconds "
            "- executing action",
            check_name,
            down_for
        )

        worker = threading.Thread(
            target=self._run_action,
            args=(
                check_name,
                action
            ),
            name=f"action-{check_name}",
            daemon=True
        )

        worker.start()


    def _run_action(
        self,
        check_name,
        action
    ):
        try:
            action_type = action.get(
                "type",
                ""
            ).lower()

            if action_type == "powershell":
                self._run_powershell(
                    check_name,
                    action
                )

            else:
                logging.error(
                    "%s has unsupported "
                    "action type: %s",
                    check_name,
                    action_type
                )

        except Exception:
            logging.exception(
                "Unexpected error while "
                "executing action for %s",
                check_name
            )

        finally:
            with self.lock:
                state = self.states.get(
                    check_name
                )

                if state is not None:
                    state["running"] = False


    def _run_powershell(
        self,
        check_name,
        action
    ):
        script = action.get(
            "script"
        )

        if not script:
            logging.error(
                "%s action has no script",
                check_name
            )

            return

        #
        # Scripts dürfen nur innerhalb des
        # Projektverzeichnisses liegen.
        #
        script_path = os.path.abspath(
            os.path.join(
                self.base_dir,
                script
            )
        )

        try:
            common_path = os.path.commonpath(
                [
                    self.base_dir,
                    script_path
                ]
            )

        except ValueError:
            logging.error(
                "%s action script path "
                "is invalid: %s",
                check_name,
                script
            )

            return

        if common_path != self.base_dir:
            logging.error(
                "%s action script is outside "
                "the project directory: %s",
                check_name,
                script_path
            )

            return

        if not os.path.isfile(
            script_path
        ):
            logging.error(
                "%s action script not found: %s",
                check_name,
                script_path
            )

            return

        try:
            timeout = int(
                action.get(
                    "timeout",
                    60
                )
            )

        except (
            TypeError,
            ValueError
        ):
            timeout = 60

        if timeout < 1:
            timeout = 60


        powershell = shutil.which(
            "powershell.exe"
        )

        if powershell is None:
            logging.error(
                "%s cannot execute action: "
                "powershell.exe not found",
                check_name
            )

            return


        command = [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path
        ]


        logging.info(
            "%s executing PowerShell action: %s",
            check_name,
            script
        )


        creation_flags = 0

        if os.name == "nt":
            creation_flags = getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0
            )


        try:
            result = subprocess.run(
                command,
                cwd=self.base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                creationflags=creation_flags
            )

        except subprocess.TimeoutExpired:
            logging.error(
                "%s action timed out after "
                "%s seconds: %s",
                check_name,
                timeout,
                script
            )

            return

        except Exception:
            logging.exception(
                "%s action could not be executed: %s",
                check_name,
                script
            )

            return


        stdout = (
            result.stdout
            or ""
        ).strip()

        stderr = (
            result.stderr
            or ""
        ).strip()


        if result.returncode == 0:
            logging.info(
                "%s action completed successfully: %s",
                check_name,
                script
            )

        else:
            logging.error(
                "%s action failed with "
                "exit code %s: %s",
                check_name,
                result.returncode,
                script
            )


        #
        # Ausgabe begrenzen, damit ein Script
        # das Log nicht aufblasen kann.
        #
        if stdout:
            logging.info(
                "%s action stdout: %s",
                check_name,
                stdout[:2000]
            )

        if stderr:
            logging.warning(
                "%s action stderr: %s",
                check_name,
                stderr[:2000]
            )
