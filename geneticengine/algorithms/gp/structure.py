from __future__ import annotations

import abc

from geneticengine.solutions.individual import Individual
from geneticengine.problems import Problem
from geneticengine.random.sources import Source
from geneticengine.representations.api import Representation
from geneticengine.evaluation import Evaluator


class PopulationInitializer(abc.ABC):
    @abc.abstractmethod
    def initialize(
        self,
        problem: Problem,
        representation: Representation,
        random_source: Source,
        target_size: int,
    ) -> list[Individual]:
        ...


class GeneticStep(abc.ABC):
    @abc.abstractmethod
    def iterate(
        self,
        problem: Problem,
        evaluator: Evaluator,
        representation: Representation,
        random_source: Source,
        population: list[Individual],
        target_size: int,
        generation: int,
    ) -> list[Individual]:
        ...

    def __str__(self):
        return f"{self.__class__.__name__}"


class StoppingCriterium(abc.ABC):
    """TerminationCondition provides information when to terminate
    evolution."""

    @abc.abstractmethod
    def is_ended(
        self,
        problem: Problem,
        population: list[Individual],
        generation: int,
        elapsed_time: float,
        evaluator: Evaluator,
    ) -> bool:
        ...
