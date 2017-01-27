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

var Sheet=NFView.extend({
    _name: "sheet",
    className: "nf-sheet",
    events: {
        "click .nf-sheet-add-line": "add_line",
        "mousedown .nf-row-handle": "drag_row",
        "focus .hidden-input-before": "focus_first_cell",
        "focus .hidden-input-after": "focus_last_cell"
    },

    initialize: function(options) {
        log("sheet init",this);
        var that=this;
        NFView.prototype.initialize.call(this,options);
        if (this.options.fields) {
            this.data.fields=this.options.fields;
        } else {
            var content=this.options.inner({context: this.context});
            var xml="<root>"+content+"</root>";
            //log("SHEET XML",xml);
            var doc=$.parseXML(xml);
            var fields=[];
            $(doc).find("root").children().each(function() {
                var $el=$(this);
                var tag=$el.prop("tagName");
                if (tag=="field") {
                    var f={
                        name: $el.attr("name"),
                        onchange: $el.attr("onchange"),
                        onfocus: $el.attr("onfocus"),
                        focus: $el.attr("focus"),
                        string: $el.attr("string"),
                        condition: $el.attr("condition")||$el.attr("condition"), // XXX
                        readonly: $el.attr("readonly"),
                        action: $el.attr("action"),
                        attrs: $el.attr("attrs")
                    };
                    if ($el.attr("readonly")) {
                        f.readonly=$el.attr("readonly")=="1";
                    }
                    fields.push(f);
                }
            });
            this.data.fields=fields;
        }
        this.field_names=_.pluck(this.data.fields,"name");
        var collection=this.context.collection;
        log("sheet collection",collection);
        var model_name=collection.name;

        if (collection.length==0 && this.options.default_count) {
            var ctx=clean_context(this.context);
            rpc_execute(model_name,"default_get",[this.field_names],{context:ctx},function(err,data) {
                var models=[];
                for (var i=0; i<that.options.default_count; i++) {
                    var model=new NFModel(data,{name:model_name});
                    models.push(model);
                }
                collection.add(models);
            });
        }
        collection.on("add remove",this.render,this);
    },

    render: function() {
        log("sheet.render",this);
        var that=this;
        this.data.sheet_view=this;
        this.data.show_add=!this.context.readonly && !this.options.readonly && !this.context.noadd && !this.options.noadd;
        this.data.readonly=this.options.readonly;
        var model_name=this.context.collection.name;
        that.required_fields={};
        _.each(this.data.fields,function(field) {
            var name=field.name;

            var hide=is_hidden({type:'field', model:model_name, name: name});
            if(hide){
                field.invisible=true;
            }

            var f=get_field(model_name,name);
            if (f.type=="float") {
                field.align="right";
            }
            if (f.required || field.required){
                that.required_fields[name]=true;
            }
            var perms=get_field_permissions(model_name,name);
            if (!perms.perm_read) {
                field.invisible=true;
            }
        });
        that.context.collection.each(function(model){
            for (field in that.required_fields){
                model.set_required(field);
            }
        });
        NFView.prototype.render.call(this);
    },

    add_line: function(e) {
        if(e){
            e.preventDefault();
            e.stopPropagation();
        }
        var collection=this.context.collection;
        var that=this;
        var model_name=collection.name;
        var ctx=clean_context(this.context);
        ctx.data=collection.parent_model.get_vals(); // XXX
        rpc_execute(model_name,"default_get",[this.field_names],{context:ctx},function(err,data) {
            var model=new NFModel(data,{name:model_name});
            collection.add(model);
            //========== focus field
            if(that.data.fields){
                var focus_field=that.data.fields[0].name; // set default to first column
                _.each(that.data.fields,function(field){
                    if(field.focus){focus_field=field.name;}
                });
                if (focus_field){
                    var cells=that.$el.find("td[data-field="+focus_field+"]").last();
                    var cell=cells[0];
                    that.focus_cell(cell);
                }
            }
        });
    },

    drag_row: function(e) {
        log("drag_row",this);
        e.stopPropagation();
        e.preventDefault();
        var from_cid=$(e.target).parent("tr").data("model-cid");
        log("from_cid",from_cid);
        var to_cid;
        var that=this;
        $("body").on("mousemove.row-drag",function(e) {
            e.stopPropagation();
            e.preventDefault();
            var x=e.pageX;
            var y=e.pageY;
            //log("mouse_move",x,y);
            that.$el.find("tr.sheet-line td").css("border-top","");
            to_cid=null;
            that.$el.find("tr.sheet-line").each(function() {
                var y0=$(this).offset().top;
                var y1=y0+$(this).outerHeight();
                if (y>=y0 && y<=y1) {
                    //log("found",this,y0,y1);
                    $(this).find("td").css("border-top","2px solid #369");
                    to_cid=$(this).data("model-cid");
                }
            });
        });
        $("body").one("mouseup",function(e) {
            log("mouseup");
            that.$el.find("tr.sheet-line td").css("border-top","");
            $("body").off("mousemove.row-drag");
            log("to_cid",to_cid);
            if (to_cid && to_cid!=from_cid) {
                var collection=that.context.collection;
                var from_model=collection.get(from_cid);
                var to_model=collection.get(to_cid);
                var i=collection.indexOf(to_model);
                collection.remove(from_model,{silent:true});
                collection.add(from_model,{at:i});
                if (from_model.get_field("sequence")) {
                    log("reset sequences");
                    collection.each(function(m,i) {
                        m.set("sequence",i,{silent:true});
                    });
                }
            }
        });
    },

    focus_first_cell: function() {
        log("sheet.focus_first_cell");
        var cell=this.$el.find(".sheet-cell[data-readonly!='1']:first");
        if (cell.length==0) {
            log("first cell not found");
            return;
        }
        this.focus_cell(cell[0]);
    },

    focus_last_cell: function() {
        log("sheet.focus_last_cell");
        var cell=this.$el.find(".sheet-cell[data-readonly!='1']:last");
        if (cell.length==0) {
            log("last cell not found");
            return;
        }
        this.focus_cell(cell[0]);
    },

    focus_cell: function(cell) {
        log("sheet.focus_cell",cell);
        var line_view=null;
        for (var view_id in this.subviews) {
            var view=this.subviews[view_id];
            if ($.contains(view.el,cell)) {
                line_view=view;
                break;
            }
        }
        if (!line_view) {
            log("line view not found");
            return;
        }
        line_view.focus_cell(cell);
    }
});

Sheet.register();
