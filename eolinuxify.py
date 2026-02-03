import os
import json
import glob
import subprocess
import click
import termcolor


def ensure_git_repo():
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        print(termcolor.colored("Error: not a git repository.", "red"))
        exit(1)


def get_included_files():
    result = subprocess.run(
        ["git", "ls-files", "--others", "--cached", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(termcolor.colored("Error: failed to list git files.", "red"))
        if result.stderr:
            print(result.stderr.strip())
        exit(1)
    return [line for line in result.stdout.splitlines() if line.strip() != ""]


def has_any_crlf(root, relpath):
    with open(os.path.join(root, relpath), "rb") as f:
        contents = f.read()
    if b"\r\n" in contents:
        return True
    return False


def fix_file(root, relpath):
    with open(os.path.join(root, relpath), "rb") as f:
        contents = f.read()
    contents = contents.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    with open(os.path.join(root, relpath), "wb") as f:
        f.write(contents)


def get_config():
    config_path = os.path.join(os.getcwd(), "eolinuxify.json")
    config = {"exclude": []}
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
    return config


def is_matched_by_glob(root, relpath, relglob_pattern):
    """
    Check if any files match a glob pattern within a directory relative to a root directory.

    Args:
        root (str): Root directory.
        relpath (str): Relative path from the root directory.
        relglob_pattern (str): Glob pattern to match files.

    Returns:
        bool: True if files are matched by the glob pattern, False otherwise.
    """
    abs_path = os.path.normpath(os.path.join(root, relpath))
    glob_pattern = os.path.normpath(os.path.join(root, relglob_pattern))
    matching_files = glob.glob(glob_pattern)
    return abs_path in (matching_files if matching_files else [])


@click.command()
@click.option("-y","--yes",is_flag=True,required=False,default=False)
def main(yes):
    """
    Normalizes the line endings of all the source code files in the current directory
    Source files are determined using `git ls-files`
    """
    CWD = os.getcwd()
    ensure_git_repo()
    included_files = get_included_files()
    config = get_config()
    exclude = config.get("exclude", [])
    included_files = [
        file for file in included_files if not any(
            is_matched_by_glob(CWD, file, pattern) for pattern in exclude
        )
    ]
    found_crlf = []
    for file in included_files:
        try:
            if has_any_crlf(CWD, file):
                found_crlf.append(file)
        except Exception as e:
            print(str(e))
    if len(found_crlf) == 0:
        print("All source files have proper line endings (LF), no files to fix")
        exit(0)

    print(f"Found {len(found_crlf)} files with CRLF line endings:")
    for file in found_crlf:
        print(f"  {file}")
    if (not yes) and (not click.confirm("Do you want to fix these files?")):
        print("Aborting")
        return
    for file in found_crlf:
        try:
            print(f'Normalizing eol in file "{file}" to LF...', end="")
            fix_file(CWD, file)
            print(" done")
        except Exception as e:
            print(e)
    os.chdir(CWD)


if __name__ == "__main__":
    main()
