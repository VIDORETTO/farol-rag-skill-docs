"""Distribution identity: current and legacy package names."""

from __future__ import annotations

DISTRIBUTION_NAMES = ("farol-kit", "consulta-documentacao")


def installed_version() -> str | None:
    """Version of the installed distribution under its current or legacy name."""

    from importlib.metadata import PackageNotFoundError, version

    for name in DISTRIBUTION_NAMES:
        try:
            return version(name)
        except PackageNotFoundError:
            continue
    return None
