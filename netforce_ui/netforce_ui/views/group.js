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

var Group=NFView.extend({
    _name: "group",

    initialize: function(options) {
        //log("group.initialize",this);
        NFView.prototype.initialize.call(this,options);
        this.$group=this.options.group_layout;
        this.listen_attrs();
    },

    render: function() {
        //log("group.render");
        var that=this;
        this.data.render_form_body=function($group,ctx) { return that.render_form_body.call(that,$group,ctx); };
        var attrs=this.eval_attrs();
        if (attrs.invisible) {
            this.$el.hide();
        } else {
            this.$el.show();
        }
        NFView.prototype.render.call(this);
        return this;
    },

    render_form_body: function($group,context) {
        //log("group.render_form_body",this,$group,context);
        var that=this;
        var body=$("<div/>");
        var row=$('<div class="row"/>');
        body.append(row);
        var columns=this.options.columns||2;
        var col_span=Math.floor(12/columns);
        var col=0;
        var attrs=this.eval_attrs();
        var form_layout=this.options.form_layout||"horizontal";
        $group.children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="field") {
                var name=$el.attr("name");
                var model=context.model;
                var field=model.get_field(name);
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
                var readonly=$el.attr("readonly")||that.options.readonly||attrs.readonly;
                if ($el.attr("readonly")=="0") { // XXX
                    readonly=false;
                }
                var ctx=_.clone(context);
                if ($el.attr("context")) {
                    var ctx2=eval_json($el.attr("context"),{}); // XXX
                    _.extend(ctx,ctx2);
                }
                var opts={
                    name: name,
                    readonly: readonly,
                    required: $el.attr("required"),
                    nolabel: $el.attr("nolabel"),
                    invisible: $el.attr("invisible"),
                    onchange: $el.attr("onchange"),
                    click_action: $el.attr("click_action"),
                    count: $el.attr("count")||1,
                    password: $el.attr("password"),
                    size: $el.attr("size"),
                    selection: $el.attr("selection"),
                    attrs: $el.attr("attrs"),
                    width: $el.attr("width"),
                    height: $el.attr("height"),
                    condition: $el.attr("condition"),
                    perm: $el.attr("perm"),
                    pkg: $el.attr("pkg"),
                    mode: $el.attr("mode"),
                    link: $el.attr("link"),
                    view: $el.attr("view"),
                    strong: $el.attr("strong"),
                    select_view_xml: $el.attr("select_view_xml"),
                    create: $el.attr("create"),
                    search_mode: $el.attr("search_mode"),
                    string: $el.attr("string"),
                    method: $el.attr("method"),
                    show_buttons: $el.attr("show_buttons"),
                    auto_save: $el.attr("auto_save"),
                    email: $el.attr("email"),
                    help: $el.attr("help"),
                    form_layout: form_layout,
                    context: ctx
                };
                if ($el.find("list").length>0) {
                    if (field.type=="one2many") {
                        opts.inner=function(params) { 
                            var $list=$el.find("list");
                            var sub_fields=[];
                            $list.children().each(function() {
                                var $el2=$(this);
                                sub_fields.push({
                                    name: $el2.attr("name"),
                                    condition: $el2.attr("condition"),
                                    readonly: $el2.attr("readonly"),
                                    required: $el2.attr("required"),
                                    invisible: $el2.attr("invisible"),
                                    onchange: $el2.attr("onchange"),
                                    onfocus: $el2.attr("onfocus"),
                                    search_mode: $el2.attr("search_mode"),
                                    scale: $el2.attr("scale"),
                                    create: $el2.attr("create"),
                                    attrs: $el2.attr("attrs")
                                });
                            });
                            var opts2={
                                fields: sub_fields,
                                readonly: $el.attr("readonly")||that.options.readonly,
                                default_count: $el.attr("count")||1,
                                noadd: $el.attr("noadd"),
                                noremove: $el.attr("noremove"),
                                context: params.context
                            }
                            var view=Sheet.make_view(opts2);
                            html="<div id=\""+view.cid+"\" class=\"view\"></div>";
                            return html;
                        };
                    } if (field.type=="many2many") {
                        opts.inner=function(params) { 
                            var $list=$el.find("list");
                            var sub_fields=[];
                            $list.find("field").each(function() {
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
                        opts.view_layout=$el.find("list"); // XXX
                    }
                    opts.field_names=[];
                    $el.find("list").find("field").each(function() {
                        var $el2=$(this);
                        opts.field_names.push($el2.attr("name"));
                    });
                } else if ($el.find("template").length>0) {
                    opts.inner=function(params) { 
                        log("o2m template inner",name,params);
                        var tmpl_src=(new XMLSerializer()).serializeToString($el.find("template")[0]).replace("<template>","").replace("</template>","");
                        log("tmpl_src",tmpl_src);
                        var tmpl=Handlebars.compile(tmpl_src);
                        log("tmpl",tmpl);
                        var html=tmpl(params);
                        log("html");
                        return html;
                    };
                    opts.field_names=[];
                    $el.find("fields").find("field").each(function() {
                        var $el2=$(this);
                        opts.field_names.push($el2.attr("name"));
                    });
                    opts.raw=true;
                    opts.count=0;
                }
                var view=Field.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                col+=span;
                if (that.options.form_view) { // XXX
                    that.options.form_view.field_views[name]=view;
                }
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
                    attrs: $el.attr("attrs"),
                    context: context
                };
                if (that.active_id) {
                    opts.action_options="refer_id="+that.active_id;
                }
                var view=Button.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
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
            } else if (tag=="group") {
                var span=parseInt($el.attr("span"))||12;
                var offset=parseInt($el.attr("offset"))||0;
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
                    form_layout: $el.attr("form_layout")||that.options.form_layout,
                    context: context
                };
                var view_cls=get_view_cls("group");
                var view=view_cls.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                col+=span;
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
                    readonly: $el.attr("readonly")||that.options.readonly,
                    nobackground: $el.attr("readonly")||that.options.readonly,
                    context: context
                };
                var view=TabsView.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
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

    eval_attrs: function() {
        var str=this.options.attrs;
        //log("group.eval_attrs",this,str);
        if (!str) return {};
        var expr=JSON.parse(str);
        var model=this.context.model;
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
                } else if (op=="not in") {
                    clause_v=!_.contains(cons,v);
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

    listen_attrs: function() {
        var str=this.options.attrs;
        //log("listen_attrs",this,str);
        if (!str) return;
        var expr=JSON.parse(str);
        var attrs={};
        var depends=[];
        for (var attr in expr) {
            var conds=expr[attr];
            for (var i in conds) {
                var clause=conds[i];
                var n=clause[0];
                depends.push(n);
            }
        }
        //log("==> depends",depends);
        var model=this.context.model;
        for (var i in depends) {
            var n=depends[i];
            //log("...listen "+n);
            model.on("change:"+n,this.render,this);
        }
    }
});

Group.register();
