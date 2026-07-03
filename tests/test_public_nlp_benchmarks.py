from veriharness.benchmarks import public_nlp
from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.core.context_pack import build_context_pack
from veriharness.core.types import BudgetConfig, HarnessVariant, LeafOutput, LeafRequest, TaskSpec
from veriharness.leaves.prompts import render_leaf_prompt


def test_sciq_generator_builds_multiple_choice_task(monkeypatch):
    rows = [
        {
            "row_idx": 7,
            "row": {
                "question": "What gas do plants absorb?",
                "correct_answer": "carbon dioxide",
                "distractor1": "oxygen",
                "distractor2": "helium",
                "distractor3": "argon",
                "support": "Plants absorb carbon dioxide during photosynthesis.",
            },
        }
    ]
    monkeypatch.setattr(public_nlp, "load_hf_rows", lambda *args, **kwargs: rows)

    task = public_nlp.generate_sciq_tasks(n_tasks=1, seed=1)[0]

    assert task.family == "multiple_choice"
    assert task.metadata["benchmark"] == "sciq"
    assert task.hidden_oracle_payload["answer_text"] == "carbon dioxide"
    assert len(task.input_payload["choices"]) == 4


def test_glue_sst2_generator_builds_classification_task(monkeypatch):
    rows = [{"row_idx": 3, "row": {"sentence": "quietly excellent", "label": 1}}]
    monkeypatch.setattr(public_nlp, "load_hf_rows", lambda *args, **kwargs: rows)

    task = public_nlp.generate_glue_sst2_tasks(n_tasks=1, seed=1)[0]

    assert task.family == "text_classification"
    assert task.input_payload["labels"] == ["negative", "positive"]
    assert task.hidden_oracle_payload["label"] == "positive"


def test_multiple_choice_oracle_accepts_label():
    task = TaskSpec(
        task_id="mc-fake",
        family="multiple_choice",
        description="Fake multiple-choice task.",
        input_payload={
            "choices": [
                {"label": "A", "text": "first"},
                {"label": "B", "text": "second"},
            ]
        },
        hidden_oracle_payload={
            "oracle_type": "multiple_choice",
            "answer_label": "B",
            "answer_text": "second",
        },
    )
    output = LeafOutput(task_id=task.task_id, answer='{"answer":"B"}', artifacts=["answer.json"])

    assert evaluate_oracle(task, output).passed


def test_multiple_choice_oracle_accepts_answer_text():
    task = TaskSpec(
        task_id="mc-fake",
        family="multiple_choice",
        description="Fake multiple-choice task.",
        input_payload={
            "choices": [
                {"label": "A", "text": "carbon dioxide"},
                {"label": "B", "text": "oxygen"},
            ]
        },
        hidden_oracle_payload={
            "oracle_type": "multiple_choice",
            "answer_label": "A",
            "answer_text": "carbon dioxide",
        },
    )
    output = LeafOutput(
        task_id=task.task_id,
        answer='{"answer":"the carbon dioxide"}',
        artifacts=["answer.json"],
    )

    assert evaluate_oracle(task, output).passed


def test_text_classification_oracle_accepts_normalized_label():
    task = TaskSpec(
        task_id="rte-fake",
        family="text_classification",
        description="Fake RTE task.",
        input_payload={"labels": ["entailment", "not_entailment"]},
        hidden_oracle_payload={
            "oracle_type": "text_classification",
            "label": "not_entailment",
            "accepted_labels": ["entailment", "not_entailment"],
        },
    )
    output = LeafOutput(task_id=task.task_id, answer='{"label":"not entailment"}')

    assert evaluate_oracle(task, output).passed


def test_text_classification_oracle_accepts_alias():
    task = TaskSpec(
        task_id="trec-fake",
        family="text_classification",
        description="Fake TREC task.",
        input_payload={
            "labels": ["ABBR", "DESC", "ENTY", "HUM", "LOC", "NUM"],
            "label_descriptions": {"NUM": "numeric value"},
        },
        hidden_oracle_payload={
            "oracle_type": "text_classification",
            "label": "NUM",
            "accepted_labels": ["ABBR", "DESC", "ENTY", "HUM", "LOC", "NUM"],
            "accepted_aliases": {"NUM": ["number", "numeric value"]},
        },
    )
    output = LeafOutput(task_id=task.task_id, answer='{"label":"number"}')

    assert evaluate_oracle(task, output).passed


def test_veriharness_candidates_get_distinct_public_nlp_strategies():
    task = TaskSpec(
        task_id="trec-fake",
        family="text_classification",
        description="Fake TREC task.",
        input_payload={
            "text": "What city is the Eiffel Tower in?",
            "labels": ["ABBR", "DESC", "ENTY", "HUM", "LOC", "NUM"],
            "benchmark_name": "trec_qc",
        },
        hidden_oracle_payload={"oracle_type": "text_classification", "label": "LOC"},
    )
    pack = build_context_pack(task, HarnessVariant.H4, BudgetConfig(veriharness_k=2))

    prompt_a = render_leaf_prompt(LeafRequest(context_pack=pack, task=task, candidate_id="candidate-0"))
    prompt_b = render_leaf_prompt(LeafRequest(context_pack=pack, task=task, candidate_id="candidate-1"))

    assert "candidate strategy" in prompt_a
    assert prompt_a != prompt_b
