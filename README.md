# VW-Statusmonitor


Lightweight status monitoring dashboard for Windows Server.

## Features

- ICMP/Ping checks
- HTTP/HTTPS checks
- TCP port checks
- JSON API
- Web dashboard
- Configurable check interval
- Runs as a Windows service
- No database required

## Architecture

## Screenshot

## Requirements

## Installation

1. Installiere Python
   * https://www.python.org/downloads/windows/
   * globale Installation

2. Clone Repository
   * einfach downloaden und
   * in ein Verzeichnis der Wahl (bsp.: c:\vw-statusmonitor) entpacken

3. Virtuelle Python-Umgebung erstellen
   * Kommandozeile im Repository-Verzeichnis mit erhöhten Rechten öffnen
   * venv erstellen
     ```
     python -m venv .venv
     ```

4. Install dependencies
   * Powershell aktivieren, Befehl:
     ```
     powershell
     ```
   * Execution-Policy umgehen
     ```
     Set-ExecutionPolicy -Scope Process Bypass
     ```
   * Python Virtual Environment starten
     ```
     python -m venv .venv
     ```
   * Virtual Environment aktivieren
     ```
     .\.venv\Scripts\Activate.ps1
     ```
   * Abhängigkeiten nachinstallieren
     ```
     python -m pip install --upgrade pip
     pip install -r requirements.txt
     ```
   * Config aus Beispiel erstellen
     ```
     Copy-Item config.example.json config.json
     ```
   * Webserver als Konsolentest starten, ggf. Port in Firewall öffnen
     ```
     python app.py
     ```
5. Aufruf testen
   ```
   http://localhost:8080/
   ```
   oder
   ```
   http://localhost:8080/api/status
   ```

6. Config anpassen
   * in der config.json die notwendigen Korrekturen vornehmen
   * Webserver mit STRG+C stopnne und mit dem letzten Aufruf neu starten

7. Install Windows service

## Konfig-Beispiel
```
{
    "settings": {
        "check_interval": 30,
        "default_timeout": 3,
        "listen_address": "0.0.0.0",
        "listen_port": 8080
    },
    "checks": [
        {
            "name": "Localhost",
            "type": "ping",
            "target": "127.0.0.1"
        },
        {
            "name": "Google",
            "type": "tcp",
            "target": "8.8.8.8",
            "port": 53
        }
    ]
}
```

### Ping checks
### HTTP checks
### TCP checks

## API

### GET /api/status

## Windows Service
* Durch folgenden Befehl wird der Dienst "VW-Statusmonitor" erzeugt
  ```
  .\.venv\Scripts\python.exe .\service.py --startup auto install
  ```
* Dienst starten

## Updating

## Troubleshooting

## Security

## License
