from __future__ import annotations

from geneticengine.algorithms.gp.individual import Individual
from geneticengine.algorithms.gp.structure import StoppingCriterium
from geneticengine.core.evaluators import Evaluator
from geneticengine.core.problems import Problem


class GenerationStoppingCriterium(StoppingCriterium):
    """Runs the evolution during a number of generations."""

    def __init__(self, max_generations: int):
        """Creates a limit for the evolution, based on the number of
        generations.

        Arguments:
            max_generations (int): Number of generations to execute
        """
        self.max_generations = max_generations

    def is_ended(
        self,
        problem: Problem,
        population: list[Individual],
        generation: int,
        elapsed_time: float,
        evaluator: Evaluator,
    ) -> bool:
        return generation >= self.max_generations


class TimeStoppingCriterium(StoppingCriterium):
    """Runs the evolution during a given amount of time.

    Note that termination is not pre-emptive. If fitnessfunction is
    flow, this might take more than the pre-specified time.
    """

    def __init__(self, max_time: int):
        """Creates a limit for the evolution, based on the execution time.

        Arguments:
            max_time (int): Maximum time in seconds to run the evolution
        """
        self.max_time = max_time

    def is_ended(
        self,
        problem: Problem,
        population: list[Individual],
        generation: int,
        elapsed_time: float,
        evaluator: Evaluator,
    ) -> bool:
        return elapsed_time >= self.max_time


class EvaluationLimitCriterium(StoppingCriterium):
    """Runs the evolution with a fixed budget for evaluations."""

    def __init__(self, max_evaluations: int):
        """Creates a limit for the evolution, based on the budget for
        evaluation.

        Arguments:
            max_evaluations (int): Maximum number of evaluations
        """
        self.max_evaluations = max_evaluations

    def is_ended(
        self,
        problem: Problem,
        population: list[Individual],
        generation: int,
        elapsed_time: float,
        evaluator: Evaluator,
    ) -> bool:
        return evaluator.get_count() >= self.max_evaluations
