"""Composio boundary: the sole module that knows Composio exists.

All vendor interaction goes through :func:`execute` (CLI subprocess, JSON
in/out, per-call timeout). Models, specialists and the tool registry only
ever see the fixed internal tools in ``core_agent.tools.composio_tools``.
"""
