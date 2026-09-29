"""Streamlit interface for the propositional-logic Sudoku solver."""

from collections import defaultdict, deque
import json
from pathlib import Path
import re
import time

import streamlit as st
from logic_ import conjuncts, is_prop_symbol
from sudoku_solver import (
    atom,
    build_definite_kb,
    build_general_kb,
    pl_bc_entails,
    solve_full_grid_bc,
    solve_full_grid_fc,
)

APP_DIR = Path(__file__).resolve().parent
with (APP_DIR / "puzzles.json").open(encoding="utf-8") as file:
    PUZZLE_POOL = json.load(file)

N = PUZZLE_POOL["n"]
BOX_H = PUZZLE_POOL["box_h"]
BOX_W = PUZZLE_POOL["box_w"]

st.set_page_config(page_title="Sudoku Logic Solver", page_icon="🧩", layout="centered")


def puzzle_givens(index):
    """Return one puzzle as {(row, column): value}."""
    return {
        tuple(map(int, key.split("_"))): value
        for key, value in PUZZLE_POOL["puzzles"][index]["givens"].items()
    }


def puzzle_solution(index):
    return {
        tuple(map(int, key.split("_"))): value
        for key, value in PUZZLE_POOL["puzzles"][index]["solution"].items()
    }


BOARD_STYLE = """
<style>
.sudoku-wrap {display: flex; justify-content: center; width: 100%;}
.sudoku-board {
    border: 3px solid #41444b; border-collapse: collapse; margin: .35rem auto .8rem;
    box-shadow: 0 2px 10px rgba(0, 0, 0, .08);
}
.sudoku-board td {
    border: 1px solid #a8abb2; width: 2.7rem; height: 2.7rem;
    text-align: center; font-size: 1.15rem; font-variant-numeric: tabular-nums;
}
.sudoku-board .given {background: #e8eef9; color: #17243d; font-weight: 750;}
.sudoku-board .answer {background: #f8fafc; color: #28735a; font-weight: 600;}
.sudoku-board .empty {background: #f1f2f4; color: transparent;}
.sudoku-board .focus {box-shadow: inset 0 0 0 3px #e58b2a;}
.sudoku-board .box-right {border-right: 3px solid #41444b;}
.sudoku-board .box-bottom {border-bottom: 3px solid #41444b;}
@media (max-width: 520px) {
    .sudoku-board td {width: 9vw; height: 9vw; font-size: 1rem;}
}
</style>
"""


