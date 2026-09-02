#!/usr/bin/env python3
"""Run counterfactual evaluations of individual catalog directives against Ollama.

The runner calls Ollama's native chat API without a coding harness. It caches a
shared baseline for every prompt and seed, queues treatment requests with bounded
concurrency, scores deterministic violations, and writes an ignored Markdown
report under .counterfactual-artifacts/.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import http.client
import json
import re
import sys
import threading
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import rule_template

REPO = Path(__file__).parent.parent
DEFAULT_CONFIG = REPO / "tests/counterfactual/config.toml"
DEFAULT_PROMPTS = REPO / "tests/counterfactual/prompts.toml"
ARTIFACTS_DIR = REPO / ".counterfactual-artifacts"
MODEL_ID = "qwen3.8:27b-iq4xs"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
FENCED_CODE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
MARKDOWN_HYPHEN_STRUCTURE_RE = re.compile(
    r"^[ \t]*(?:-{3,}|(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|)[ \t]*$",
    re.MULTILINE,
)
CLI_LONG_OPTION_RE = re.compile(r"(?<!\S)--[a-z][\w-]*(?:=[^\s]+)?", re.IGNORECASE)


@dataclass(frozen=True)
class ExperimentConfig:
    """Declare the fixed model, server, sampling controls, and queue size."""

    server: str
    model: str
    workers: int
    timeout_seconds: int
    temperature: float
    top_p: float
    num_ctx: int
    num_predict: int
    think: bool
    keep_alive: str
    system_prompt: str
    seeds: tuple[int, ...]


@dataclass(frozen=True)
class PromptSpec:
    """Describe one stable ecological or challenge prompt."""

    id: str
    category: str
    text: str


@dataclass(frozen=True)
class EvaluationCase:
    """Describe one source-derived directive, exemplar, or composed treatment."""

    id: str
    kind: str
    source: str
    section: str
    evaluator: str
    prompts: tuple[str, ...]
    source_item_ids: tuple[str, ...]
    treatment: str | None = None
    parent: str | None = None
    components: tuple[str, ...] = ()
    evidence: str | None = None


@dataclass(frozen=True)
class EvaluationBinding:
    """Assign deterministic scoring metadata to one canonical source item."""

    source_item_id: str
    evaluator: str
    prompts: tuple[str, ...]
    parent: str | None = None
    evidence: str | None = None


@dataclass(frozen=True)
class ServerMetadata:
    """Pin an experiment to the Ollama and model versions that generated it."""

    ollama_version: str
    model_digest: str


@dataclass(frozen=True)
class Job:
    """Represent one independently cacheable generation request."""

    arm: str
    prompt: PromptSpec
    seed: int
    instruction: str | None


@dataclass(frozen=True)
class Occurrence:
    """Locate one deterministic evaluator match in generated prose."""

    start: int
    end: int
    snippet: str


Evaluator = Callable[[str], list[Occurrence]]


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    """Return a mapping or raise a readable configuration error."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a TOML table")
    return value


