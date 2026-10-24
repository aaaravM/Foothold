"""Route modules. ``main.py`` imports every module here (pkgutil) and includes its
``router`` if present. Modules whose name starts with ``_`` are skipped. A module
that fails to import is logged and reported in ``GET /health`` as ``route_errors``
instead of crashing the app.

Convention: ``router = APIRouter(prefix="/api/<name>", tags=["<name>"])``.
"""
