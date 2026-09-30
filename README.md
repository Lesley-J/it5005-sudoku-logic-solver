# IT5005 Sudoku Logic Solver 🧩

An interactive **Streamlit Sudoku solver** built for **IT5005: Artificial Intelligence**.
The puzzle is formalized entirely in **propositional logic** and solved with classic
inference algorithms — **resolution, model checking, forward chaining, and backward
chaining** — implemented on top of the Russell & Norvig `logic_.py` library.

> 🔗 **Live demo:** [it5005-sudoku-logic-solver.streamlit.app](https://it5005-sudoku-logic-solver-ck8zbtv8hsdhrrunygowt8.streamlit.app/)

## Features

- **Two knowledge-base representations** of Sudoku rules:
  - **General KB (`build_general_kb`)** — raw CNF clauses: at-least-one / at-most-one
    value per cell, row / column / box uniqueness, and givens as unit clauses.
  - **Definite (Horn) KB (`build_definite_kb`)** — only clauses with one positive
    literal, using an `Is_rcv` / `Not_rcv` symbol vocabulary. Disjunctive constraints
    (e.g. "every cell holds *some* value") are re-expressed as **elimination rules**
    plus **last-candidate / last-place** rules.
- **Inference algorithms:**
  - `pl_resolution` and `tt_entails` on the general KB (demonstrated to be sound &
    complete but computationally intractable for a full grid).
  - `pl_fc_entails` (forward chaining) via `solve_full_grid_fc`.
  - **`pl_bc_entails`** — our own iterative (stack-based) backward-chaining
    implementation with cycle detection, monotone proof caching, and guaranteed
    termination, exposed via `solve_full_grid_bc`.
- **Interactive Streamlit app (`sudoku_app.py`)**:
  - Puzzle selector for all puzzles in `puzzles.json`, with givens clearly
    distinguished from empty cells.
  - Full-grid auto-solve with **forward- vs. backward-chaining** selection and
    elapsed-time reporting.
  - Targeted cell entailment query — checks `Is_rcv` with `pl_bc_entails` and
    returns `True / False`.
  - **Tutor mode**: a human-readable reasoning trace explaining every elimination
    and placement in plain Sudoku language, instead of raw internal symbols.

## Performance Highlights

Measured on a 30-given puzzle (see `Sudoku_Assignment.ipynb` for full experiments):

| Item | Value |
|---|---|
| General KB | 11,775 clauses / 729 symbols |
| Definite KB | 23,358 clauses |
| `tt_entails` / `pl_resolution` on one query | >30 s, no result (interrupted) |
| `solve_full_grid_fc` (whole grid) | 25.30 s |
| `solve_full_grid_bc` (whole grid) | **1.05 s** |
| One `pl_bc_entails` query (fresh KB) | 0.08 s (674 symbols proved and cached) |
| All 81 entailed queries on a warm KB | 0.09 s |

The large gap between the two full-grid solvers comes from the library interface,
not the algorithm itself: `pl_fc_entails` rebuilds premise counters for all 23,358
clauses on every one of its 247 calls, while our `pl_bc_entails` keeps its proof
set on the KB object and shares it across queries.

## Project Structure