def _require_string(value: Any, label: str) -> str:
    """Return a non-empty string or raise a readable configuration error."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _validate_id(value: str, label: str) -> str:
    """Reject identifiers that would create ambiguous or unsafe artifact paths."""
    if not ID_RE.fullmatch(value):
        raise ValueError(f"{label} '{value}' must match {ID_RE.pattern}")
    return value


def load_config(path: Path = DEFAULT_CONFIG) -> ExperimentConfig:
    """Load and validate the experiment configuration."""
    with path.open("rb") as handle:
        raw = _require_mapping(tomllib.load(handle), str(path))

    model = _require_string(raw.get("model"), "model")
    if model != MODEL_ID:
        raise ValueError(f"counterfactual evaluation is pinned to model '{MODEL_ID}'")

    seeds_raw = raw.get("seeds")
    if (
        not isinstance(seeds_raw, list)
        or not seeds_raw
        or not all(isinstance(seed, int) for seed in seeds_raw)
    ):
        raise ValueError("seeds must be a non-empty array of integers")

    config = ExperimentConfig(
        server=_require_string(raw.get("server"), "server").rstrip("/"),
        model=model,
        workers=int(raw.get("workers", 12)),
        timeout_seconds=int(raw.get("timeout_seconds", 900)),
        temperature=float(raw.get("temperature", 0.7)),
        top_p=float(raw.get("top_p", 0.9)),
        num_ctx=int(raw.get("num_ctx", 16384)),
        num_predict=int(raw.get("num_predict", 4096)),
        think=bool(raw.get("think", False)),
        keep_alive=_require_string(raw.get("keep_alive", "30m"), "keep_alive"),
        system_prompt=_require_string(raw.get("system_prompt"), "system_prompt"),
        seeds=tuple(seeds_raw),
    )
    if config.workers < 1 or config.timeout_seconds < 1:
        raise ValueError("workers and timeout_seconds must be positive")
    return config


def load_prompts(path: Path = DEFAULT_PROMPTS) -> dict[str, PromptSpec]:
    """Load the stable prompt suite keyed by semantic identifier."""
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    prompts: dict[str, PromptSpec] = {}
    for index, item in enumerate(raw.get("prompts", [])):
        data = _require_mapping(item, f"prompts[{index}]")
        prompt_id = _validate_id(_require_string(data.get("id"), "prompt id"), "prompt id")
        if prompt_id in prompts:
            raise ValueError(f"duplicate prompt id '{prompt_id}'")
        prompts[prompt_id] = PromptSpec(
            id=prompt_id,
            category=_require_string(data.get("category"), f"{prompt_id}.category"),
            text=_require_string(data.get("text"), f"{prompt_id}.text"),
        )
    if not prompts:
        raise ValueError("the prompt suite is empty")
    return prompts


def _canonical_source_items() -> dict[str, rule_template.SourceItem]:
    """Index every structurally derived canonical source item by identifier."""
    return {item.id: item for artifact in rule_template.load_inventory() for item in artifact.items}


def composite_id_for(parent_id: str, exemplar_id: str) -> str:
    """Derive one composite arm identifier entirely from its source components."""
    digest = hashlib.sha256(f"{parent_id}\n{exemplar_id}".encode()).hexdigest()[:8]
    return f"{parent_id}.with-exemplar-{digest}"


def load_cases() -> dict[str, EvaluationCase]:
    """Build screening cases from canonical source items and evaluator bindings."""
    source_items = _canonical_source_items()
    cases: dict[str, EvaluationCase] = {}
    for binding in SCREENING_BINDINGS:
        item = source_items.get(binding.source_item_id)
        if item is None:
            raise ValueError(f"stale evaluator binding '{binding.source_item_id}'")
        if item.kind not in {"directive", "anti-hallucination"} or item.treatment is None:
            raise ValueError(
                f"evaluator binding '{binding.source_item_id}' does not name a treatment"
            )
        if binding.source_item_id in cases:
            raise ValueError(f"duplicate evaluator binding '{binding.source_item_id}'")
        cases[binding.source_item_id] = EvaluationCase(
            id=binding.source_item_id,
            kind=item.kind,
            source=item.path,
            section=item.section,
            evaluator=binding.evaluator,
            prompts=binding.prompts,
            source_item_ids=(item.id,),
            treatment=item.treatment,
            parent=binding.parent,
            evidence=binding.evidence,
        )

    for binding in SCREENING_BINDINGS:
        if binding.parent is None:
            continue
        if binding.parent not in cases:
            raise ValueError(
                f"evaluator binding '{binding.source_item_id}' has unknown parent "
                f"'{binding.parent}'"
            )
        exemplar = cases[binding.source_item_id]
        parent = cases[binding.parent]
        composite_id = composite_id_for(parent.id, exemplar.id)
        cases[composite_id] = EvaluationCase(
            id=composite_id,
            kind="composite",
            source=exemplar.source,
            section=f"{parent.section}; {exemplar.section}",
            evaluator=binding.evaluator,
            prompts=binding.prompts,
            source_item_ids=(parent.id, exemplar.id),
            parent=parent.id,
            components=(parent.id, exemplar.id),
            evidence=binding.evidence,
        )
    if not cases:
        raise ValueError("the case inventory is empty")
    return cases


def validate_inventory(
    cases: dict[str, EvaluationCase], prompts: dict[str, PromptSpec]
) -> list[str]:
    """Return source identity and scoring metadata errors without network requests."""
    errors: list[str] = []
    source_items = _canonical_source_items()
    for case in cases.values():
        if case.evaluator not in EVALUATORS:
            errors.append(f"{case.id}: unknown evaluator '{case.evaluator}'")
        for prompt_id in case.prompts:
            if prompt_id not in prompts:
                errors.append(f"{case.id}: unknown prompt '{prompt_id}'")
        for source_item_id in case.source_item_ids:
            if source_item_id not in source_items:
                errors.append(f"{case.id}: unknown source item '{source_item_id}'")

        # Keep atomic and generated composite semantics explicit
        if case.kind in {"directive", "anti-hallucination"}:
            if case.source_item_ids != (case.id,):
                errors.append(f"{case.id}: atomic case must use its source-derived id")
            source_item = source_items.get(case.id)
            if source_item and case.treatment != source_item.treatment:
                errors.append(f"{case.id}: treatment differs from canonical source")
            if case.kind == "anti-hallucination" and not case.parent:
                errors.append(f"{case.id}: anti-hallucination case requires a parent")
        elif case.kind == "composite":
            if len(case.components) < 2 or case.treatment is not None:
                errors.append(f"{case.id}: composite requires components and no copied treatment")
        else:
            errors.append(f"{case.id}: unsupported kind '{case.kind}'")

        if case.parent and case.parent not in cases:
            errors.append(f"{case.id}: unknown parent '{case.parent}'")
        for component in case.components:
            if component not in cases:
                errors.append(f"{case.id}: unknown component '{component}'")
    return errors


def instruction_for_case(
    case_id: str, cases: dict[str, EvaluationCase], active: tuple[str, ...] = ()
) -> str:
    """Render the exact canonical system-message addition for one treatment case."""
    if case_id in active:
        cycle = " -> ".join((*active, case_id))
        raise ValueError(f"case component cycle: {cycle}")
    case = cases[case_id]
    if case.kind in {"directive", "anti-hallucination"}:
        return _require_string(case.treatment, f"{case.id}.treatment")
    if case.kind == "composite":
        return "\n\n".join(
            instruction_for_case(component, cases, (*active, case_id))
            for component in case.components
        )
    raise ValueError(f"unsupported case kind '{case.kind}'")


def _visible_prose(text: str) -> str:
    """Remove Markdown code and comment regions that prose directives exempt."""
    without_fences = FENCED_CODE_RE.sub(" ", text)
    without_inline_code = INLINE_CODE_RE.sub(" ", without_fences)
    return HTML_COMMENT_RE.sub(" ", without_inline_code)


def _matches(text: str, pattern: re.Pattern[str]) -> list[Occurrence]:
    """Convert regex matches into auditable spans and short snippets."""
    occurrences: list[Occurrence] = []
    for match in pattern.finditer(text):
        start, end = match.span()
        snippet = " ".join(text[max(0, start - 60) : min(len(text), end + 60)].split())
        occurrences.append(Occurrence(start=start, end=end, snippet=snippet))
    return occurrences


def evaluate_antithesis_pivot(text: str) -> list[Occurrence]:
    """Find high-precision grammatical variants of antithesis pivots."""
    prose = _visible_prose(text)
    subject = r"[a-z][\w’'-]*(?:[ \t]+[a-z][\w’'-]*){0,5}"
    contracted_subject = r"(?:it|this|that|he|she|there)[’']s"
    negative_copula = (
        rf"(?:{subject}[ \t]+(?:(?:is|was|are|were)[ \t]+not|"
        rf"(?:isn|wasn|aren|weren)[’']t)|{contracted_subject}[ \t]+not)"
    )
    positive_copula = rf"(?:{subject}[ \t]+(?:is|was|are|were)|{contracted_subject})"
    pattern = re.compile(
        rf"\b{negative_copula}\b[^.!?\n]{{1,140}}?[,;:]\s*"
        rf"(?:(?:but|rather|instead)\s*,?\s*)?{positive_copula}\b|"
        r"\b(?:not|(?:isn|wasn|aren|weren)[’']t)\s+(?:just|merely|only)\b"
        r"[^.!?\n]{1,140}?\bbut(?:\s+also)?\b|"
        r"\bnot\b[^.!?\n]{1,140}?[,;:]\s*(?:but\s+rather|rather|instead)\b",
        re.IGNORECASE,
    )
    return _matches(prose, pattern)


def evaluate_dash_interruption(text: str) -> list[Occurrence]:
    """Find prose dashes while excluding Markdown structure and CLI options."""
    prose = _visible_prose(text)
    without_structures = MARKDOWN_HYPHEN_STRUCTURE_RE.sub(
        lambda match: " " * len(match.group()), prose
    )
    without_options = CLI_LONG_OPTION_RE.sub(
        lambda match: " " * len(match.group()), without_structures
    )
    return _matches(without_options, re.compile(r"—|–|-{2,}"))


def evaluate_filler_opening(text: str) -> list[Occurrence]:
    """Find known filler phrases near the beginning of a response."""
    opening = _visible_prose(text).lstrip()[:400]
    pattern = re.compile(
        r"\b(?:"
        r"(?:sure|certainly|absolutely|of\s+course)[,!]?[ \t]+"
        r"(?:here(?:[’']s|[ \t]+is)\b)?|"
        r"here(?:[’']s|[ \t]+is)\b|"
        r"it(?:[’']s|[ \t]+is)[ \t]+(?:worth[ \t]+noting|important[ \t]+to[ \t]+note)"
        r"[ \t]+that|"
        r"it[ \t]+should[ \t]+be[ \t]+noted[ \t]+that|"
        r"before[ \t]+we[ \t]+(?:begin|start)\b|"
        r"let(?:[’']s|[ \t]+us)[ \t]+(?:begin|start)\b|"
        r"this[ \t]+(?:report|response|answer|essay)[ \t]+will\b|"
        r"in[ \t]+this[ \t]+(?:report|response|answer|essay),?[ \t]+(?:i|we)[ \t]+will\b|"
        r"in[ \t]+today(?:[’']s)[ \t]+world"
        r")",
        re.IGNORECASE,
    )
    return _matches(opening, pattern)


def evaluate_concluding_summary(text: str) -> list[Occurrence]:
    """Find unprompted summary markers near the end of a response."""
    prose = _visible_prose(text)
    offset = max(0, len(prose) - 800)
    pattern = re.compile(
        r"\b(?:ultimately|in[ \t]+conclusion|in[ \t]+summary|all[ \t]+in[ \t]+all|"
        r"to[ \t]+summarize|to[ \t]+sum[ \t]+up|to[ \t]+conclude|in[ \t]+closing|"
        r"by[ \t]+way[ \t]+of[ \t]+conclusion)\b",
        re.IGNORECASE,
    )
    found = _matches(prose[offset:], pattern)
    return [
        Occurrence(start=item.start + offset, end=item.end + offset, snippet=item.snippet)
        for item in found
    ]


def evaluate_banned_vocabulary(text: str) -> list[Occurrence]:
    """Find listed overused vocabulary and its regular inflections."""
    forms = (
        r"delv(?:e|es|ed|ing)",
        r"tapestr(?:y|ies)",
        r"beacons?",
        r"testaments?",
        r"symphon(?:y|ies)",
        r"pivotal(?:ly)?",
        r"landscapes?",
        r"realms?",
        r"navigat(?:e|es|ed|ing)",
        r"leverag(?:e|es|ed|ing)",
        r"seamless(?:ly)?",
    )
    pattern = re.compile(rf"\b(?:{'|'.join(forms)})\b", re.IGNORECASE)
    return _matches(_visible_prose(text), pattern)


EVALUATORS: dict[str, Evaluator] = {
    "antithesis-pivot": evaluate_antithesis_pivot,
    "dash-interruption": evaluate_dash_interruption,
    "filler-opening": evaluate_filler_opening,
    "concluding-summary": evaluate_concluding_summary,
    "banned-vocabulary": evaluate_banned_vocabulary,
}
ALL_PROMPT_IDS = (
    "history-fall-of-rome",
    "science-pregnane-x-receptor",
    "technical-llm-architecture",
    "creative-time-dilated-door",
)
ANTITHESIS_ID = "writing-conventions.rhetoric-and-structure.never-use-the-it-s-not-x-it-s-ea68a7b2"
ANTITHESIS_EXEMPLAR_ID = (
    "writing-conventions.anti-hallucination.it-s-not-a-hyperparameter-it-s-a-design-c2cbb66c"
)
SCREENING_BINDINGS = (
    EvaluationBinding(
        source_item_id=ANTITHESIS_ID,
        evaluator="antithesis-pivot",
        prompts=ALL_PROMPT_IDS,
    ),
    EvaluationBinding(
        source_item_id=(
            "writing-conventions.punctuation."
            "never-use-em-dashes-en-dashes-or-sequential-hyphens-6a4e9328"
        ),
        evaluator="dash-interruption",
        prompts=ALL_PROMPT_IDS,
    ),
    EvaluationBinding(
        source_item_id=(
            "writing-conventions.rhetoric-and-structure."
            "no-conversational-filler-or-throat-clearing-openers-sure-here-27c139c4"
        ),
        evaluator="filler-opening",
        prompts=ALL_PROMPT_IDS,
    ),
    EvaluationBinding(
        source_item_id=(
            "writing-conventions.rhetoric-and-structure."
            "no-unprompted-concluding-summary-ultimately-in-conclusion-in-summary-7345f2e1"
        ),
        evaluator="concluding-summary",
        prompts=ALL_PROMPT_IDS,
    ),
    EvaluationBinding(
        source_item_id=(
            "writing-conventions.banned-vocabulary."
            "avoid-the-overused-ai-register-delve-tapestry-beacon-testament-ffb2ab6f"
        ),
        evaluator="banned-vocabulary",
        prompts=ALL_PROMPT_IDS,
    ),
    EvaluationBinding(
        source_item_id=ANTITHESIS_EXEMPLAR_ID,
        evaluator="antithesis-pivot",
        prompts=ALL_PROMPT_IDS,
        parent=ANTITHESIS_ID,
        evidence="observed-failure",
    ),
)


def _request_json(
    server: str,
    path: str,
    timeout_seconds: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send one fixed-path request and parse a JSON object response."""
    parsed = urlsplit(server)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("server must be an http or https URL with a hostname")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("server URL must not contain credentials, query parameters, or fragments")

    connection_type = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port, timeout=timeout_seconds)
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    method = "POST" if payload is not None else "GET"
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
    finally:
        connection.close()
    if not 200 <= response.status < 300:
        detail = raw.decode(errors="replace")[:500]
        raise RuntimeError(f"Ollama {path} returned HTTP {response.status}: {detail}")
    decoded = json.loads(raw)
    if not isinstance(decoded, dict):
        raise RuntimeError(f"Ollama {path} returned a non-object JSON response")
    return decoded


