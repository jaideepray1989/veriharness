from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, Field

_LEGACY_VERIHARNESS_K_ALIAS = "fire" + "pool_k"


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    accepted = "accepted"
    rejected = "rejected"
    failed = "failed"


class HarnessVariant(str, Enum):
    SELF_ACCEPT = "self-accept"
    H1 = "H1"
    H2 = "H2"
    GATED_RESAMPLE = "gated-resample"
    GENERIC_RETRY = "generic-retry"
    GENERIC_DIAGNOSTICS = "generic+diagnostics"
    NATURAL_RETRY = "natural-retry"
    SAME_INFO_NATURAL = "same-info-natural"
    LOCATION_OBSERVED = "location-observed"
    BEST_OF_N_GATED = "best-of-n-gated"
    LANGGRAPH_VALIDATOR_RETRY = "langgraph-validator-retry"
    RETAIN_GENERIC = "retain+generic"
    TARGETED_UNTYPED = "targeted+untyped"
    TYPED_LABEL_ONLY = "typed-label-only"
    TYPED_FIELDS = "typed-fields"
    TYPED_NO_RETAIN = "typed+no-retain"
    TYPED_PRESERVE = "typed-preserve"
    TYPED_REPAIR_RETAIN = "typed-repair+retain"

    # Deprecated member aliases keep imports from older scripts working. The
    # _missing_ hook below also accepts legacy string values in saved configs.
    H0 = "self-accept"
    H3 = "gated-resample"
    H4 = "typed-repair+retain"

    @classmethod
    def _missing_(cls, value: object) -> HarnessVariant | None:
        legacy = {
            "H0": cls.SELF_ACCEPT,
            "H3": cls.GATED_RESAMPLE,
            "H4": cls.TYPED_REPAIR_RETAIN,
        }
        return legacy.get(str(value))

    @property
    def uses_state_context(self) -> bool:
        return self in {
            HarnessVariant.H2,
            HarnessVariant.GATED_RESAMPLE,
            HarnessVariant.GENERIC_RETRY,
            HarnessVariant.GENERIC_DIAGNOSTICS,
            HarnessVariant.NATURAL_RETRY,
            HarnessVariant.SAME_INFO_NATURAL,
            HarnessVariant.LOCATION_OBSERVED,
            HarnessVariant.BEST_OF_N_GATED,
            HarnessVariant.LANGGRAPH_VALIDATOR_RETRY,
            HarnessVariant.RETAIN_GENERIC,
            HarnessVariant.TARGETED_UNTYPED,
            HarnessVariant.TYPED_LABEL_ONLY,
            HarnessVariant.TYPED_FIELDS,
            HarnessVariant.TYPED_NO_RETAIN,
            HarnessVariant.TYPED_PRESERVE,
            HarnessVariant.TYPED_REPAIR_RETAIN,
        }

    @property
    def uses_external_gates(self) -> bool:
        return self in {
            HarnessVariant.GATED_RESAMPLE,
            HarnessVariant.GENERIC_RETRY,
            HarnessVariant.GENERIC_DIAGNOSTICS,
            HarnessVariant.NATURAL_RETRY,
            HarnessVariant.SAME_INFO_NATURAL,
            HarnessVariant.LOCATION_OBSERVED,
            HarnessVariant.BEST_OF_N_GATED,
            HarnessVariant.LANGGRAPH_VALIDATOR_RETRY,
            HarnessVariant.RETAIN_GENERIC,
            HarnessVariant.TARGETED_UNTYPED,
            HarnessVariant.TYPED_LABEL_ONLY,
            HarnessVariant.TYPED_FIELDS,
            HarnessVariant.TYPED_NO_RETAIN,
            HarnessVariant.TYPED_PRESERVE,
            HarnessVariant.TYPED_REPAIR_RETAIN,
        }

    @property
    def uses_veriharness(self) -> bool:
        return self == HarnessVariant.TYPED_REPAIR_RETAIN

    @property
    def uses_candidate_retention(self) -> bool:
        return self in {HarnessVariant.RETAIN_GENERIC, HarnessVariant.TYPED_REPAIR_RETAIN}

    @property
    def uses_best_of_n_gated(self) -> bool:
        return self == HarnessVariant.BEST_OF_N_GATED

    @property
    def uses_generic_retry(self) -> bool:
        return self in {HarnessVariant.GENERIC_RETRY, HarnessVariant.RETAIN_GENERIC}

    @property
    def uses_diagnostic_retry(self) -> bool:
        return self == HarnessVariant.GENERIC_DIAGNOSTICS

    @property
    def uses_natural_retry(self) -> bool:
        return self == HarnessVariant.NATURAL_RETRY

    @property
    def uses_same_info_natural_repair(self) -> bool:
        return self == HarnessVariant.SAME_INFO_NATURAL

    @property
    def uses_location_observed_repair(self) -> bool:
        return self == HarnessVariant.LOCATION_OBSERVED

    @property
    def uses_langgraph_validator_retry(self) -> bool:
        return self == HarnessVariant.LANGGRAPH_VALIDATOR_RETRY

    @property
    def uses_targeted_untyped_repair(self) -> bool:
        return self == HarnessVariant.TARGETED_UNTYPED

    @property
    def uses_typed_label_only_repair(self) -> bool:
        return self == HarnessVariant.TYPED_LABEL_ONLY

    @property
    def uses_typed_field_repair(self) -> bool:
        return self == HarnessVariant.TYPED_FIELDS

    @property
    def uses_full_typed_preserve_repair(self) -> bool:
        return self in {HarnessVariant.TYPED_PRESERVE, HarnessVariant.TYPED_REPAIR_RETAIN}

    @property
    def uses_typed_repair(self) -> bool:
        return self in {
            HarnessVariant.TYPED_LABEL_ONLY,
            HarnessVariant.LOCATION_OBSERVED,
            HarnessVariant.TYPED_FIELDS,
            HarnessVariant.TYPED_NO_RETAIN,
            HarnessVariant.TYPED_PRESERVE,
            HarnessVariant.TYPED_REPAIR_RETAIN,
        }


