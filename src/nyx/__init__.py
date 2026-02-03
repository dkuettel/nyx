from __future__ import annotations

import json
from collections.abc import Iterable
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
    inputs: None | dict[str, str | list[str]] = None


class Flake(msgspec.Struct, frozen=True):
    version: int
    nodes: dict[str, Node]
    root: str


def get_flat_inputs(flake: Flake) -> dict[str, str]:
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


# TODO hmm not sure if that format is as I thought
# it might be the follow path, but why is this useful in the lock?
# it has already been flattened anyway, or in a way, a single str is just [str]
# because ... ah wait, following from root vs entry? not clear, damn
# ok str is just flat, list is thru root it seems
# a lot of jumping
def qualified_uses(flake: Flake, name: str) -> list[str]:
    def get_inputs_using(name: str) -> Iterable[tuple[str, str, str]]:
        for name, node in flake.nodes.items():
            if node.inputs is not None:
                for input, targets in node.inputs.items():
                    match targets:
                        case str():
                            targets = [targets]
                        case _:
                            pass
                    for target in targets:
                        if target == name:
                            yield (name, input, target)

    uses = list(get_inputs_using(name))
    if len(uses) == 0:
        return [name]

    return [
        f"{prev}/{name}/{input}@{target}"
        for (name, input, target) in uses
        for prev in qualified_uses(flake, name)
    ]


def main():
    # path = Path("~/config/flake.lock").expanduser()
    path = Path("./flake.lock").expanduser()
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
            qus = {qu for name in names[alock] for qu in qualified_uses(flake, name)}
            print(f"    - {qus}")

    rich.print(get_flat_inputs(flake))
