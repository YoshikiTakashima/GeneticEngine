from __future__ import annotations

from typing import Any
from typing import TypeVar

from geneticengine.grammar.grammar import Grammar
from geneticengine.random.sources import RandomSource
from geneticengine.representations.api import (
    RepresentationWithCrossover,
    RepresentationWithMutation,
    Representation,
)
from geneticengine.representations.tree.initializations import apply_constructor, create_node
from geneticengine.representations.tree.utils import relabel_nodes
from geneticengine.representations.tree.utils import relabel_nodes_of_trees
from geneticengine.solutions.tree import GengyList, TreeNode
from geneticengine.grammar.utils import get_arguments
from geneticengine.grammar.utils import get_generic_parameter
from geneticengine.grammar.utils import has_annotated_crossover
from geneticengine.grammar.utils import has_annotated_mutation
from geneticengine.grammar.utils import is_abstract
from geneticengine.exceptions import GeneticEngineError

T = TypeVar("T")


def random_node(
    r: RandomSource,
    g: Grammar,
    max_depth: int,
    starting_symbol: type[Any] | None = None,
):
    starting_symbol = starting_symbol if starting_symbol else g.starting_symbol
    return create_node(r, g, starting_symbol)


def random_individual(
    r: RandomSource,
    g: Grammar,
    max_depth: int = 5,
) -> TreeNode:
    try:
        assert max_depth >= g.get_min_tree_depth()
    except AssertionError:
        if g.get_min_tree_depth() == 1000000:
            raise GeneticEngineError(
                f"""Grammar's minimal tree depth is {g.get_min_tree_depth()}, which is the default tree depth.
                 It's highly like that there are nodes of your grammar than cannot reach any terminal.""",
            )
        raise GeneticEngineError(
            f"""Cannot use complete grammar for individual creation. Max depth ({max_depth})
            is smaller than grammar's minimal tree depth ({g.get_min_tree_depth()}).""",
        )
    ind = random_node(r, g, max_depth, g.starting_symbol)
    assert isinstance(ind, TreeNode)
    return ind


def mutate_inner(
    r: RandomSource,
    g: Grammar,
    i: TreeNode,
    max_depth: int,
    ty: type,
    force_mutate: bool,
    depth_aware_mut: bool,
) -> Any:
    counter = i.gengy_weighted_nodes if depth_aware_mut else i.gengy_nodes
    if counter > 0:
        c = r.randint(0, counter - 1)
        if c == 0 or (c <= i.gengy_distance_to_term and depth_aware_mut) or force_mutate:
            # If Metahandler mutation exists, the mutation process is different
            if any(has_annotated_mutation(arg[1]) for arg in get_arguments(i)):
                options = [(kdx, arg[1]) for kdx, arg in enumerate(get_arguments(i)) if has_annotated_mutation(arg[1])]
                index = r.randint(0, len(options) - 1)
                (index, arg_to_be_mutated) = options[index]

                args = list(i.gengy_init_values)
                args[index] = arg_to_be_mutated.__metadata__[0].mutate(  # type: ignore
                    r,
                    g,
                    random_node,
                    max_depth - 1,
                    get_generic_parameter(arg_to_be_mutated),
                    current_node=args[index],
                )
                return apply_constructor(type(i), args)

            replacement = None
            for _ in range(5):
                try:
                    replacement = random_node(r, g, max_depth, ty)
                    if replacement != i:
                        break
                except GeneticEngineError:
                    pass
            return replacement if replacement else i
        else:
            if is_abstract(ty) and g.expansion_depthing:
                max_depth -= g.abstract_dist_to_t[ty][type(i)]
            max_depth -= 1
            args = list(i.gengy_init_values)
            c -= i.gengy_distance_to_term if depth_aware_mut else 1
            for idx, (_, field_type) in enumerate(get_arguments(i)):
                child = args[idx]
                if hasattr(child, "gengy_nodes"):
                    count = child.gengy_weighted_nodes if depth_aware_mut else child.gengy_nodes
                    if c <= count:
                        mi = mutate_inner(
                            r,
                            g,
                            child,
                            max_depth,
                            field_type,
                            force_mutate,
                            depth_aware_mut,
                        )
                        args[idx] = mi
                        break
                    else:
                        c -= count
            if isinstance(i, GengyList):
                return GengyList(i.typ, args)
            else:
                return apply_constructor(type(i), args)
    else:
        rn = None
        for _ in range(5):
            try:
                rn = random_node(r, g, max_depth, ty)
                if rn != i:
                    break
            except GeneticEngineError:
                pass
        return rn if rn else i


