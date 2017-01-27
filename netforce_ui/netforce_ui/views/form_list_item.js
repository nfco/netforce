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

var FormListItem=NFView.extend({
    _name: "form_list_item",
    events: {
        "click .btn-delete": "delete_item"
    },

    initialize: function(options) {
        //log("form_list_item.initialize",this);
        NFView.prototype.initialize.call(this,options);
        var layout=this.options.layout;
        if (_.isString(layout)) {
            var doc=$.parseXML(layout);
            this.$form=$(doc).children();
        } else {
            this.$form=layout;
        }
    },

    render: function() {
        //log("form_list_item.render",this);
        var that=this;
        this.data.render_form_body=function(ctx) { return that.render_form_body.call(that,ctx); };
        NFView.prototype.render.call(this);
        return this;
    },

    render_form_body: function(context) {
        //log("render_form_body",this,context);
        var that=this;
        var body=$("<div/>");
        var row=$('<div class="row"/>');
        body.append(row);
        var line_cols=0;
        var form_layout=this.options.form_layout||"horizontal";
        var model=this.context.model;
        this.$form.children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="field") {
                var name=$el.attr("name");

                var hide_opts=is_hidden({type:"field", model:model.name, name: name});
                if(hide_opts) return;

                var span=$el.attr("span")
                if (span) span=parseInt(span);
                else span=6;
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
                    count: $el.attr("count")||1,
                    password: $el.attr("password"),
                    size: $el.attr("size"),
                    selection: $el.attr("selection"),
                    attrs: $el.attr("attrs"),
                    width: $el.attr("width"),
                    height: $el.attr("height"),
                    condition: $el.attr("condition")||$el.attr("condition"), // XXX
                    perm: $el.attr("perm"),
                    link: $el.attr("link"),
                    nolink: $el.attr("nolink"), // only for many2one
                    form_layout: form_layout,
                    context: context
                };
                if ($el.find("list").length>0) {
                    opts.inner=function(params) { 
                        var $list=$el.find("list");
                        var sub_fields=[];
                        $list.children().each(function() {
                            var $el2=$(this);
                            sub_fields.push({
                                name: $el2.attr("name"),
                                condition: $el2.attr("condition")||$el2.attr("condition"), // XXX
                                onchange: $el2.attr("onchange")
                            });
                        });
                        var opts2={
                            fields: sub_fields,
                            context: params.context
                        }
                        var view=Sheet.make_view(opts2);
                        html="<div id=\""+view.cid+"\" class=\"view\"></div>";
                        return html;
                    };
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
            }
        });
        return body.html();
    },

    delete_item: function(e) {
        log("delete_item",this);
        e.preventDefault();
        e.stopPropagation();
        var collection=this.context.collection;
        var model=this.context.model;
        collection.remove(model);
    }
});

FormListItem.register();
