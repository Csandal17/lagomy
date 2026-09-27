import os
from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from lagomy.step_logging import log_step
from lagomy.tools.uk_evidence_search import UKEvidenceSearchTool

DEFAULT_MODEL = "openai/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
# Override for all agents with LAGOMY_MODEL, e.g. anthropic/claude-sonnet-4-6.
MODEL = os.environ.get("LAGOMY_MODEL", "").strip() or DEFAULT_MODEL


def make_llm(model: str) -> LLM:
    """openai/ models go to the Nebius OpenAI-compatible endpoint; anything else
    (e.g. anthropic/...) uses its provider's own endpoint and API key."""
    if model.startswith("openai/"):
        return LLM(
            model=model,
            base_url=os.environ["NEBIUS_BASE_URL"],
            api_key=os.environ["NEBIUS_API_KEY"],
            max_tokens=8000,
        )
    return LLM(model=model, max_tokens=8000)


llm = make_llm(MODEL)

@CrewBase
class Lagomy():
    """Lagomy crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def intake_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['intake_agent'],  # type: ignore[index]
            llm=llm,
            max_iter=5,
            verbose=True
        )

    @agent
    def evidence_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['evidence_agent'],  # type: ignore[index]
            llm=llm,
            tools=[UKEvidenceSearchTool()],
            max_iter=5,
            verbose=True
        )

    @agent
    def synthesis_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['synthesis_agent'],  # type: ignore[index]
            llm=llm,
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
