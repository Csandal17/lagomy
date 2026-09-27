import os
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

from lagomy.tools.uk_evidence_search import UKEvidenceSearchTool

# Override the model for all agents with LAGOMY_MODEL, e.g. anthropic/claude-opus-5-5.
# Unset, each agent uses the llm in config/agents.yaml.
MODEL_OVERRIDE = os.environ.get("LAGOMY_MODEL", "").strip() or None


def _config_models() -> str:
    with open(Path(__file__).parent / "config" / "agents.yaml") as f:
        config = yaml.safe_load(f)
    return ",".join(sorted({a["llm"] for a in config.values() if a.get("llm")}))


# The model the crew runs on, as recorded by the eval scripts.
MODEL = MODEL_OVERRIDE or _config_models()
_llm = {"llm": MODEL_OVERRIDE} if MODEL_OVERRIDE else {}


@CrewBase
class Lagomy():
    """Lagomy crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def intake_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['intake_agent'],  # type: ignore[index]
            **_llm,
            max_iter=5,
            verbose=True
        )

    @agent
    def evidence_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['evidence_agent'],  # type: ignore[index]
            **_llm,
            tools=[UKEvidenceSearchTool()],
            max_iter=5,
            verbose=True
        )

    @agent
    def synthesis_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['synthesis_agent'],  # type: ignore[index]
            **_llm,
            max_iter=5,
            verbose=True
        )
    
    @task
    def evidence_task(self) -> Task:
        return Task(
            config=self.tasks_config['evidence_task'],  # type: ignore[index]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Lagomy crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
    
    @task
    def synthesis_task(self) -> Task:
        return Task(
            config=self.tasks_config['synthesis_task'],  # type: ignore[index]
        )