def mutate_specific_type_inner(
    r: RandomSource,
    g: Grammar,
    i: TreeNode,
    max_depth: int,
    ty: type,
    specific_type: type,
    n: int,
    depth_aware_mut: bool,
) -> Any:
    if n == 1 and type(i) == specific_type:
        return mutate_inner(
            r,
            g,
            i,
            max_depth,
            ty,
            force_mutate=True,
            depth_aware_mut=depth_aware_mut,
        )
    else:
        args = list(i.gengy_init_values)
        for idx, (_, field_type) in enumerate(get_arguments(i)):
            child = args[idx]
            if hasattr(child, "gengy_nodes"):
                n_options = len(
                    list(find_in_tree_exact(g, specific_type, child, max_depth)),
                )
                if n_options <= n:
                    args[idx] = mutate_specific_type_inner(
                        r,
                        g,
                        child,
                        max_depth,
                        ty,
                        specific_type,
                        n,
                        depth_aware_mut,
                    )
                else:
                    n -= n_options
        if isinstance(i, GengyList):
            return GengyList(i.typ, args)
        else:
            return apply_constructor(type(i), args)


def mutate_specific_type(
    r: RandomSource,
    g: Grammar,
    i: TreeNode,
    max_depth: int,
    target_type: type,
    specific_type: type,
    depth_aware_mut: bool,
) -> TreeNode:
    ch = r.randint(0, 2)
    n_options = len(list(find_in_tree_exact(g, specific_type, i, max_depth)))
    if ch == 0 or n_options == 0:
        new_tree = mutate_inner(
            r,
            g,
            i,
            max_depth,
            target_type,
            force_mutate=False,
            depth_aware_mut=depth_aware_mut,
        )
        relabeled_new_tree = relabel_nodes_of_trees(new_tree, g)
        return relabeled_new_tree
    else:
        n = r.randint(1, n_options)
        new_tree = mutate_specific_type_inner(
            r,
            g,
            i,
            max_depth,
            target_type,
            specific_type,
            n,
            depth_aware_mut,
        )
        relabeled_new_tree = relabel_nodes_of_trees(new_tree, g)
        return relabeled_new_tree


def tree_mutate(
    r: RandomSource,
    g: Grammar,
    i: TreeNode,
    max_depth: int,
    target_type: type,
    depth_aware_mut: bool = False,
) -> Any:
    new_tree = mutate_inner(r, g, i, max_depth, target_type, False, depth_aware_mut)
    relabeled_new_tree = relabel_nodes_of_trees(new_tree, g)
    return relabeled_new_tree


def find_in_tree(g: Grammar, ty: type, o: TreeNode, max_depth: int):
    is_abs = is_abstract(ty)
    if hasattr(o, "gengy_types_this_way"):
        for t in o.gengy_types_this_way:

            def is_valid(node):
                _, depth, _, _ = relabel_nodes(node, g)

                if is_abs and g.expansion_depthing:
                    depth += g.abstract_dist_to_t[ty][t]

                return depth <= max_depth

            if ty in t.__bases__:
                vals = o.gengy_types_this_way[t]
                if vals:
                    yield from filter(is_valid, vals)


def find_in_tree_exact(g: Grammar, ty: type, o: TreeNode, max_depth: int):
    if hasattr(o, "gengy_types_this_way") and ty in o.gengy_types_this_way:
        vals = o.gengy_types_this_way[ty]
        if vals:

            def is_valid(node):
                _, depth, _, _ = relabel_nodes(node, g)
                return depth <= max_depth

            yield from filter(is_valid, vals)


