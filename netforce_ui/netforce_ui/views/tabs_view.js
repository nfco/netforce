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

var TabsView=NFView.extend({ // XXX: rename to tabs
    _name: "tabs_view",
    events: {
        "click ul.nav-tabs a": "click_tab"
    },

    initialize: function(options) {
        //log("tabs_view.initialize",this);
        NFView.prototype.initialize.call(this,options);
        this.$tabs=this.options.tabs_layout;

        //hidden remove separator
        this.spt_list=[];
        this.spt_rm=false;
    },

    render: function() {
        //log("tabs_view.render");
        var that=this;
        var tabs=[];
        var model=that.context.model;
        this.$tabs.children().each(function(i) {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag!="tab") throw "Expected 'tab' element";
            var perm=$el.attr("perm");
            if (perm && !check_other_permission(perm)) {
                return;
            }
            var attrs=that.eval_attrs($el.attr("attrs") || "");
            if(attrs.invisible){
                return;
            }
            var tab={
                string: $el.attr("string"),
                action: $el.attr("action"),
                active: i==0,
                tab_id: _.uniqueId("tab"),
                tab_layout: $el
            }

            var hide=is_hidden({type:"tab", model: that.context.model.name, name: tab.string});
            if(hide) return;

            tabs.push(tab);
        });
        if(!tabs.length) return;

        if(tabs){tabs[0]['active']=true;} // set active first tab
        this.tabs=tabs;
        this.data.tabs=tabs;
        this.data.render_form_body=function($tab,ctx) { return that.render_form_body.call(that,$tab,ctx); };
        NFView.prototype.render.call(this);
        if (tabs[0].action) {
            var model=this.context.model;
            var action={
                name: tabs[0].action,
                target: this.$el.find("#"+tabs[0].tab_id),
                refer_id: model.id
            }
            exec_action(action);
        }
        return this;
    },

    render_form_body: function($tab,context) {
        //log("tabs_view.render_form_body",$tab,context);
        var that=this;
        var body=$("<div/>");
        var row=$('<div class="row"/>');
        body.append(row);
        var col=0;
        var form_layout=this.options.form_layout||"horizontal";
        $tab.children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="field") {
                var name=$el.attr("name");

                var hide_opts=is_hidden({type:tag, model: that.context.model.name, name: name});

                if(hide_opts){
                    var sp_rm=hide_opts.separator_remove;
                    if(sp_rm=='before' && that.spt_list){
                        var cid=that.spt_list.pop();
                        body.find("#"+cid).last().remove();
                    }else if(sp_rm=='after'){
                        that.spt_rm=!that.spt_rm;
                    }
                    return;
                }

                var focus=$el.attr("focus");
                if(focus && that.options.form_view){
                    that.options.form_view.focus_field=name;
                }
                var model=context.model;
                var field=model.get_field(name);
                if (field && field.type=="one2many") {
                    default_span=12;
                } else {
                    default_span=6;
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
                var readonly=that.options.readonly;
                if ($el.attr("readonly")) {
                    readonly=$el.attr("readonly")=="1";
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
                    link: $el.attr("link"),
                    nolink: $el.attr("nolink"), // many2one only
                    view: $el.attr("view"),
                    mode: $el.attr("mode"),
                    wysi: $el.attr("wysi"),
                    help: $el.attr("help"),
                    string: $el.attr("string"),
                    create: $el.attr("create"),
                    search_mode: $el.attr("search_mode"),
                    action: $el.attr("action"),
                    form_layout: form_layout,
                    context: ctx
                };
                if ($el.find("list").length>0) {
                    opts.inner=function(params) { 
                        var view_cls_name=$el.attr("view_cls")||"sheet";
                        var $list=$el.find("list");
                        if (view_cls_name=="sheet") { // XXX
                            var sub_fields=[];
                            $list.children().each(function() {
                                var $el2=$(this);
                                var f2={
                                    name: $el2.attr("name"),
                                    condition: $el2.attr("condition"),
                                    click_action: $el2.attr("click_action"),
                                    readonly: $el2.attr("readonly"),
                                    required: $el2.attr("required"),
                                    focus: $el2.attr("focus"),
                                    invisible: $el2.attr("invisible"),
                                    onchange: $el2.attr("onchange"),
                                    onfocus: $el2.attr("onfocus"),
                                    create: $el2.attr("create"),
                                    search_mode: $el2.attr("search_mode"),
                                    string: $el2.attr("string"),
                                    selection: $el2.attr("selection"),
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
                                count: parseInt($el.attr("count")),
                                readonly: $el.attr("readonly")||that.options.readonly,
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
                if(name!='id'){
                    var view=Field.make_view(opts);
                    cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                    col+=span;
                }
            } else if (tag=="separator") {

                //hidden remove separator
                if(that.spt_rm){
                    that.spt_rm=!that.spt_rm;
                    return;
                }

                var span=$el.attr("span")
                if (span) cols=parseInt(span);
                else span=12;
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                row.append(cell);
                var opts={
                    string: $el.attr("string")
                };

                var hide=is_hidden({type:"separator", model: that.context.model.name, name: opts.string});
                if(hide) return;

                var view=Separator.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                col+=span;
                // hidden
                that.spt_list.push(view.cid);
            } else if (tag=="newline") {
                col+=12;
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
                    form_layout: $el.attr("form_layout"),
                    columns: $el.attr("columns"),
                    readonly: $el.attr("readonly")||that.options.readonly,
                    form_view: that.options.form_view,
                    context: context
                };
                var view_cls=get_view_cls("group");
                var view=view_cls.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
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
                    attrs: $el.attr("attrs"),
                    confirm: $el.attr("confirm"),
                    context: context
                };
                if (that.active_id) {
                    opts.action_options="refer_id="+that.active_id;
                }
                var view=Button.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            }
        });

        return body.html();
    },

    eval_attrs: function(attrs) {
        var str=attrs;
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

    click_tab: function(e) {
        log("click_tab");
        e.preventDefault();
        e.stopPropagation();
        var tab_id=$(e.target).attr("href").substr(1);
        log("tab_id",tab_id);
        var tab=_.find(this.tabs,function(t) { return t.tab_id==tab_id; });
        if (!tab) throw "Tab not found: "+tab_id;
        if (tab.action) {
            log("action tab");
            $(e.target).tab("show");
            var model=this.context.model;
            var action={
                name: tab.action,
                target: tab_id,
                refer_id: model.id
            };
            exec_action(action);
        } else {
            log("normal tab");
            $(e.target).tab("show");
        }
    }
});

TabsView.register();
