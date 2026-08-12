"""Persistent memory store for solved/failed task atoms."""
from __future__ import annotations
import json
from pathlib import Path
from .memory_atom import MemoryAtom


class MemoryStore:
    def __init__(self):
        self._atoms: dict[str, MemoryAtom] = {}

    def add(self, atom: MemoryAtom) -> None:
        self._atoms[atom.task_id] = atom

    def get(self, task_id: str) -> MemoryAtom | None:
        return self._atoms.get(task_id)

    def all_atoms(self) -> list[MemoryAtom]:
        return list(self._atoms.values())

    def solved_atoms(self) -> list[MemoryAtom]:
        return [a for a in self._atoms.values() if a.status == "solved"]

    def failed_atoms(self) -> list[MemoryAtom]:
        return [a for a in self._atoms.values() if a.status in ("failed", "near_solved")]

    def __len__(self) -> int:
        return len(self._atoms)

    def save(self, path: str | Path) -> None:
        data = [atom.to_dict() for atom in self._atoms.values()]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str | Path) -> None:
        with open(path) as f:
            data = json.load(f)
        for d in data:
            atom = MemoryAtom.from_dict(d)
            self._atoms[atom.task_id] = atom