def crossover_inner(
    r: RandomSource,
    g: Grammar,
    i: TreeNode,
    o: TreeNode,
    max_depth: int,
    ty: type,
    force_crossover: bool,
    depth_aware_co: bool,
) -> Any:
    counter = i.gengy_weighted_nodes if depth_aware_co else i.gengy_nodes
    if counter > 0:
        c = r.randint(0, counter - 1)
        if c == 0 or (c <= i.gengy_distance_to_term and depth_aware_co) or force_crossover:
            replacement = None
            args_with_specific_crossover = [has_annotated_crossover(arg[1]) for arg in get_arguments(i)]
            if any(args_with_specific_crossover):
                crossover_possibilities = len(args_with_specific_crossover)
                crossover_choice = r.randint(
                    0,
                    crossover_possibilities - 1,
                )
                options = list(find_in_tree_exact(g, type(i), o, max_depth))
                if not options:
                    pass  # Replace whole node
                else:
                    (index, arg_to_be_crossovered) = [(kdx, arg) for kdx, arg in enumerate(get_arguments(i))][
                        crossover_choice
                    ]
                    args = list(i.gengy_init_values)
                    if has_annotated_crossover(arg_to_be_crossovered[1]):
                        args[index] = (
                            arg_to_be_crossovered[1]
                            .__metadata__[0]  # type: ignore
                            .crossover(
                                r,
                                g,
                                options,
                                arg_to_be_crossovered[0],
                                ty,
                                current_node=args[index],
                            )
                        )
                        return apply_constructor(type(i), args)

            options = list(find_in_tree(g, ty, o, max_depth))
            if options:
                replacement = r.choice(options)
            if replacement is None:
                for _ in range(5):
                    replacement = create_node(r, g, ty)
                    if replacement != i:
                        break

            return replacement
        else:
            if is_abstract(ty) and g.expansion_depthing:
                max_depth -= g.abstract_dist_to_t[ty][type(i)]
            max_depth -= 1
            args = list(i.gengy_init_values)
            c -= i.gengy_distance_to_term if depth_aware_co else 1
            for idx, (field, field_type) in enumerate(get_arguments(i)):
                child = args[idx]
                if hasattr(child, "gengy_nodes"):
                    count = child.gengy_weighted_nodes if depth_aware_co else child.gengy_nodes
                    if c <= count:
                        args[idx] = crossover_inner(
                            r,
                            g,
                            child,
                            o,
                            max_depth,
                            field_type,
                            force_crossover=False,
                            depth_aware_co=depth_aware_co,
                        )
                        break
                    else:
                        c -= count
            if isinstance(i, GengyList):
                return GengyList(i.typ, args)
            else:
                return apply_constructor(type(i), args)
    else:
        return i


def crossover_specific_type_inner(
    r: RandomSource,
    g: Grammar,
    i: TreeNode,
    o: TreeNode,
    max_depth: int,
    ty: type,
    specific_type: type,
    n: int,
    depth_aware_co: bool,
) -> Any:
    if n == 1 and type(i) == specific_type:
        return crossover_inner(
            r,
            g,
            i,
            o,
            max_depth,
            ty,
            force_crossover=True,
            depth_aware_co=depth_aware_co,
        )
    else:
        args = list(i.gengy_init_values)
        for idx, (_, field_type) in enumerate(get_arguments(i)):
            child = args[idx]
            n_options = len(
                list(find_in_tree_exact(g, specific_type, child, max_depth)),
            )
            if n_options <= n:
                args[idx] = crossover_specific_type_inner(
                    r,
                    g,
                    child,
                    o,
                    max_depth,
                    ty,
                    specific_type,
                    n,
                    depth_aware_co=depth_aware_co,
                )
            else:
                n -= n_options
        if isinstance(i, GengyList):
            return GengyList(i.typ, args)
        else:
            return apply_constructor(type(i), args)


