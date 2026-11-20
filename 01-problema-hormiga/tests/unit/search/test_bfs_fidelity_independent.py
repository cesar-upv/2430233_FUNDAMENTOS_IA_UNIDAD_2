"""``solve_bfs`` is a FIFO breadth-first loop, pop for pop - checked against my own.

Two claims are pinned here, both of which are stronger than "some optimal path came back":

* :func:`solve_bfs` answers exactly what a hand-written deque loop over the same
  ``(cell, collected)`` states answers - same path, same cost, same number of pops, same
  ``found``. The reference is written in :mod:`independent_oracle` with its own queue and its
  own parent map; a disagreement here is a real difference in the search, not in the pacing.
* :func:`solve_dijkstra` is the same run under a different name - identical path, cost and
  ``expanded_states``, which can only agree if both pop the states in the same order.

**The FIFO identity depends on the neighbour order.** ``bfs.py`` documents that the engine's
``(cost, sequence)`` priority reproduces a FIFO queue, which is true; it also documents that
the parents and ``expanded_states`` come out identical to a hand-written breadth-first loop.
That second claim only holds for a loop that walks neighbours in the *same* order - east,
south, west, north, which is what ``Position.neighbors`` yields. A first version of this
reference iterated east, west, south, north and disagreed with the engine on the parent map,
and therefore on the returned path and on ``expanded_states``, for hundreds of maps, while
finding an equally optimal answer every time. The ordering is therefore pinned in
``OracleGrid.neighbours``, and the docstring in ``bfs.py`` now names it.

The sweeps are looped over inside each test rather than parametrized: thousands of maps per
property, one collected case each.
"""

from independent_cases import Discrepancies, exhaustive, random_maps, sample, sweep
from independent_oracle import OracleScenario, fifo_bfs, to_scenario

from ant_pathfinding.search.bfs import solve_bfs
from ant_pathfinding.search.dijkstra import solve_dijkstra

WALLS_3x4 = [
    ("open", frozenset()),
    ("one-wall-middle", frozenset({(1, 1)})),
    ("a-column", frozenset({(1, 0), (1, 1)})),
]

FIDELITY_MAPS = sweep(
    ("2x2-two-foods", exhaustive(2, 2, frozenset(), 2)),
    ("3x3-one-food", exhaustive(3, 3, frozenset(), 1)),
    ("3x3-two-foods", exhaustive(3, 3, frozenset(), 2)),
    *(
        (f"3x4-{label}", sample(exhaustive(3, 4, walls, 2), 700, seed=seed))
        for label, walls in WALLS_3x4
        for seed in (301, 302)
    ),
    ("4x3-walled-three-foods", sample(exhaustive(4, 3, frozenset({(2, 0)}), 3), 700, seed=303)),
    ("random-4x4-15pc", random_maps(250, 304, ((4, 4),), 0.15)),
    ("random-4x4-30pc", random_maps(250, 305, ((4, 4),), 0.3)),
    ("random-5x4-20pc", random_maps(200, 306, ((5, 4),), 0.2)),
    ("random-5x5-10pc", random_maps(150, 307, ((5, 5),), 0.1, maxfoods=5)),
)
"""9,062 maps: exhaustive where the grid allows it, seeded samples where it does not.

    A 4x3 grid with three foods holds 18,150 maps and an open 3x4 with two foods 8,712, so those
    families contribute fixed-seed samples of 700 each; the 2x2 and 3x3 families and all the
    random draws are taken whole. Each map here costs two engine runs, which is what makes this
    one of the sweeps to keep small.
    """


