"""
nbcomet: Jupyter Notebook extension to track notebook history
"""

import os
import subprocess

def verify_git_repository(directory):
    """
    check is directory is already a git repository
    directory: (str) directory to verify
    """

    if '.git' not in os.listdir(directory):
        p = subprocess.Popen(['git','init','--quiet'], cwd=directory)
        out, err = p.communicate()

def git_commit(fname, dest_dir):
    """
    commit changes to notebook
    fname: (str) notebook filename
    dest_dir: (str) directory to commit
    """
    p1 = subprocess.Popen(["git", "add", fname + ".ipynb"], cwd=dest_dir)
    out, err = p1.communicate()
    p2 = subprocess.Popen(["git", "commit", "-m", "'Commit'", '--quiet'], cwd=dest_dir)
