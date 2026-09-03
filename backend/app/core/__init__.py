"""Deterministic gates: the SQL validator, sanity flags, and the reference reader.

LLM-free and transport-free (ADR-0005). The agent reaches this only through
``agents/tools.py``; there is no path out of ``core/`` to a model or a socket.
"""
