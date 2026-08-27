from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

from lagomy.tools.uk_evidence_search import UKEvidenceSearchTool


@CrewBase
class Lagomy():
    """Lagomy crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def intake_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['intake_agent'],  # type: ignore[index]
            verbose=True
        )

    @agent
    def evidence_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['evidence_agent'],  # type: ignore[index]
            tools=[UKEvidenceSearchTool()],
            max_iter=5,
            verbose=True
        )

    @agent
    def synthesis_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['synthesis_agent'],  # type: ignore[index]
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
