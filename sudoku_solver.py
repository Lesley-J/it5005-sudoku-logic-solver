"""IT5005 Assignment 1: student implementation file.

Implement the functions marked below. Do not modify utils.py or logic_.py.
"""

from utils import *
from logic_ import *


# Do not change this function; it is used to create atomic propositions.
def atom(prefix, r, c, v):
    """prefix is 'Is' or 'Not'. Returns the Expr for e.g. Is3_2_4."""
    return expr(f'{prefix}{r}_{c}_{v}')


def build_general_kb(n, box_h, box_w, givens):
    """Return a PropKB encoding this n x n Sudoku's constraints plus the given
    cells, as general clauses.

    Parameters
    ----------
    n, box_h, box_w : int
    givens : dict[(int, int), int]

    Returns
    -------
    PropKB
    """
    
    kb = PropKB()
    values = range(1, n + 1)
    cells = [(r, c) for r in values for c in values]
    
    # when we tried to optimize our algorithm, we found that atom() calls expr()/eval() every time, 
    # and the same symbol is requested repeatedly while building KB
    # so we used memoize() to cache its result, then each symbol will be built only once
    cached_atom = memoize(atom, maxsize=None)

    for r, c in cells:
        # 1: each cell has at least one value
        kb.tell(associate('|', [cached_atom('Is', r, c, v) for v in values]))

        # 2: each cell has at most one value
        for v, w in combinations(values, 2):
            kb.tell(~cached_atom('Is', r, c, v) | ~cached_atom('Is', r, c, w))

    # 3-5: for rows, columns and boxes: no two cells share a same value
    units = ([[(r, c) for c in values] for r in values] +
             [[(r, c) for r in values] for c in values] +
             [[(br + i, bc + j) for i in range(box_h) for j in range(box_w)]
              for br in range(1, n + 1, box_h) for bc in range(1, n + 1, box_w)])
    for unit in units:
        for v in values:
            for (r1, c1), (r2, c2) in combinations(unit, 2):
                kb.tell(~cached_atom('Is', r1, c1, v) | ~cached_atom('Is', r2, c2, v))

    # 6: deal with givens
    for (r, c), v in givens.items():
        kb.tell(cached_atom('Is', r, c, v))

    return kb


def build_definite_kb(n, box_h, box_w, givens):
    """Return a PropDefiniteKB encoding this n x n Sudoku's constraints plus
    the given cells, using elimination + last-candidate reasoning.

    Parameters
    ----------
    n, box_h, box_w : int
    givens : dict[(int, int), int] -- {(row, col): value}, 1-indexed

    Returns
    -------
    PropDefiniteKB
    """
    
    kb = PropDefiniteKB()
    values = range(1, n + 1)
    cells = [(r, c) for r in values for c in values]
    units = ([[(r, c) for c in values] for r in values] +
             [[(r, c) for r in values] for c in values] +
             [[(br + i, bc + j) for i in range(box_h) for j in range(box_w)]
              for br in range(1, n + 1, box_h) for bc in range(1, n + 1, box_w)])
    
    # each symbol can be built only once
    cached_atom = memoize(atom, maxsize=None)
    
    for r, c in cells:
        #rests define other cells in the same row, column or box
        rests = {cell for unit in units if (r, c) in unit for cell in unit}
        rests.discard((r, c))

        for v in values:
            # 2
            for w in values:
                if w != v:
                    kb.tell(cached_atom('Is', r, c, v) | '==>' | cached_atom('Not', r, c, w))

            # 3-5
            for pr, pc in rests:
                kb.tell(cached_atom('Is', r, c, v) | '==>' | cached_atom('Not', pr, pc, v))

    # how to find "is v": the last candidate in a cell after elimination
    for r, c in cells:
        for v in values:
            premises = associate('&', [cached_atom('Not', r, c, w) for w in values if w != v])
            kb.tell(premises | '==>' | cached_atom('Is', r, c, v))

    # how to find "v's place": the last place in a unit after elimination
    for unit in units:
        for v in values:
            for r, c in unit:
                premises = associate('&', [cached_atom('Not', pr, pc, v)
                                           for pr, pc in unit if (pr, pc) != (r, c)])
                kb.tell(premises | '==>' | cached_atom('Is', r, c, v))

    # 6
    for (r, c), v in givens.items():
        kb.tell(cached_atom('Is', r, c, v))
    
    # when we tried to optimize our algorithm, we found that PropDefiniteKB version was scanning KB's every clause on each call
    # then we design a speed-up structure by building a premise index once
    # so each call becomes a dictionary lookup instead of a full scan of all clauses
    premise_index = {}
    for clause in kb.clauses:
        if clause.op == '==>':
            for premise in conjuncts(clause.args[0]):
                premise_index.setdefault(premise, []).append(clause)
    kb.clauses_with_premise = lambda p: premise_index.get(p, [])
    
    return kb


