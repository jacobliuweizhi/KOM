This folder contains the packaged Python runtime used by the KOM reviewer local demo.

The start, health-check, and auto-demo scripts call runtime\python\python.exe directly.
The package does not require the user's system Python, Microsoft Store Python alias,
FastAPI, uvicorn, or external package installation for offline demo-cache mode.

Default server path:
  app\start_server.py -> app\backend\fallback_server.py when FastAPI is unavailable.

Clinical-use notice:
  This package is for reviewer inspection and manuscript demonstration only.