def get_server_metadata(config: ExperimentConfig) -> ServerMetadata:
    """Read the Ollama version and require the pinned model digest."""
    version = _request_json(config.server, "/api/version", config.timeout_seconds)
    tags = _request_json(config.server, "/api/tags", config.timeout_seconds)
    models = tags.get("models")
    if not isinstance(models, list):
        raise RuntimeError("Ollama /api/tags response has no model list")
    for model in models:
        if isinstance(model, dict) and model.get("name") == config.model:
            return ServerMetadata(
                ollama_version=_require_string(version.get("version"), "Ollama version"),
                model_digest=_require_string(model.get("digest"), "model digest"),
            )
    raise RuntimeError(f"required model '{config.model}' is not installed on {config.server}")


def _generation_options(config: ExperimentConfig, seed: int) -> dict[str, Any]:
    """Build the sampling options shared by baseline and treatment arms."""
    return {
        "seed": seed,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "num_ctx": config.num_ctx,
        "num_predict": config.num_predict,
    }


def _request_payload(config: ExperimentConfig, job: Job) -> dict[str, Any]:
    """Build one native Ollama chat request with an optional atomic instruction."""
    system = config.system_prompt
    if job.instruction:
        system = f"{system}\n\nAdditional instruction:\n{job.instruction}"
    return {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": job.prompt.text},
        ],
        "stream": False,
        "think": config.think,
        "keep_alive": config.keep_alive,
        "options": _generation_options(config, job.seed),
    }


