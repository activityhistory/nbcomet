"""
NBComet: Jupyter Notebook extension to track full notebook history
"""

import os
import nbformat

# TODO see if we can use nbdime to do diff, or continue using our own code

def get_nb_diff(action_data, dest_fname, compare_outputs = False):
    """
    find diff between two notebooks

    action_data: (dict) new notebook data to compare
    dest_fname: (str) name of file to compare to
    compare_outputs: (bool) compare cell outputs, or just the sources
    """

    # don't even compare if the old version of the notebook does not exist
    if not os.path.isfile(dest_fname):
        diff = {}
        cell_order = []

        nb_b = action_data['model']['cells']
        if valid_ids([], nb_b):
            cell_order = [c['metadata']['comet_cell_id'] for c in nb_b]
        else:
            cell_order = list(range(len(nb_b)))
        return diff, cell_order

    nb_a = nbformat.read(dest_fname, nbformat.NO_CONVERT)['cells']
    nb_b = action_data['model']['cells']
    diff = {}
    cell_order = []

    # either use a diff method based on cell ids
    if valid_ids(nb_a, nb_b):
        nb_a_cell_ids = [c['metadata']['comet_cell_id'] for c in nb_a]
        nb_b_cell_ids = [c['metadata']['comet_cell_id'] for c in nb_b]
        cell_order = nb_b_cell_ids

        for i in nb_b_cell_ids:
            # if it is a cell id seen in prior nb, check if contents changed
            if i in nb_a_cell_ids:
                # get the old and new cell contents
                cell_a = nb_a[nb_a_cell_ids.index(i)]
                cell_b = nb_b[nb_b_cell_ids.index(i)]
                if cells_different(cell_a, cell_b, compare_outputs):
                    diff[i] = cell_b
            # the cell is entirely new, so it is part of the diff
            else:
                diff[i] = nb_b[nb_b_cell_ids.index(i)]

    # or if no cell ids, rely on more targeted method based on type of action
    else:
        action = action_data['name']
        selected_index = action_data['index']
        selected_indices = action_data['indices']
        cell_order = list(range(len(nb_b)))

        check_indices = indices_to_check(action, selected_index,
                                        selected_indices, nb_a, nb_b)
        for i in check_indices:
            # don't compare cells that don't exist in the current notebook
            if i >= len(nb_b):
                continue
            # if its a new cell at the end of the nb, it is part of the diff
            elif i >= len(nb_a):
                diff[i] = nb_b[i]
            else:
                cell_a = nb_a[i]
                cell_b = nb_b[i]
                if cells_different(cell_a, cell_b, compare_outputs):
                    diff[i] = cell_b
    return diff, cell_order

def valid_ids(nb_a, nb_b):
    """
    Ensure each notebook we are comparing has a full set of unique cell ids

    nb_a: (dict) one notebook to compare
    nb_b: (dict) the other notebook to compare
    """

    prior_a_ids = []
    prior_b_ids = []

    for c in nb_a:
        if "comet_cell_id" not in c["metadata"]:
            return False
        elif c["metadata"]["comet_cell_id"] in prior_a_ids:
            return False
        else:
            prior_a_ids.append(c["metadata"]["comet_cell_id"])

    for c in nb_b:
        if "comet_cell_id" not in c["metadata"]:
            return False
        elif c["metadata"]["comet_cell_id"] in prior_b_ids:
            return False
        else:
            prior_b_ids.append(c["metadata"]["comet_cell_id"])

    return True

def cells_different(cell_a, cell_b, compare_outputs):
    # check if cell type or source is different
    if (cell_a["cell_type"] != cell_b["cell_type"]
        or cell_a["source"] != cell_b["source"]):
        return True

    # otherwise compare outputs if it is a code cell
    elif compare_outputs and cell_b["cell_type"] == "code":
        # get the outputs
        cell_a_outs = cell_a['outputs']
        cell_b_outs = cell_b['outputs']
        # if different number of outputs, the cell has changed
        if len(cell_a_outs) != len(cell_b_outs):
            return True
        # compare the outputs one by one
        for j in range(len(cell_b_outs)):
            # check that the output type matches
            if cell_b_outs[j]['output_type'] != cell_a_outs[j]['output_type']:
                return True
            # and that the relevant data matches
            elif((cell_a_outs[j]['output_type'] in ["display_data","execute_result"]
                and cell_a_outs[j]['data'] != cell_b_outs[j]['data'])
                or (cell_a_outs[j]['output_type'] == "stream"
                and cell_a_outs[j]['text'] != cell_b_outs[j]['text'])
                or (cell_a_outs[j]['output_type'] == "error"
                and cell_a_outs[j]['evalue'] != cell_b_outs[j]['evalue'])):
                return True

    return False

