"""
nbcomet: Jupyter Notebook extension to track notebook history
"""

import os
import pickle
import sqlite3
import nbformat
from threading import Timer

from nbcomet.nbcomet_diff import get_nb_diff


class DbManager(object):
    def __init__(self, db_key, db_path):
        self.db_key = db_key
        self.db_path = db_path
        self.commitTimer = None
        self.queue = []

        self.create_action_table()

    def create_action_table(self):
        # create the main db table for storing action data
        self.conn = sqlite3.connect(self.db_path)
        self.c = self.conn.cursor()
        self.c.execute('''CREATE TABLE IF NOT EXISTS actions (time integer,
            name text, cell_index integer, selected_cells text, cell_order text, 
            diff text)''')
        self.conn.commit()
        self.conn.close()

    def add_to_commit_queue(self, action_data, diff, cell_order):
        # add data to the queue
        ad = action_data
        action_data_tuple = (str(ad['time']), ad['name'], str(ad['index']),
                            str(ad['indices']), str(cell_order), 
                            pickle.dumps(diff))
        self.queue.append(action_data_tuple)

        if self.commitTimer:
            if self.commitTimer.is_alive():
                self.commitTimer.cancel()
                self.commitTimer = None

        # commit data before notebook closes, otherwise  let data queue for a
        # while to prevent rapid serial writing to the db
        if ad['name'] == 'notebook-closed':
            self.commit_queue()
        else:
            self.commitTimer = Timer(2.0, self.commit_queue)
            self.commitTimer.start()

    def commit_queue(self):
        # commit the queued data
        self.conn = sqlite3.connect(self.db_path)
        self.c = self.conn.cursor()

        try:
            self.c.executemany('INSERT INTO actions VALUES (?,?,?,?,?,?)', self.queue)
            self.conn.commit()
            self.queue = []
        except:
            self.conn.rollback()
            raise

    def record_action_to_db(self, action_data, dest_fname):
        """
        save action to sqlite database

        action_data: (dict) data about action, see above for more details
        dest_fname: (str) full path to where file is saved on volume
        db_manager: (DbManager) object managing DB read / write
        """

        # handle edge cases of copy-cell and undo-cell-deletion events
        diff, cell_order = get_nb_diff(action_data, dest_fname, True)

        # don't track extraneous events
        if action_data['name'] in ['unselect-cell'] and diff == {}:
            return

        # save the data to the database queue
        self.add_to_commit_queue(action_data, diff, cell_order)

def get_viewer_data(db, start_time, end_time):
    # get data for the comet visualization
    conn = sqlite3.connect(db)
    c = conn.cursor()

    search = "SELECT name FROM actions WHERE name = 'delete-cell' AND time BETWEEN " + str(start_time) + " and " + str(end_time)
    c.execute(search)
    rows = c.fetchall()
    num_deletions = len(rows)

    # TODO how to count when multiple cells are selected and run, or run-all?
    search = "SELECT name FROM actions WHERE name LIKE 'run-cell%' AND time BETWEEN " + str(start_time) + " and " + str(end_time)
    c.execute(search)
    rows = c.fetchall()
    num_runs = len(rows)
    
    search = "SELECT time FROM actions WHERE time BETWEEN " + str(start_time) + " and " + str(end_time)
    c.execute(search)
    rows = c.fetchall()
    total_time = 0;
    if len(rows) > 0:
        start_time = rows[0][0]
        last_time = rows[0][0]
        for i in range(1,len(rows)):
            # use 5 minutes of inactivity as threshold for each editing session
            if (rows[i][0] - last_time) >= (5 * 60 * 1000) or i == len(rows) - 1:
                total_time = total_time + last_time - start_time
                start_time = rows[i][0]
                last_time = rows[i][0]
            else:
                last_time = rows[i][0]

    search = "SELECT * FROM actions WHERE time BETWEEN " + str(start_time) + " and " + str(end_time)
    c.execute(search)
    all_rows = c.fetchall()

    return (num_deletions, num_runs, total_time/1000, all_rows)
