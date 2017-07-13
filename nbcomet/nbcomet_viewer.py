"""
nbcomet: Jupyter Notebook extension to track notebook history
"""

import os
import time
import datetime
import nbformat

from nbcomet.nbcomet_sqlite import get_viewer_data

def get_viewer_html(data_dir, hashed_path, fname):
    # get paths to files and databases
    nb_path = os.path.join(data_dir, hashed_path, fname, fname + '.ipynb')
    nb = nbformat.read(nb_path, nbformat.NO_CONVERT)
    
    # get the history of names this file has had
    nb_name_history = [os.path.join(hashed_path, fname), 0]        
    if "comet_paths" in nb["metadata"]:
        nb_name_history = nb['metadata']['comet_paths']
    # turn time of filename into time ranges when file had each name
    for i, v in enumerate(nb_name_history):
        if i == len(nb_name_history) - 1:
            v.append(int(time.time()*1000))
        else:
            v.append(nb_name_history[i+1][1])

    # get the notebook actions in each range
    num_deletions = 0
    num_runs = 0
    total_time = 0
    
    # get the high-level overview about nb use
    for n in nb_name_history:
        hp = n[0].split('/')[0]
        fn = n[0].split('/')[1].split('.')[0]
        
        start_time = n[1]
        end_time = n[2]
        
        db = os.path.join(data_dir, hp, fn, fn + ".db")
        d, r, t = get_viewer_data(db, start_time, end_time)
        
        num_deletions += d
        num_runs += r    
        total_time += t
    
    # set up json datastructure    
    data = {'name': fname,
            'editTime': total_time,
            'numRuns': num_runs,
            'numDeletions': num_deletions,
            'gaps': [],
            'versions':[]};
    
    versions = []
    
    # get the notebook versions that fall in our specified ranges for each file
    for n in nb_name_history:
        hp = n[0].split('/')[0]
        fn = n[0].split('/')[1].split('.')[0]
        
        version_dir = os.path.join(data_dir, hp, fn, 'versions')
        if os.path.isdir(version_dir):
            versions_with_this_name = [ f for f in os.listdir(version_dir)
                if os.path.isfile(os.path.join(version_dir, f))
                and f[-6:] == '.ipynb']
            
            
            for v in versions_with_this_name:
                # filter this list to only those in the correct time frame
                nb_time = datetime.datetime.strptime(v[-32:-6], 
                    "%Y-%m-%d-%H-%M-%S-%f")
                start_time = datetime.datetime.fromtimestamp(n[1]/1000) - datetime.timedelta(seconds=1)  
                end_time = datetime.datetime.fromtimestamp(n[2]/1000)
                
                if nb_time < end_time and nb_time > start_time:
                    versions.append(os.path.join(hp, fn, 'versions', v))
    
    if len(versions) > 0:
        for i, v in enumerate(versions):
            if i > 0:
                #TODO these datetime conversions seem hacky
                current_nb_time = datetime.datetime.strptime(v[-32:-6],
                    "%Y-%m-%d-%H-%M-%S-%f")
                past_nb_time = datetime.datetime.strptime(versions[i-1][-32:-6],
                    "%Y-%m-%d-%H-%M-%S-%f")
                time_diff = current_nb_time - past_nb_time
                # consider 15 minutes of inactivity as a gap in editing
                if time_diff.total_seconds() >= 15 * 60:
                    data['gaps'].append(i)

            version_data = {'num': i,
                            'time': v[-26:], #TODO I bet this is broken
                            'cells':[]};

            nb_path = os.path.join(data_dir, v)
            nb_cells = nbformat.read(nb_path, nbformat.NO_CONVERT)['cells']

            # cells can have multiple outputs , each with a different type
            # here we track the "highest" level output with
            # error > display_data > execute result > stream
            for c in nb_cells:
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

                version_data['cells'].append(cell_type)

            data['versions'].append(version_data)

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
            .statbar{
                width: 100%; 
                overflow: auto;               
            }
            .stat{
                width: 240px;
                float: left;
            }
            h2{
                padding: 10px 0px 10px 0px;
                margin: 0px;
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
            var height = 600;\n
            var cellSize = 16;\n
            \n
            var data = """ + str(data) + """\n
            \n
            var maxLength = 0\n
            for (i = 0; i < data.versions.length; i++){\n
                maxLength = Math.max(data.versions[i].cells.length, maxLength)\n
            }\n
            \n
            cellSize = Math.min(cellSize, width / (data.versions.length + data.gaps.length))\n
            \n
            cellSize = Math.min(cellSize, height / maxLength)\n
            \n
            var legend_colors = [\n
                ["markdown", "#7da7ca"],\n
                ["no output", "silver"],\n
                ["text output", "grey"],\n
                ["graphical output", "#a7ca7d"],\n
                ["error", "#ca7da7"]\n
            ]\n
            \n
            var title = d3.select("body")\n
                .append("h1")\n
                .text(data.name);\n
            \n
            d3.select("body")\n
                .append("hr")\n
            \n
            var mainStats = d3.select("body")
                .append("div")
                .attr("class","statbar");
            
            var versionStats = d3.select("body")
                .append("div")
                .attr("class","statbar");
                
            var time = mainStats.append("div")\n
                .attr("class", "stat")\n
                    .append("h2")\n
                    .text(function(){\n
                        hours = Math.floor( data.editTime / 3600 );\n
                        minutes = Math.floor( ( data.editTime - hours * 3600 ) / 60 );\n
                        text = hours.toString() + "h " + minutes.toString() + "m editing";\n
                        return text;\n
                })\n
            \n
            var runs = mainStats.append("div")\n
                .attr("class", "stat")\n
                    .append("h2")\n
                    .text(function(){\n
                        text = data.numRuns.toString() + " cells run";\n
                        return text;\n
                })\n
            \n
            var deletions = mainStats.append("div")\n
                .attr("class", "stat")\n
                    .append("h2")\n
                    .text(function(){\n
                        text = data.numDeletions.toString() + " cells deleted";\n
                        return text;\n
                })\n
            
            var versionName = versionStats.append("div")\n
                .attr("class", "stat")\n
                    .append("p")\n
                    .text(".")
            
            var versionAdditons = versionStats.append("div")\n
                .attr("class", "stat")\n
                    .append("p")\n
                    .text(".")
            
            var versionDeletions = versionStats.append("div")\n
                .attr("class", "stat")\n
                    .append("p")\n
                    .text(".")
            
            var svg = d3.select("body")\n
                .append("svg")\n
                .attr("width", width)\n
                .attr("height", height)\n
            \n
            var nb = svg.selectAll("g")\n
                .data(data.versions)\n
                .enter().append("g")
                .on("mouseover", function(d){versionName.text("Hi There");})
                .on("mouseout", function(d){versionName.text(".");});\n
            \n
            nb.each(function(p, j) {\n
                d3.select(this)\n
                .selectAll("rect")\n
                    .data(function(d){return d.cells; })\n
                    .enter().append("rect")\n
                    .attr("width", cellSize)\n
                    .attr("height", cellSize)\n
                    .attr("x", function(d, i){\n
                        var numGaps = data.gaps.filter(function(x){return x<=j}).length
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
                        return type_colors[d]
                     })\n
                    .attr("stroke", "white");\n
            });\n
            \n
            var legend = svg.append('g')\n
                .attr('transform', function(){return "translate(0," + (height - 100).toString() + ")"});\n
            \n
            legend.selectAll("rect.legend")\n
                .data(legend_colors)\n
                .enter().append("rect")\n
                .attr("class", "legend")\n
                .attr('x', 0)\n
                .attr('y', function(d, i){return 16 * i})\n
                .attr('width', 16)\n
                .attr('height', 16)\n
                .style("fill", function(d){return d[1];})\n
                .attr('stroke', 'white');\n
            \n
            legend.selectAll("text.legend")\n
                .data(legend_colors)\n
                .enter().append("text")\n
                .attr("class", "legend")\n
                .attr('x', function(d, i){return 16 + 4})\n
                .attr('y', function(d, i){return 16 * i + 12})\n
                .text(function(d){ return d[0]; })
                .attr('fill', '#666');\n
            \n
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
