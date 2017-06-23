# nbcomet
nbcomet is a Jupyter Notebook extension that tracks Notebook history. It
consists of both a server side extension (python) and a client-side nbextenion
(javascript). Both must be installed for the tracking to work properly.

## Installation
### 1. Install python package
For your convenience, nbcomet's server and nbextenion are contained in a single
python package that can be installed with pip. Simply run the following command
in your terminal:

 ```
 pip install nbcomet
 ```

### 2. Configure server extension
While nbcomet is now installed, you need to tell Jupyter to use it. First, enable
 the server extension

```
jupyter serverextension enable --py nbcomet
```

### 3. Configure NBExtension
Next, you will need to install and enable the nbextension component of nbcomet:

```
jupyter nbextension install --py nbcomet
jupyter nbextension enable --py nbcomet
```

### 4. Check installation
You may check that nbcomet installed correctly by running the following commands:

```
jupyter serverextension list
jupyter nbextension list
```

### 5. Optional: Configure Data Directory
By default, Comet with store its data in `~/.jupyter/nbcomet`; You can change
this parameter by editing the `notebook.json` configuration file in your
`~/.jupyter/nbconfig` folder to include a line specifying your data directory.
For example: `"Comet": {"data_directory": "/full/path/to/directory" }`.

## What Comet Tracks
Comet tracks how your notebook changes over time. It does so by:
1. tracking the occurrence of actions such as creating, deleting, moving, or executing cells
2. tracking how your notebook changes as a result of these actions

Comet tracks this information in three ways:
1. committing every notebook change to a local git repository
2. periodically saving a full version of the notebook
3. saving the name and time of every action to an sqlite database

Comet is a research tool designed to help scientists in human-computer interaction better understand how people use Jupyter Notebooks. It is primarily a recording tool with limited support for visualizing or reviewing the recorded data.

![Comet Extension HistoryFlow Visualization](imgs/historyflow.png)  
