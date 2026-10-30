"""Maps a method and path to an endpoint; a path ending in ``/`` passes the rest as a parameter."""

from typing import Callable, NamedTuple, Optional


class Route(NamedTuple):
    handler: Callable
    param: Optional[str]
    public: bool


class Router:
    def __init__(self) -> None:
        self._exact = {}
        self._prefixes = []

    def add(self, method: str, path: str, handler: Callable, public: bool = False) -> None:
        if path.endswith("/") and path != "/":
            self._prefixes.append((method, path, handler, public))
        else:
            self._exact[(method, path)] = (handler, public)

    def add_exact(self, method: str, path: str, handler: Callable,
                  public: bool = False) -> None:
        """A path that ends in ``/`` but must still match exactly (a page, not a parameter)."""
        self._exact[(method, path)] = (handler, public)

    def match(self, method: str, path: str) -> Optional[Route]:
        if (method, path) in self._exact:
            handler, public = self._exact[(method, path)]
            return Route(handler, None, public)
        for route_method, prefix, handler, public in self._prefixes:
            rest = path[len(prefix):]
            if route_method == method and path.startswith(prefix) and rest and "/" not in rest:
                return Route(handler, rest, public)
        return None
