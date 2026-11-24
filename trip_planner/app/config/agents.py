"""Settings of the LLM agents and simulated humans."""

import pydantic_settings

from trip_planner.app.config import base


class AgentsConfiguration(base.ConfigurationSection):
    """Agent settings, read from the `TRIP_AGENTS_` variables.

    Attributes:
        model_name: OpenAI model the two assistants run on.
        human_model_name: OpenAI model the simulated humans run on.
        temperature: Sampling temperature of every LLM call.
        seed: OpenAI sampling seed, for reproducible completions.
        recursion_limit: Maximum LangGraph steps of one agent turn.
        max_retries: Retries of one failed OpenAI request.
        request_timeout_s: Timeout of one OpenAI request, in seconds.
        input_cost_per_million: USD per million prompt tokens, for metrics.
        output_cost_per_million: USD per million completion tokens.
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='TRIP_AGENTS_'
    )

    model_name: str = 'gpt-4.1-mini'
    human_model_name: str = 'gpt-4.1-mini'
    # Zero temperature plus a fixed seed is what makes runs converge.
    temperature: float = 0.0
    seed: int = 42
    # One turn needs ~12 steps; the margin absorbs retries of failed tools.
    recursion_limit: int = 40
    max_retries: int = 3
    request_timeout_s: float = 60.0
    input_cost_per_million: float = 0.4
    output_cost_per_million: float = 1.6
