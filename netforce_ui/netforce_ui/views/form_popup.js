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

var FormPopup=NFView.extend({
    _name: "form_popup",
    className: "modal nf-modal",

    initialize: function(options) {
        //log("form_popup.initialize",this);
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
        this.next_action=this.options.next_action;
        this.next_action_options=this.options.next_action_options;
    },

    render: function() {
        //log("form_popup.render",this);
        var that=this;
        var model_name=this.options.model;
        var field_names=[];
        var model_cls=get_model_cls(model_name);
        this.$form.find("field").each(function() {
            if ($(this).parents("field").length>0) {
                return;
            }
            var name=$(this).attr("name");
            field_names.push(name);
        });
        this.field_names=field_names;
        this.data.popup_title=this.$form.attr("title")||this.options.string;
        if (this.active_id) {
            rpc_execute(model_name,"read",[[this.active_id]],{field_names:field_names},function(err,data) {
                that.model=new NFModel(data[0],{name:model_name});
                that.model.on("reload",that.reload,that);
                that.data.context.data=data[0];
                that.data.context.model=that.model;
                NFView.prototype.render.call(that);
                if (that.options.width) {
                    that.$el.find(".modal-dialog").width(that.options.width);
                }
                if (that.$form.attr("height")) {
                    var h=parseInt(that.$form.attr("height"));
                    that.$el.find(".modal-body").height(h);
                }
            });
        } else {
            var ctx=clean_context(_.extend({},this.context,this.options));
            rpc_execute(model_name,"default_get_data",[],{field_names:field_names,context:ctx},function(err,res) {
                var data=res[0];
                that.data.context.field_default=res[1];
                that.model=new NFModel(data,{name:model_name});
                that.model.on("reload",that.reload,that);
                that.data.context.data=data;
                that.data.context.model=that.model;
                NFView.prototype.render.call(that);
                if (that.options.width) {
                    that.$el.find(".modal-dialog").width(that.options.width);
                }
                if (that.$form.attr("height")) {
                    var h=parseInt(that.$form.attr("height"));
                    that.$el.find(".modal-body").height(h);
                }
            });
        }
        return this;
    },

    reload: function() {
        this.active_id=this.model.id;
        this.render();
    },

    render_form_body: function(context) {
        //log("form_popup.render_form_body",this,context,$form);
        var that=this;
        var body=$("<div/>");
        var row=$('<div class="row"/>');
        body.append(row);
        var line_cols=0;
        var columns=parseInt(this.options.columns)||1;
        var col_span=Math.floor(12/columns);
        var form_layout=this.options.form_layout||"horizontal";
        this.$form.children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="field") {
                var name=$el.attr("name");
                var field=get_field(that.options.model,name);
                if (field.type=="one2many" || field.type=="many2many") {
                    default_span=12;
                } else {
                    default_span=col_span;
                }
                var span=$el.attr("span");
                if (span) span=parseInt(span);
                else span=default_span;
                if (line_cols+span>12) {
                    line_cols=0;
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
                var opts={
                    name: name,
                    readonly: $el.attr("readonly"),
                    required: $el.attr("required"),
                    nolabel: $el.attr("nolabel"),
                    invisible: $el.attr("invisible"),
                    onchange: $el.attr("onchange"),
                    password: $el.attr("password"),
                    size: $el.attr("size"),
                    selection: $el.attr("selection"),
                    attrs: $el.attr("attrs"),
                    width: $el.attr("width"),
                    height: $el.attr("height"),
                    condition: $el.attr("condition")||$el.attr("condition"), // XXX
                    perm: $el.attr("perm"),
                    link: $el.attr("link"),
                    view: $el.attr("view"),
                    count: $el.attr("count"),
                    string: $el.attr("string"),
                    confirm: $el.attr("confirm"),
                    form_layout: form_layout,
                    context: context
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
                                    show_image: $el2.attr("show_image"),
                                    onchange: $el2.attr("onchange")
                                });
                            });
                            var opts2={
                                fields: sub_fields,
                                default_count: 1,
                                noadd: $list.attr("noadd"),
                                noremove: $list.attr("noremove"),
                                context: params.context
                            }
                            var view=Sheet.make_view(opts2);
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
                line_cols+=span;
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
                line_cols+=span;
            } else if (tag=="newline") {
                line_cols+=12;
            } else if (tag=="tabs") {
                var span=$el.attr("span")
                if (span) cols=parseInt(span);
                else span=12;
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                row.append(cell);
                var opts={
                    tabs_layout: $el,
                    context: context
                };
                var view=TabsView.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                line_cols+=span;
            } else if (tag=="group") {
                var span=$el.attr("span")
                if (span) span=parseInt(span);
                else span=12;
                var offset=$el.attr("offset")
                if (offset) offset=parseInt(offset);
                else offset=0;
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
                    context: context
                };
                var view_cls=get_view_cls("group");
                var view=view_cls.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                line_cols+=span;
            } else if (tag=="label") {
                var span=$el.attr("span")
                if (span) cols=parseInt(span);
                else span=6;
                var cell=$('<div/>');
                cell.addClass("col-sm-"+span);
                row.append(cell);
                cell.text($el.attr("string"));
                line_cols+=span;
            } else if (tag=="template") {
                var span=$el.attr("span")
                if (span) span=parseInt(span);
                else span=12;
                var offset=$el.attr("offset")
                if (offset) offset=parseInt(offset);
                else offset=0;
                line_cols+=offset;
                if (line_cols+span>12) {
                    line_cols=0;
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
                line_cols+=span;
            }
        });
        return body.html();
    },

    render_form_foot: function(context) {
        //log("form_popup.render_form_foot",this,context);
        var that=this;
        var foot=$("<div/>");
        this.$form.find("foot").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="button") {
                var opts={
                    string: $el.attr("string"),
                    method: $el.attr("method"),
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
                var view=Button.make_view(opts);
                foot.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            }
        });
        if (!this.$form.find("foot").attr("replace")) {
            var opts={
                string: "Cancel",
                action: "_close",
                context: context
            };
            var view=Button.make_view(opts);
            foot.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
        }
        return foot.html();
    }
});

FormPopup.register();
