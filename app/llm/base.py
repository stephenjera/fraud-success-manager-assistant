from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate_sql(self, question: str, schema: str) -> str:
        ...

    @abstractmethod
    def explain_insight(self, metrics: dict) -> str:
        ...

    @abstractmethod
    def generate_rule(self, insight: str) -> str:
        ...
