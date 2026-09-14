"""Present so pytest puts `backend/` on `sys.path`.

Tests import the way the app does (`from core.platforms import Platform`),
which only resolves if the backend root is importable. pytest adds the
directory containing the root conftest.py, so this file existing is the
whole mechanism — there is nothing to configure here.
"""