def canonical_variant_name(value: object) -> str:
    """Return the current label for known variants and preserve unknown labels."""
    try:
        return HarnessVariant(str(value)).value
    except ValueError:
        return str(value)


class TaskInput(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


class TaskOracle(BaseModel):
    oracle_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class TaskSpec(BaseModel):
    task_id: str
    family: str
    description: str
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    hidden_oracle_payload: Dict[str, Any] = Field(default_factory=dict)
    acceptance_criteria: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextPack(BaseModel):
    task_id: str
    variant: str
    objective: str
    current_state: Dict[str, Any] = Field(default_factory=dict)
    accepted_facts: List[str] = Field(default_factory=list)
    rejected_facts: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    distractors: List[str] = Field(default_factory=list)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    budget: Dict[str, Any] = Field(default_factory=dict)


class EvidenceRef(BaseModel):
    source: str
    locator: str = ""
    quote: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Claim(BaseModel):
    claim: str
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    confidence: float = 0.5
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LeafRequest(BaseModel):
    context_pack: ContextPack
    task: TaskSpec
    attempt: int = 0
    candidate_id: str = "candidate-0"
    retry_feedback: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LeafOutput(BaseModel):
    task_id: str
    answer: str
    artifacts: List[str] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    self_assessment: Dict[str, Any] = Field(default_factory=dict)
    done: bool = False


class GateFailure(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class GateResult(BaseModel):
    gate_name: str
    passed: bool
    score: float = 0.0
    failures: List[GateFailure] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RunMetadata(BaseModel):
    experiment_id: str
    run_id: str
    task_id: Optional[str] = None
    variant: Optional[str] = None
    model_client: str = "dummy"
    model_name: Optional[str] = None
    status: RunStatus = RunStatus.pending
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BudgetConfig(BaseModel):
    max_retries: int = 2
    veriharness_k: int = Field(
        default=3,
        validation_alias=AliasChoices("veriharness_k", _LEGACY_VERIHARNESS_K_ALIAS),
    )
    max_leaf_calls_per_task: int = 8
    max_tokens_per_task: int = 8000
    max_wall_time_seconds: int = 300


class ModelConfig(BaseModel):
    client: str = "dummy"
    model_name: Optional[str] = None
    endpoint: Optional[str] = None
    provider: Optional[str] = None
    parameter_count: Optional[int] = None
    active_parameter_count: Optional[int] = None
    parameter_count_label: Optional[str] = None
    max_output_tokens: int = 768
    temperature: float = 0.0
    top_p: Optional[float] = None
    sampling_seed: Optional[int] = None
    timeout_seconds: int = 120


class EvaluationConfig(BaseModel):
    oracle_guided_acceptance: bool = True
    result_role: str = "primary"


class BenchmarkConfig(BaseModel):
    name: str
    n_tasks: int = 10
    trace_lengths: List[int] = Field(default_factory=lambda: [4, 8])
    seeds: List[int] = Field(default_factory=lambda: [1])


class ExperimentConfig(BaseModel):
    experiment_id: str
    benchmarks: List[BenchmarkConfig] = Field(default_factory=list)
    variants: List[HarnessVariant] = Field(
        default_factory=lambda: [
            HarnessVariant.SELF_ACCEPT,
            HarnessVariant.H1,
            HarnessVariant.H2,
            HarnessVariant.GATED_RESAMPLE,
            HarnessVariant.TYPED_REPAIR_RETAIN,
        ]
    )
    model: ModelConfig = Field(default_factory=ModelConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    backend: str = "local"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperimentResult(BaseModel):
    experiment_id: str
    task_id: str
    benchmark: str
    variant: str
    model_client: str = ""
    model_name: Optional[str] = None
    model_provider: Optional[str] = None
    model_parameter_count: Optional[int] = None
    model_active_parameter_count: Optional[int] = None
    model_parameter_count_label: Optional[str] = None
    seed: int = 0
    trace_length: Optional[int] = None
    constraint_position: Optional[str] = None
    noise_type: Optional[str] = None
    provenance_label: Optional[str] = None
    success: bool = False
    accepted_by_agent: bool = False
    accepted_by_gate: bool = False
    premature_stop: bool = False
    wrong_claim_accepted: bool = False
    constraint_violation: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    num_leaf_calls: int = 0
    num_retries: int = 0
    wall_time_sec: float = 0.0
    failure_reasons: List[str] = Field(default_factory=list)
    run_path: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