def _stable_hash(value: Any) -> str:
    """Hash JSON-serializable experiment state deterministically."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_id_for(
    config: ExperimentConfig,
    metadata: ServerMetadata,
    prompts: dict[str, PromptSpec],
    seeds: tuple[int, ...],
) -> str:
    """Build the cache identity shared by all directives in one baseline matrix."""
    generation_config = asdict(config)
    generation_config.pop("workers")
    generation_config.pop("timeout_seconds")
    generation_config["seeds"] = list(seeds)
    identity = {
        "config": generation_config,
        "metadata": asdict(metadata),
        "prompts": [asdict(prompts[key]) for key in sorted(prompts)],
    }
    return _stable_hash(identity)[:16]


def build_jobs(
    cases: dict[str, EvaluationCase],
    prompts: dict[str, PromptSpec],
    seeds: tuple[int, ...],
) -> list[Job]:
    """Create one shared baseline matrix and every selected treatment matrix."""
    jobs = [
        Job(arm="baseline", prompt=prompt, seed=seed, instruction=None)
        for prompt in prompts.values()
        for seed in seeds
    ]
    for case in cases.values():
        instruction = instruction_for_case(case.id, cases)
        jobs.extend(
            Job(arm=case.id, prompt=prompts[prompt_id], seed=seed, instruction=instruction)
            for prompt_id in case.prompts
            for seed in seeds
        )
    return jobs


def _artifact_paths(run_dir: Path, job: Job) -> tuple[Path, Path]:
    """Return the prose and metadata paths for one generation job."""
    base = run_dir / "responses" / job.arm / job.prompt.id / str(job.seed)
    return base.with_suffix(".txt"), base.with_suffix(".json")


def _is_cached(run_dir: Path, config: ExperimentConfig, job: Job) -> bool:
    """Accept a cached response only when its exact request hash matches."""
    text_path, metadata_path = _artifact_paths(run_dir, job)
    if not text_path.is_file() or not metadata_path.is_file():
        return False
    try:
        metadata = json.loads(metadata_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return metadata.get("request_hash") == _stable_hash(_request_payload(config, job))


def _atomic_write(path: Path, content: str) -> None:
    """Replace one artifact atomically so interrupted runs remain resumable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
    temporary.write_text(content)
    temporary.replace(path)


