"""Optional neural guidance modules for bounded neuro-symbolic experiments."""

from .dataset import GridPairRecord, arc_tasks_to_records, pad_grids, reasoning_tasks_to_records
from .grid_encoder import HandcraftedGridEncoder, TorchGridEncoder, build_grid_encoder, torch_available
from .grid_jepa import GridJEPA, GridMaskSampler, load_grid_jepa_checkpoint
from .program_ranker import HeuristicProgramRanker, ProgramRanker, RankedProgram

__all__ = [
    "GridPairRecord",
    "arc_tasks_to_records",
    "pad_grids",
    "reasoning_tasks_to_records",
    "HandcraftedGridEncoder",
    "TorchGridEncoder",
    "build_grid_encoder",
    "torch_available",
    "GridJEPA",
    "GridMaskSampler",
    "load_grid_jepa_checkpoint",
    "HeuristicProgramRanker",
    "ProgramRanker",
    "RankedProgram",
]
