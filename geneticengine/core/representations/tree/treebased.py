import sys
from copy import deepcopy

from typing import (
    Any,
    Dict,
    Type,
    TypeVar,
    Tuple,
    List,
)

from geneticengine.core.decorators import get_gengy
from geneticengine.core.random.sources import Source
from geneticengine.core.grammar import Grammar
from geneticengine.core.representations.api import Representation
from geneticengine.core.representations.tree.utils import relabel_nodes_of_trees
from geneticengine.core.representations.tree.wrapper import Wrapper, WrapperType
from geneticengine.core.representations.tree.position_independent_grow import (
    create_position_independent_grow,
)

from geneticengine.core.tree import TreeNode
from geneticengine.core.utils import (
    get_arguments,
    is_generic_list,
    get_generic_parameter,
)
from geneticengine.exceptions import GeneticEngineError
from geneticengine.metahandlers.base import MetaHandlerGenerator, is_metahandler


def random_int(r: Source) -> int:
    return r.randint(-(sys.maxsize - 1), sys.maxsize)


def random_float(r: Source) -> float:
    return r.random_float(-100, 100)


T = TypeVar("T")


def random_list(
    r: Source,
    g: Grammar,
    rec: WrapperType,
    depth: int,
    ty: Type[List[T]],
):
    inner_type = get_generic_parameter(ty)
    size = r.randint(0, depth - 1)
    return [rec(depth - 1, inner_type) for _ in range(size)]


def apply_metahandler(
    r: Source,
    g: Grammar,
    rec: WrapperType,
    depth: int,
    ty: Type[Any],
    argn: str,
    context: Dict[str, Type],
) -> Any:
    """
    This method applies a metahandler to use a custom generator for things of a given type.

    As an example, AnnotatedType[int, IntRange(3,10)] will use the IntRange.generate(r, recursive_generator)

    The generator is the annotation on the type ("__metadata__").
    """
    metahandler: MetaHandlerGenerator = ty.__metadata__[0]
    base_type = get_generic_parameter(ty)
    if is_generic_list(base_type):
        base_type = get_generic_parameter(base_type)
    return metahandler.generate(r, g, rec, depth, base_type, argn, context)


def filter_choices(g: Grammar, possible_choices: List[type], depth):
    valid_productions = [
        vp for vp in possible_choices if g.distanceToTerminal[vp] <= depth
    ]
    if any(  # Are we the last recursive symbol?
        [
            prod in g.recursive_prods for prod in valid_productions
        ]  # Are there any  recursive symbols in our expansion?
    ):
        valid_productions = [
            vp for vp in valid_productions if vp in g.recursive_prods
        ]  # If so, then only expand into recursive symbols

    return valid_productions


def expand_node(
    r: Source,
    g: Grammar,
    depth: int,
    starting_symbol: Any,
    argname: str = "",
    context: Dict[str, Type] = None,
) -> Any:
    """
    Creates a random node of a given type (starting_symbol)
    """

    if context is None:
        context = {}

    if depth < 0:
        raise GeneticEngineError("Recursion Depth reached")
    if depth < g.get_distance_to_terminal(starting_symbol):
        raise GeneticEngineError(
            "There will be no depth sufficient for symbol {} in this grammar (provided: {}, required: {}).".format(
                starting_symbol, depth, g.get_distance_to_terminal(starting_symbol)
            )
        )

    if starting_symbol is int:
        return random_int(r)
    elif starting_symbol is float:
        return random_float(r)
    elif is_generic_list(starting_symbol):
        return random_list(r, g, Wrapper, depth, starting_symbol)
    elif is_metahandler(starting_symbol):
        return apply_metahandler(
            r, g, Wrapper, depth, starting_symbol, argname, context
        )
    else:
        if starting_symbol not in g.all_nodes:
            raise GeneticEngineError(f"Symbol {starting_symbol} not in grammar rules.")

        if starting_symbol in g.alternatives:  # Alternatives
            compatible_productions = g.alternatives[starting_symbol]
            valid_productions = filter_choices(g, compatible_productions, depth)
            if not valid_productions:
                raise GeneticEngineError(
                    "No productions for non-terminal node with type: {} in depth {} (minimum required: {}).".format(
                        starting_symbol,
                        depth,
                        str(
                            [
                                (vp, g.distanceToTerminal[vp])
                                for vp in compatible_productions
                            ]
                        ),
                    )
                )
            if any(["weight" in get_gengy(p) for p in valid_productions]):
                weights = [get_gengy(p).get("weight", 1.0) for p in valid_productions]
                rule = r.choice_weighted(valid_productions, weights)
            else:
                rule = r.choice(valid_productions)
            return expand_node(r, g, depth, rule)
        else:  # Normal production
            args = get_arguments(starting_symbol)
            obj = starting_symbol(*[None for _ in args])
            context = {argn: argt for (argn, argt) in args}
            for (argn, argt) in args:
                w = Wrapper(depth - 1, argt)
                setattr(obj, argn, w)
            return obj


def random_node(
    r: Source,
    g: Grammar,
    depth: int,
    starting_symbol: Type[Any] = int,
):
    k = create_position_independent_grow(expand_node)
    root = k(r, g, depth, starting_symbol)
    relabel_nodes_of_trees(root, g.non_terminals)
    return root


