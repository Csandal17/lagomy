import os
from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

from lagomy.tools.uk_evidence_search import UKEvidenceSearchTool

nemotron = LLM(
    model="openai/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    base_url=os.environ["NEBIUS_BASE_URL"],
    api_key=os.environ["NEBIUS_API_KEY"],
)

@CrewBase
class Lagomy():
    """Lagomy crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def intake_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['intake_agent'],  # type: ignore[index]
            llm=nemotron,
            max_iter=5,
            verbose=True
        )

    @agent
    def evidence_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['evidence_agent'],  # type: ignore[index]
            llm=nemotron,
            tools=[UKEvidenceSearchTool()],
            max_iter=5,
            verbose=True
        )

    @agent
    def synthesis_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['synthesis_agent'],  # type: ignore[index]
            llm=nemotron,
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
