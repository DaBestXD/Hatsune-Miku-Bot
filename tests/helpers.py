from __future__ import annotations

from types import ModuleType
from unittest.mock import Mock


def module_proxy(module: ModuleType, **overrides: object) -> Mock:
    """Return a specced proxy without modifying the shared module object."""
    proxy = Mock(spec_set=module, wraps=module)
    for name, value in overrides.items():
        setattr(proxy, name, value)
    return proxy
