"""
nbcomet: Jupyter Notebook extension to track notebook history
"""

import os
import datetime
import nbformat

from nbcomet.nbcomet_sqlite import get_viewer_data

def get_viewer_html(data_dir, fname):
    version_dir = os.path.join(data_dir, 'versions')
    db = os.path.join(data_dir, fname + ".db")
    numDeletions, numRuns, totalTime = get_viewer_data(db)

    if os.path.isdir(version_dir):
        data = {'name': fname,
                'editTime': totalTime,
                'numRuns': numRuns,
                'numDeletions': numDeletions,
                'gaps': [],
                'versions':[]};

        versions = [f for f in os.listdir(version_dir)
            if os.path.isfile(os.path.join(version_dir, f))
            and f[-6:] == '.ipynb']

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
                            'time': v[-26:],
                            'cells':[]};

            nb_path = os.path.join(version_dir, v)
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
            .stat{
                width: 240px;
                float: left;
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
            var time = d3.select("body")\n
                .append("div")\n
                .attr("class", "stat")\n
                    .append("h2")\n
                    .text(function(){\n
                        hours = Math.floor( data.editTime / 3600 );\n
                        minutes = Math.floor( ( data.editTime - hours * 3600 ) / 60 );\n
                        text = hours.toString() + "h " + minutes.toString() + "m editing";\n
                        return text;\n
                })\n
            \n
            var runs = d3.select("body")\n
                .append("div")\n
                .attr("class", "stat")\n
                    .append("h2")\n
                    .text(function(){\n
                        text = data.numRuns.toString() + " cells run";\n
                        return text;\n
                })\n
            \n
            var deletions = d3.select("body")\n
                .append("div")\n
                .attr("class", "stat")\n
                    .append("h2")\n
                    .text(function(){\n
                        text = data.numDeletions.toString() + " cells deleted";\n
                        return text;\n
                })\n
            \n
            var versions = d3.select("body")\n
                .append("div")\n
                .attr("class", "stat")\n
                    .append("h2")\n
                    .text(function(){\n
                        text = data.versions.length.toString() + " versions";\n
                        return text;\n
                })\n
            \n
            var svg = d3.select("body")\n
                .append("svg")\n
                .attr("width", width)\n
                .attr("height", height)\n
            \n
            var nb = svg.selectAll("g")\n
                .data(data.versions)\n
                .enter().append("g")\n
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
