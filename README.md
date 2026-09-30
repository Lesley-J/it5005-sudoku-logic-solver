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
```
├── Sudoku_Assignment.ipynb   # Experiments, verification, and conceptual answers
├── sudoku_solver.py          # Core KB construction & inference (single source of truth)
├── sudoku_app.py             # Streamlit application
├── puzzles.json              # Puzzle pool (givens, given_count, solutions)
├── logic_.py                 # Provided: pl_resolution, tt_entails, pl_fc_entails, ...
├── utils.py                  # Provided helpers (do not edit)
├── requirements.txt
└── LICENSE                   # MIT
```
> `sudoku_app.py` and the notebook **import** the solver from `sudoku_solver.py`;
> no core function is duplicated.
## Getting Started
```bash
# 1. Clone
git clone https://github.com/Lesley-J/it5005-sudoku-logic-solver.git
cd it5005-sudoku-logic-solver
# 2. Install dependencies
pip install -r requirements.txt
# 3. Run the notebook experiments
jupyter notebook Sudoku_Assignment.ipynb
# 4. Launch the app
streamlit run sudoku_app.py
```
## How It Works
1. **Symbols** — `Is_rcv` ("cell (r,c) has value v") and `Not_rcv`
   ("cell (r,c) does not have value v"), built with the provided `atom()` helper.
2. **General KB** — the six well-posedness conditions are translated directly into
   CNF: at-least-one clauses, pairwise at-most-one clauses, row / column / box
   uniqueness, and given unit clauses.
3. **Definite KB** — since Horn clauses forbid disjunctions, exclusion facts are
   reified as positive `Not` atoms; `Is ⇒ Not` elimination rules propagate them,
   and last-candidate / last-place rules convert "n−1 options eliminated" back
   into a positive conclusion. Givens are added as facts.
4. **Solving** — for every cell, each candidate value is queried; the one that is
   entailed is the solution. Forward chaining recomputes from the givens; backward
   chaining works goal-driven and caches everything it proves.
5. **Why not resolution / model checking?** Both are sound and complete, but
   `tt_entails` must examine up to 2^729 truth assignments, and `pl_resolution`'s
   first round already considers ≈6.9 × 10^7 clause pairs — neither returned
   within 30 seconds in our experiments (see Conceptual Question 2 in the notebook).
## References
1. H. Simonis. *Sudoku as a Constraint Problem.* CP Workshop on Modeling and
   Reformulating Constraint Satisfaction Problems, 2005.
2. I. Lynce and J. Ouaknine. *Sudoku as a SAT Problem.* Proceedings of the 9th
   International Symposium on Artificial Intelligence and Mathematics (AIMATH), 2006.
3. G. McGuire, B. Tugemann, G. Civario. *There Is No 16-Clue Sudoku: Solving the
   Sudoku Minimum Number of Clues Problem via Hitting Set Enumeration.*
   Experimental Mathematics, 23(2):190–217, 2014.
4. J. F. Crook. *A Pencil-and-Paper Algorithm for Solving Sudoku Puzzles.* Notices
   of the American Mathematical Society, 56(4):460–468, 2009.
5. S. Russell and P. Norvig. *Artificial Intelligence: A Modern Approach.* Pearson,
   4th edition, 2020.
## License
Distributed under the [MIT License](LICENSE).

