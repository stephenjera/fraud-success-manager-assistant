"""The service layer: run lifecycle and durable appstate.

Thin over ``core/`` (the gates) and the Postgres ``appstate`` schema. This is the
"API enforces core" edge (ADR-0005) — the model never sees a socket; it only got
here through the ``agents`` tools, and from here the state is durable.
"""
