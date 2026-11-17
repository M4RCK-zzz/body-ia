from enum import StrEnum

class DataKind(StrEnum):
    OBSERVED = "observed"
    VISUAL_ESTIMATE = "visual_estimate"
    APPROXIMATE_RECONSTRUCTION = "approximate_reconstruction"
    SIMULATION = "simulation"