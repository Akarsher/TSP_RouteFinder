from functools import lru_cache
from typing import List, Tuple


# Held–Karp TSP (returns optimal cost and tour order starting at 0 and ending at 0)


def solve_tsp_held_karp(distance_matrix: List[List[float]]) -> Tuple[float, list]:
    n = len(distance_matrix)
    if n == 0:
        return 0.0, []

    ALL_VISITED = (1 << n) - 1

    @lru_cache(None)
    def visit(pos: int, mask: int):
        # Returns (cost_from_pos_covering_remaining, path_tuple_of_next_nodes_ending_in_0)
        if mask == ALL_VISITED:
            # return to start (0)
            return distance_matrix[pos][0], (0,)

        best_cost = float('inf')
        best_tail = None

        for nxt in range(n):
            if mask & (1 << nxt):
                continue
            edge = distance_matrix[pos][nxt]
            if edge == float('inf'):
                continue
            sub_cost, sub_tail = visit(nxt, mask | (1 << nxt))
            total = edge + sub_cost
            if total < best_cost:
                best_cost = total
                best_tail = (nxt,) + sub_tail
        return best_cost, best_tail

    cost, tail = visit(0, 1)
    path = (0,) + tail  # e.g., (0, 3, 2, 1, 0)
    return cost, list(path)