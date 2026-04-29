"""MongoDB migration framework for MongoRAG.

Lightweight, idempotent, versioned migration runner.
Each migration is a Python module exposing async ``up(db)`` and ``down(db)``.
Applied migrations are tracked in the ``_migrations`` collection.
"""
