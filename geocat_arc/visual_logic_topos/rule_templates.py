"""Rule templates for ARC reasoning."""
from __future__ import annotations
from dataclasses import dataclass
from .proposition import Proposition


@dataclass
class RuleTemplate:
    name: str
    condition: Proposition
    action: str

    def matches(self, objects: list) -> list:
        return [obj for obj in objects if self.condition.evaluate(obj)]

    def __repr__(self):
        return f"Rule({self.name}: {self.condition} => {self.action})"


def match_rule(template: RuleTemplate, objects: list) -> list:
    return template.matches(objects)
