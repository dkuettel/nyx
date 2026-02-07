from __future__ import annotations

from pathlib import Path
from typing import Literal, override

import msgspec
import typer


class Original(msgspec.Struct, frozen=True, kw_only=True):
    type: Literal["github"]

    repo: str
    owner: str
    ref: str | None = None  # this is the branch, tag, or commit

    def as_ref(self) -> str:
        if self.ref is None:
            return f"github:{self.owner}/{self.repo}/*"
        else:
            return f"github:{self.owner}/{self.repo}/{self.ref}"


class Locked(msgspec.Struct, frozen=True, kw_only=True):
    narHash: str

    type: Literal["github"]

    owner: str
    repo: str
    rev: str

    @override
    def __eq__(self, other: object) -> bool:
        match other:
            case Locked():
                return self.narHash == other.narHash
            case _:
                return False

    @override
    def __hash__(self) -> int:
        return hash(self.narHash)

    def as_rev(self) -> str:
        return self.rev


class Node(msgspec.Struct, frozen=True, kw_only=True):
    original: Original | None = None
    locked: Locked | None = None
    inputs: None | dict[str, str | list[str]] = None


class Flake(msgspec.Struct, frozen=True, kw_only=True):
    version: Literal[7]
    root: str
    nodes: dict[str, Node]


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
        print(f"{original.as_ref()}")
        for lock, names in locks.items():
            print(f"    {lock.as_rev()}")
            for name in names:
                print(f"        {name}")


app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)


@app.command("invert")
def app_invert(path: Path = Path("./flake.lock")):
    flake = msgspec.json.decode(path.read_text(), type=Flake)
    forks = get_inverted_mapping(flake)
    print_forks(forks)


@app.command("lint")
def app_lint(path: Path = Path("./flake.lock")):
    flake = msgspec.json.decode(path.read_text(), type=Flake)
    forks = get_inverted_mapping(flake)
    forks = get_forks(forks)
    print_forks(forks)
