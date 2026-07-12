from __future__ import annotations

from veriharness.core.types import HarnessVariant

VARIANT_DESCRIPTIONS = {
    HarnessVariant.SELF_ACCEPT: "Full raw trace. Leaf self-assessment controls done. Oracle is post-hoc.",
    HarnessVariant.H1: "Summarized trace. Leaf self-assessment controls done. Oracle is post-hoc.",
    HarnessVariant.H2: "State-lifted context. Leaf self-assessment controls done. Oracle is post-hoc.",
    HarnessVariant.GATED_RESAMPLE: "State-lifted context plus external gates and feedback-free resampling.",
    HarnessVariant.GENERIC_RETRY: "State-lifted context plus external gates plus generic retry.",
    HarnessVariant.GENERIC_DIAGNOSTICS: "Generic retry plus raw validation diagnostics.",
    HarnessVariant.NATURAL_RETRY: "State-lifted context plus gates plus natural-language gate-error retry.",
    HarnessVariant.SAME_INFO_NATURAL: "Location, expected, and observed values rendered as untyped natural language.",
    HarnessVariant.LOCATION_OBSERVED: "Typed failure label, location, and observed value without expected alternatives.",
    HarnessVariant.BEST_OF_N_GATED: "State-lifted context plus external gates over multiple independent candidates, without repair feedback.",
    HarnessVariant.LANGGRAPH_VALIDATOR_RETRY: "Generate-validate-retry graph baseline with natural-language validation feedback.",
    HarnessVariant.RETAIN_GENERIC: "State-lifted context plus gates plus candidate retention with generic retry.",
    HarnessVariant.TARGETED_UNTYPED: "State-lifted context plus gates plus targeted natural-language repair.",
    HarnessVariant.TYPED_LABEL_ONLY: "Typed repair exposing failure labels only.",
    HarnessVariant.TYPED_FIELDS: "Typed repair exposing failure labels plus location/expected/observed fields.",
    HarnessVariant.TYPED_NO_RETAIN: "State-lifted context plus gates plus typed repair without candidate retention.",
    HarnessVariant.TYPED_PRESERVE: "Full typed repair with preserve-set instructions.",
    HarnessVariant.TYPED_REPAIR_RETAIN: "VeriHarness typed repair with candidate retention and preserve-set instructions.",
}


def parse_variants(values: list[str]) -> list[HarnessVariant]:
    return [HarnessVariant(value) for value in values]
