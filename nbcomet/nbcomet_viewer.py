"""
NBComet: Jupyter Notebook extension to track full notebook history
"""

import os
import time
import json
import datetime
import nbformat
import pickle

from nbcomet.nbcomet_sqlite import get_viewer_data
from nbcomet.nbcomet_diff import valid_ids

# TODO use html / javascript templates for page rather than injecting code here
# TODO package current view as "timeline" view that only needs metadata
# TODO build separate history view that linearly renders every version cell that
# was executed, cells should not be editable
# TODO build smart collapsing of history view for redundant cell executions
# TODO build minimap that shows where edited or run cell is in notebook

def get_prior_filenames(nb, hashed_path, fname):
    # get the history of names this file has had
    # returns [[name, start_time, end_time], ...]

    if "comet_paths" in nb["metadata"]:
        prior_names = nb['metadata']['comet_paths']
    else:
        prior_names = [[os.path.join(hashed_path, fname), 0]]

    # get time range when file had each name
    for i, v in enumerate(prior_names):
        if i == len(prior_names) - 1:
            v.append(int(time.time()*1000))
        else:
            v.append(prior_names[i+1][1])

    return prior_names

def get_action_data(data_dir, prior_names):
    # get the notebook actions in each range
    total_dels = 0
    total_runs = 0
    total_time = 0
    all_actions = []

    # get the high-level overview about nb use
    for n in prior_names:
        hp = n[0].split('/')[0]
        fn = n[0].split('/')[1].split('.')[0]
        start_time = n[1]
        end_time = n[2]

        try:
            db = os.path.join(data_dir, hp, fn, fn + ".db")
            d, r, t, actions = get_viewer_data(db, start_time, end_time)

            total_dels += d
            total_runs += r
            total_time += t
            for a in actions:
                all_actions.append(list(a))
        except:
            print("Had trouble accesing db")

    return total_dels, total_runs, total_time, all_actions

def get_saved_versions(prior_names, data_dir, all_actions):
    # get the notebook versions that fall in our specified ranges for each file
    versions = []
    for n in prior_names:
        hp = n[0].split('/')[0]
        fn = n[0].split('/')[1].split('.')[0]

        # get all the versions of the notebook sharing this name
        version_dir = os.path.join(data_dir, hp, fn, 'versions')
        if os.path.isdir(version_dir):
            versions_with_this_name = [ f for f in os.listdir(version_dir)
                if os.path.isfile(os.path.join(version_dir, f))
                and f[-6:] == '.ipynb']

            # filter this list to only those in the correct time frame
            for v in versions_with_this_name:
                try:
                    nb_time = datetime.datetime.strptime(v[-32:-6],
                        "%Y-%m-%d-%H-%M-%S-%f")
                    start_time = datetime.datetime.fromtimestamp(n[1]/1000) - datetime.timedelta(seconds=1)
                    end_time = datetime.datetime.fromtimestamp(n[2]/1000)
                    if nb_time <= end_time and nb_time >= start_time:
                        versions.append(os.path.join(hp, fn, 'versions', v))
                except:
                    print("Trouble checking time of file versions")
    return versions

def get_activity_gaps(versions):
    #TODO return the seconds of the gap
    gaps = []
    for i, v in enumerate(versions):
        # look for gaps of over 15 min in activity

        if i > 0:
            try:
                current_nb_time = datetime.datetime.strptime(v[-32:-6],
                    "%Y-%m-%d-%H-%M-%S-%f")
                past_nb_time = datetime.datetime.strptime(versions[i-1][-32:-6],
                    "%Y-%m-%d-%H-%M-%S-%f")
                time_diff = current_nb_time - past_nb_time
                if time_diff.total_seconds() >= 15 * 60:
                    gaps.append([i, time_diff.total_seconds()])
            except:
                print("Trouble checking version time to determine gaps in activity")
    return gaps

def get_cell_data(data_dir, versions, vi, all_actions, last_change):
    cell_data = []

    nb_b_path = os.path.join(data_dir, versions[vi])
    nb_b = nbformat.read(nb_b_path, nbformat.NO_CONVERT)['cells']

    # get ids of next nb
    next_cell_ids = []
    if vi < len(versions) - 1:
        nb_c_path = nb_b_path = os.path.join(data_dir, versions[vi + 1])
        nb_c = nbformat.read(nb_c_path, nbformat.NO_CONVERT)['cells']

        for i, c in enumerate(nb_c):
            # get the cell id
            try:
                cell_id = c.metadata.comet_cell_id
            except:
                cell_id = i
            next_cell_ids.append(cell_id)

    for i, c in enumerate(nb_b):
        # get the cell id
        try:
            cell_id = c.metadata.comet_cell_id
        except:
            cell_id = i

        # get the cell type
        # cells can have multiple outputs , each with a different type
        # here we track the "highest" level output with
        # error > display_data > execute result > stream
        cell_type = c.cell_type
        if c.cell_type == "code":
            output_types = [x.output_type for x in c.outputs]
            if "error" in output_types:
                cell_type = "error"
            elif "display_data" in output_types:
                cell_type = "display_data"
            elif "execute_result" in output_types:
                cell_type = "execute_result"
            elif "stream" in output_types:
                cell_type = "stream"

        # if a new notebook, or we have not seen the cell before
        if vi == 0 or cell_id not in last_change:
            new_source = c.source
            last_change[cell_id] = [vi, c.source]
            last_source = 'false'
        # but if we have seen this cell before
        else:
            if last_change[cell_id][1] == c.source:
                new_source = 'false'
                last_source = last_change[cell_id][0]
            else:
                new_source = c.source
                last_source = last_change[cell_id][0]
                last_change[cell_id] = [vi, c.source]
        # get deleted metric
        if vi == len(versions) - 1:
            deleted = 'false'
        elif cell_id in next_cell_ids:
            deleted = 'false'
        else:
            deleted = 'true'

        cell_data.append( [cell_id, cell_type, new_source, last_source, deleted] )

    return cell_data, last_change

def get_version_data(data_dir, versions, all_actions):
    version_data = []
    last_change = {}

    for i, v in enumerate(versions):

        # get name and time of nb version
        nb_name = v[0:-33].split('/')[-1] + '.ipynb'
        current_nb_time = datetime.datetime.strptime(v[-32:-6],
            "%Y-%m-%d-%H-%M-%S-%f")
        current_nb_time_str = datetime.datetime.strftime(current_nb_time,
            "%a %b %d, %Y - %-I:%M %p")
        cell_data, last_change = get_cell_data(data_dir, versions, i, all_actions, last_change)

        # set up our version document
        v_data = {'num': i,
                'name': nb_name,
                'time': current_nb_time_str,
                'cells': cell_data};

        version_data.append(v_data)

    return version_data

def get_viewer_html(data_dir, hashed_path, fname):
    # get paths to files and databases
    nb_path = os.path.join(data_dir, hashed_path, fname, fname + '.ipynb')
    nb = nbformat.read(nb_path, nbformat.NO_CONVERT)

    # get names, actions, and versions for this
    prior_names = get_prior_filenames(nb, hashed_path, fname)
    total_dels, total_runs, total_time, all_actions = get_action_data(data_dir, prior_names)
    versions = get_saved_versions(prior_names, data_dir, all_actions)

    # set up json datastructure
    data = {'name': fname,
            'editTime': total_time,
            'numRuns': total_runs,
            'numDeletions': total_dels,
            'gaps': [],
            'versions':[]};

    # get data for each version
    if len(versions) > 0:
        data['gaps'] = get_activity_gaps(versions)
        data['versions'] = get_version_data(data_dir, versions, all_actions)

    return data
