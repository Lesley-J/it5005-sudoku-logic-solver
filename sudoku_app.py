"""Streamlit interface for the propositional-logic Sudoku solver."""

from collections import defaultdict, deque
import json
from pathlib import Path
import re
import time

import pandas as pd
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
.sudoku-board .attempt {background: #fff4e8; color: #7b3fc6; font-weight: 750;}
.sudoku-board .empty {background: #f1f2f4; color: transparent;}
.sudoku-board .focus {box-shadow: inset 0 0 0 3px #e58b2a;}
.sudoku-board .box-right {border-right: 3px solid #41444b;}
.sudoku-board .box-bottom {border-bottom: 3px solid #41444b;}
@media (max-width: 520px) {
    .sudoku-board td {width: 9vw; height: 9vw; font-size: 1rem;}
}
</style>
"""


def render_board(givens, solved=None, attempts=None, focus=None):
    """Draw the board and keep givens visually separate from derived values."""
    solved = solved or {}
    attempts = attempts or {}
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
            elif position in attempts:
                value = attempts[position]
                classes.append("attempt")
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


def accepted_values_for(index):
    """Return values that the user has tested successfully for this puzzle."""
    return st.session_state.get("accepted_values", {}).get(index, {})


def input_lock_for(index):
    """Return the failed attempt that currently locks this puzzle, if any."""
    return st.session_state.get("input_locks", {}).get(index)


def store_candidate_result(index, row, column, value, verdict, seconds):
    """Keep one verdict and add only entailed values to the test board."""
    st.session_state["query_result"] = (
        index, row, column, value, verdict, seconds
    )

    if verdict:
        if (row, column) not in puzzle_givens(index):
            accepted = {
                puzzle: dict(values)
                for puzzle, values in st.session_state["accepted_values"].items()
            }
            accepted.setdefault(index, {})[(row, column)] = value
            st.session_state["accepted_values"] = accepted
    else:
        locks = dict(st.session_state["input_locks"])
        locks[index] = (row, column, value)
        st.session_state["input_locks"] = locks


def clear_test_state(index):
    """Clear accepted test values and unlock input without touching solver output."""
    accepted = dict(st.session_state["accepted_values"])
    accepted.pop(index, None)
    st.session_state["accepted_values"] = accepted

    locks = dict(st.session_state["input_locks"])
    locks.pop(index, None)
    st.session_state["input_locks"] = locks

    versions = dict(st.session_state["grid_versions"])
    versions[index] = versions.get(index, 0) + 1
    st.session_state["grid_versions"] = versions
    st.session_state.pop("query_result", None)
    st.session_state.pop("trace_result", None)


def direct_input_grid(givens, accepted):
    """Build the editable grid shown in the direct-input form."""
    rows = []
    for row in range(1, N + 1):
        item = {"Row": f"R{row}"}
        for column in range(1, N + 1):
            position = (row, column)
            value = givens.get(position, accepted.get(position, ""))
            item[f"C{column}"] = str(value) if value != "" else ""
        rows.append(item)
    return pd.DataFrame(rows)


def read_direct_entry(edited_grid, givens, accepted):
    """Validate the grid and return its one newly entered candidate."""
    changes = []
    for row in range(1, N + 1):
        for column in range(1, N + 1):
            position = (row, column)
            raw_value = edited_grid.at[row - 1, f"C{column}"]
            text = "" if pd.isna(raw_value) else str(raw_value).strip()
            baseline = givens.get(position, accepted.get(position, ""))
            baseline_text = str(baseline) if baseline != "" else ""
            if text == baseline_text:
                continue
            if not re.fullmatch(r"[0-9]?", text):
                return None, "Input error: each cell accepts one digit from 0 to 9 only."
            if position in givens:
                return None, f"Input error: R{row}C{column} is a given and cannot be changed."
            if position in accepted:
                return None, (
                    f"Input error: R{row}C{column} has already been verified. "
                    "Use Clear / reset tests to start again."
                )
            if text not in ("", "0"):
                changes.append((row, column, int(text)))

    if not changes:
        return None, "Input error: enter a value from 1 to 9 in one empty cell."
    if len(changes) > 1:
        return None, "Input error: please test one new cell at a time."
    return changes[0], None


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
st.session_state.setdefault("accepted_values", {})
st.session_state.setdefault("input_locks", {})
st.session_state.setdefault("grid_versions", {})
pending_query = st.session_state.pop("pending_query", None)
if pending_query:
    st.session_state["query_row"], st.session_state["query_column"], st.session_state[
        "query_value"
    ] = pending_query

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
accepted_values = accepted_values_for(selected_index)
input_lock = input_lock_for(selected_index)

st.caption(
    "Blue bold digits are givens; green digits are solver results; purple digits "
    "are values verified in Section 3. The orange outline follows the selected cell."
)
render_board(
    givens,
    current_values,
    accepted_values,
    focus=(query_row, query_column),
)

top_left, top_middle, top_right = st.columns(3)
top_left.metric("Selected cell", f"R{query_row}C{query_column}")
top_middle.metric("Candidate", query_value)
if (query_row, query_column) in givens:
    board_state = f"Given: {givens[(query_row, query_column)]}"
elif (query_row, query_column) in accepted_values:
    board_state = f"Tested: {accepted_values[(query_row, query_column)]}"
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
    "Test as many empty cells as needed. Correct values stay on this test board "
    "and also appear in Section 1; the completed grid from Section 2 is kept separate."
)
row_col, column_col, value_col = st.columns(3)
query_row = int(
    row_col.number_input(
        "Row", min_value=1, max_value=N, key="query_row", disabled=bool(input_lock)
    )
)
query_column = int(
    column_col.number_input(
        "Column", min_value=1, max_value=N, key="query_column",
        disabled=bool(input_lock)
    )
)
query_value = int(
    value_col.number_input(
        "Value", min_value=1, max_value=N, key="query_value", disabled=bool(input_lock)
    )
)

preview_left, preview_middle, preview_right = st.columns(3)
preview_left.metric("Live focus", f"R{query_row}C{query_column}")
preview_middle.metric("Testing value", query_value)
if (query_row, query_column) in givens:
    preview_state = f"Given: {givens[(query_row, query_column)]}"
elif (query_row, query_column) in accepted_values:
    preview_state = f"Tested: {accepted_values[(query_row, query_column)]}"
else:
    preview_state = "Not filled"
preview_right.metric("Current value", preview_state)
render_board(
    givens,
    attempts=accepted_values,
    focus=(query_row, query_column),
)
st.caption(
    "This board contains givens and values accepted during testing only. A full-grid "
    "solution from Section 2 does not fill these empty cells."
)

check_col, reset_col = st.columns(2)
check_pressed = check_col.button(
    "Check entailment", disabled=bool(input_lock), use_container_width=True
)
if reset_col.button("Clear / reset tests", use_container_width=True):
    clear_test_state(selected_index)
    st.rerun()

if check_pressed:
    with st.spinner("Running backward chaining..."):
        verdict, query_seconds = check_entailment(
            selected_index, query_row, query_column, query_value
        )
    store_candidate_result(
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
            f"{query_value} ({query_seconds * 1000:.1f} ms). Input is locked; "
            "use Clear / reset tests to try again."
        )

st.markdown("#### Direct puzzle input")
st.caption(
    "Enter one candidate directly in an empty cell, then press Check grid entry. "
    "Use a single digit from 1 to 9; blank or 0 leaves a cell empty. Blue givens and "
    "purple verified values are protected."
)
grid_version = st.session_state["grid_versions"].get(selected_index, 0)
with st.form(f"direct_grid_form_{selected_index}_{grid_version}"):
    edited_grid = st.data_editor(
        direct_input_grid(givens, accepted_values),
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=True if input_lock else ["Row"],
        column_config={
            "Row": st.column_config.TextColumn("", width="small"),
            **{
                f"C{column}": st.column_config.TextColumn(
                    f"C{column}", width="small", max_chars=1
                )
                for column in range(1, N + 1)
            },
        },
        key=f"direct_grid_{selected_index}_{grid_version}",
    )
    grid_pressed = st.form_submit_button(
        "Check grid entry", disabled=bool(input_lock), use_container_width=True
    )

if grid_pressed:
    direct_entry, input_error = read_direct_entry(
        edited_grid, givens, accepted_values
    )
    if input_error:
        st.error(input_error)
    else:
        direct_row, direct_column, direct_value = direct_entry
        st.session_state["pending_query"] = (
            direct_row, direct_column, direct_value
        )
        with st.spinner("Running backward chaining..."):
            verdict, query_seconds = check_entailment(
                selected_index, direct_row, direct_column, direct_value
            )
        store_candidate_result(
            selected_index,
            direct_row,
            direct_column,
            direct_value,
            verdict,
            query_seconds,
        )
        versions = dict(st.session_state["grid_versions"])
        versions[selected_index] = grid_version + 1
        st.session_state["grid_versions"] = versions
        st.rerun()

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