def solve_full_grid_fc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + pl_fc_entails.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    
    kb = build_definite_kb(n, box_h, box_w, givens)
    solved = dict(givens)

    for r in range(1, n + 1):
        for c in range(1, n + 1):
            if (r, c) in givens:
                continue
            value = first(v for v in range(1, n + 1)
                          if pl_fc_entails(kb, atom('Is', r, c, v)))
            if value is not None:
                solved[(r, c)] = value

    return solved


def pl_bc_entails(kb, query):
    """Your own backward-chaining implementation.

    Parameters
    ----------
    kb : PropDefiniteKB
    query : Expr

    Returns
    -------
    bool
    """

    state = getattr(kb, '_bc_proof_state', None)
    if state is None or state['size'] != len(kb.clauses):
        facts = set()
        pairs = []
        symbols = set() 
        
        for clause in kb.clauses:
            
            # we use parse_definite_clause(): split kb clause into antecedents and conclusion/facts
            premises, conclusion = parse_definite_clause(clause)
            symbols.add(conclusion)
            symbols.update(premises)
            
            if premises:
                pairs.append((conclusion, premises))
            else:
                facts.add(conclusion)
                
        # we use multimap(): transfer pairs to {key: [val, ....], ...}
        state = {'size': len(kb.clauses), 'rules': multimap(pairs), 'proved': set(facts), 'num_symbols': len(symbols)} 
        kb._bc_proof_state = state

    rules = state['rules']
    proved = state['proved']
    num_symbols = state['num_symbols'] 

    def search(query):
        # We use an explicit stack instead of recursion, because 
        # during testing we found that 
        # proof chains in this KB might exceed python default recursion limit,
        # and once it did raise a RecursionError
        
        # collect known facts/ already proved
        if query in proved:                      
            return True
        
        failed = set()                      
        
        # we add on_stack tag to avoid circular reasoning
        on_stack = {query}          
        
        stack = [[query, 0, 0]]
        child_result = None                      

        # each step performs either one push or one pop
        # we set the round of loop as 2 * num_symbols + 1, +1 is a buffer setting
        for x in range(2 * num_symbols + 1):
            if not stack:
                break

            frame = stack[-1]
            goal, ri, pi = frame
            goal_rules = rules.get(goal, [])
            
            # if premise proved: go to next premise
            if child_result is True:             
                pi += 1
                
            # if premise failed: try next rule    
            elif child_result is False:          
                ri, pi = ri + 1, 0
            child_result = None

            next_premise = None
            goal_proved = False
            
            for ri in range(ri, len(goal_rules)):
                premises = goal_rules[ri]
                # we use first() to find the first premise that is not proved yet
                k = first((k for k in range(pi, len(premises)) if premises[k] not in proved), None)
                pi = 0    
                       
                if k is None:
                    # if all premises are proved, the goal is proved
                    goal_proved = True           
                    break
                
                # if this rule failed: try next rule 
                elif premises[k] in on_stack or premises[k] in failed:
                    continue                     
                else:
                    frame[1], frame[2] = ri, k
                    next_premise = premises[k]
                    break

            if next_premise is not None:
                stack.append([next_premise, 0, 0])
                on_stack.add(next_premise)
            else:
                stack.pop()
                on_stack.discard(goal)
                if goal_proved:
                    proved.add(goal)
                    child_result = True
                else:
                    failed.add(goal)
                    child_result = False

        return child_result

    # during testing, we found that a goal may also fail just because it was cut by the loop check,
    # not because it is really unprovable
    # so we designed to search again while new symbols keep getting proved; stop when nothing changes.
    for x in range(num_symbols + 1):
        proved_before = len(proved)
        if search(query):
            return True
        elif len(proved) == proved_before:
            return False
        
    return False



def solve_full_grid_bc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + your own pl_bc_entails.

    For each cell, try each candidate value until pl_bc_entails confirms one
    -- the same per-cell strategy as solve_full_grid_fc, but backed by
    backward chaining instead of a single shared forward-chaining pass.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    
    kb = build_definite_kb(n, box_h, box_w, givens)
    solved = dict(givens)

    for r in range(1, n + 1):
        for c in range(1, n + 1):
            if (r, c) in givens:
                continue
            value = first(v for v in range(1, n + 1)
                          if pl_bc_entails(kb, atom('Is', r, c, v)))
            if value is not None:
                solved[(r, c)] = value

    return solved
