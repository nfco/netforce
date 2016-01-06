/*
 * Copyright (c) 2012-2015 Netforce Co. Ltd.
 * 
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
 * DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
 * OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
 * OR OTHER DEALINGS IN THE SOFTWARE.
 */

var Gantt=NFView.extend({
    _name: "gantt",
    events: {
        "click .run-report": "run_report",
        "click .nf-zoom-in": "zoom_in",
        "click .nf-zoom-out": "zoom_out",
        "click .nf-move-up": "move_up",
        "click .nf-move-down": "move_down",
        "click .nf-critical-path": "critical_path",
    },

    initialize: function(options) {
        log("Gantt.initialize",this);
        var that=this;
        NFView.prototype.initialize.call(this,options);
        if (!this.options.model) throw "GanttView: missing model";
        var search_view=get_xml_layout({model:this.options.model,type:"search",noerr:true});
        if (!search_view) {
            search_view=get_default_search_view(this.options.model);
        }
        var doc=$.parseXML(search_view.layout);
        this.$search=$(doc).children();
        this.model=new NFModel({},{name:"_gantt"});
        this.data.context.model=this.model;
        this.data.context.collection=null;
        this.$search.find("field").each(function() {
            var $el=$(this);
            var name=$el.attr("name");
            log("conv field: "+name);
            var orig_field=get_field_path(that.options.model,name);
            var search_field;
            if (orig_field.type=="char") search_field={type:"char",string:orig_field.string};
            else if (orig_field.type=="selection") search_field={type:"selection",selection:orig_field.selection,string:orig_field.string};
            else if (orig_field.type=="many2one") {
                if ($el.attr("noselect")) {
                    search_field={type:"char",string:orig_field.string};
                } else {
                    search_field={type:"many2one",relation:orig_field.relation,string:orig_field.string};
                }
            } else if (orig_field.type=="text") search_field={type:"char",string:orig_field.string};
            else if (orig_field.type=="reference") search_field={type:"char",string:orig_field.string};
            else if (orig_field.type=="float") search_field={type:"float_range",string:orig_field.string};
            else if (orig_field.type=="integer") search_field={type:"float_range",string:orig_field.string}; // XXX
            else if (orig_field.type=="date" || orig_field.type=="datetime") search_field={type:"date_range",string:orig_field.string};
            else if (orig_field.type=="boolean") search_field={type:"selection",selection:[["yes","Yes"],["no","No"]],string:orig_field.string};
            else if (orig_field.type=="many2many") {
                search_field={type:"many2one",relation:orig_field.relation,string:orig_field.string};
            }
            else throw "Can't search field: "+name;
            that.model.fields[name]=search_field;
        });
    },

    render: function() {
        console.log("Gantt.render",this);
        var that=this;
        this.data.title=this.options.string;
        this.data.render_search_body=function(ctx) { return that.render_search_body.call(that,ctx); };
        NFView.prototype.render.call(this);
        var orig_tasks={};
        setTimeout(function() {
            $("#ganttemplates").loadTemplates();
            var ge=new GanttMaster();
            this.ge=ge;
            var orig_endTransaction=ge.endTransaction.bind(ge);
            var that=this;
            ge.endTransaction=function() {
                log("gantt endTransaction");
                orig_endTransaction();
                var new_proj_data=ge.saveProject();
                log("new_proj_data",new_proj_data);
                _.each(new_proj_data.tasks,function(task) {
                    var orig_task=orig_tasks[task.id];
                    if (!orig_task) return;
                    if (task.start==orig_task.start && task.duration==orig_task.duration) return;
                    log("task "+task.id+" modified, saving...",task,orig_task);
                    orig_tasks[task.id]=task;
                    var vals={};
                    vals[that.start_field_name]=moment(task.start).format("YYYY-MM-DD");
                    vals[that.duration_field_name]=task.duration;
                    rpc_execute(that.options.model,"write",[[task.id],vals],{},function(err,data) {
                        if (err) {
                            throw "Failed to save task "+task.id;
                        }
                    });
                });
            };
            var workspace=this.$el.find(".nf-gantt-content");
            workspace.css({height: 960});
            log("workspace",workspace);
            ge.init(workspace);
            var gantt_view=get_xml_layout({model:this.options.model,type:"gantt"});
            log("gantt_view",gantt_view);
            this.$layout=$($.parseXML(gantt_view.layout)).children();
            this.group_field_name=this.$layout.attr("group_field");
            if (this.group_field_name) {
                this.group_field=get_field(this.options.model,this.group_field_name);
            }
            this.subgroup_field_name=this.$layout.attr("subgroup_field");
            if (this.subgroup_field_name) {
                this.subgroup_field=get_field(this.options.model,this.subgroup_field_name);
            }
            this.subsubgroup_field_name=this.$layout.attr("subsubgroup_field");
            if (this.subsubgroup_field_name) {
                this.subsubgroup_field=get_field(this.options.model,this.subsubgroup_field_name);
            }
            this.start_field_name=this.$layout.attr("start_field");
            if (!this.start_field_name) throw "Missing attribute 'start_field' in gantt layout";
            this.start_field=get_field(this.options.model,this.start_field_name);
            this.duration_field_name=this.$layout.attr("duration_field");
            if (!this.duration_field_name) throw "Missing attribute 'duration_field' in gantt layout";
            this.duration_field=get_field(this.options.model,this.duration_field_name);
            this.label_field_name=this.$layout.attr("label_field");
            if (!this.label_field_name) throw "Missing attribute 'label_field' in gantt layout";
            this.label_field=get_field(this.options.model,this.label_field_name);
            this.progress_field_name=this.$layout.attr("progress_field");
            if (this.progress_field_name) {
                this.progress_field=get_field(this.options.model,this.progress_field_name);
            }
            this.depends_field_name=this.$layout.attr("depends_field");
            if (this.depends_field_name) {
                this.depends_field=get_field(this.options.model,this.depends_field_name);
            }

            var fields=[this.start_field_name,this.duration_field_name,this.label_field_name];
            if (this.group_field_name) fields.push(this.group_field_name);
            if (this.subgroup_field_name) fields.push(this.subgroup_field_name);
            if (this.subsubgroup_field_name) fields.push(this.subsubgroup_field_name);
            if (this.progress_field_name) fields.push(this.progress_field_name);
            if (this.depends_field_name) fields.push(this.depends_field_name);
            var condition=this.get_condition();
            console.log("condition",condition);
            rpc_execute(this.options.model,"search_read",[condition,fields],{},function(err,data) {
                if (err) {
                    throw "Failed to get gantt data: "+err.message;
                }
                var data=_.sortBy(data,function(obj) {
                    var vals=[];
                    if (this.group_field_name) {
                        var group_field_value=render_field_value(obj[this.group_field_name],this.group_field);
                        vals.push(group_field_value||" ");
                    }
                    if (this.subgroup_field_name) {
                        var subgroup_field_value=render_field_value(obj[this.subgroup_field_name],this.subgroup_field);
                        vals.push(subgroup_field_value||" ");
                    }
                    if (this.subsubgroup_field_name) {
                        var subsubgroup_field_value=render_field_value(obj[this.subsubgroup_field_name],this.subsubgroup_field);
                        vals.push(subsubgroup_field_value||" ");
                    }
                    var start_field_value=render_field_value(obj[this.start_field_name],this.start_field);
                    vals.push(start_field_value);
                    return vals.join("_");
                }.bind(this));
                log("sorted gantt data",data);
                var proj_data={
                    tasks: [],
                    canWrite: true,
                };
                var last_group_value=null;
                var last_subgroup_value=null;
                var last_subsubgroup_value=null;
                var task_index={};
                _.each(data,function(obj) {
                    var label_value=render_field_value(obj[this.label_field_name],this.label_field);
                    var start_date=obj[this.start_field_name];
                    if (!start_date) throw "Missing start date for task "+obj.id;
                    var duration=obj[this.duration_field_name];
                    if (duration==null) throw "Missing duration for task "+obj.id;
                    if (this.group_field_name) {
                        var group_value=render_field_value(obj[this.group_field_name],this.group_field);
                    }
                    if (this.subgroup_field_name) {
                        var subgroup_value=render_field_value(obj[this.subgroup_field_name],this.subgroup_field);
                    }
                    if (this.subsubgroup_field_name) {
                        var subsubgroup_value=render_field_value(obj[this.subsubgroup_field_name],this.subsubgroup_field);
                    }
                    console.log("task ",obj.id,"group",group_value,"subgroup",subgroup_value,"subsubgroup",subsubgroup_value);
                    if (group_value!=last_group_value) {
                        console.log("new group",group_value);
                        if (group_value) {
                            var task={
                                id: Math.floor(Math.random()*100000000), // XXX
                                name: group_value,
                                level: 0,
                                start: new moment(start_date).unix()*1000,
                                startIsMilestone: false,
                                endIsMilestone: false,
                                depends: "",
                                status: "STATUS_ACTIVE",
                            }
                            proj_data.tasks.push(task);
                        }
                        last_group_value=group_value;
                        last_subgroup_value=null;
                        last_subsubgroup_value=null;
                    }
                    if (subgroup_value!=last_subgroup_value) {
                        console.log("new subgroup",subgroup_value);
                        if (subgroup_value) {
                            var task={
                                id: Math.floor(Math.random()*100000000), // XXX
                                name: subgroup_value,
                                level: 1,
                                start: new moment(start_date).unix()*1000,
                                startIsMilestone: false,
                                endIsMilestone: false,
                                depends: "",
                                status: "STATUS_ACTIVE",
                            }
                            proj_data.tasks.push(task);
                        }
                        last_subgroup_value=subgroup_value;
                        last_subsubgroup_value=null;
                    }
                    if (subsubgroup_value!=last_subsubgroup_value) {
                        console.log("new subsubgroup",subsubgroup_value);
                        if (subsubgroup_value) {
                            var task={
                                id: Math.floor(Math.random()*100000000), // XXX
                                name: subsubgroup_value,
                                level: 2,
                                start: new moment(start_date).unix()*1000,
                                startIsMilestone: false,
                                endIsMilestone: false,
                                depends: "",
                                status: "STATUS_ACTIVE",
                            }
                            proj_data.tasks.push(task);
                        }
                        last_subsubgroup_value=subsubgroup_value;
                    }
                    var level;
                    if (subsubgroup_value) {
                        level=3;
                    } else if (subgroup_value) {
                        level=2;
                    } else if (group_value) {
                        level=1;
                    } else {
                        level=0;
                    }
                    var depends=null;
                    if (this.depends_field_name) {
                        var res=obj[this.depends_field_name];
                        var deps=[];
                        _.each(res,function(r) {
                            var i=task_index[r[0]];
                            if (!i) {
                                log("WARNING: Task index not found for task "+r[0]);
                            }
                            if (r[1]) {
                                deps.push(""+i+":"+r[1]);
                            } else {
                                deps.push(""+i);
                            }
                        });
                        depends=deps.join(",");
                    }
                    log("depends",depends); 
                    var task={
                        id: obj.id,
                        name: label_value,
                        level: level,
                        start: new moment(start_date).unix()*1000,
                        duration: duration,
                        startIsMilestone: false,
                        endIsMilestone: false,
                        depends: depends,
                        status: "STATUS_ACTIVE",
                        progress: obj[this.progress_field_name],
                        assigs: [],
                    };
                    console.log("add task",task);
                    proj_data.tasks.push(task);
                    task_index[task.id]=proj_data.tasks.length;
                    orig_tasks[task.id]=task;
                }.bind(this));
                ge.loadProject(proj_data);
            }.bind(this));
        }.bind(this),100);
        return this;
    },

    render_search_body: function(context) {
        log("Gantt.render_search_body",this,context);
        var that=this;
        var body=$("<div/>");
        var row=$('<div class="row"/>');
        body.append(row);
        var col=0;
        this.$search.children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="field") {
                var name=$el.attr("name");
                var cell=$('<div class="col-sm-2"/>');
                if (col+2>12) {
                    row=$('<div class="row"/>');
                    body.append(row);
                    col=0;
                }
                row.append(cell);
                col+=2;
                var opts={
                    name: name,
                    context: context
                };
                var view=Field.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            } else if (tag=="newline") {
                row=$('<div class="row"/>');
                body.append(row);
            }
        });
        return body.html();
    },

    run_report: function(e) {
        log("report_view.run_report");
        e.preventDefault();
        e.stopPropagation();
        this.render();
    },

    get_condition: function() {
        log("report_view.get_condition",this);
        var that=this;
        var condition=[];
        this.$search.find("field").each(function() {
            var $el=$(this);
            var n=$el.attr("name");
            var v=that.model.get(n);
            if (!v) return;
            var f=get_field_path(that.options.model,n);
            var sf=that.model.get_field(n);
            if ((f.type=="float") || (f.type=="date")) {
                if (v[0]) {
                    var clause=[n,">=",v[0]];
                    condition.push(clause);
                }
                if (v[1]) {
                    var clause=[n,"<=",v[1]];
                    condition.push(clause);
                }
            } else if ((f.type=="many2one") && (sf.type=="many2one")) {
                if (_.isArray(v)) v=v[0];
                if ($el.attr("child_of")) {
                    var clause=[n,"child_of",v];
                } else {
                    var clause=[n,"=",v];
                }
                condition.push(clause);
            } else if (f.type=="boolean") {
                if (v=="yes") {
                    condition.push([[n,"=",true]]);
                } else if (v=="no") {
                    condition.push([[n,"=",false]]);
                }
            } else if (f.type=="many2many") {
                if ($el.attr("child_of")) {
                    var clause=[n,"child_of",v[0]];
                } else {
                    var clause=[n,"=",v[0]];
                }
                condition.push(clause);
            } else {
                var clause=[n,"ilike",v];
                condition.push(clause);
            }
        });
        log("=> condition",condition);
        return condition;
    },

    zoom_in: function(e) {
        e.preventDefault();
        this.$el.find(".nf-gantt-content").trigger("zoomPlus.gantt");
    },

    zoom_out: function(e) {
        e.preventDefault();
        this.$el.find(".nf-gantt-content").trigger("zoomMinus.gantt");
    },

    move_up: function(e) {
        e.preventDefault();
        this.$el.find(".nf-gantt-content").trigger("moveUpCurrentTask.gantt");
    },

    move_down: function(e) {
        e.preventDefault();
        this.$el.find(".nf-gantt-content").trigger("moveDownCurrentTask.gantt");
    },

    critical_path: function(e) {
        e.preventDefault();
        this.ge.gantt.showCriticalPath=!this.ge.gantt.showCriticalPath;
        this.ge.redraw();
    },
});

Gantt.register();
