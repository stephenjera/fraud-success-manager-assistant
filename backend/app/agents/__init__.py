"""The agent layer: the LangGraph loop, the two tools, the ADR-0006 output type.

LLM-reachable and transport-free. The only door back to data is the two tools
(``run_sql`` / ``profile_column``), and both call ``core/`` (ADR-0005). No
``core`` import appears in ``core/``; the ``agents -> core`` edge is the wall.
"""
