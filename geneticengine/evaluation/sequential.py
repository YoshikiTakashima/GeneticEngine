from typing import Any

from geneticengine.solutions.individual import Individual
from geneticengine.problems import Problem
from geneticengine.evaluation.api import Evaluator


class SequentialEvaluator(Evaluator):
    """Default evaluator for individuals, executes sequentially."""

    def evaluate(self, problem: Problem, indivs: list[Individual[Any, Any]]):
        for individual in indivs:
            self.eval_single(problem, individual)
