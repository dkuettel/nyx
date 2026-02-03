from __future__ import annotations

from pathlib import Path

import msgspec


class Original(msgspec.Struct, frozen=True, kw_only=True):
    owner: str
    # TODO correct? and also, this could hide things that might be forks?
    ref: str | None = None
    repo: str
    type: str


class Locked(msgspec.Struct, frozen=True):
    narHash: str


class Node(msgspec.Struct, frozen=True, kw_only=True):
    original: Original | None = None
    locked: Locked | None = None
    inputs: None | dict[str, str | list[str]] = None


class Flake(msgspec.Struct, frozen=True):
    version: int
    nodes: dict[str, Node]
    root: str


def get_qualified_inputs(flake: Flake) -> dict[str, str]:
    """maps qualified names to the final flat input"""

    def follow(at: str, targets: list[str]) -> str:
        for target in targets:
            node = flake.nodes[at]
            assert node.inputs is not None
            match node.inputs[target]:
                case str(at):
                    pass
                case list(ats):
                    at = follow(flake.root, ats)
        return at

    def flatten(node: Node) -> dict[str, str]:
        if node.inputs is None:
            return dict()
        flat: dict[str, str] = dict()
        for name, targets in node.inputs.items():
            match targets:
                case str(target):
                    flat[name] = target
                case list():
                    flat[name] = follow(flake.root, targets)
            flat.update(
                {
                    f"{name}.{subname}": target
                    for (subname, target) in flatten(flake.nodes[name]).items()
                }
            )
        return flat

    return {
        f"root.{name}": target
        for (name, target) in flatten(flake.nodes[flake.root]).items()
    }


type Inverted = dict[Original, dict[Locked, set[str]]]


def get_inverted_mapping(flake: Flake) -> Inverted:
    """maps originals to differently locked qualified entries"""
    flat = get_qualified_inputs(flake)
    inverted: dict[Original, dict[Locked, set[str]]] = dict()
    for name, target in flat.items():
        # TODO can original really be None?
        original = flake.nodes[target].original
        assert original is not None
        locked = flake.nodes[target].locked
        assert locked is not None
        inverted.setdefault(original, dict()).setdefault(locked, set()).add(name)
    return inverted


def get_forks(inverted: Inverted) -> Inverted:
    return {original: locks for (original, locks) in inverted.items() if len(locks) > 1}


def print_forks(forks: Inverted):
    for original, locks in forks.items():
        print(f"{original}")
        for lock, names in locks.items():
            print(f"  {lock}")
            for name in names:
                print(f"    {name}")


def main():
    path = Path("~/config/flake.lock").expanduser()
    # path = Path("./flake.lock").expanduser()
    flake = msgspec.json.decode(path.read_text(), type=Flake)
    assert flake.version == 7, flake.version
    # rich.print(get_flat_inputs(flake))
    # rich.print(get_forks(flake))
    forks = get_inverted_mapping(flake)
    forks = get_forks(forks)
    print_forks(forks)
    # TODO filter out problems
