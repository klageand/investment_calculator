import os


def get_project_abs_path(project_name: str, current_dir) -> str:
    """Returns absolute path of the project directory. The project directory must be a parent directory of the given
    `current_dir`.

    Args:
        project_name (str): Name of the project
        current_dir (str): Current directory path

    Returns:
        str: Absolute path of the project directory
    """
    # get the absolute path of the parent directory of the current file
    parent_dir = current_dir

    # recursively search for the project directory in the parent directory
    while True:
        project_dir = os.path.join(parent_dir, project_name)
        if os.path.isdir(project_dir):
            break
        parent_dir = os.path.dirname(parent_dir)

    # return the absolute path of the 'project_name' directory
    return os.path.abspath(project_dir)
