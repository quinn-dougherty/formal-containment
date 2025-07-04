"""Formal containment protocol CLI."""

import subprocess
from containment.structures.cli_basic import AsyncTyper
from containment.structures import (
    Polarity,
    Specification,
    VerificationSuccess,
    VerificationFailure,
)
from containment.structures.enums.data import ModelName
from containment.structures.enums import ProofMethod
from containment.mcp.server import mcp
from containment.mcp.clients.experts.imp import ImpExpert
from containment.mcp.clients.experts.proof.loop import ProofExpert as LoopProofExpert
from containment.protocol import boundary
from containment.fsio.experiment import run_experiments
from containment.fsio.data import MODEL_DICT
from containment.fsio.logs import logs

sonnet = MODEL_DICT["snt4"]
haiku = MODEL_DICT["hku35"]


def mcp_server_run() -> None:
    mcp.run(transport="stdio")


def inspector() -> None:
    """
    Run the inspector with `npx`.
    """
    subprocess.run(
        ["npx", "@modelcontextprotocol/inspector", "uv", "run", "mcp-server"]
    )


def test() -> None:
    """
    Test runs.
    """
    cli = AsyncTyper()

    @cli.command()
    async def synthesize_and_prove(
        precondition: str,
        postcondition: str,
        model: ModelName = getattr(ModelName, "snt4"),
        max_iterations: int = 25,
    ) -> None:
        """
        Take a precondition and postcondition and ask the LLM to fill in the hoare triple and prove it.
        """
        spec = Specification(precondition=precondition, postcondition=postcondition)
        expert = await ImpExpert.connect_and_run(model.value, spec)
        if expert is None or expert.triple is None:
            raise ValueError("No program found. XML parse error probably.")
        prover_pos = await LoopProofExpert.connect_and_run(
            model,
            expert.triple,
            polarity=Polarity.POS,
            max_iterations=max_iterations,
        )
        msg = ""
        if isinstance(prover_pos.verification_result, VerificationSuccess):
            msg += "Exit code 0 for proof: "
        elif isinstance(prover_pos.verification_result, VerificationFailure):
            msg += "Exit code 1 for proof: "
        else:
            msg += "Unknown prover oracle result"
        if len(prover_pos.code_dt) > 0:
            msg += prover_pos.code_dt[-1]
        logs.info(msg)
        return None

    @cli.command()
    async def imp_complete(
        precondition: str,
        postcondition: str,
        model: ModelName = getattr(ModelName, "snt4"),
    ) -> None:
        """
        Take a precondition and postcondition and ask the LLM to fill in the hoare triple with an imp program
        """
        spec = Specification(precondition=precondition, postcondition=postcondition)

        expert = await ImpExpert.connect_and_run(model.value, spec)
        print(expert.triple)
        return None

    cli()


def contain() -> None:
    """
    Run the containment protocol.
    """
    cli = AsyncTyper()

    INCLUDE_MODELS = [getattr(ModelName, "snt4"), getattr(ModelName, "gpt41")]

    @cli.command()
    async def protocol(
        precondition: str,
        postcondition: str,
        metavariables: str = "",  # space-separated lean identifiers
        model: ModelName = getattr(ModelName, "snt4"),
        attempt_budget: int = 5,
        proof_method: ProofMethod = ProofMethod.LOOP,
        proof_loop_budget: int = 10,
        proof_search_max_steps: int = 100,
        proof_search_max_trials_per_goal: int = 10,
    ) -> None:
        """
        Run the containment protocol at the given precondition-postcondition pair.
        """
        model_id = MODEL_DICT[model.value].litellm_id
        specification = Specification(
            precondition=precondition,
            postcondition=postcondition,
            metavariables=metavariables,
        )
        msg = f"Running containment protocol at {model_id} for {specification}"
        logs.info(msg)
        result = await boundary(
            model_id,
            specification,
            proof_method=proof_method,
            proof_loop_budget=proof_loop_budget,
            attempt_budget=attempt_budget,
            proof_search_max_steps=proof_search_max_steps,
            proof_search_max_trials_per_goal=proof_search_max_trials_per_goal,
        )

        if isinstance(result, list):
            msg = f"({model_id}, {specification}): No code found that is provably safe to run in the world."
            logs.info(msg)
            logs.info(f"\tNum of failed attempts: {len(result)}")
            for i, failure in enumerate(result, 1):
                logs.info(f"\tAttempt {i} failed with error: {failure.error_message}")
        elif isinstance(result, VerificationSuccess):
            msg = f"({model_id}, {specification}): The following imp code is safe to execute in the world: <imp>{result.triple.command}</imp>"
            logs.info(msg)
            msg = f"\t The lean code of the proof for you to audit is located in {result.audit_trail}"
            logs.info(msg)
        return None

    @cli.command()
    async def experiments(
        proof_loop_budget: int = 50,
        attempt_budget: int = 10,
        models: list[ModelName] | None = None,
        sequential: bool = False,
    ) -> None:
        """
        Run the containment protocol experiments from `data.toml`
        """
        if models is None:
            model_ids = [name.value for name in INCLUDE_MODELS]
        else:
            model_ids = [name.value for name in models]
        results = await run_experiments(
            proof_loop_budget,
            attempt_budget,
            include_models=model_ids,
            sequential=sequential,
        )
        print(results)
        return None

    cli()
