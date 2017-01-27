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

var ReportView=NFView.extend({
    _name: "report_view",
    events: {
        "click .run-report": "run_report",
        "click .drill-down": "drill_down",
        "click .nf-export-xls": "export_xls"
    },

    initialize: function(options) {
        //log("report_view.initialize",this);
        var that=this;
        NFView.prototype.initialize.call(this,options);
        if (!this.options.model) throw "ReportView: missing model";
        if (this.options.list_layout) {
            var layout=this.options.list_layout;
        } else {
            if (this.options.view_xml) {
                var list_view=get_xml_layout({name:this.options.view_xml});
            } else {
                var list_view=get_xml_layout({model:this.options.model,type:"list"});
            }
            var layout=list_view.layout;
        }
        if (_.isString(layout)) {
            var doc=$.parseXML(layout);
            this.$list=$(doc).children();
        } else {
            this.$list=layout;
        }
        this.data.colors=this.$list.attr("colors");
        var search_view=get_xml_layout({model:this.options.model,type:"search",noerr:true});
        if (!search_view) {
            search_view=get_default_search_view(this.options.model);
        }
        var doc=$.parseXML(search_view.layout);
        this.$search=$(doc).children();
        this.data.search_fields=[];
        this.$search.find("field").each(function() {
            that.data.search_fields.push({
                name: $(this).attr("name"),
                select: $(this).attr("select")
            });
        });
        this.data.render_search_body=function(ctx) { return that.render_search_body.call(that,ctx); };
        this.model=new NFModel({},{name:"_report"});
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
            else if (orig_field.type=="decimal") search_field={type:"float_range",string:orig_field.string};
            else if (orig_field.type=="integer") search_field={type:"float_range",string:orig_field.string}; // XXX
            else if (orig_field.type=="date" || orig_field.type=="datetime") search_field={type:"date_range",string:orig_field.string};
            else if (orig_field.type=="boolean") search_field={type:"selection",selection:[["yes","Yes"],["no","No"]],string:orig_field.string};
            else if (orig_field.type=="many2many") {
                search_field={type:"many2one",relation:orig_field.relation,string:orig_field.string};
            }
            else throw "Can't search field: "+name;
            that.model.fields[name]=search_field;
        });
        var group_select=this.options.group_select.split(",");
        var selection=[];
        _.each(group_select,function(n) {

            var hide=is_hidden({type:"field", model:that.options.model, name:n});
            if(hide) return;

            var f=get_field_path(that.options.model,n);
            if (!f) throw "Invalid field: "+n;
            selection.push([n,f.string]);
        });
        var group_field1={type:"selection",selection:selection,string:"Group Field"};
        that.model.fields["_group_field1"]=group_field1;
        var group_field2={type:"selection",selection:selection,string:"Subgroup Field"};
        that.model.fields["_group_field2"]=group_field2;
        if (this.options.group_fields) {
            var group_fields=this.options.group_fields.split(",");
        } else {
            var group_fields=[];
        }
        that.model.set("_group_field1",group_fields[0]);
        that.model.set("_group_field2",group_fields[1]);
        var view_type={type:"selection",selection:[["list","List"],["crosstab","Crosstab"],["bar","Bar Chart"],["pie","Pie Chart"]],string:"View Type"};
        that.model.fields["_view_type"]=view_type;
        that.model.set("_view_type",this.options.view_type||"list");
        if (this.options.condition) {
            var cond=JSON.parse(this.options.condition);
            this.set_condition(cond);
        }
        this.function_select=[];
        if (this.options.function_select) {
            this.function_select=this.options.function_select.split(",");
        }
        var agg_select=[];
        _.each(this.function_select,function(n) {
            var f=get_field_path(that.options.model,n);
            if (!f) throw "Invalid field: "+n;
            var hide=is_hidden({type:"field", model:that.options.model, name:n});
            if(hide) return;
            agg_select.push([n,f.string]);
        });
        var agg_field1={type:"selection",selection:agg_select,string:"Aggregate Field"};
        that.model.fields["_agg_field1"]=agg_field1;
        if (this.options.agg_fields) {
            var agg_fields=this.options.agg_fields.split(",");
        } else {
            var agg_fields=[];
        }
        that.model.set("_agg_field1",agg_fields[0]);
        var agg_field2={type:"selection",selection:agg_select,string:"Aggregate Field #2"};
        that.model.fields["_agg_field2"]=agg_field2;
        that.model.set("_agg_field2",agg_fields[1]);
    },

    render: function() {
        log("report_view.render",this);
        var that=this;
        var group_field1=this.model.get("_group_field1");
        var group_field2=this.model.get("_group_field2");
        var agg_field1=this.model.get("_agg_field1");
        var agg_field2=this.model.get("_agg_field2");
        var group_fields=[];
        if (group_field1) {
            var f=get_field_path(this.options.model,group_field1);
            group_fields.push(group_field1);
        }
        if (group_field2) {
            var f=get_field_path(this.options.model,group_field2);
            group_fields.push(group_field2);
        }
        var agg_fields=[];
        if (agg_field1) {
            agg_fields.push(agg_field1);
        }
        if (agg_field2) {
            agg_fields.push(agg_field2);
        }
        var condition=this.get_condition();
        log("group_fields",group_fields);
        log("agg_fields",agg_fields);
        log("condition",condition);
        var order=group_fields.join(",");
        rpc_execute(this.options.model,"read_group",[group_fields,agg_fields,condition],{order:order},function(err,data) {
            var view_type=that.model.get("_view_type");
            that.data.view_type=view_type;
            if (view_type=="list") {
                var cols=[];
                if (group_field1) {
                    var f=get_field_path(that.options.model,group_field1);
                    cols.push({
                        string: f.string
                    });
                }
                if (group_field2) {
                    var f=get_field_path(that.options.model,group_field2);
                    cols.push({
                        string: f.string
                    });
                }
                cols.push({
                    string: "Count"
                });
                _.each(agg_fields,function(n) {
                    var f=get_field_path(that.options.model,n);
                    cols.push({
                        string: f.string
                    });
                });
                that.data.cols=cols;
                log("cols",cols);
                var lines=[];
                _.each(data,function(r) {
                    var line={
                        cols: []
                    };
                    _.each(group_fields,function(n) {
                        var f=get_field_path(that.options.model,n);
                        var v=render_field_value(r[n],f);
                        line_vals={
                            string: v,
                            'is_year': n.indexOf("year") > -1 ? true : false
                        };
                        line.cols.push(line_vals);
                    });
                    line.cols.push({
                        string: r._count
                    });
                    _.each(agg_fields,function(n) {
                        var f=get_field_path(that.options.model,n);
                        var v=render_field_value(r[n],f);
                        line.cols.push({
                            string: v
                        });
                    });
                    lines.push(line);
                });
                log("lines",lines);
                that.data.lines=lines;
                NFView.prototype.render.call(that);
            } else if (view_type=="crosstab") {
                if (!group_field1) throw "Missing group field";
                var group_field=get_field_path(that.options.model,group_field1);
                that.data.group_field={
                    string: group_field.string
                };
                if (!group_field2) throw "Missing subgroup field";
                var subgroup_field=get_field_path(that.options.model,group_field2);
                that.data.subgroup_field={
                    string: subgroup_field.string
                };
                var subgroup_vals=[];
                var subgroup_test={};
                var group_lines=[];
                var group_test={};
                _.each(data,function(r) {
                    var v2=render_field_value(r[group_field2],subgroup_field);
                    if (!subgroup_test[v2]) {
                        subgroup_vals.push({
                            string: v2
                        });
                        subgroup_test[v2]=true;
                    }
                    var v1=render_field_value(r[group_field1],group_field);
                    var group_line=group_test[v1];
                    if (!group_line) {
                        group_line={
                            group_val: {
                                string: v1
                            },
                            subgroups: {}
                        };
                        group_lines.push(group_line);
                        group_test[v1]=group_line;
                    }
                    var agg_vals=[{string:r._count}];
                    _.each(agg_fields,function(n) {
                        var f=get_field_path(that.options.model,n);
                        agg_vals.push({
                            string: render_field_value(r[n],f)
                        });
                    });
                    group_line.subgroups[v2]=agg_vals;
                });
                subgroup_vals=_.sortBy(subgroup_vals,function(v) {return v.string});
                that.data.subgroup_vals=subgroup_vals;
                _.each(group_lines,function(group_line) {
                    group_line.cols=[];
                    _.each(subgroup_vals,function(v) {
                        var agg_vals=group_line.subgroups[v.string];
                        if (!agg_vals) agg_vals=[];
                        group_line.cols.push({
                            agg_vals: agg_vals
                        });
                    });
                });
                that.data.group_lines=group_lines;
                that.data.agg_fields=[{string:"Count"}];
                _.each(agg_fields,function(n) {
                    var f=get_field_path(that.options.model,n);
                    that.data.agg_fields.push({
                        string: f.string
                    });
                });
                NFView.prototype.render.call(that);
            } else if (view_type=="bar") {
                if (agg_field1) {
                    var f=get_field_path(that.options.model,agg_field1);
                    var agg_field={
                        name: agg_field1,
                        string: f.string
                    };
                } else {
                    var agg_field={
                        name: "_count",
                        string: "Count"
                    }
                }
                var categs=[];
                var series=[];
                if (group_field2) {
                    var subcategs=[];
                    var subcateg_test={};
                    var categ_vals={};
                    _.each(data,function(r) {
                        var f1=get_field_path(that.options.model,group_field1);
                        var v1=render_field_value(r[group_field1],f1);
                        var f2=get_field_path(that.options.model,group_field2);
                        var v2=render_field_value(r[group_field2],f2);
                        var val=r[agg_field.name];
                        if (!subcateg_test[v2]) {
                            subcategs.push(v2);
                            subcateg_test[v2]=true;
                        }
                        if (!categ_vals[v1]) {
                            categ_vals[v1]={};
                            categs.push(v1);
                        }
                        categ_vals[v1][v2]=val;
                    });
                    log("subcategs",subcategs);
                    _.each(subcategs,function(subcateg) {
                        var ser_data=[];
                        _.each(categs,function(categ) {
                            var v=categ_vals[categ][subcateg]||0;
                            ser_data.push(v);
                        });
                        series.push({
                            name: subcateg,
                            data: ser_data
                        });
                    });
                } else {
                    var ser_data=[];
                    series.push({
                        name: agg_field.string,
                        data: ser_data
                    });
                    _.each(data,function(r) {
                        var f=get_field_path(that.options.model,group_field1);
                        var categ=render_field_value(r[group_field1],f);
                        var val=r[agg_field.name];
                        categs.push(categ);
                        ser_data.push(val);
                    });
                }
                log("bar chart series",series);
                NFView.prototype.render.call(that);
                var chart_el=that.$el.find(".chart")[0];
                var chart=new Highcharts.Chart({
                    chart: {
                        renderTo: chart_el,
                        type: "column"
                    },
                    title: {
                        text: ""
                    },
                    xAxis: {
                        categories: categs
                    },
                    yAxis: {
                        title: {
                            enabled: false,
                            text: ""
                        }
                    },
                    series: series,
                    credits: {
                        enabled: false
                    }
                });
            } else if (view_type=="pie") {
                var group_field=get_field_path(that.options.model,group_field1);
                if (agg_field1) {
                    var f=get_field_path(that.options.model,agg_field1);
                    var agg_field={
                        name: agg_field1,
                        string: f.string
                    };
                } else {
                    var agg_field={
                        name: "_count",
                        string: "Count"
                    }
                }
                var values=[];
                _.each(data,function(r) {
                    var categ=render_field_value(r[group_field1],group_field);
                    var val=r[agg_field.name];
                    values.push([categ,val]);
                });
                NFView.prototype.render.call(that);
                var chart_el=that.$el.find(".chart")[0];
                var chart=new Highcharts.Chart({
                    chart: {
                        renderTo: chart_el,
                        type: "pie"
                    },
                    title: {
                        text: ""
                    },
                    series: [{
                        name: agg_field.string,
                        data: values
                    }],
                    plotOptions: {
                        pie: {
                            dataLabels: {
                                enabled: true
                            }
                        }
                    },
                    credits: {
                        enabled: false
                    }
                });
            }
        });
        return this;
    },

    render_search_body: function(context) {
        //log("report_view.render_search_body",this,context);
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

                var hide=is_hidden({type:tag, model:that.options.model, name: name});
                if(hide) return;

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

    line_click: function(model) {
        log("report_view.line_click",this,model);
        if (this.$list.attr("action")) {
            var action={name:this.$list.attr("action")};
            if (this.$list.attr("action_options")) {
                var action_options=qs_to_obj(this.$list.attr("action_options"));
                _.extend(action,action_options);
            }
            action.active_id=model.id;
        } else if (this.options.action) {
            var action={name:this.options.action};
            if (this.options.action_options) {
                _.extend(action,this.options.action_options);
            }
            action.active_id=model.id;
        } else {
            var action=find_details_action(this.options.model,model.id);
        }
        exec_action(action);
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

    set_condition: function(condition) {
        log("report_view.set_condition",this,condition);
        var that=this;
        var model_cls=get_model(this.options.model);
        for (var i in condition) {
            var clause=condition[i];
            var n=clause[0];
            if (n.indexOf(".id")!=-1) {
                n=n.replace(".id","");
            }
            var f=model_cls.fields[n];
            if (!f) continue; // XXX
            log("clause",clause,n,f);
            var op=clause[1];
            var v=clause[2];
            if (f.type=="char") {
                if (v) v=v.replace(/%/g,"");
                that.model.set(n,v);
                log(n,"<-",v);
            } else if (f.type=="many2one") {
                if (_.isNumber(v)) {
                    that.model.set(n,v);
                    log(n,"<-",v);
                } else if (_.isString(v)) {
                    v=v.replace(/%/g,"");
                    that.model.set(n,v);
                    log(n,"<-",v);
                }
            } else if ((f.type=="date")||(f.type=="float")) {
                var r=that.model.get(n)||[null,null];
                if (op==">=") r[0]=v;
                else if (op=="<=") r[1]=v;
                that.model.set(n,r);
                log(n,"<-",r);
            } else if (f.type=="datetime") {
                var r=that.model.get(n)||[null,null];
                if (op==">=") r[0]=v.substr(0,10);
                else if (op=="<=") r[1]=v.substr(0,10);
                that.model.set(n,r);
                log(n,"<-",r);
            } else if (f.type=="many2many") {
                if (_.isNumber(v)) {
                    that.model.set(n,v);
                    log(n,"<-",v);
                }
            } else if (f.type=="selection") {
                that.model.set(n,v);
                log(n,"<-",v);
            }
        }
    },

    drill_down: function(e) {
        log("report_view.drill_down",this);
        e.preventDefault();
        e.stopPropagation();
        var group_field=this.model.get("_group_field1");
        log("group_field",group_field);
        var subgroup_field=this.model.get("_group_field2");
        log("subgroup_field",subgroup_field);
        var model_cls=get_model(this.options.model);
        var f=model_cls.fields[group_field];
        if (!f) throw "Invalid field: "+group_field;
        var vals=[];
        this.collection.each(function(m) {
            if (!m.get("_selected")) return;
            var val=m.get(group_field);
            if ((f.type=="many2one") && _.isArray(val)) {
                val=val[0];
            }
            vals.push(val);
        });
        log("vals",vals);
        if (vals.length==0) {
            set_flash("error","No rows selected.");
            render_flash();
            return;
        }
        if (vals.length>1) {
            set_flash("error","Can't select more than 1 row.");
            render_flash();
            return;
        }
        this.model.set(group_field,vals[0]);
        this.model.set("_group_field1",subgroup_field);
        this.model.set("_group_field2",null);
        this.render();
    },

    export_xls: function(e) {
        log("export_xls",e,this);
        e.preventDefault();
        var model=this.options.model;
        var group_field=this.model.get("_group_field1");
        var subgroup_field=this.model.get("_group_field2");
        var agg_field=this.model.get("_agg_field1");
        var agg_field2=this.model.get("_agg_field2");
        var condition=this.get_condition();
        var url="/report_xls?model="+model+"&condition="+JSON.stringify(condition);
        if (group_field) {
            url+="&group_field="+group_field;
        }
        if (subgroup_field) {
            url+="&subgroup_field="+subgroup_field;
        }
        if (agg_field) {
            url+="&agg_field="+agg_field;
        }
        if (agg_field2) {
            url+="&agg_field2="+agg_field2;
        }
        download_url(url);
    }
});

ReportView.register();