def render_board(givens, solved=None, focus=None):
    """Draw the board and keep givens visually separate from derived values."""
    solved = solved or {}
    rows = []
    for row in range(1, N + 1):
        cells = []
        for column in range(1, N + 1):
            position = (row, column)
            classes = []
            if column % BOX_W == 0 and column != N:
                classes.append("box-right")
            if row % BOX_H == 0 and row != N:
                classes.append("box-bottom")
            if position == focus:
                classes.append("focus")

            if position in givens:
                value = givens[position]
                classes.append("given")
            elif position in solved:
                value = solved[position]
                classes.append("answer")
            else:
                value = "&nbsp;"
                classes.append("empty")
            cells.append(f'<td class="{" ".join(classes)}">{value}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")

    table = '<table class="sudoku-board">' + "".join(rows) + "</table>"
    st.markdown(
        BOARD_STYLE + '<div class="sudoku-wrap">' + table + "</div>",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def solve_puzzle(index, algorithm):
    givens = puzzle_givens(index)
    solver = solve_full_grid_fc if algorithm == "Forward chaining" else solve_full_grid_bc
    started = time.perf_counter()
    solved = solver(N, BOX_H, BOX_W, givens)
    return solved, time.perf_counter() - started


@st.cache_data(show_spinner=False)
def check_entailment(index, row, column, value):
    kb = build_definite_kb(N, BOX_H, BOX_W, puzzle_givens(index))
    started = time.perf_counter()
    result = pl_bc_entails(kb, atom("Is", row, column, value))
    return result, time.perf_counter() - started


@st.cache_data(show_spinner=False)
def knowledge_base_sizes(index):
    givens = puzzle_givens(index)
    general = build_general_kb(N, BOX_H, BOX_W, givens)
    definite = build_definite_kb(N, BOX_H, BOX_W, givens)
    return len(general.clauses), len(definite.clauses)


def solved_values_for(index):
    """Return the current solved values only when they belong to this puzzle."""
    result = st.session_state.get("solved_result")
    if result and result[0] == index:
        return result[2]
    return {}


def query_result_for(index, row, column, value):
    """Ignore an old verdict after the puzzle or query inputs have changed."""
    result = st.session_state.get("query_result")
    if result and result[:4] == (index, row, column, value):
        return result
    return None


def _proof_steps(kb, target):
    """Run forward chaining once and retain the first reason for each fact."""
    agenda = deque()
    waiting = defaultdict(list)
    rules = {}
    remaining = {}

    for rule_id, clause in enumerate(kb.clauses):
        if is_prop_symbol(clause.op):
            agenda.append(clause)
            continue
        if clause.op != "==>":
            continue
        premises = tuple(conjuncts(clause.args[0]))
        conclusion = clause.args[1]
        rules[rule_id] = (premises, conclusion)
        remaining[rule_id] = len(premises)
        for premise in premises:
            waiting[premise].append(rule_id)

    facts = set(agenda)
    if target in facts:
        return True, []

    known = set()
    queued = set(facts)
    reason = {}

    while agenda and target not in queued:
        fact = agenda.popleft()
        if fact in known:
            continue
        known.add(fact)
        for rule_id in waiting.get(fact, ()):
            remaining[rule_id] -= 1
            if remaining[rule_id] != 0:
                continue
            premises, conclusion = rules[rule_id]
            if conclusion not in queued:
                reason[conclusion] = premises
                queued.add(conclusion)
                agenda.append(conclusion)

    if target not in queued:
        return False, []

    ordered = []
    seen = set()
    stack = [(target, False)]
    while stack:
        symbol, ready = stack.pop()
        if symbol in seen or symbol not in reason:
            continue
        if ready:
            seen.add(symbol)
            ordered.append((tuple(str(item) for item in reason[symbol]), str(symbol)))
            continue
        stack.append((symbol, True))
        for premise in reversed(reason[symbol]):
            if premise not in seen:
                stack.append((premise, False))
    return True, ordered


@st.cache_data(show_spinner=False)
def reasoning_trace(index, row, column, value):
    kb = build_definite_kb(N, BOX_H, BOX_W, puzzle_givens(index))
    return _proof_steps(kb, atom("Is", row, column, value))


SYMBOL_PATTERN = re.compile(r"^(Is|Not)(\d+)_(\d+)_(\d+)$")


def symbol_parts(symbol):
    prefix, row, column, value = SYMBOL_PATTERN.fullmatch(symbol).groups()
    return prefix, int(row), int(column), int(value)


def same_box(first, second):
    return (
        (first[0] - 1) // BOX_H == (second[0] - 1) // BOX_H
        and (first[1] - 1) // BOX_W == (second[1] - 1) // BOX_W
    )


def describe_step(premises, conclusion):
    """Turn one fired rule into a short Sudoku explanation."""
    prefix, row, column, value = symbol_parts(conclusion)
    parsed = [symbol_parts(item) for item in premises]
    cell = f"R{row}C{column}"

    if prefix == "Not":
        _, source_row, source_column, source_value = parsed[0]
        source = f"R{source_row}C{source_column}"
        if (source_row, source_column) == (row, column):
            body = f"{cell} is already {source_value}, so it cannot also be {value}."
        elif source_row == row:
            body = f"{source} is {source_value}. The same value cannot appear again in row {row}."
        elif source_column == column:
            body = f"{source} is {source_value}. The same value cannot appear again in column {column}."
        elif same_box((source_row, source_column), (row, column)):
            body = f"{source} is {source_value}. The same value cannot appear again in this 3 x 3 box."
        else:
            body = f"{source} rules out {value} at {cell}."
        return f"Eliminate {value} from {cell}", body

    locations = {(item[1], item[2]) for item in parsed}
    values = {item[3] for item in parsed}
    if locations == {(row, column)}:
        ruled_out = ", ".join(map(str, sorted(values)))
        return (
            f"Place {value} at {cell}",
            f"Values {ruled_out} have been eliminated from {cell}; {value} is the only candidate left.",
        )

    if all(item[1] == row for item in parsed):
        unit = f"row {row}"
    elif all(item[2] == column for item in parsed):
        unit = f"column {column}"
    else:
        unit = "this 3 x 3 box"
    other_cells = ", ".join(f"R{item[1]}C{item[2]}" for item in parsed)
    return (
        f"Place {value} at {cell}",
        f"In {unit}, {value} has been ruled out at {other_cells}. Its remaining place is {cell}.",
    )


st.session_state.setdefault("query_row", 1)
st.session_state.setdefault("query_column", 1)
st.session_state.setdefault("query_value", 1)

st.title("Sudoku Logic Solver")
st.write(
    "Choose a puzzle, compare the two inference methods, or ask why a value "
    "belongs in a particular cell."
)

st.subheader("1. Choose a puzzle")
selected_index = st.selectbox(
    "Puzzle",
    range(len(PUZZLE_POOL["puzzles"])),
    format_func=lambda index: (
        f"Puzzle {index + 1} — {PUZZLE_POOL['puzzles'][index]['given_count']} givens"
    ),
)
givens = puzzle_givens(selected_index)
query_row = int(st.session_state["query_row"])
query_column = int(st.session_state["query_column"])
query_value = int(st.session_state["query_value"])
current_values = solved_values_for(selected_index)

st.caption(
    "Blue bold digits are givens; green digits are solver results; "
    "the orange outline follows the cell selected in Section 3."
)
render_board(
    givens,
    current_values,
    focus=(query_row, query_column),
)

top_left, top_middle, top_right = st.columns(3)
top_left.metric("Selected cell", f"R{query_row}C{query_column}")
top_middle.metric("Candidate", query_value)
if (query_row, query_column) in givens:
    board_state = f"Given: {givens[(query_row, query_column)]}"
elif (query_row, query_column) in current_values:
    board_state = f"Solved: {current_values[(query_row, query_column)]}"
else:
    board_state = "Not filled"
top_right.metric("Board state", board_state)

top_query_result = query_result_for(
    selected_index, query_row, query_column, query_value
)
if top_query_result:
    top_verdict, top_seconds = top_query_result[4], top_query_result[5]
    top_message = (
        f"Latest query: R{query_row}C{query_column} = {query_value} → "
        f"{top_verdict} ({top_seconds * 1000:.1f} ms)"
    )
    if top_verdict:
        st.success(top_message)
    else:
        st.error(top_message)
else:
    st.caption(
        f"Current query: R{query_row}C{query_column} = {query_value}. "
        "Change it below in Section 3; both boards update immediately."
    )

with st.expander("Knowledge-base size"):
    general_count, definite_count = knowledge_base_sizes(selected_index)
    general_col, definite_col = st.columns(2)
    general_col.metric("General clauses", f"{general_count:,}")
    definite_col.metric("Definite clauses", f"{definite_count:,}")

st.subheader("2. Solve the full grid")
algorithm = st.radio(
    "Inference algorithm",
    ["Backward chaining", "Forward chaining"],
    horizontal=True,
    help="Both use the functions imported from sudoku_solver.py. Runtime is measured on this run.",
)
if algorithm == "Forward chaining":
    st.info("With the current per-cell solver, forward chaining can take noticeably longer.")

if st.button("Solve puzzle", type="primary"):
    with st.spinner(f"Running {algorithm.lower()}..."):
        solved_grid, solve_seconds = solve_puzzle(selected_index, algorithm)
    st.session_state["solved_result"] = (
        selected_index,
        algorithm,
        solved_grid,
        solve_seconds,
    )
    st.rerun()

solved_result = st.session_state.get("solved_result")
if solved_result and solved_result[0] == selected_index:
    _, used_algorithm, solved_grid, solve_seconds = solved_result
    method_col, time_col = st.columns(2)
    method_col.metric("Method", used_algorithm)
    time_col.metric("Elapsed time", f"{solve_seconds:.3f} s")
    render_board(givens, solved_grid)
    if solved_grid == puzzle_solution(selected_index):
        st.success("The complete grid matches the supplied solution.")
    else:
        st.warning(f"The solver derived {len(solved_grid)} of {N * N} cells.")

st.subheader("3. Check one cell")
st.write(
    "Adjust the row and column to move the orange outline on both boards. "
    "The candidate is only tested after **Check entailment** is pressed."
)
row_col, column_col, value_col = st.columns(3)
query_row = int(
    row_col.number_input("Row", min_value=1, max_value=N, key="query_row")
)
query_column = int(
    column_col.number_input(
        "Column", min_value=1, max_value=N, key="query_column"
    )
)
query_value = int(
    value_col.number_input("Value", min_value=1, max_value=N, key="query_value")
)

preview_left, preview_middle, preview_right = st.columns(3)
preview_left.metric("Live focus", f"R{query_row}C{query_column}")
preview_middle.metric("Testing value", query_value)
if (query_row, query_column) in givens:
    preview_state = f"Given: {givens[(query_row, query_column)]}"
elif (query_row, query_column) in current_values:
    preview_state = f"Solved: {current_values[(query_row, query_column)]}"
else:
    preview_state = "Not filled"
preview_right.metric("Current value", preview_state)
render_board(
    givens,
    current_values,
    focus=(query_row, query_column),
)
st.caption(
    "This is the same current board shown in Section 1, so the selected cell "
    "and any solved values can be checked here without scrolling back up."
)

if st.button("Check entailment"):
    with st.spinner("Running backward chaining..."):
        verdict, query_seconds = check_entailment(
            selected_index, query_row, query_column, query_value
        )
    st.session_state["query_result"] = (
        selected_index, query_row, query_column, query_value, verdict, query_seconds
    )
    st.rerun()

query_result = query_result_for(
    selected_index, query_row, query_column, query_value
)
if query_result:
    verdict = query_result[4]
    query_seconds = query_result[5]
    if verdict:
        st.success(
            f"True — the KB entails R{query_row}C{query_column} = {query_value} "
            f"({query_seconds * 1000:.1f} ms)."
        )
    else:
        st.error(
            f"False — the KB does not entail R{query_row}C{query_column} = "
            f"{query_value} ({query_seconds * 1000:.1f} ms)."
        )

st.subheader("4. Tutor mode")
st.write("Show the forward-chaining rules that support the selected value.")
if st.button("Explain this value"):
    with st.spinner("Building the reasoning trace..."):
        entailed, trace = reasoning_trace(
            selected_index, query_row, query_column, query_value
        )
    st.session_state["trace_result"] = (
        selected_index, query_row, query_column, query_value, entailed, trace
    )

trace_result = st.session_state.get("trace_result")
if trace_result and trace_result[:4] == (
    selected_index, query_row, query_column, query_value
):
    entailed, trace = trace_result[4], trace_result[5]
    target = f"R{query_row}C{query_column} = {query_value}"
    if not entailed:
        st.warning(f"No proof was found for {target}.")
    elif not trace:
        st.info(f"{target} is one of the givens, so no inference step is needed.")
    else:
        st.success(f"{target} follows from {len(trace)} recorded rule firings.")
        show_full_trace = st.checkbox("Show every supporting step", value=len(trace) <= 20)
        shown_trace = trace if show_full_trace else trace[-20:]
        if not show_full_trace:
            st.caption(f"Showing the final 20 of {len(trace)} supporting steps.")

        first_number = len(trace) - len(shown_trace) + 1
        for step_number, (premises, conclusion) in enumerate(
            shown_trace, start=first_number
        ):
            heading, explanation = describe_step(premises, conclusion)
            with st.expander(f"Step {step_number}: {heading}"):
                st.write(explanation)

st.divider()
st.caption("Core KB construction and solving functions are imported from sudoku_solver.py.")
