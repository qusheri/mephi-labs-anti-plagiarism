# DFG parser for C++ — adapted from microsoft/CodeBERT DFG_java
# Node names verified against tree-sitter-cpp grammar.

from dfg_utils import tree_to_variable_index


def DFG_cpp(root_node, index_to_code, states):
    """
    Build a Data Flow Graph for C++ code parsed by tree-sitter-cpp.

    Returns:
        (DFG, states)
        DFG  — list of tuples: (var_name, token_idx, relation, [src_names], [src_idxs])
        states — dict mapping var_name -> [token_idx]  (last known definition)

    Relations:
        'comesFrom'   — variable USE: whose value comes from an earlier definition
        'computedFrom'— variable DEF: whose value is computed from rhs variables
    """
    # ---- node type lists (verified against tree-sitter-cpp AST) ----
    assignment_nodes    = ['assignment_expression']           # x=y  sum+=arr[i]
    def_nodes           = ['init_declarator']                 # int x = expr
    increment_nodes     = ['update_expression']               # i++  --j
    if_nodes            = ['if_statement', 'else_clause']
    for_nodes           = ['for_statement']
    while_nodes         = ['while_statement']

    states = states.copy()

    # ------------------------------------------------------------------ leaf
    if len(root_node.children) == 0 or root_node.type == 'string':
        if root_node.type == 'comment':
            return [], states
        idx, code = index_to_code[(root_node.start_point, root_node.end_point)]
        # punctuation / keyword: token text == node type → skip
        if root_node.type == code:
            return [], states
        if code in states:
            return [(code, idx, 'comesFrom', [code], states[code].copy())], states
        if root_node.type == 'identifier':
            states[code] = [idx]
        return [(code, idx, 'comesFrom', [], [])], states

    # ------------------------------------------------------------------ int x = expr
    elif root_node.type in def_nodes:
        name  = root_node.child_by_field_name('declarator')   # identifier
        value = root_node.child_by_field_name('value')        # rhs expression
        DFG = []
        if value is None:
            # declaration without initializer: int x;
            for index in tree_to_variable_index(name, index_to_code):
                idx, code = index_to_code[index]
                DFG.append((code, idx, 'comesFrom', [], []))
                states[code] = [idx]
            return sorted(DFG, key=lambda x: x[1]), states
        else:
            name_idxs  = tree_to_variable_index(name,  index_to_code)
            value_idxs = tree_to_variable_index(value, index_to_code)
            temp, states = DFG_cpp(value, index_to_code, states)
            DFG += temp
            for i1 in name_idxs:
                idx1, code1 = index_to_code[i1]
                for i2 in value_idxs:
                    idx2, code2 = index_to_code[i2]
                    DFG.append((code1, idx1, 'comesFrom', [code2], [idx2]))
                states[code1] = [idx1]
            return sorted(DFG, key=lambda x: x[1]), states

    # ------------------------------------------------------------------ x = y   sum += arr[i]
    elif root_node.type in assignment_nodes:
        left  = root_node.child_by_field_name('left')
        right = root_node.child_by_field_name('right')
        DFG = []
        temp, states = DFG_cpp(right, index_to_code, states)
        DFG += temp
        name_idxs  = tree_to_variable_index(left,  index_to_code)
        value_idxs = tree_to_variable_index(right, index_to_code)
        for i1 in name_idxs:
            idx1, code1 = index_to_code[i1]
            for i2 in value_idxs:
                idx2, code2 = index_to_code[i2]
                DFG.append((code1, idx1, 'computedFrom', [code2], [idx2]))
            states[code1] = [idx1]
        return sorted(DFG, key=lambda x: x[1]), states

    # ------------------------------------------------------------------ i++  --j
    elif root_node.type in increment_nodes:
        DFG = []
        idxs = tree_to_variable_index(root_node, index_to_code)
        for i1 in idxs:
            idx1, code1 = index_to_code[i1]
            for i2 in idxs:
                idx2, code2 = index_to_code[i2]
                DFG.append((code1, idx1, 'computedFrom', [code2], [idx2]))
            states[code1] = [idx1]
        return sorted(DFG, key=lambda x: x[1]), states

    # ------------------------------------------------------------------ if / else_clause
    elif root_node.type in if_nodes:
        DFG = []
        current_states = states.copy()
        others_states  = []
        flag = False
        tag  = 'else' in root_node.type   # True when we ARE an else_clause

        for child in root_node.children:
            if 'else' in child.type:
                tag = True
            if child.type not in if_nodes and not flag:
                temp, current_states = DFG_cpp(child, index_to_code, current_states)
                DFG += temp
            else:
                flag = True
                temp, new_states = DFG_cpp(child, index_to_code, states)
                DFG += temp
                others_states.append(new_states)

        others_states.append(current_states)
        if not tag:
            others_states.append(states)

        new_states = {}
        for dic in others_states:
            for key, val in dic.items():
                if key not in new_states:
                    new_states[key] = val.copy()
                else:
                    new_states[key] += val
        for key in new_states:
            new_states[key] = sorted(set(new_states[key]))

        return sorted(DFG, key=lambda x: x[1]), new_states

    # ------------------------------------------------------------------ for (init; cond; update) body
    elif root_node.type in for_nodes:
        DFG = []
        # First pass: full traversal
        for child in root_node.children:
            temp, states = DFG_cpp(child, index_to_code, states)
            DFG += temp
        # Second pass: re-process everything after the 'declaration' initializer
        # to capture loop-carried dependencies (same strategy as DFG_java)
        flag = False
        for child in root_node.children:
            if flag:
                temp, states = DFG_cpp(child, index_to_code, states)
                DFG += temp
            elif child.type == 'declaration':
                flag = True

        # Deduplicate edges
        dic = {}
        for x in DFG:
            key = (x[0], x[1], x[2])
            if key not in dic:
                dic[key] = [x[3], x[4]]
            else:
                dic[key][0] = list(set(dic[key][0] + x[3]))
                dic[key][1] = sorted(set(dic[key][1] + x[4]))
        DFG = [(k[0], k[1], k[2], v[0], v[1]) for k, v in sorted(dic.items(), key=lambda t: t[0][1])]
        return sorted(DFG, key=lambda x: x[1]), states

    # ------------------------------------------------------------------ while (cond) body
    elif root_node.type in while_nodes:
        DFG = []
        # Two passes to capture loop-carried deps
        for _ in range(2):
            for child in root_node.children:
                temp, states = DFG_cpp(child, index_to_code, states)
                DFG += temp

        dic = {}
        for x in DFG:
            key = (x[0], x[1], x[2])
            if key not in dic:
                dic[key] = [x[3], x[4]]
            else:
                dic[key][0] = list(set(dic[key][0] + x[3]))
                dic[key][1] = sorted(set(dic[key][1] + x[4]))
        DFG = [(k[0], k[1], k[2], v[0], v[1]) for k, v in sorted(dic.items(), key=lambda t: t[0][1])]
        return sorted(DFG, key=lambda x: x[1]), states

    # ------------------------------------------------------------------ all other nodes: recurse
    else:
        DFG = []
        for child in root_node.children:
            temp, states = DFG_cpp(child, index_to_code, states)
            DFG += temp
        return sorted(DFG, key=lambda x: x[1]), states
