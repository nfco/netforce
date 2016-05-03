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

var FormView=NFView.extend({
    _name: "form_view",
    events: {
        "click ol.breadcrumb li": "click_bread",
        "click .call-method": "call_method"
    },

    initialize: function(options) {
        //log("form_view.initialize",this);
        var that=this;
        NFView.prototype.initialize.call(this,options);
        if (this.options.form_layout) {
            var layout=this.options.form_layout;
        } else {
            if (this.options.view_xml) {
                var form_view=get_xml_layout({name:this.options.view_xml});
            } else {
                var form_view=get_xml_layout({model:this.options.model,type:"form"});
            }
            var layout=form_view.layout;
        }
        if (_.isString(layout)) {
            var doc=$.parseXML(layout);
            this.$form=$(doc).children();
        } else {
            this.$form=layout;
        }
        if (this.options.active_id) {
            this.active_id=parseInt(this.options.active_id);
        } else {
            this.active_id=null;
        }
        this.data.render_form_body=function(ctx) { return that.render_form_body.call(that,ctx); };
        this.data.render_form_foot=function(ctx) { return that.render_form_foot.call(that,ctx); };
        this.data.render_form_head=function(ctx) { return that.render_form_head.call(that,ctx); };
        this.data.render_form_related=function(ctx) { return that.render_form_related.call(that,ctx); };
        if (this.options.action_name) {
            this.data.show_bread=true;
            this.data.bread_string=this.options.string;
            this.data.bread_action=this.options.action_name;
        }
        this.next_action=this.options.next_action;
        if (!this.next_action && this.options.name) {
            this.next_action=this.options.name;
        }
        if (!this.next_action) throw "FormView: missing next_action";
        this.next_action_options=this.options.next_action_options;
        if (this.$form.find("script")) {
            this.data.script=this.$form.find("script").text();
        }
    },

    render: function() {
        //log("form_view.render",this);
        var that=this;
        this.field_views={};
        var model_name=this.options.model;
        var field_names=[];
        var model_cls=get_model(model_name);
        this.$form.find("field").each(function() {
            if ($(this).parents("field").length>0) {
                return;
            }
            if ($(this).parents("related").length>0) {
                return;
            }
            var name=$(this).attr("name");
            field_names.push(name);
        });
        this.field_names=field_names;
        var title_field=this.$form.attr("title_field");
        if (title_field) {
            this.field_names.push(title_field);
        }
        var breads=[];
        this.$form.find("bread").children().each(function() {
            breads.push({
                string: $(this).attr("string"),
                action: $(this).attr("action")
            });
        });
        this.data.breads=breads;
        this.render_waiting();
        if (this.active_id) {
            var ctx=clean_context(_.extend({},this.context,this.options));
            var opts={
                field_names:field_names,
                get_time: true,
                context:ctx
            };
            var args=[[this.active_id]];
            nf_execute(model_name,"read",args,opts,function(err,data) {
                if (err) throw "ERROR: "+err;
                var form_data=data[0];
                var read_time=form_data.read_time;
                delete form_data.read_time;
                that.model=new NFModel(form_data,{name:model_name});
                that.model.set_orig_data(form_data);
                that.model.read_time=read_time;
                that.model.on("reload",that.reload,that);
                that.data.context.data=form_data;
                that.data.context.model=that.model;
                var attrs=that.eval_attrs();
                that.readonly=attrs.readonly;
                that.data.readonly=that.readonly;
                if (title_field) {
                    that.data.page_title=that.model.get(title_field);
                } else {
                    if (that.$form.attr("title")) {
                        that.data.page_title=that.$form.attr("title");
                    } else {
                        if (that.data.readonly) {
                            var title="View";
                        } else {
                            var title="Edit";
                        }
                        var model_string=that.options.model_string||that.$form.attr("model_string")||model_cls.string;
                        if (model_string) {
                            title+=" "+model_string;
                        }
                        that.data.page_title=title;
                    }
                }
                if (that.$form.find("head").length>0) {
                    that.data.show_head=true;
                }
                var $el=that.$form.find("head field");
                if ($el.length>0) {
                    var name=$el.attr("name");
                    that.data.head_title="<b>"+field_value(name,that.data.context)+"</b>";
                }
                if (that.$form.attr("show_company")) {
                    that.data.show_company=true;
                    var val=that.model.get("company_id");
                    that.data.company_name=val?val[1]:null;
                }
                var expr=that.$form.find("foot").attr("states");
                if (expr) {
                    var states=expr.split(",");
                    that.data.show_foot=_.contains(states,that.model.get("state"));
                } else {
                    that.data.show_foot=true;
                }
                that.data.show_background=!that.data.readonly;
                var args=[that.options.search_condition || []];
                var opts={
                    offset: that.options.offset||0,
                    limit: that.options.limit||100,
                };
                nf_execute(model_name,"search",args,opts,function(err,data) {
                    if (err) throw "ERROR: "+err;
                    that.data.count=data.length;
                    that.data.record_index=data.indexOf(that.active_id);
                    that.data.record_index_p1=that.data.record_index+1;
                    if (that.data.record_index>0) {
                        var prev_active_id=data[that.data.record_index-1];
                        var h=window.location.hash.substr(1);
                        var action=qs_to_obj(h);
                        action.active_id=prev_active_id;
                        var h2=obj_to_qs(action);
                        that.data.prev_url="#"+h2;

                        var start_active_id=data[0];
                        var h=window.location.hash.substr(1);
                        var action=qs_to_obj(h);
                        action.active_id=start_active_id;
                        var h2=obj_to_qs(action);
                        that.data.start_url="#"+h2;
                    }
                    if (that.data.record_index < that.data.count-1) {
                        var next_active_id=data[that.data.record_index+1];
                        var h=window.location.hash.substr(1);
                        var action=qs_to_obj(h);
                        action.active_id=next_active_id;
                        var h2=obj_to_qs(action);
                        that.data.next_url="#"+h2;

                        var end_active_id=data[data.length-1];
                        var h=window.location.hash.substr(1);
                        var action=qs_to_obj(h);
                        action.active_id=end_active_id;
                        var h2=obj_to_qs(action);
                        that.data.end_url="#"+h2;
                    }
                    NFView.prototype.render.call(that);
                    if (that.focus_field) {
                        var view=that.get_field_view(that.focus_field);
                        view.focus();
                    }
                });
            });
        } else {
            var ctx=clean_context(_.extend({},this.context,this.options));
            if (this.options.defaults) {
                ctx.defaults=this.options.defaults;
            }
            var opts={
                field_names: field_names,
                context: ctx
            };
            nf_execute(model_name,"default_get",[],opts,function(err,data) {
                if (err) throw "ERROR: "+err;
                that.model=new NFModel(data,{name:model_name});
                that.model.on("reload",that.reload,that);
                that.data.context.data=data;
                that.data.context.model=that.model;
                if (title_field) {
                    that.data.page_title=that.model.get(title_field);
                } else {
                    if (that.$form.attr("title")) {
                        that.data.page_title=that.$form.attr("title");
                    } else {
                        var title="New";
                        var model_string=that.options.model_string||that.$form.attr("model_string")||model_cls.string;
                        if (model_string) {
                            title+=" "+model_string;
                        }
                        that.data.page_title=title;
                    }
                }
                if (that.$form.find("head").length>0) {
                    that.data.show_head=true;
                }
                var $el=that.$form.find("head field");
                if ($el.length>0) {
                    var name=$el.attr("name");
                    that.data.head_title="<b>"+field_value(name,that.data.context)+"</b>";
                }
                var attrs=that.eval_attrs();
                that.readonly=attrs.readonly;
                if (that.$form.attr("show_company")) {
                    that.data.show_company=true;
                    var val=that.model.get("company_id");
                    that.data.company_name=val?val[1]:null;
                }
                var expr=that.$form.find("foot").attr("states");
                if (expr) {
                    var states=expr.split(",");
                    that.data.show_foot=_.contains(states,that.model.get("state"));
                } else {
                    that.data.show_foot=true;
                }
                that.data.show_background=!that.data.readonly;
                NFView.prototype.render.call(that);
                if (that.focus_field) {
                    var view=that.get_field_view(that.focus_field);
                    view.focus();
                }
            });
        }
        return this;
    },

    get_field_view: function(field_name) {
        var view=this.field_views[field_name];
        if (!view) {
            log(this.field_views);
            throw "Can't find view of field "+field_name;
        }
        return view;
    },

    render_waiting: function() {
        var img=$("<img/>").attr("src","/static/img/spinner.gif");
        this.$el.empty();
        this.$el.append(img);
    },

    reload: function(opts) {
        log("form_view.reload",opts);
        if (!opts) opts={};
        this.active_id=this.model.id;
        this.focus_field=opts.focus_field;
        this.render();
    },

    render_form_body: function(context) {
        //log("render_form_body",this,context,$form);
        var that=this;
        var body=$("<div/>");
        var row=$('<div class="row"/>');
        body.append(row);
        var col=0;
        var readonly=this.readonly;
        var columns=parseInt(this.options.columns)||2;
        var col_span=Math.floor(12/columns);
        var form_layout=this.options.form_layout||"horizontal";
        this.$form.children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="field") {
                var name=$el.attr("name");
                var field=that.model.get_field(name);
                if (field.type=="one2many") {
                    default_span=12;
                } else {
                    default_span=col_span;
                }
                var span=$el.attr("span");
                if (span) span=parseInt(span);
                else span=default_span;
                if (col+span>12) {
                    col=0;
                    row=$('<div class="row"/>');
                    body.append(row);
                }
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                if ($el.attr("offset")) {
                    cell.addClass("col-sm-offset-"+$el.attr("offset"));
                }
                if (form_layout=="horizontal") {
                    cell.addClass("form-horizontal");
                }
                row.append(cell);
                var ctx=_.clone(context);
                if ($el.attr("context")) {
                    var ctx2=eval_json($el.attr("context"),{}); // XXX
                    _.extend(ctx,ctx2);
                }
                var readonly=that.readonly;
                if ($el.attr("readonly")!=null) {
                    readonly=$el.attr("readonly")=="1";
                }
                var opts={
                    name: name,
                    readonly: readonly,
                    required: $el.attr("required"),
                    nolabel: $el.attr("nolabel"),
                    invisible: $el.attr("invisible"),
                    onchange: $el.attr("onchange"),
                    count: $el.attr("count")||1,
                    password: $el.attr("password"),
                    size: $el.attr("size"),
                    click_action: $el.attr("click_action"),
                    selection: $el.attr("selection"),
                    attrs: $el.attr("attrs"),
                    width: $el.attr("width"),
                    height: $el.attr("height"),
                    condition: $el.attr("condition")||$el.attr("condition"), // XXX
                    perm: $el.attr("perm"),
                    pkg: $el.attr("pkg"),
                    link: $el.attr("link"),
                    view: $el.attr("view"),
                    help: $el.attr("help"),
                    wysi: $el.attr("wysi"),
                    mode: $el.attr("mode"),
                    target: $el.attr("target"),
                    mode: $el.attr("mode"),
                    create: $el.attr("create"),
                    search_mode: $el.attr("search_mode"),
                    method: $el.attr("method"),
                    string: $el.attr("string"),
                    form_layout: form_layout,
                    context: ctx
                };
                if ($el.find("list").length>0) {
                    if (field.type=="one2many") {
                        opts.inner=function(params) { 
                            var view_cls_name=$el.attr("view_cls")||"sheet";
                            var $list=$el.find("list");
                            if (view_cls_name=="sheet") { // XXX
                                var sub_fields=[];
                                $list.children().each(function() {
                                    var $el2=$(this);
                                    var f2={
                                        name: $el2.attr("name"),
                                        condition: $el2.attr("condition")||$el2.attr("condition"), // XXX
                                        readonly: $el2.attr("readonly"),
                                        required: $el2.attr("required"),
                                        invisible: $el2.attr("invisible"),
                                        onchange: $el2.attr("onchange"),
                                        onfocus: $el2.attr("onfocus"),
                                        create: $el2.attr("create"),
                                        search_mode: $el2.attr("search_mode"),
                                        scale: $el2.attr("scale"),
                                        attrs: $el2.attr("attrs")
                                    };
                                    if ($el2.attr("readonly")) {
                                        f2.readonly=$el2.attr("readonly")=="1";
                                    }
                                    sub_fields.push(f2);
                                });
                                var opts2={
                                    fields: sub_fields,
                                    default_count: parseInt($el.attr("default_count"))||1,
                                    readonly: $el.attr("readonly")||that.readonly,
                                    noadd: $el.attr("noadd"),
                                    noremove: $el.attr("noremove"),
                                    context: params.context
                                }
                            } else if (view_cls_name=="form_list_view") { // XXX
                                var opts2={
                                    model: field.relation,
                                    list_layout: $list,
                                    context: params.context
                                }
                            }
                            var view_cls=get_view_cls(view_cls_name);
                            var view=view_cls.make_view(opts2);
                            html="<div id=\""+view.cid+"\" class=\"view\"></div>";
                            return html;
                        };
                    } else if (field.type=="many2many") {
                        opts.inner=function(params) { 
                            var $list=$el.find("list");
                            var sub_fields=[];
                            $list.children().each(function() {
                                var $el2=$(this);
                                sub_fields.push({
                                    col_type: "field",
                                    name: $el2.attr("name")
                                });
                            });
                            var opts2={
                                cols: sub_fields,
                                context: params.context
                            }
                            var view=List.make_view(opts2);
                            html="<div id=\""+view.cid+"\" class=\"view\"></div>";
                            return html;
                        };
                    }
                    opts.field_names=[];
                    $el.find("list").find("field").each(function() {
                        var $el2=$(this);
                        opts.field_names.push($el2.attr("name"));
                    });
                }
                var view=Field.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                col+=span;
                that.field_views[name]=view;
            } else if (tag=="separator") {
                var span=$el.attr("span")
                if (span) cols=parseInt(span);
                else span=12;
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                row.append(cell);
                var opts={
                    string: $el.attr("string")
                };
                var view=Separator.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                col+=span;
            } else if (tag=="newline") {
                col+=12;
            } else if (tag=="tabs") {
                var span=$el.attr("span")
                if (span) span=parseInt(span);
                else span=12;
                if (col+span>12) {
                    col=0;
                    row=$('<div class="row"/>');
                    body.append(row);
                }
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                row.append(cell);
                var opts={
                    tabs_layout: $el,
                    readonly: $el.attr("readonly")||that.readonly,
                    nobackground: $el.attr("readonly")||that.readonly,
                    context: context
                };
                var view=TabsView.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                col+=span;
            } else if (tag=="group") {
                var span=$el.attr("span")
                if (span) span=parseInt(span);
                else span=12;
                var offset=$el.attr("offset")
                if (offset) offset=parseInt(offset);
                else offset=0;
                col+=offset;
                if (col+span>12) {
                    col=0;
                    row=$('<div class="row"/>');
                    body.append(row);
                }
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                if (offset) {
                    cell.addClass("col-sm-offset-"+offset);
                }
                row.append(cell);
                var opts={
                    group_layout: $el,
                    attrs: $el.attr("attrs"),
                    span: $el.attr("span"),
                    columns: $el.attr("columns"),
                    readonly: $el.attr("readonly")||that.readonly,
                    form_layout: $el.attr("form_layout"),
                    form_view: that,
                    context: context
                };
                var view_cls=get_view_cls("group");
                var view=view_cls.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                col+=span;
            } else if (tag=="label") {
                var span=$el.attr("span")
                if (span) cols=parseInt(span);
                else span=12;
                var cell=$('<div style="margin-bottom:10px"/>');
                cell.addClass("col-sm-"+span);
                row.append(cell);
                cell.text($el.attr("string"));
                col+=span;
            } else if (tag=="button") {
                var span=$el.attr("span")
                if (span) span=parseInt(span);
                else span=2;
                if (col+span>12) {
                    col=0;
                    row=$('<div class="row"/>');
                    body.append(row);
                }
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                cell.css({"padding-top":"10px"});
                row.append(cell);
                col+=span;
                var opts={
                    string: $el.attr("string"),
                    method: $el.attr("method"),
                    action: $el.attr("action"),
                    action_context: $el.attr("action_context"),
                    size: $el.attr("size"),
                    type: $el.attr("type"),
                    next: $el.attr("next"),
                    icon: $el.attr("icon"),
                    states: $el.attr("states"),
                    perm: $el.attr("perm"),
                    perm_model: $el.attr("perm_model"),
                    attrs: $el.attr("attrs"),
                    context: context
                };
                if (that.active_id) {
                    opts.action_options="refer_id="+that.active_id;
                }
                var view=Button.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            } else if (tag=="html") {
                var span=$el.attr("span")
                if (span) span=parseInt(span);
                else span=12;
                var offset=$el.attr("offset")
                if (offset) offset=parseInt(offset);
                else offset=0;
                col+=offset;
                if (col+span>12) {
                    col=0;
                    row=$('<div class="row"/>');
                    body.append(row);
                }
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                if (offset) {
                    cell.addClass("col-sm-offset-"+offset);
                }
                row.append(cell);
                cell.append($el.children().clone());
                col+=span;
            } else if (tag=="template") {
                var span=$el.attr("span")
                if (span) span=parseInt(span);
                else span=12;
                var offset=$el.attr("offset")
                if (offset) offset=parseInt(offset);
                else offset=0;
                col+=offset;
                if (col+span>12) {
                    col=0;
                    row=$('<div class="row"/>');
                    body.append(row);
                }
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                if (offset) {
                    cell.addClass("col-sm-offset-"+offset);
                }
                row.append(cell);
                var tmpl_src=(new XMLSerializer()).serializeToString($el[0]).replace("<template>","").replace("</template>","");
                var tmpl=Handlebars.compile(tmpl_src);
                var data={context:context};
                try {
                    var html=tmpl(data);
                } catch (err) {
                    throw "Failed to render template: "+err.message;
                }
                cell.append(html);
                col+=span;
            }
        });
        return body.html();
    },

    render_form_foot: function(context) {
        //log("render_form_foot",this,context);
        var that=this;
        var foot=$("<div/>");
        if (!this.$form.find("foot").attr("replace")) {
            if (!this.readonly||this.$form.attr("show_save")=="1") {
                if ((this.model.id && check_model_permission(this.options.model,"write"))||(!this.model.id && check_model_permission(this.options.model,"create"))) {
                    var opts={
                        string: "Save",
                        method: "_save",
                        size: "large",
                        type: "primary",
                        next: function() { // XXX: simplify this
                            var action={name:that.next_action,active_id:that.model.id};
                            if (that.next_action_options) {
                                _.extend(action,qs_to_obj(that.next_action_options));
                            }
                            exec_action(action);
                        },
                        context: context
                    };
                    var view=Button.make_view(opts);
                    foot.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                }
            }
        }
        this.$form.find("foot").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="button") {
                var opts={
                    string: $el.attr("string"),
                    method: $el.attr("method"),
                    action: $el.attr("action"),
                    next: $el.attr("next"),
                    action_context: $el.attr("action_context"),
                    size: $el.attr("size")||"large",
                    type: $el.attr("type"),
                    icon: $el.attr("icon"),
                    states: $el.attr("states"),
                    perm: $el.attr("perm"),
                    perm_model: $el.attr("perm_model"),
                    attrs: $el.attr("attrs"),
                    split: $el.attr("split"),
                    confirm: $el.attr("confirm"),
                    context: context
                };
                if (opts['method']=='_save') {
                        opts['next']=function() {
                            var action={name:that.next_action,active_id:that.model.id,form_view_xml:that.options.view_xml};
                            if (that.next_action_options) {
                                _.extend(action,qs_to_obj(that.next_action_options));
                            }
                            exec_action(action);
                        };
                }
                if (that.active_id) {
                    opts.action_options="refer_id="+that.active_id;
                }
                if (opts.split) {
                    var inner="";
                    $el.children().each(function() {
                        var $el2=$(this);
                        var tag=$el2.prop("tagName");
                        if (tag=="item") {
                            var opts2={
                                string: $el2.attr("string"),
                                method: $el2.attr("method"),
                                action: $el2.attr("action"),
                                action_options: $el2.attr("action_options"),
                                action_context: $el2.attr("action_context"),
                                states: $el2.attr("states"),
                                next: $el2.attr("next"),
                                confirm: $el2.attr("confirm"),
                                perm: $el2.attr("perm"),
                                perm_model: $el2.attr("perm_model"),
                                context: context
                            }
                            if (that.active_id) {
                                if (opts2.action_options) { // XXX
                                    opts2.action_options+="&";
                                } else{
                                    opts2.action_options="";
                                }
                                opts2.action_options+="refer_id="+that.active_id; // XXX: orig_id
                            }
                            var view=Item.make_view(opts2);
                            inner+="<li id=\""+view.cid+"\" class=\"view\"></li>";
                        } else if (tag=="divider") {
                            inner+="<li class=\"divider\"></li>";
                        }
                    });
                    opts.inner=function() {return inner; };
                    var view=ButtonGroup.make_view(opts);
                } else {
                    var view=Button.make_view(opts);
                }
                foot.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            }
        });
        if (!this.$form.find("foot").attr("replace")) {
            var opts={
                string: "Cancel",
                size: "large",
                pull: "right",
                onclick: function() {
                    log("click cancel");
                    var action={name:that.options.action_name};
                    if (_.contains(that.options.modes,"page") && that.model.id) {
                        action.mode="page";
                        action.active_id=that.model.id;
                    } else if (_.contains(that.options.modes,"list")) {
                        action.mode="list";
                        if (that.model.id) {
                            action.active_id=that.model.id;
                        }
                    }
                    exec_action(action);
                },
                context: context
            };
            var view=Button.make_view(opts);
            foot.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
        }
        return foot.html();
    },

    render_form_head: function(context) {
        //log("render_form_head",this,context);
        var that=this;
        var content=$("<div/>");
        this.$form.children("head").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="button") {
                var opts={
                    string: $el.attr("string"),
                    method: $el.attr("method"),
                    action: $el.attr("action"),
                    action_options: $el.attr("action_options"),
                    action_context: $el.attr("action_context"),
                    size: $el.attr("size")||"small",
                    type: $el.attr("type"),
                    next: $el.attr("next"),
                    icon: $el.attr("icon"),
                    dropdown: $el.attr("dropdown"),
                    align: "right",
                    perm: $el.attr("perm"),
                    perm_model: $el.attr("perm_model"),
                    context: context
                };
                if (that.active_id) {
                    opts.action_options="refer_model="+that.options.model+"&refer_id="+that.active_id; // XXX: orig_id
                }
                if (opts.dropdown) { // XXX
                    var inner="";
                    $el.children().each(function() {
                        var $el2=$(this);
                        var tag=$el2.prop("tagName");
                        if (tag=="item") {
                            var opts2={
                                string: $el2.attr("string"),
                                method: $el2.attr("method"),
                                action: $el2.attr("action"),
                                action_options: $el2.attr("action_options"),
                                action_context: $el2.attr("action_context"),
                                states: $el2.attr("states"),
                                confirm: $el2.attr("confirm"),
                                perm: $el2.attr("perm"),
                                perm_model: $el2.attr("perm_model"),
                                context: context
                            }
                            if (that.active_id) { // XXX: deprecated
                                if (opts2.action_options) { // XXX
                                    if (opts2.action_options[0]!="{") {
                                        opts2.action_options+="&";
                                        opts2.action_options+="refer_id="+that.active_id; // XXX: orig_id
                                    }
                                } else{
                                    opts2.action_options="";
                                    opts2.action_options+="refer_id="+that.active_id; // XXX: orig_id
                                }
                            }
                            var view=Item.make_view(opts2);
                            inner+="<li id=\""+view.cid+"\" class=\"view\"></li>";
                        } else if (tag=="divider") {
                            inner+="<li class=\"divider\"></li>";
                        }
                    });
                    opts.inner=function() {return inner; };
                    var view=ButtonGroup.make_view(opts);
                } else {
                    var view=Button.make_view(opts);
                }
                content.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            }
        });
        return content.html();
    },

    render_form_related: function(context) {
        //log("render_form_related",this,context);
        var that=this;
        var model=this.model;
        if (!model.id) return "";
        var content=$("<div/>");
        this.$form.find("related").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="field") {
                var name=$el.attr("name");
                var opts={
                    model: that.options.model,
                    field_name: name,
                    attrs: $el.attr("attrs"),
                    list_view_xml: $el.attr("list_view_xml"),
                    click_action: $el.attr("click_action"),
                    action: $el.attr("action"),
                    readonly: $el.attr("readonly"),
                    context: context
                };
                var $list=$el.find("list");
                if ($list.length>0) {
                    opts.list_layout=$list;
                }
                var $form=$el.find("form");
                if ($form.length>0) {
                    opts.form_layout=$form;
                }
                var view_cls=get_view_cls("related");
                var view=view_cls.make_view(opts);
                content.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            } else if (tag=="action") {
                var expr=$el.attr("states");
                if (expr) {
                    var states=expr.split(",");
                    if (!_.contains(states,that.model.get("state"))) {
                        return;
                    }
                }
                var action={
                    name: $el.attr("name"),
                    parent_id: model.id
                };
                var opts={
                    action: action,
                    context: context 
                };
                var view_cls=get_view_cls("action");
                var view=view_cls.make_view(opts);
                content.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            } else if (tag=="template") {
                var tmpl_src=(new XMLSerializer()).serializeToString($el[0]).replace(/<template(.*?)>/,"").replace("</template>","");
                log("tmpl_src");
                var tmpl=Handlebars.compile(tmpl_src);
                var data={context:context};
                log("tmpl data",data);
                var html=tmpl(data);
                log("tmpl html",html);
                content.append(html);
            }
        });
        return content.html();
    },

    eval_attrs: function() {
        var str=this.$form.attr("attrs");
        //log("form_view.eval_attrs",this,str);
        if (!str) return {};
        var expr=JSON.parse(str);
        var model=this.model;
        var attrs={};
        for (var attr in expr) {
            var conds=expr[attr];
            var attr_val=true;
            for (var i in conds) {
                var clause=conds[i];
                var n=clause[0];
                var op=clause[1];
                var cons=clause[2];
                var v=model.get(n);
                var clause_v;
                if (op=="=") {
                    clause_v=v==cons;
                } else if (op=="!=") {
                    clause_v=v!=cons;
                } else if (op=="in") {
                    clause_v=_.contains(cons,v);
                } else {
                    throw "Invalid operator: "+op;
                }
                if (!clause_v) {
                    attr_val=false;
                    break;
                }
            }
            attrs[attr]=attr_val;
        }
        //log("==>",attrs);
        return attrs;
    },

    click_bread: function(e) {
        log("form_view.click_bread");
        e.preventDefault();
        this.trigger("change_mode",{active_id:this.model.id});
    },

    call_method: function(e) {
        log("form_view.call_method");
        e.preventDefault();
        var $el=$(e.target).closest("a");
        var msg=$el.data("confirm");
        if (msg) {
            var res=confirm(msg);
            if (!res) return;
        }
        var method=$el.data("method");
        var context=$el.data("context");
        var that=this;
        nf_execute(this.model.name,method,[],{context:context},function(err,data) {
            if (err) {
                set_flash("error",err.message);
                render_flash();
                return;
            }
            if (data && data.flash) {
                set_flash(data.flash.type,data.flash.message);
            }
            if (data && data.next) {
                exec_action(data.next);
            } else {
                window.location.reload();
            }
        });
    }
});

FormView.register();
