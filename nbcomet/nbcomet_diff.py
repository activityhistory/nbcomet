"""
nbcomet: Jupyter Notebook extension to track notebook history
"""

import os
import nbformat

def get_diff_at_indices(indices, action_data, dest_fname,
                        compare_outputs = False):
    """
    look for diff at particular indices
    indices: (list) cell indices to compare
    action_data: (dict) new notebook data to compare
    dest_fname: (str) name of file to compare to
    compare_outputs: (bool) compare cell outputs
    """

    diff = {}

    # if there is no prior notebook to compare to, we cannot generate a diff
    if not os.path.isfile(dest_fname):
        return diff

    prior_nb = nbformat.read(dest_fname, nbformat.NO_CONVERT)['cells']
    current_nb = action_data['model']['cells']

    # for all other action types
    for i in indices:
        # compare source
        if i >= len(current_nb):
            break # don't compare cells that don't exist
        # its a new cell at the end of the nb
        if i >= len(prior_nb):
            diff[i] = current_nb[i]
        elif (prior_nb[i]["cell_type"] != current_nb[i]["cell_type"]
            or prior_nb[i]["source"] != current_nb[i]["source"]):
            diff[i] = current_nb[i]
        # compare outputs
        elif compare_outputs and current_nb[i]["cell_type"] == "code":
            prior_outs = prior_nb[i]['outputs']
            current_outs = current_nb[i]['outputs']
            if len(prior_outs) != len(current_outs):
                diff[i] = current_nb[i]
                break
            for j in range(len(current_outs)):
                # check that the output type matches
                if prior_outs[j]['output_type'] != current_outs[j]['output_type']:
                    diff[i] = current_nb[i]
                # and that the relevant data matches
                elif((prior_outs[j]['output_type'] in ["display_data","execute_result"]
                    and prior_outs[j]['data'] != current_outs[j]['data'])
                    or (prior_outs[j]['output_type'] == "stream"
                    and prior_outs[j]['text'] != current_outs[j]['text'])
                    or (prior_outs[j]['output_type'] == "error"
                    and prior_outs[j]['evalue'] != current_outs[j]['evalue'])):
                    diff[i] = current_nb[i]
    return diff

def indices_to_check(action, selected_index, selected_indices, len_current,
                    len_prior):
    """
    Identify which notebook cells may have changed based on the type of action
    action: (str) action name
    selected_index: (int) single selected cell
    selected_indices: (list of ints) all selected cells
    len_current: (int) length in cells of the notebook we are comparing
    """

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
        num_inserted = len_current - len_prior
        return [x for x in range(start, start + num_inserted)]
    elif action in ['paste-cell-below']:
        start = selected_indices[-1] + 1 # first cell after last selected
        num_inserted = len_current - len_prior
        return [x for x in range(start, start + num_inserted)]
    elif action in ['paste-cell-replace']:
        start = selected_indices[0] # first cell in selelction
        num_inserted = len_current - len_prior + len(selected_indices)
        return [x for x in range(start, start + num_inserted)]

    # actions to move groups of cells up and down
    elif action in ['move-cell-down']:
        if selected_indices[-1] < len_current-1:
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
                    'confirm-restart-kernel-and-run-all-cells',
                    'undo-cell-deletion']:
        return [x for x in range(len_current)]

    # actions applied to all cells above or below the selected one
    elif action in ['run-all-cells-above']:
        return [x for x in range(selected_index)]
    elif action in ['run-all-cells-below']:
        return [x for x in range(selected_index, len_current)]

    # remaining acitons such as delete-cell, cut-cell
    else:
        return []

def get_action_diff(action_data, dest_fname):
    """
    Get a modified diff when saving the diff caused by an action
    accounts for special cases with copy / paste and undo-cell-deletion
    action_data: (dict) new notebook data to compare
    dest_fname: (str) name of file to compare to
    """
    if not os.path.isfile(dest_fname):
        return {}

    diff = {}
    action = action_data['name']
    selected_index = action_data['index']
    selected_indices = action_data['indices']
    current_nb = action_data['model']['cells']
    len_current = len(current_nb)
    prior_nb = nbformat.read(dest_fname, nbformat.NO_CONVERT)['cells']
    len_prior = len(prior_nb)

    check_indices = indices_to_check(action, selected_index, selected_indices,
                                    len_current, len_prior)

    # if it is a cut or copy action, save the copied cells as the diff
    if action in ['cut-cell', 'copy-cell', 'paste-cell-above',
                'paste-cell-below', 'paste-cell-replace']:
        for i in check_indices:
            diff[i] = current_nb[i]

    # Special case for undo-cell-deletion. The cell may insert at any part of
    # the notebook, so simply return the first cell that is not the same
    elif action in ['undo-cell-deletion']:
        num_inserted = len_current - len_prior
        if num_inserted > 0:
            first_diff = 0
            for i in range(len_current):
                if (prior_nb[i]["source"] != current_nb[i]["source"]
                    or i >= len(prior_nb)): # a new cell at the end of the nb
                    first_diff = i
                    break
            for j in range(first_diff, first_diff + num_inserted):
                if j < len_current:
                    diff[j] = current_nb[j]
    else:
        diff = get_diff_at_indices(check_indices, action_data, dest_fname, True)

    return diff
