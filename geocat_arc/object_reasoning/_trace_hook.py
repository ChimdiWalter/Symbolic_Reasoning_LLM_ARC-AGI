"""Observational candidate-trace hook for the delivery sprint.

Dependency-free and inert by default: with no observer installed every
emission is a single attribute load and a return, so the engine's search
result is identical with and without observation. The engine never imports
the sprint's tracing code; the adapter installs a sink here.

Outcome names are the existing TraceObserver vocabulary and are NOT
redefined. See records/ENGINE_EVENT_MAPPING.md for the transition each one
is emitted at.
"""

_SINK = None


def set_sink(sink) -> None:
    """Install a callable sink(ast, outcome), or None to uninstall."""
    global _SINK
    _SINK = sink


def get_sink():
    return _SINK


def emit(ast_builder, outcome: str) -> None:
    """Record one candidate transition.

    ``ast_builder`` is a zero-argument callable so that serializing a
    candidate costs nothing when no observer is installed.
    """
    sink = _SINK
    if sink is None:
        return
    try:
        sink(ast_builder(), outcome)
    except Exception:
        #  observation must never change the search result
        pass


# --------------------------------------------------------------------------
# candidate serialization: registry names and arguments only, no closures,
# no grids, no test data
# --------------------------------------------------------------------------

def program_ast(program):
    """A fitted, executable program as a canonical (op, args) tuple.

    ``op`` names the transformation vocabulary the program actually uses, so
    the frontier records which operators the reasoning reached for, not a
    single constant.
    """
    detail = program.to_dict()
    deltas = sorted({str(r.get("action", {}).get("delta_type"))
                     for r in detail.get("rules", [])})
    default = str(detail.get("default_action", {}).get("delta_type", ""))
    op = "prog:" + ("+".join(deltas) if deltas else "default:" + default)
    return (op, (detail,))


def group_ast(delta_type, n_members: int, selector_detail=None):
    """A typed candidate group before or after parameter fitting."""
    op = "group:" + str(getattr(delta_type, "value", delta_type))
    return (op, ({"n_members": int(n_members),
                  "selector": selector_detail},))
