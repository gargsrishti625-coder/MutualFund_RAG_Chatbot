"""
api — Phase 5: API & Application Layer

Exposes the query pipeline as a REST API via FastAPI.

  Phase 5.1 — Schemas      : Pydantic request / response models (API contract)
  Phase 5.2 — Session Router: /sessions CRUD (create, list, get, rename, delete)
  Phase 5.3 — Chat Router  : POST /sessions/{id}/messages (main query endpoint)
  Phase 5.4 — Error Handler: KeyError → 404, ValueError → 422, Exception → 500

Entry point:
  uvicorn api.app:app --reload --port 8000

Interactive docs:
  http://localhost:8000/docs   (Swagger UI)
  http://localhost:8000/redoc  (ReDoc)
"""
