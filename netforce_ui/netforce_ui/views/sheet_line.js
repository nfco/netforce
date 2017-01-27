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

var SheetLine=NFView.extend({
    _name: "sheet_line",
    tagName: "tr",
    className: "sheet-line",
    events: {
        "click .nf-sheet-remove-line": "remove_line",
        "click td.sheet-cell": "click_cell",
        "contextmenu .nf-row-handle": "on_contextmenu"
    },

    initialize: function(options) {
        var that=this;
        NFView.prototype.initialize.call(this,options);
        var model=this.context.model;
        _.each(this.options.fields,function(f) {
            var name=f.name;
            model.on("change:"+name,function() {
                log("sheet_line model change: "+name);
                var cell=that.$el.find("td[data-field="+name+"]");
                if (cell.length==0) return;
                if (cell.hasClass("nf-cell-edit")) return;
                log("sheet_line rerender R/O: "+name);
                cell.empty();
                var val=field_value(name,that.context,null,null,true,f.click_action,f.show_image,f.scale);
                cell.html(val);
            });
            var field=model.get_field(name);
            var perms=get_field_permissions(model.name,name);
            if (field.readonly || !perms.perm_write) {
                f.readonly=true; // XXX
            }
            if (field.type=="float" || field.type=="decimal") {
                f.align="right";
            }
            if (field.required) {
                f.required=true;
            }
        });
        this.$el.data("model-cid",model.cid);
    },

    render: function() {
        //log("sheet_line render",this);
        this.sheet_view=this.options.sheet_view;
        var data={
            context: this.data.context
        };
        this.data.fields=this.options.fields;
        this.data.show_remove=!this.sheet_view.options.noremove && !this.context.readonly && !this.options.readonly;
        this.data.view_cid=this.cid; // XXX
        this.$el.data("view-cid",this.cid); // XXX
        NFView.prototype.render.call(this);
        this.$el.css({height: "22px", backgroundColor: "#fff"});
        return this;
    },

    remove_line: function(e) {
        e.preventDefault();
        e.stopPropagation();
        var collection=this.context.collection;
        var model=this.context.model;
        collection.remove(model);
    },

    click_cell: function(e) {
        log("click_cell",this);
        //e.preventDefault();
        e.stopPropagation();
        if ($(e.target).parents(".nf-field").length>0) {
            return;
        }
        if ($(e.target).hasClass("sheet-cell")) {
            var cell=e.target;
        } else {
            var cell=$(e.target).parents(".sheet-cell")[0];
        }
        this.focus_cell(cell);
    },

    focus_cell: function(cell) {
        log("sheet_line.focus_cell",cell);
        log("lineview cid",this.cid);
        log("model cid",this.context.model.cid);
        if (!$.contains(this.el,cell)) throw "Cell not found in line view";
        var that=this;
        var name=$(cell).data("field");
        log("field name",name);
        var fld=_.find(this.options.fields,function(f) {return f.name==name});
        log("fld",fld);
        if (!fld) throw "Invalid field: "+name;
        var field=this.context.model.get_field(name);
        var readonly=fld.readonly;
        if (readonly==null && fld.attrs) {
            var attrs=this.eval_attrs(fld.attrs);
            readonly=attrs.readonly;
        }
        if (readonly==null) {
            readonly=this.options.readonly;
        }
        if (readonly==null) {
            readonly=field.readonly;
        }
        if (readonly) {
            log("Field "+name+" is readonly");
            return;
        }
        var type=field.type;
        var view_cls=get_view_cls("field");
        var opts={
            name: name,
            nolabel: true,
            onchange: fld.onchange,
            onfocus: fld.onfocus,
            string: fld.string,
            condition: fld.condition,
            readonly: fld.readonly,
            required: fld.required,
            action: fld.action,
            attrs: fld.attrs,
            create: fld.create,
            search_mode: fld.search_mode,
            selection: fld.selection,
            show_image: fld.show_image,
            scale: fld.scale,
            context: this.context,
            nomargin: true,
            autoresize: true, // for text field only
            disable_edit_link: true, // for m2o field only
            disable_focus_change: true,
            form_layout: "stacked"
        };
        if (type=="boolean") {
            opts.use_select=true;
        }
        opts.width=$(cell).width()+10;
        opts.height=$(cell).height();
        field_view=view_cls.make_view(opts);
        field_view.render();
        $(cell).empty();
        $(cell).append(field_view.el);
        $(cell).width(opts.width-10);
        log("field_view",field_view);
        setTimeout(function() {
            field_view.focus();
            field_view.on("blur",function() {
                log("blur",name);
                //remove_view_instance(field_view.cid);
                $(cell).empty();
                var val=field_value(name,that.context,null,null,true,fld.click_action,fld.show_image,fld.scale);
                $(cell).html(val);
                $(cell).removeClass("nf-cell-edit");
                setTimeout(function() {
                    var res=sheet.find(".nf-cell-edit");
                    if (res.length==0) {
                        hidden.removeAttr("tabindex");
                    }
                },100);
            });
        },0);
        var err=this.context.model.get_field_error(name);
        if (err) {
            $(cell).addClass("cell-error");
        } else {
            $(cell).removeClass("cell-error");
        }
        $(cell).addClass("nf-cell-edit");
        var sheet=this.$el.parents(".nf-sheet");
        hidden=sheet.find(".hidden-input-before,.hidden-input-after");
        log("hidden",hidden);
        hidden.attr("tabindex","-1");
        field_view.on("focus_next",function() {
            log("sheet_line.focus_next");
            var el=field_view.$el;
            var cell=el.parents(".sheet-cell");
            log("cell",cell);
            var cells=cell.parents(".nf-sheet").find(".sheet-cell[data-readonly!='1']");
            var i=cells.index(cell);
            if (i==-1) throw "Cell position not found";
            if (i<cells.length-1) {
                var next_cell=cells.eq(i+1)[0];
                that.sheet_view.focus_cell(next_cell);
            } else {
                focus_next();
                that.sheet_view.add_line();
            }
        });
        field_view.on("focus_prev",function() {
            log("sheet_line.focus_prev");
            var el=field_view.$el;
            var cell=el.parents(".sheet-cell");
            log("cell",cell);
            var cells=cell.parents(".nf-sheet").find(".sheet-cell[data-readonly!='1']");
            var i=cells.index(cell);
            if (i==-1) throw "Cell position not found";
            if (i>0) {
                var prev_cell=cells.eq(i-1)[0];
                that.sheet_view.focus_cell(prev_cell);
            } else {
                focus_prev();
            }
        });
        field_view.on("focus_down",function() {
            log("sheet_line.focus_down");
            var el=field_view.$el;
            var cell=el.parents(".sheet-cell");
            var name=cell.data("field");
            log("cell",cell,"name",name);
            var cells=cell.parents(".nf-sheet").find(".sheet-cell[data-readonly!='1'][data-field='"+name+"']");
            var i=cells.index(cell);
            if (i==-1) throw "Cell position not found";
            if (i<cells.length-1) {
                var next_cell=cells.eq(i+1)[0];
                that.sheet_view.focus_cell(next_cell);
            }
        });
        field_view.on("focus_up",function() {
            log("sheet_line.focus_up");
            var el=field_view.$el;
            var cell=el.parents(".sheet-cell");
            var name=cell.data("field");
            log("cell",cell,"name",name);
            var cells=cell.parents(".nf-sheet").find(".sheet-cell[data-readonly!='1'][data-field='"+name+"']");
            var i=cells.index(cell);
            if (i==-1) throw "Cell position not found";
            if (i>0) {
                var next_cell=cells.eq(i-1)[0];
                that.sheet_view.focus_cell(next_cell);
            }
        });
        return true;
    },

    eval_attrs: function() {
        var str=this.options.attrs;
        //log("sheet_line.eval_attrs",this,str);
        if (!str) return {};
        var expr=JSON.parse(str);
        var model=this.context.model;
        var attrs={};
        for (var attr in expr) {
            var conds=expr[attr];
            if (_.isArray(conds)) {
                var attr_val=true;
            } else if (_.isObject(conds)) {
                var attr_val=conds.value;
                conds=conds.condition;
                if (!conds) {
                    throw "Missing condition in attrs expression: "+str;
                }
            } else {
                throw "Invalid attrs expression: "+str;
            }
            for (var i in conds) {
                var clause=conds[i];
                var n=clause[0];
                var op=clause[1];
                var cons=clause[2];
                var v=model.get_path_value(n);
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

    on_contextmenu: function(e) {
        e.preventDefault();
        var that=this;
        var view_cls=get_view_cls("context_menu");
        var opts={
            click_x: e.pageX,
            click_y: e.pageY,
            items: [
                {
                    string: "Insert line before",
                    callback: function() {
                        that.insert_line_before();
                    }
                },
                {
                    string: "Insert line after",
                    callback: function() {
                        that.insert_line_after();
                    }
                }
            ]
        };
        var view=view_cls.make_view(opts);
        $("body").append(view.el);
        view.render();
    },

    insert_line_before: function() {
        log("insert_line_before");
        var collection=this.context.collection;
        var model=this.context.model;
        var i=collection.indexOf(model);
        var new_model=new NFModel({},{name:collection.name});
        collection.add(new_model,{at:i});
    },

    insert_line_after: function() {
        log("insert_line_after");
        var collection=this.context.collection;
        var model=this.context.model;
        var i=collection.indexOf(model);
        var new_model=new NFModel({},{name:collection.name});
        collection.add(new_model,{at:i+1});
    }
});

SheetLine.register();
