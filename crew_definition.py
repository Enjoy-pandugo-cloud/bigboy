from crewai import Agent, Crew, Task
from logging_config import get_logger
from gmail_tool import Draft_tool

class ResearchCrew:
    def __init__(self, verbose=True, logger=None):
        self.verbose = verbose
        self.logger = logger or get_logger(__name__)
        self.crew = self.create_crew()
        self.logger.info("ResearchCrew initialized")

    def create_crew(self):
        self.logger.info("Creating crew with multiple agents")

        researcher = Agent(
            role='Researcher',
            goal='Extract key points and facts from input',
            backstory='Specialist in gathering and summarizing information',
            verbose=self.verbose
        )

        summarizer = Agent(
            role='Summarizer',
            goal='Produce concise summaries from research results',
            backstory='Skilled at creating short, actionable summaries',
            verbose=self.verbose
        )

        reply_generator = Agent(
            role='Reply Generator',
            goal='Compose email replies or drafts',
            backstory='Expert at crafting professional email replies',
            verbose=self.verbose
        )

        # Tasks are simple descriptors; crewai will use the specified agent
        tasks = [
            Task(
                description='Research: {text}',
                expected_output='Research findings',
                agent=researcher
            ),
            Task(
                description='Summarize research: {text}',
                expected_output='Concise summary',
                agent=summarizer
            ),
            Task(
                description='Create reply: {text}',
                expected_output='Gmail draft body and recipient',
                agent=reply_generator,
                tools=[Draft_tool()]
            )
        ]

        crew = Crew(
            agents=[researcher, summarizer, reply_generator],
            tasks=tasks
        )

        self.logger.info("Crew setup completed")
        return crew