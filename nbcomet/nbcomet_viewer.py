"""
nbcomet: Jupyter Notebook extension to track notebook history
"""

import os
import time
import json
import datetime
import nbformat
import pickle

from nbcomet.nbcomet_sqlite import get_viewer_data
from nbcomet.nbcomet_diff import valid_ids


def get_prior_filenames(nb, hashed_path, fname):
    # get the history of names this file has had
    # returns [[name, start_time, end_time], ...]
    
    if "comet_paths" in nb["metadata"]:
        prior_names = nb['metadata']['comet_paths']
    else:
        prior_names = [os.path.join(hashed_path, fname), 0]
    
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
        
        db = os.path.join(data_dir, hp, fn, fn + ".db")
        d, r, t, actions = get_viewer_data(db, start_time, end_time)
        
        total_dels += d
        total_runs += r    
        total_time += t
        for a in actions:
            all_actions.append(list(a))
        
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
                nb_time = datetime.datetime.strptime(v[-32:-6], 
                    "%Y-%m-%d-%H-%M-%S-%f")
                start_time = datetime.datetime.fromtimestamp(n[1]/1000) - datetime.timedelta(seconds=1)  
                end_time = datetime.datetime.fromtimestamp(n[2]/1000)                
                if nb_time <= end_time and nb_time >= start_time:
                    versions.append(os.path.join(hp, fn, 'versions', v))
    return versions

def get_activity_gaps(versions):
    #TODO return the seconds of the gap
    gaps = []
    for i, v in enumerate(versions):
        # look for gaps of over 15 min in activity
        
        if i > 0:
            current_nb_time = datetime.datetime.strptime(v[-32:-6],
                "%Y-%m-%d-%H-%M-%S-%f")
            past_nb_time = datetime.datetime.strptime(versions[i-1][-32:-6],
                "%Y-%m-%d-%H-%M-%S-%f")
            time_diff = current_nb_time - past_nb_time
            if time_diff.total_seconds() >= 15 * 60:
                gaps.append([i, time_diff.total_seconds()])
    return gaps

