# VW-Statusmonitor


Lightweight status monitoring dashboard for Windows Server.
<img width="691" height="1006" alt="image" src="https://github.com/user-attachments/assets/c7dedae8-a69c-4448-a6c8-251c56d30c59" />



## Features

- ICMP/Ping checks
- HTTP/HTTPS checks
- TCP port checks
- JSON API
- Web dashboard
- History 24h, Topology
- Logs
- Configurable check interval
- Runs as a Windows service
- No database required

## Requirements
* Windows
* Powershell
* Admin-Rechte (zur Installation)
* Python

## Installation

1. Installiere Python
   * https://www.python.org/downloads/windows/
     * globale Installation (for all users / "C:\Program Files\Python3" for example)
     * pip
     * add python for environment

2. Clone Repository
   * einfach downloaden und
   * in ein Verzeichnis der Wahl (bsp.: d:\vw-statusmonitor) entpacken

3. Virtuelle Python-Umgebung erstellen
   * Kommandozeile im Verzeichnis (bsp.: d:\vw-statusmonitor) mit erhöhten Rechten öffnen
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
        "listen_port": 8080,

        "logging": {
            "level": "INFO",
            "max_size_mb": 5,
            "backup_count": 5
        },

        "history": {
            "enabled": true,
            "retention_days": 30,
            "default_display_hours": 24
        }
    },

    "checks": [
        {
            "name": "Gateway",
            "description": "Default Gateway",
            "type": "ping",
            "target": "10.0.0.1"
        },

        {
            "name": "Webserver",
            "description": "Interner Webserver",
            "type": "http",
            "target": "https://10.0.0.20/",
            "expected_status": 200,
            "verify_tls": false
        },

        {
            "name": "Webserver Zugriffsschutz",
            "description": "HTTP 403 wird erwartet",
            "type": "http",
            "target": "https://10.0.0.30/",
            "expected_status": 403,
            "verify_tls": false
        },

        {
            "name": "LDAP",
            "description": "Domain Controller LDAP",
            "type": "tcp",
            "target": "10.0.0.10",
            "port": 389
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
* Dienst stoppen
* neue Dateien aus dem Repo ins Verzeichnis laden, vorhandene Dateien überschreiben
* Config ggf. anpassen
* Dienst starten

## Troubleshooting

## Security

## License
