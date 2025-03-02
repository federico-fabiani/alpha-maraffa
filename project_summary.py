import os
import ast

def extract_info_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        tree = ast.parse(file.read(), filename=file_path)

    # Extracting information from the abstract syntax tree (AST)
    file_structure = []
    constants = []
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            file_structure.append(('Class', node.name))
        elif isinstance(node, ast.FunctionDef):
            functions.append(('Function', node.name))
            docstring = ast.get_docstring(node)
            if docstring:
                functions.append(('Docstring', docstring))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants.append(('Constant', target.id))

    return file_structure, constants, functions

def traverse_project(directory):
    project_info = {}

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, directory)
                file_structure, constants, functions = extract_info_from_file(file_path)
                
                project_info[relative_path] = {
                    'file_structure': file_structure,
                    'constants': constants,
                    'functions': functions,
                }

    return project_info

if __name__ == "__main__":
    project_directory = r'D:\Workspace\alpha-maraffa\src\aimarafone'
    project_info = traverse_project(project_directory)

    # Printing the collected information
    for file_path, info in project_info.items():
        print(f"File: {file_path}")
        print("File Structure:")
        for entry_type, name in info['file_structure']:
            print(f"  {entry_type}: {name}")

        print("Constants:")
        for entry_type, name in info['constants']:
            print(f"  {entry_type}: {name}")

        print("Functions:")
        for entry_type, name_or_docstring in info['functions']:
            print(f"  {entry_type}: {name_or_docstring}")

        print("\n")