def indices_to_check(action, selected_index, selected_indices, nb_a, nb_b):
    """
    Identify which notebook cells may have changed based on the type of action
    action: (str) action name
    selected_index: (int) single selected cell
    selected_indices: (list of ints) all selected cells
    nb_a: (dict) one notebook to compare
    nb_b: (dict) the other notebook to compare
    """

    len_a = len(nb_a)
    len_b = len(nb_b)

    # actions that apply to all selected cells
    if action in['run-cell', 'clear-cell-output', 'change-cell-to-markdown',
                'change-cell-to-code', 'change-cell-to-raw',
                'toggle-cell-output-collapsed', 'toggle-cell-output-scrolled']:
        return [x for x in selected_indices]

    # actions that apply to all selected cells, and the next one
    elif action in ['run-cell-and-insert-below','run-cell-and-select-next']:
        ind = [x for x in selected_indices]
        ind.append(selected_indices[-1] + 1)
        return ind

    # actions that apply to the cell before or after first or last selected cell
    elif action in ['insert-cell-above']:
        return [selected_indices[0]]
    elif action in ['insert-cell-below']:
        return [selected_indices[-1] + 1]

    # actions that may insert multiple cells
    elif action in ['paste-cell-above']:
        start = selected_indices[0] # first cell in selection
        num_inserted = len_b - len_a
        return [x for x in range(start, start + num_inserted)]
    elif action in ['paste-cell-below']:
        start = selected_indices[-1] + 1 # first cell after last selected
        num_inserted = len_b - len_a
        return [x for x in range(start, start + num_inserted)]
    elif action in ['paste-cell-replace']:
        start = selected_indices[0] # first cell in selelction
        num_inserted = len_b - len_a + len(selected_indices)
        return [x for x in range(start, start + num_inserted)]

    # actions to move groups of cells up and down
    elif action in ['move-cell-down']:
        if selected_indices[-1] < len_b-1:
            ind = [x for x in selected_indices]
            ind.append(selected_indices[-1] + 1)
            return ind
        else:
            return []
    elif action in ['move-cell-up']:
        if selected_index == 0:
            return []
        else:
            ind = [x for x in selected_indices]
            ind.append(selected_indices[0] - 1)
            return ind

    # split, merege, and selection
    elif action in ['merge-cell-with-next-cell', 'unselect-cell']:
        return [selected_index]
    elif action in ['merge-cell-with-previous-cell']:
        return [max([0, selected_index-1])]
    elif action in ['merge-selected-cells','merge-cells']:
        return min(selected_indices)
    elif action in ['split-cell-at-cursor']:
        return [selected_indices[0], selected_index + 1]

    # actions applied to all cells in the notebook, or could affect all cells
    elif action in ['run-all-cells','restart-kernel-and-clear-output',
                    'confirm-restart-kernel-and-run-all-cells']:
        return [x for x in range(len_b)]

    # actions applied to all cells above or below the selected one
    elif action in ['run-all-cells-above']:
        return [x for x in range(selected_index)]
    elif action in ['run-all-cells-below']:
        return [x for x in range(selected_index, len_b)]

    # special case for undo deletion which could put a new cell anywhere
    elif action in ['undo-cell-deletion']:
        num_inserted = len_b - len_a
        if num_inserted > 0:
            first_diff = 0
            for i in range(len_b):
                # a new cell at the end of the nb
                if i >= len(nb_a):
                    first_diff = i
                    return range(first_diff, first_diff + num_inserted)
                elif nb_a[i]["source"] != nb_b[i]["source"]:
                    first_diff = i
                    return range(first_diff, first_diff + num_inserted)

    # do nothing for remaining acitons such as delete-cell, cut-cell
    else:
        return []