def crossover_specific_type(
    r: RandomSource,
    g: Grammar,
    i: TreeNode,
    o: TreeNode,
    max_depth: int,
    target_type: type,
    specific_type: type,
    depth_aware_co: bool,
) -> TreeNode:
    ch = r.randint(0, 1)
    n_options_i = len(list(find_in_tree_exact(g, specific_type, i, max_depth)))
    n_options_o = len(list(find_in_tree_exact(g, specific_type, o, max_depth)))
    if ch == 0 or n_options_i == 0 or n_options_o == 0:
        new_tree = crossover_inner(
            r,
            g,
            i,
            o,
            max_depth,
            target_type,
            force_crossover=False,
            depth_aware_co=depth_aware_co,
        )
        relabeled_new_tree = relabel_nodes_of_trees(new_tree, g)
        return relabeled_new_tree
    else:
        n = r.randint(1, n_options_i)
        new_tree = crossover_specific_type_inner(
            r,
            g,
            i,
            o,
            max_depth,
            target_type,
            specific_type,
            n,
            depth_aware_co=depth_aware_co,
        )
        relabeled_new_tree = relabel_nodes_of_trees(new_tree, g)
        return relabeled_new_tree


def tree_crossover(
    r: RandomSource,
    g: Grammar,
    p1: TreeNode,
    p2: TreeNode,
    max_depth: int,
    specific_type: type | None = None,
    depth_aware_co: bool = False,
) -> tuple[TreeNode, TreeNode]:
    """Given the two input trees [p1] and [p2], the grammar and the random
    source, this function returns two trees that are created by crossing over.

    [p1] and [p2].

    The first tree returned has [p1] as the base, and the second tree
    has [p2] as a base.
    """
    if specific_type:
        new_tree1 = crossover_specific_type(
            r,
            g,
            p1,
            p2,
            max_depth,
            g.starting_symbol,
            specific_type,
            depth_aware_co=depth_aware_co,
        )
    else:
        new_tree1 = crossover_inner(
            r,
            g,
            p1,
            p2,
            max_depth,
            g.starting_symbol,
            force_crossover=False,
            depth_aware_co=depth_aware_co,
        )
    relabeled_new_tree1 = relabel_nodes_of_trees(new_tree1, g)

    if specific_type:
        new_tree2 = crossover_specific_type(
            r,
            g,
            p2,
            p1,
            max_depth,
            g.starting_symbol,
            specific_type,
            depth_aware_co=depth_aware_co,
        )
    else:
        new_tree2 = crossover_inner(
            r,
            g,
            p2,
            p1,
            max_depth,
            g.starting_symbol,
            force_crossover=False,
            depth_aware_co=depth_aware_co,
        )
    relabeled_new_tree2 = relabel_nodes_of_trees(new_tree2, g)
    return relabeled_new_tree1, relabeled_new_tree2


class TreeBasedRepresentation(
    Representation[TreeNode, TreeNode],
    RepresentationWithMutation[TreeNode],
    RepresentationWithCrossover[TreeNode],
):
    """This class represents the tree representation of an individual.

    In this approach, the genotype and the phenotype are exactly the
    same.
    """

    def __init__(
        self,
        grammar: Grammar,
        max_depth: int,
    ):
        self.grammar = grammar
        self.max_depth = max_depth

    def create_genotype(self, random: RandomSource, **kwargs) -> TreeNode:
        actual_depth = kwargs.get("depth", self.max_depth)
        return random_individual(random, self.grammar, max_depth=actual_depth)

    def genotype_to_phenotype(self, genotype: TreeNode) -> TreeNode:
        return genotype

    def mutate(self, random: RandomSource, internal: TreeNode, **kwargs) -> TreeNode:
        return tree_mutate(
            random,
            self.grammar,
            internal,
            max_depth=self.max_depth,
            target_type=self.grammar.starting_symbol,
        )

    def crossover(
        self,
        random: RandomSource,
        parent1: TreeNode,
        parent2: TreeNode,
        **kwargs,
    ) -> tuple[TreeNode, TreeNode]:
        return tree_crossover(random, self.grammar, parent1, parent2, self.max_depth)
