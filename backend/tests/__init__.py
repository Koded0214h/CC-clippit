"""Clippit's backend test package.

Keeping this as an explicit package ensures imports such as
``tests.http_app`` resolve to this repository even when a dependency also
installs a top-level package named ``tests``.
"""