def _run_job(run_dir: Path, config: ExperimentConfig, job: Job) -> str:
    """Generate and persist one baseline or treatment response."""
    if _is_cached(run_dir, config, job):
        return "cached"

    payload = _request_payload(config, job)
    response = _request_json(
        config.server,
        "/api/chat",
        config.timeout_seconds,
        payload,
    )
    message = response.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise RuntimeError("Ollama /api/chat response has no assistant content")
    content = message["content"]
    text_path, metadata_path = _artifact_paths(run_dir, job)

    # Keep large prose separate from compact request and response metadata
    response_metadata = {key: value for key, value in response.items() if key != "message"}
    metadata = {
        "arm": job.arm,
        "prompt": job.prompt.id,
        "seed": job.seed,
        "request_hash": _stable_hash(payload),
        "request": payload,
        "response": response_metadata,
        "word_count": word_count(content),
    }
    _atomic_write(text_path, content)
    _atomic_write(metadata_path, json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return "generated"


def _write_manifest(
    run_dir: Path,
    config: ExperimentConfig,
    metadata: ServerMetadata,
    prompts: dict[str, PromptSpec],
    cases: dict[str, EvaluationCase],
    seeds: tuple[int, ...],
) -> None:
    """Record all inputs needed to interpret and reproduce an experiment."""
    manifest = {
        "repository_commit": _git_commit(),
        "config": {**asdict(config), "seeds": list(seeds)},
        "server": asdict(metadata),
        "prompts": [asdict(prompts[key]) for key in sorted(prompts)],
        "cases": [asdict(cases[key]) for key in sorted(cases)],
    }
    _atomic_write(run_dir / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _git_commit() -> str:
    """Return the current commit without importing repository tooling."""
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def run_experiment(
    config: ExperimentConfig,
    prompts: dict[str, PromptSpec],
    cases: dict[str, EvaluationCase],
    seeds: tuple[int, ...],
    workers: int,
) -> Path:
    """Queue all missing requests with the configured concurrency."""
    metadata = get_server_metadata(config)
    run_id = run_id_for(config, metadata, prompts, seeds)
    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_manifest(run_dir, config, metadata, prompts, cases, seeds)

    jobs = build_jobs(cases, prompts, seeds)
    missing = [job for job in jobs if not _is_cached(run_dir, config, job)]
    print(
        f"Run {run_id}: {len(jobs)} total requests, {len(missing)} missing, "
        f"{workers} concurrent queue workers"
    )
    if not missing:
        return run_dir

    generated = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_job = {executor.submit(_run_job, run_dir, config, job): job for job in missing}
        for future in concurrent.futures.as_completed(future_to_job):
            job = future_to_job[future]
            try:
                future.result()
            except Exception as error:
                raise RuntimeError(
                    f"generation failed for {job.arm}/{job.prompt.id}/{job.seed}: {error}"
                ) from error
            generated += 1
            print(f"  {generated}/{len(missing)}  {job.arm}/{job.prompt.id}/{job.seed}")
    return run_dir


def word_count(text: str) -> int:
    """Count prose words consistently across every arm."""
    return len(WORD_RE.findall(text))


def _read_response(run_dir: Path, arm: str, prompt_id: str, seed: int) -> str:
    """Read one cached response or raise a clear incomplete-run error."""
    path = run_dir / "responses" / arm / prompt_id / f"{seed}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"missing response: {path.relative_to(REPO)}")
    return path.read_text()


def _bootstrap_delta_interval(
    pairs: list[tuple[float, float]], samples: int = 5000
) -> tuple[float, float]:
    """Estimate a deterministic paired-bootstrap interval for treatment minus baseline."""
    if not pairs:
        return 0.0, 0.0

    # Counter-addressed hashes produce reproducible draws without a global random state
    deltas: list[float] = []
    for sample_index in range(samples):
        selected: list[tuple[float, float]] = []
        for draw_index in range(len(pairs)):
            address = f"20260831:{sample_index}:{draw_index}".encode()
            draw = int.from_bytes(hashlib.sha256(address).digest()[:8]) % len(pairs)
            selected.append(pairs[draw])
        delta = sum(treatment - baseline for baseline, treatment in selected) / len(selected)
        deltas.append(delta)
    deltas.sort()
    return deltas[int(samples * 0.025)], deltas[int(samples * 0.975)]


def _score_case(
    run_dir: Path,
    case: EvaluationCase,
    prompts: dict[str, PromptSpec],
    seeds: tuple[int, ...],
) -> dict[str, Any]:
    """Score one treatment against matched baseline responses."""
    evaluator = EVALUATORS[case.evaluator]
    baseline_occurrences = 0
    treatment_occurrences = 0
    baseline_words = 0
    treatment_words = 0
    baseline_documents = 0
    treatment_documents = 0
    pairs: list[tuple[float, float]] = []
    snippets: list[str] = []

    for prompt_id in case.prompts:
        if prompt_id not in prompts:
            continue
        for seed in seeds:
            baseline = _read_response(run_dir, "baseline", prompt_id, seed)
            treatment = _read_response(run_dir, case.id, prompt_id, seed)
            baseline_found = evaluator(baseline)
            treatment_found = evaluator(treatment)
            baseline_count = len(baseline_found)
            treatment_count = len(treatment_found)
            baseline_word_count = max(1, word_count(baseline))
            treatment_word_count = max(1, word_count(treatment))

            baseline_occurrences += baseline_count
            treatment_occurrences += treatment_count
            baseline_words += baseline_word_count
            treatment_words += treatment_word_count
            baseline_documents += int(bool(baseline_found))
            treatment_documents += int(bool(treatment_found))
            pairs.append(
                (
                    baseline_count * 1000 / baseline_word_count,
                    treatment_count * 1000 / treatment_word_count,
                )
            )
            if len(snippets) < 3:
                snippets.extend(item.snippet for item in treatment_found[: 3 - len(snippets)])

    baseline_rate = baseline_occurrences * 1000 / max(1, baseline_words)
    treatment_rate = treatment_occurrences * 1000 / max(1, treatment_words)
    reduction = (baseline_rate - treatment_rate) / baseline_rate if baseline_rate > 0 else None
    interval = _bootstrap_delta_interval(pairs)
    return {
        "id": case.id,
        "kind": case.kind,
        "parent": case.parent,
        "evidence": case.evidence,
        "documents": len(pairs),
        "baseline_occurrences": baseline_occurrences,
        "treatment_occurrences": treatment_occurrences,
        "baseline_rate_per_1000_words": baseline_rate,
        "treatment_rate_per_1000_words": treatment_rate,
        "relative_rate_reduction": reduction,
        "baseline_document_prevalence": baseline_documents / max(1, len(pairs)),
        "treatment_document_prevalence": treatment_documents / max(1, len(pairs)),
        "mean_baseline_words": baseline_words / max(1, len(pairs)),
        "mean_treatment_words": treatment_words / max(1, len(pairs)),
        "paired_rate_delta_ci95": interval,
        "treatment_snippets": snippets[:3],
    }


def _missing_case_responses(
    run_dir: Path, case: EvaluationCase, seeds: tuple[int, ...]
) -> list[str]:
    """List missing paired response keys that prevent scoring one case."""
    missing: list[str] = []
    for prompt_id in case.prompts:
        for seed in seeds:
            for arm in ("baseline", case.id):
                path = run_dir / "responses" / arm / prompt_id / f"{seed}.txt"
                if not path.is_file():
                    missing.append(f"{arm}/{prompt_id}/{seed}")
    return missing


def write_report(
    run_dir: Path,
    prompts: dict[str, PromptSpec],
    cases: dict[str, EvaluationCase],
    seeds: tuple[int, ...],
) -> Path:
    """Score complete cases and identify arms still pending in a partial run."""
    scores: list[dict[str, Any]] = []
    pending: dict[str, list[str]] = {}
    for case in cases.values():
        missing = _missing_case_responses(run_dir, case, seeds)
        if missing:
            pending[case.id] = missing
            continue
        scores.append(_score_case(run_dir, case, prompts, seeds))
    scores.sort(key=lambda item: item["id"])
    _atomic_write(run_dir / "scores.json", json.dumps(scores, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Counterfactual rule evaluation",
        "",
        f"Run: `{run_dir.name}`",
        "",
        "| Case | Kind | Baseline count | Treatment count | Baseline / 1k words | "
        "Treatment / 1k words | Relative reduction | 95% CI, rate delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for score in scores:
        reduction = score["relative_rate_reduction"]
        reduction_text = "undefined" if reduction is None else f"{reduction:.1%}"
        lower, upper = score["paired_rate_delta_ci95"]
        lines.append(
            f"| {score['id']} | {score['kind']} | {score['baseline_occurrences']} | "
            f"{score['treatment_occurrences']} | "
            f"{score['baseline_rate_per_1000_words']:.3f} | "
            f"{score['treatment_rate_per_1000_words']:.3f} | {reduction_text} | "
            f"[{lower:.3f}, {upper:.3f}] |"
        )

    if pending:
        lines.extend(["", "## Pending cases", ""])
        lines.extend(
            f"- `{case_id}`: {len(missing)} missing paired responses"
            for case_id, missing in sorted(pending.items())
        )
    lines.extend(
        [
            "",
            "Anti-hallucination rows are reported as exemplar treatments linked to their "
            "parent directive. An ecological null does not erase their observed-failure "
            "provenance.",
            "",
        ]
    )
    report_path = run_dir / "report.md"
    _atomic_write(report_path, "\n".join(lines))
    return report_path


def _selected_seeds(config: ExperimentConfig, count: int | None) -> tuple[int, ...]:
    """Select the first configured seeds for a screening or confirmation run."""
    if count is None:
        return config.seeds
    if count < 1 or count > len(config.seeds):
        raise ValueError(f"seed count must be between 1 and {len(config.seeds)}")
    return config.seeds[:count]


def _selected_cases(
    cases: dict[str, EvaluationCase], requested: list[str] | None
) -> dict[str, EvaluationCase]:
    """Select requested cases and any component arms needed to interpret them."""
    if not requested:
        return cases
    unknown = sorted(set(requested) - set(cases))
    if unknown:
        raise ValueError(f"unknown cases: {', '.join(unknown)}")

    # Composite results require their constituent arms for a meaningful comparison
    selected = set(requested)
    pending = list(requested)
    while pending:
        case = cases[pending.pop()]
        for component in case.components:
            if component not in selected:
                selected.add(component)
                pending.append(component)
    return {case_id: cases[case_id] for case_id in cases if case_id in selected}


def _latest_run() -> Path:
    """Return the most recently modified artifact directory with a run manifest."""
    runs = [
        path
        for path in ARTIFACTS_DIR.glob("*")
        if path.is_dir() and (path / "manifest.json").is_file()
    ]
    if not runs:
        raise FileNotFoundError("no counterfactual artifact runs found")
    return max(runs, key=lambda path: path.stat().st_mtime)


def _load_manifest_run(
    run_dir: Path,
) -> tuple[dict[str, PromptSpec], dict[str, EvaluationCase], tuple[int, ...]]:
    """Reconstruct report inputs from an immutable run manifest."""
    raw = json.loads((run_dir / "manifest.json").read_text())
    prompts = {item["id"]: PromptSpec(**item) for item in raw["prompts"]}
    cases = {
        item["id"]: EvaluationCase(
            **{
                **item,
                "prompts": tuple(item["prompts"]),
                "source_item_ids": tuple(item["source_item_ids"]),
                "components": tuple(item.get("components", [])),
            }
        )
        for item in raw["cases"]
    }
    return prompts, cases, tuple(raw["config"]["seeds"])


def main() -> None:
    """Validate, estimate, run, or report the counterfactual experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inventory", help="validate source mappings and case metadata")

    estimate_parser = subparsers.add_parser("estimate", help="show the uncached request count")
    estimate_parser.add_argument("--seeds", type=int, help="use the first N configured seeds")
    estimate_parser.add_argument("--case", action="append", help="limit to one case; repeatable")

    run_parser = subparsers.add_parser("run", help="queue baseline and treatment requests")
    run_parser.add_argument("--seeds", type=int, help="use the first N configured seeds")
    run_parser.add_argument("--case", action="append", help="limit to one case; repeatable")
    run_parser.add_argument("--workers", type=int, help="override queue concurrency")

    report_parser = subparsers.add_parser("report", help="score a completed artifact run")
    report_parser.add_argument("--run-id", help="artifact run id; defaults to latest")
    args = parser.parse_args()

    try:
        if args.command == "report":
            run_dir = ARTIFACTS_DIR / args.run_id if args.run_id else _latest_run()
            prompts, cases, seeds = _load_manifest_run(run_dir)
            report = write_report(run_dir, prompts, cases, seeds)
            print(f"Wrote {report.relative_to(REPO)}")
            return

        config = load_config()
        prompts = load_prompts()
        all_cases = load_cases()
        errors = validate_inventory(all_cases, prompts)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            raise SystemExit(1)
        if args.command == "inventory":
            print(f"OK: {len(all_cases)} cases, {len(prompts)} prompts, model {config.model}")
            return

        cases = _selected_cases(all_cases, args.case)
        seeds = _selected_seeds(config, args.seeds)
        if args.command == "estimate":
            jobs = build_jobs(cases, prompts, seeds)
            baseline = len(prompts) * len(seeds)
            print(
                f"{len(jobs)} requests: {baseline} shared baseline and "
                f"{len(jobs) - baseline} treatment"
            )
            print(f"Maximum requested output: {len(jobs) * config.num_predict:,} tokens")
            return

        workers = args.workers or config.workers
        if workers < 1:
            raise ValueError("workers must be positive")
        run_dir = run_experiment(config, prompts, cases, seeds, workers)
        report = write_report(run_dir, prompts, cases, seeds)
        print(f"Wrote {report.relative_to(REPO)}")
    except (FileNotFoundError, KeyError, OSError, RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
