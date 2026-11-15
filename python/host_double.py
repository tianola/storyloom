"""A fake machine for the preflight tests, so the gate can be tested without this box.

`healthy_host` reads the shipped registry and answers every question it asks with yes. That is
deliberate: a double hand-written against today's capability list silently stops covering the day
somebody adds one, and the test that exists to catch a half-built machine starts passing for the
wrong reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.capabilities import capabilities, resolve_interpreter, resolve_path  # noqa: E402


def healthy_host(root: Path, *, missing_modules=(), missing_paths=(), short_paths=None,
                 missing_executables=(), blender=True) -> FakeHost:
    """A machine where everything the registry declares is installed and whole."""
    registry = capabilities(root)
    host = FakeHost()
    short_paths = short_paths or {}
    if blender:
        host.blender = Path("C:/fake/blender.exe")
        host.present.add(_key(host.blender))
    for capability in registry["capabilities"]:
        for check in capability["checks"]:
            kind = check["kind"]
            if kind == "module":
                python = resolve_interpreter(root, registry, check["interpreter"])
                if check["name"] not in missing_modules:
                    host.modules.add((python, check["name"]))
            elif kind == "path":
                key = _key(resolve_path(root, check["path"]))
                if check["path"] in missing_paths:
                    continue
                if check["path"] in short_paths:
                    host.sizes[key] = short_paths[check["path"]]
                else:
                    host.present.add(key)
            elif kind == "executable":
                for candidate in check["any_of"]:
                    if _basename(candidate) in missing_executables:
                        continue
                    (host.present if _is_path_like(candidate) else host.on_path).add(_key(candidate))
    return host


class FakeHost:
    """Answers the four things preflight can ask, and records what it asked."""

    def __init__(self, *, sizes=None, on_path=(), present=(), modules=(), blender=None):
        self.sizes = dict(sizes or {})
        self.on_path = {_key(name) for name in on_path}
        self.present = {_key(path) for path in present}
        self.modules = set(modules)
        self.blender = blender
        self.asked = []

    def size(self, path):
        key = _key(path)
        self.asked.append(("path", key))
        if key in self.sizes:
            return self.sizes[key]
        return 1_000_000_000_000 if key in self.present else None

    def which(self, name):
        self.asked.append(("executable", _key(name)))
        return f"C:/fake/{name}" if _key(name) in self.on_path else None

    def module(self, python, name):
        self.asked.append(("module", _key(python), name))
        return (_key(python), name) in self.modules

    def blender_executable(self, repo_root):
        self.asked.append(("blender", _key(repo_root)))
        return self.blender

    def asked_kinds(self):
        return {row[0] for row in self.asked}


def _key(value) -> str:
    return str(value).replace("\\", "/")


def _is_path_like(candidate: str) -> bool:
    return "/" in candidate or "\\" in candidate


def _basename(candidate: str) -> str:
    return _key(candidate).rsplit("/", 1)[-1]
