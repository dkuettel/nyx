from __future__ import annotations

import json
from pathlib import Path

import msgspec
import rich


class Original(msgspec.Struct, frozen=True, kw_only=True):
    owner: str
    rev: str | None = None
    repo: str
    type: str


class Locked(msgspec.Struct, frozen=True):
    narHash: str


class Node(msgspec.Struct, frozen=True, kw_only=True):
    original: Original | None = None
    locked: Locked | None = None


class Flake(msgspec.Struct, frozen=True):
    version: int
    nodes: dict[str, Node]


def main():
    path = Path("~/config/flake.lock").expanduser()
    flake = msgspec.json.decode(path.read_text(), type=Flake)
    assert flake.version == 7, flake.version
    # rich.print(locks)
    # rich.print(locks.keys())
    # rich.print(locks["nodes"].keys())
    # rich.print(flake)

    names: dict[Locked | None, set[str]] = dict()
    locks: dict[Original, set[Locked | None]] = dict()
    for name, node in flake.nodes.items():
        if node.original is not None:
            names.setdefault(node.locked, set()).add(name)
            locks.setdefault(node.original, set()).add(node.locked)
    # rich.print(names)
    # rich.print(nodes)

    ambi = {original: alocks for (original, alocks) in locks.items() if len(alocks) > 1}
    # rich.print(ambi)

    for original, alocks in ambi.items():
        print()
        print(f"{original}:")
        for alock in alocks:
            print(f"  - {alock}")
            print(f"    - {names[alock]}")
