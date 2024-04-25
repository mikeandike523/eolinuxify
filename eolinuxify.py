import os
import tempfile

from gitignore_parser import parse_gitignore
import click
import termcolor

def repair_gitignore_contents(contents):
    """
    Identifies and corrects two simple patterns that indicate that an entire folder should be ignored
    and skipped during file discovery

    Some people follow the convention to describe only the files that get ignored
    but never put a directory name directly in gitignore
    This function identifies those patterns and transforms the back into an ignore of the directory itself
    This then flags the files discovered algorithm to skip the directory and not list its contents


    NOTE:
    I can not fully ensure the correctness of this heuristic
    however it should at least work for most cases

    TODO:
    Add command line option to disable this heuristic
    this may incur a slight performance hit since for example, it may need to go through each item in
    node_modules to see if it ignored, just because the user wrote something such as "node_modules/*"
    """

    lines = contents.splitlines()
    lines = [line.strip() for line in lines]
    lines = [line for line in lines if not line == ""]
    lines = [line for line in lines if not line.startswith("#")]
    lines = [(line[:-3] if line.endswith("/**") or line.endswith("\\**") else line) for line in lines]
    lines = [(line[:-2] if line.endswith("/*") or line.endswith("\\*") else line) for line in lines]
    return "\n".join(lines)


def chain_is_ignored(root,last_dir,previous,current):
    rp = os.path.relpath(last_dir,root) if os.path.isabs(last_dir) else last_dir
    if rp == ".":
        rp = ""
    def f(x):
        if rp == "":
            return current(x)
        return previous(os.path.join(rp,x)) or current(x)
    return f


def get_included_files():
    root = os.getcwd()
    result=[]
    def recursion(chained=lambda x: x==".git"):
        last = os.getcwd()
        if ".gitignore" in os.listdir():
            with open(".gitignore") as f:
                contents = f.read()
                contents = repair_gitignore_contents(contents)
            with tempfile.NamedTemporaryFile() as f:
                f.write(contents.encode("utf-8"))
                f.flush()
                ignorer = parse_gitignore(f.name)
            is_ignored = chain_is_ignored(root, os.getcwd(),chained,lambda x: os.path.basename(x)==".git" or ignorer(
                os.path.join(os.path.join(os.path.dirname(f.name)),os.path.relpath(x,root))
            ))
        else:
            is_ignored = chain_is_ignored(root, os.getcwd(),chained,lambda x: os.path.basename(x)==".git")
        files = list(os.listdir(os.getcwd()))
        for file in files:
            fullpath = os.path.join(os.getcwd(), file)
            if is_ignored(fullpath):
                continue
            if os.path.isdir(fullpath):
                os.chdir(fullpath)
                recursion(is_ignored)
                os.chdir(last)
            else:
                result.append(os.path.relpath(fullpath,root))
    recursion()
    os.chdir(root)
    return result

def has_any_crlf(root, relpath):
    with open(os.path.join(root, relpath),"rb") as f:
        contents = f.read()
    if b"\r\n" in contents:
        return True
    return False
                 

def fix_file(root, relpath):
    with open(os.path.join(root, relpath),"rb") as f:
        contents = f.read()
    contents = contents.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    with open(os.path.join(root, relpath), "wb") as f:
        f.write(contents)
    

def main():
    CWD = os.getcwd()
    included_files = get_included_files()
    found_crlf = [file for file in included_files if has_any_crlf(CWD,file)]

    print(f"Found {len(found_crlf)} files with CRLF line endings:")
    for file in found_crlf:
        print(f"  {file}")
    if not click.confirm("Do you want to fix these files?"):
        print("Aborting")
        return
    for file in found_crlf:
        print(f"Normalizing eol in file \"{file}\" to LF...",end="")
        fix_file(CWD, file)
        print(" done")
    os.chdir(CWD)

if __name__ == "__main__":
    main()