def get_cell_data(data_dir, versions, vi, all_actions, last_change):
    cell_data = []  
    
    nb_b_path = os.path.join(data_dir, versions[vi])
    nb_b = nbformat.read(nb_b_path, nbformat.NO_CONVERT)['cells']
              
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
            
        cell_data.append( [cell_id, cell_type, new_source, last_source] )
    
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
        
        #TODO find a way to use a template rather than dump all the HTML here
        html = """<!DOCTYPE html>\n
            <html>\n
            <style>\n
            body{\n
                width: 960px;\n
                margin: auto;\n
                font-family: "Helvetica Neue", Helvetica, sans-serif;
                color: #333;
            }\n
            \n
            .titlebar{
                width: 100%;
                height: 48px;
                overflow: auto; 
                margin-top: 20px;              
            }
            .legendbar{
                width: 100%;
                height: 40px;
                overflow: auto;               
            }            
            .title{
                float: left;
                margin: 0px;
            }
            .time{
                float: right;
                margin: 12px 0px;
            }
            .versionStat{
                width: 300px;
                float: left;
            }
            .codeSample{
                width: 470px;
                height: 238px;
                float: left;
                overflow: scroll;
                padding: 4px;
                margin: 0px;
                margin-bottom: 20px;
                border: 1px solid #aaa;
                font-family: "Courier New", Courier, monospace;
                font-size: 0.8em;
                white-space: pre-wrap;
                line-height: 1.3em;
            }
            #window{
                width: 960px;
                height: 484px;
                overflow: scroll;
                padding: 0px;
                margin: 0px
            }
            button {
            	background-color:#007dc1;
            	-moz-border-radius:3px;
            	-webkit-border-radius:3px;
            	border-radius:3px;
            	border:1px solid #124d77;
            	float: right;
                display:inline-block;
            	cursor:pointer;
            	color:#ffffff;
            	font-family:Arial;
            	font-size:14px;
            	padding:6px 12px;
            	text-decoration:none;
            }
            button:hover {
            	background-color:#0061a7;
            }
            button:active {
            	position:relative;
            	top:1px;
            }
            }
            h2{
                padding: 10px 0px 10px 0px;
                margin: 0px;
            }
            h3{
                margin: 0px;
                padding-bottom: 8px;
                color: #999;
            }
            p{
                padding: 0px 0px 10px 0px;
                margin: 0px;
            }
            </style>\n
            <body>\n
            <script src="https://d3js.org/d3.v4.min.js"></script>\n
            <script>\n
            var width = 960;\n
            var height = 480;\n
            var cellSize = 16;\n
            \n
            var data = """ + str(data) + """\n
            \n
            var maxLength = 0\n
            for (i = 0; i < data.versions.length; i++){\n
                maxLength = Math.max(data.versions[i].cells.length, maxLength)\n
            }\n
            \n
            width = Math.max(width, cellSize * (data.versions.length + data.gaps.length))\n
            \n
            height = Math.max(height, cellSize * maxLength)\n

            var showingChanged = false

            \n
            var legend_colors = [\n
                ["markdown", "#7da7ca"],\n
                ["no output", "silver"],\n
                ["text output", "grey"],\n
                ["error", "#ca7da7"],\n
                ["graphical output", "#a7ca7d"]\n
            ]\n
            \n
            var mainStats = d3.select("body")
                .append("div")
                .attr("class","titlebar");
            
            var title = mainStats.append("h1")\n
                .text(data.name)
                .attr('class', 'title');\n
            
            var time = mainStats\n
                    .append("h2")\n
                    .attr('class', 'time')
                    .text(function(){\n
                        hours = Math.floor( data.editTime / 3600 );\n
                        minutes = Math.floor( ( data.editTime - hours * 3600 ) / 60 );\n
                        text = hours.toString() + "h " + minutes.toString() + "m editing";\n
                        return text;
                    });
            
            d3.select("body")\n
                .append("hr")\n
                        
            var svg_window = d3.select("body")
                .append("div")
                .attr("id", "window")
            
            var svg = d3.select("#window")\n
                .append("svg")\n
                .attr("width", width)\n
                .attr("height", height)\n
            \n
            var nb = svg.selectAll("g")\n
                .data(data.versions)\n
                .enter().append("g");\n
            \n
            nb.each(function(p, j) {\n
                d3.select(this)\n
                .selectAll("rect")\n
                    .data(function(d){return d.cells; })\n
                    .enter().append("rect")\n
                    .attr("width", cellSize)\n
                    .attr("height", cellSize)\n
                    .attr('class', function(d){ return "c-" + d[0] })
                    .classed("changed", function(d){ return d[2] != 'false'})
                    .attr("x", function(d, i){\n
                        var numGaps = data.gaps.filter(function(x){return x[0]<=j}).length
                        return (j+numGaps)*cellSize; })\n
                    .attr("y", function(d, i) { return i * cellSize; })\n
                    .attr("fill", function(d) {
                        type_colors = {
                            "markdown": "#7da7ca",
                            "code": "silver",
                            "error": "#ca7da7",
                            "stream": "grey",
                            "execute_result": "grey",
                            "display_data": "#a7ca7d"
                        }
                        return type_colors[d[1]]
                     })\n
                    .attr("stroke", "white")
                    .on('click', function(d){
                        d3.selectAll('rect')
                            .attr('stroke','white')
                        d3.select(this)
                            .attr('stroke', 'orangered')
                        
                        versionName.text(data.versions[j].name) 
                        versionTime.text(data.versions[j].time)
                              
                        if(d[2] == "false"){
                            src = data.versions[d[3]].cells.filter(e => e[0] == d[0])
                            d3.select('#currentCode')
                                .text(src[0][2])                            
                        }
                        else{
                            d3.select('#currentCode')
                                .text(d[2])
                        }                        
                        if(d[3] == "false"){
                            d3.select('#priorCode')
                                .text("")
                        }
                        else{
                            src = data.versions[d[3]].cells.filter(e => e[0] == d[0])
                            d3.select('#priorCode')
                                .text(src[0][2])                            
                        }               
                    })  
            });\n     
            
            var legendbar = d3.select('body')
                .append('div')
                .attr('class', 'legendbar')
                
            var legendsvg = legendbar.append("svg")\n
                .attr("width", 800)\n
                .attr("height", 40)\n
                
            var legend = legendsvg.append('g')\n
            \n
            legend.selectAll("rect.legend")\n
                .data(legend_colors)\n
                .enter().append("rect")\n
                .attr("class", "legend")\n
                .attr('x', function(d, i){return 128 * i})\n
                .attr('y', 12)\n
                .attr('width', 16)\n
                .attr('height', 16)\n
                .style("fill", function(d){return d[1];})\n
                .attr('stroke', 'white');\n
            \n
            legend.selectAll("text.legend")\n
                .data(legend_colors)\n
                .enter().append("text")\n
                .attr("class", "legend")\n
                .attr('x', function(d, i){return 128 * i + 24})\n
                .attr('y', 24)\n
                .text(function(d){ return d[0]; })
                .attr('fill', '#666');\n
                
            var changeButton = legendbar.append("button")
                .text("Highlight Changes")
                .on("click", function(d){  
                    if(showingChanged){
                        showingChanged = false
                        changeButton.text('Highlight Changes')
                        d3.selectAll("rect")
                            .style('fill-opacity', 1.0)
                    }
                    else{
                        showingChanged = true
                        changeButton.text('Hide Changes')
                        d3.selectAll("rect")
                            .style('fill-opacity', 0.3)
                        d3.selectAll("rect.changed")
                            .style('fill-opacity', 1.0)
                    }
                    
                });
              
            var versionStats = d3.select("body")
                .append('div')
                .attr('class', 'legendbar')
                
            var versionTime = versionStats.append('p')
                .attr('class', 'versionStat')
                .text("")
            
            var versionName = versionStats.append('p')
                .attr('class', 'versionStat')
                .text("")
            
            
            
            var priorSource = d3.select("body")
                .append("div")
                .attr("class", "codeSample")
            
            priorSource.append("h3")
                    .text("Prior Source")
            
            priorSource.append("div")
                .attr("id", "priorCode")
                .text("Select a cell")
            
            var currentSource = d3.select("body")
                .append("div")
                .attr("class", "codeSample")
                
            currentSource.append("h3")
                    .text("Current Source")
            
            currentSource.append("div")
                .attr("id", "currentCode")
                .text("Select a cell")
            
            </script>\n
            </body>\n
            </html>"""

    # If there is no data, just return a boilerplate page
    else:
        html = """<!DOCTYPE html>\n
            <html>\n
            <style>\n
            body{\n
                width: 960px;\n
                margin: auto;\n
                font-family: "Helvetica Neue", Helvetica, sans-serif;
                color: #333;
            }\n
            </style>\n
            <body>\n
            <h1>No Data</h1>
            <hr>
            <p>There is no Comet data saved for <i>%s</i></p>
            </body>
            </html>
            """ % data_dir.split('/')[-1]

    return html