def random_individual(r: Source, g: Grammar, max_depth: int = 5) -> TreeNode:
    try:
        assert max_depth >= g.get_min_tree_depth()
    except:
        if g.get_min_tree_depth() == 1000000:
            raise GeneticEngineError(
                f"Grammar's minimal tree depth is {g.get_min_tree_depth()}, which is the default tree depth. It's highly like that there are nodes of your grammar than cannot reach any terminal."
            )
        raise GeneticEngineError(
            f"Cannot use complete grammar for individual creation. Max depth ({max_depth}) is smaller than grammar's minimal tree depth ({g.get_min_tree_depth()})."
        )
    ind = random_node(r, g, max_depth, g.starting_symbol)
    assert isinstance(ind, TreeNode)
    return ind


def mutate_inner(r: Source, g: Grammar, i: TreeNode, max_depth: int) -> TreeNode:
    if i.nodes > 0:
        c = r.randint(0, i.nodes - 1)
        if c == 0:
            ty = i.__class__.__bases__[0]
            try:
                replacement = random_node(r, g, max_depth - i.depth + 1, ty)
                return replacement
            except:
                return i
        else:
            for field in i.__annotations__:
                child = getattr(i, field)
                if hasattr(child, "nodes"):
                    count = child.nodes
                    if c <= count:
                        setattr(i, field, mutate_inner(r, g, child, max_depth))
                        return i
                    else:
                        c -= count
            return i
    else:
        return i


def mutate(r: Source, g: Grammar, i: TreeNode, max_depth: int) -> Any:
    new_tree = mutate_inner(r, g, deepcopy(i), max_depth)
    relabeled_new_tree = relabel_nodes_of_trees(new_tree, g.non_terminals)
    return relabeled_new_tree


def find_in_tree(ty: type, o: TreeNode, max_depth: int):
    if ty in o.__class__.__bases__ and o.distance_to_term <= max_depth:
        yield o
    if hasattr(o, "__annotations__"):
        for field in o.__annotations__:
            child = getattr(o, field)
            yield from find_in_tree(ty, child, max_depth)


def tree_crossover_inner(
    r: Source, g: Grammar, i: TreeNode, o: TreeNode, max_depth: int
) -> Any:
    if i.nodes > 0:
        c = r.randint(0, i.nodes - 1)
        if c == 0:
            ty = i.__class__.__bases__[0]
            replacement = None
            options = list(find_in_tree(ty, o, max_depth - i.depth + 1))
            if options:
                replacement = r.choice(options)
            if replacement is None:
                try:
                    replacement = random_node(r, g, max_depth - i.depth + 1, ty)
                except:
                    return i
            return replacement
        else:
            for field in i.__annotations__:
                child = getattr(i, field)
                if hasattr(child, "nodes"):
                    count = getattr(i, field).nodes
                    if c <= count:
                        setattr(
                            i,
                            field,
                            tree_crossover_inner(r, g, getattr(i, field), o, max_depth),
                        )
                        return i
                    else:
                        c -= count
            return i
    else:
        return i


def tree_crossover(
    r: Source, g: Grammar, p1: TreeNode, p2: TreeNode, max_depth: int
) -> Tuple[TreeNode, TreeNode]:
    """
    Given the two input trees [p1] and [p2], the grammar and the random source, this function returns two trees that are created by crossing over [p1] and [p2]. The first tree returned has [p1] as the base, and the second tree has [p2] as a base.
    """
    new_tree1 = tree_crossover_inner(r, g, deepcopy(p1), deepcopy(p2), max_depth)
    relabeled_new_tree1 = relabel_nodes_of_trees(new_tree1, g.non_terminals)
    new_tree2 = tree_crossover_inner(r, g, deepcopy(p2), deepcopy(p1), max_depth)
    relabeled_new_tree2 = relabel_nodes_of_trees(new_tree2, g.non_terminals)
    return relabeled_new_tree1, relabeled_new_tree2


def tree_crossover_single_tree(
    r: Source, g: Grammar, p1: TreeNode, p2: TreeNode, max_depth: int
) -> TreeNode:
    """
    Given the two input trees [p1] and [p2], the grammar and the random source, this function returns one tree that is created by crossing over [p1] and [p2]. The tree returned has [p1] as the base.
    """
    new_tree = tree_crossover_inner(r, g, deepcopy(p1), deepcopy(p2), max_depth)
    relabeled_new_tree = relabel_nodes_of_trees(new_tree, g.non_terminals)
    return relabeled_new_tree


class TreeBasedRepresentation(Representation[TreeNode]):
    def create_individual(self, r: Source, g: Grammar, depth: int) -> TreeNode:
        return random_individual(r, g, depth)

    def mutate_individual(
        self, r: Source, g: Grammar, ind: TreeNode, depth: int
    ) -> TreeNode:
        return mutate(r, g, ind, depth)

    def crossover_individuals(
        self, r: Source, g: Grammar, i1: TreeNode, i2: TreeNode, int
    ) -> Tuple[TreeNode, TreeNode]:
        return tree_crossover(r, g, i1, i2, int)

    def genotype_to_phenotype(self, g: Grammar, genotype: TreeNode) -> TreeNode:
        return genotype


treebased_representation = TreeBasedRepresentation()