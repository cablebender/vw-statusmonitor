import os
import sys
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

os.chdir(BASE_DIR)

if BASE_DIR not in sys.path:
    sys.path.insert(
        0,
        BASE_DIR
    )


class VWStatusMonitorService(
    win32serviceutil.ServiceFramework
):
    _svc_name_ = "VW-Statusmonitor"

    _svc_display_name_ = (
        "VW Statusmonitor"
    )

    _svc_description_ = (
        "VW Statusmonitor Webserver "
        "and system check service"
    )


    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(
            self,
            args
        )

        self.win32_stop_event = (
            win32event.CreateEvent(
                None,
                0,
                0,
                None
            )
        )

        self.stop_event = threading.Event()


    def SvcStop(self):
        self.ReportServiceStatus(
            win32service.SERVICE_STOP_PENDING
        )

        servicemanager.LogInfoMsg(
            "VW-Statusmonitor stop requested"
        )

        self.stop_event.set()

        win32event.SetEvent(
            self.win32_stop_event
        )


    def SvcDoRun(self):
        servicemanager.LogInfoMsg(
            "VW-Statusmonitor service starting"
        )

        try:
            self.run()

            servicemanager.LogInfoMsg(
                "VW-Statusmonitor service stopped"
            )

        except Exception as exc:
            servicemanager.LogErrorMsg(
                "VW-Statusmonitor service failed: "
                + str(exc)
            )

            raise


    def run(self):
        from app import run

        run(
            stop_event=self.stop_event
        )


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(
        VWStatusMonitorService
    )
