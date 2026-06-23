import re


def remove_comments_and_docstrings(source):
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return " "
        return s
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )
    result = []
    for line in re.sub(pattern, replacer, source).split('\n'):
        if line.strip():
            result.append(line)
    return '\n'.join(result)


def tree_to_token_index(root_node):
    if len(root_node.children) == 0 or root_node.type == 'string':
        if root_node.type != 'comment':
            return [(root_node.start_point, root_node.end_point)]
        return []
    tokens = []
    for child in root_node.children:
        tokens += tree_to_token_index(child)
    return tokens


def tree_to_variable_index(root_node, index_to_code):
    if len(root_node.children) == 0 or root_node.type == 'string':
        if root_node.type == 'comment':
            return []
        index = (root_node.start_point, root_node.end_point)
        _, code = index_to_code[index]
        if root_node.type != code:
            return [index]
        return []
    tokens = []
    for child in root_node.children:
        tokens += tree_to_variable_index(child, index_to_code)
    return tokens


def index_to_code_token(index, code_lines):
    start_point = index[0]
    end_point = index[1]
    if start_point[0] == end_point[0]:
        return code_lines[start_point[0]][start_point[1]:end_point[1]]
    s = code_lines[start_point[0]][start_point[1]:]
    for i in range(start_point[0] + 1, end_point[0]):
        s += code_lines[i]
    s += code_lines[end_point[0]][:end_point[1]]
    return s
