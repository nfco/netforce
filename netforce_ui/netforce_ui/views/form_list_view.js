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

var FormListView=NFView.extend({
    _name: "form_list_view",

    initialize: function(options) {
        //log("form_list_view.initialize",this);
        var that=this;
        NFView.prototype.initialize.call(this,options);
        if (!this.options.model) throw "FormListView: missing model";
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
        this.data.render_list_head=function(ctx) { return that.render_list_head.call(that,ctx); };
        var collection=this.context.collection;
        collection.on("click",that.line_click,that);
    },

    render: function() {
        //log("form_list_view.render",this);
        var that=this;
        var model_name=this.options.model;
        var field_names=[];
        var cols=[];
        this.$list.find("field").each(function() {
            if (!$(this).attr("invisible")) {
                cols.push({
                    col_type: "field",
                    name: $(this).attr("name"),
                    link: $(this).attr("link"),
                    target: $(this).attr("target")
                });
            }
        });
        this.data.cols=cols;
        var no_buttons=false;
        if (this.options.readonly && this.$list.find("head button").length==0) {
            no_buttons=true;
        }
        this.data.noselect=this.options.noselect||no_buttons;
        NFView.prototype.render.call(that);
        return this;
    },

    render_list_head: function(context) {
        //log("form_list_view.render_list_head",this,context);
        var that=this;
        var html=$("<div/>");
        var collection=that.context.collection;
        if (!this.$list.find("head").attr("replace")) {
            if (collection.length>0 && !this.options.readonly && !this.options.noremove) {
                var opts={
                    string: "Delete",
                    type: "danger",
                    size: "small",
                    method: "_delete",
                    context: context
                };
                var view=Button.make_view(opts);
                html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            }
        }
        this.$list.find("head").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="button") {
                var opts={
                    string: $el.attr("string"),
                    method: $el.attr("method"),
                    action: $el.attr("action"),
                    action_options: $el.attr("action_options"),
                    size: $el.attr("size")||"small",
                    type: $el.attr("type"),
                    next: $el.attr("next"),
                    icon: $el.attr("icon"),
                    perm: $el.attr("perm"),
                    context: context
                };
                if (!$el.attr("noselect")) {
                    opts.select=true;
                }
                var view=Button.make_view(opts);
                html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            }
        });
        return html.html();
    },

    line_click: function(model) {
        log("form_list_view.line_click",this,model);
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
    }
});

FormListView.register();
