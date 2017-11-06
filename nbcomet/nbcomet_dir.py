"""
nbcomet: Jupyter Notebook extension to track notebook history
"""

import os
import json
import datetime
from hashlib import sha1

def find_storage_dir():
    storage_dir = default_storage_dir()
    filename = os.path.expanduser('~/.jupyter/nbconfig/notebook.json')
    if os.path.isfile(filename):
        with open(filename) as data_file:
            data = json.load(data_file)
            try:
                if data["Comet"]["data_directory"]:
                    storage_dir = data["Comet"]["data_directory"]
            except:
                pass
    if not os.path.exists(storage_dir):
        create_dir(storage_dir)
    return storage_dir

def default_storage_dir():
    return os.path.expanduser('~/.jupyter/nbcomet')

def create_dir(directory):
    try:
        os.makedirs(directory)
    except OSError:
        pass

def was_saved_recently(version_dir, min_time=300):
    """ check if a previous version of the file has been saved recently

    version_dir: (str) dir to look for previous versions
    min_time: (int) minimum time in seconds allowed between saves """

    versions = [f for f in os.listdir(version_dir)
        if os.path.isfile(os.path.join(version_dir, f))
        and f[-6:] == '.ipynb']
    if len(versions) > 0:
        vdir, vname = os.path.split(versions[-1])
        vname, vext = os.path.splitext(vname)
        last_time_saved = datetime.datetime.strptime(vname[-26:],
            "%Y-%m-%d-%H-%M-%S-%f")
        delta = (datetime.datetime.now() - last_time_saved).seconds
        return delta <= min_time
    else:
        return False

def hash_path(path):
    h = sha1(path.encode())
    return h.hexdigest()[0:8] #only need first 8 chars to be uniquely identified
