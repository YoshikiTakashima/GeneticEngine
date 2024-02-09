import copy
from geneticengine.algorithms.hill_climbing import HC
from geneticengine.algorithms.one_plus_one import OnePlusOne
from geneticengine.algorithms.random_search import RandomSearch
from geneticengine.evaluation.budget import EvaluationBudget
from geneticengine.problems import SingleObjectiveProblem
from geneticengine.random.sources import RandomSource
from geneticengine.representations.api import RepresentationWithMutation, SolutionRepresentation

MAX_NUMBER = 200
MAX_ELEMENTS = 10


class LinearRepresentation(SolutionRepresentation[list[int], int], RepresentationWithMutation[list[int]]):
    def instantiate(self, random: RandomSource, **kwargs) -> list[int]:
        return [random.randint(0, MAX_NUMBER) for _ in range(MAX_ELEMENTS)]

    def map(self, internal: list[int]) -> int:
        return sum(internal)

    def mutate(self, random: RandomSource, internal: list[int]) -> list[int]:
        nc = copy.deepcopy(internal)
        ind = random.randint(0, len(nc) - 1)
        nc[ind] = random.randint(0, MAX_NUMBER)
        return nc


class TestBasicRepresentation:
    def test_random_search(self):
        p = SingleObjectiveProblem(fitness_function=lambda x: abs(2024 - x), minimize=True)
        rs = RandomSearch(problem=p, budget=EvaluationBudget(100), representation=LinearRepresentation())
        v = rs.search()
        assert isinstance(v.get_phenotype(), int)
        assert 0 <= v.get_phenotype() <= MAX_NUMBER * MAX_ELEMENTS

    def test_one_plus_one(self):
        p = SingleObjectiveProblem(fitness_function=lambda x: abs(2024 - x), minimize=True)
        rs = OnePlusOne(problem=p, budget=EvaluationBudget(100), representation=LinearRepresentation())
        v = rs.search()
        assert isinstance(v.get_phenotype(), int)
        assert 0 <= v.get_phenotype() <= MAX_NUMBER * MAX_ELEMENTS

    def test_hill_climbing(self):
        p = SingleObjectiveProblem(fitness_function=lambda x: abs(2024 - x), minimize=True)
        rs = HC(problem=p, budget=EvaluationBudget(100), representation=LinearRepresentation())
        v = rs.search()
        assert isinstance(v.get_phenotype(), int)
        assert 0 <= v.get_phenotype() <= MAX_NUMBER * MAX_ELEMENTS