def test_bfs_is_identical_to_a_hand_written_fifo_loop() -> None:
    """The same path, the same cost, the same pop count and the same ``found`` flag.

    The pop count is the part that distinguishes a genuine breadth-first loop from anything that
    merely finds an optimal path: two searches can agree on the answer and still expand a
    different number of states, which is exactly what a wrong neighbour order produces.
    """
    problems = Discrepancies()
    for oracle_scenario in FIDELITY_MAPS:
        result = solve_bfs(to_scenario(oracle_scenario))
        reference = fifo_bfs(oracle_scenario)

        if result.found != reference.found:
            problems.add(oracle_scenario, "solve_bfs and the FIFO loop disagree on `found`")
        if result.cost != reference.cost:
            problems.add(
                oracle_scenario,
                f"solve_bfs reported cost {result.cost}, the FIFO loop {reference.cost}",
            )
        if result.expanded_states != reference.pops:
            problems.add(
                oracle_scenario,
                f"solve_bfs expanded {result.expanded_states} states, "
                f"the FIFO loop popped {reference.pops}",
            )
        if result.found:
            walked = tuple((position.x, position.y) for position in result.path)
            if walked != reference.path:
                problems.add(oracle_scenario, f"paths differ: {walked} against {reference.path}")
        elif result.path or result.cost:
            problems.add(oracle_scenario, "a failed result carries a path or a non-zero cost")

    problems.raise_if_any("solve_bfs is identical to a hand-written FIFO loop")
    assert len(FIDELITY_MAPS) == 9_062


def test_dijkstra_is_the_same_run_as_breadth_first_search() -> None:
    """Full result equality, ``expanded_states`` and ``path`` included, on every swept map.

    Swept separately from the FIFO identity above so that a disagreement reports against Dijkstra
    specifically; the two properties share the map list but not the conclusion.
    """
    problems = Discrepancies()
    for oracle_scenario in FIDELITY_MAPS:
        scenario = to_scenario(oracle_scenario)

        breadth_first = solve_bfs(scenario)
        uniform_cost = solve_dijkstra(scenario)

        if uniform_cost != breadth_first:
            problems.add(oracle_scenario, f"{uniform_cost} against {breadth_first}")

    problems.raise_if_any("solve_dijkstra is the same run as solve_bfs")
    assert len(FIDELITY_MAPS) == 9_062


def test_the_fifo_reference_is_order_sensitive_so_the_claim_is_not_vacuous() -> None:
    """The identity above is a real check: a differently ordered reference does disagree.

    This is the finding that produced the neighbour-order note in the module docstring. Swapping
    the reference's neighbour order to east, west, south, north changes which of several
    equal-cost parents a state gets, so its ``expanded_states`` stops matching while its cost
    keeps matching. Pinning it stops the identity test from quietly passing for the wrong reason:
    if a future edit broke FIFO behaviour *and* changed the engine's neighbour order to match,
    this would no longer catch it.
    """
    sample_map = exhaustive(3, 3, frozenset(), 2)[0]
    engine_result = solve_bfs(to_scenario(sample_map))
    reference = fifo_bfs(sample_map)

    assert engine_result.cost == reference.cost, "the matching order agrees on the cost"
    assert engine_result.expanded_states == reference.pops, "the matching order agrees on the pops"

    disagreeing = [
        candidate
        for candidate in exhaustive(3, 3, frozenset(), 2)
        if fifo_bfs(candidate).pops != _reference_with_swapped_neighbour_order(candidate)
    ]
    assert disagreeing, "the two neighbour orders never disagree, so the claim proves nothing"


def _reference_with_swapped_neighbour_order(oracle_scenario: OracleScenario):
    """The FIFO reference walking neighbours east, west, south, north instead.

    A second copy of the same loop with one line changed, so the only difference between the two
    references is the enumeration order. Both are written here; neither is the engine.
    """
    from collections import deque

    grid = oracle_scenario["grid"]
    foods = oracle_scenario["foods"]
    goal = oracle_scenario["goal"]
    first: tuple = (oracle_scenario["start"], frozenset({oracle_scenario["start"]}) & foods)
    parents: dict = {first: None}
    depth = {first: 0}
    queue = deque([first])
    pops = 0
    while queue:
        state = queue.popleft()
        pops += 1
        cell, collected = state
        if cell == goal and collected == foods:
            return pops
        x, y = cell
        for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not grid.walkable(neighbour):
                continue
            gathered = collected | {neighbour} if neighbour in foods else collected
            successor = (neighbour, frozenset(gathered))
            if successor in depth:
                continue
            depth[successor] = depth[state] + 1
            parents[successor] = state
            queue.append(successor)
    return pops
