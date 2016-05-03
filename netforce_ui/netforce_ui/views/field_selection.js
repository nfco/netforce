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

var FieldSelection=NFView.extend({
    _name: "field_selection",
    className: "form-group nf-field",
    events: {
        "change select": "onchange",
        "blur select": "blur"
    },

    initialize: function(options) {
        NFView.prototype.initialize.call(this,options);
        var name=this.options.name;
        var model=this.context.model;
        model.on("change:"+name,this.render,this);
        model.on("error",this.render,this);
        this.listen_selection();
        this.listen_attrs();
    },

    render: function() {
        //log("field_selection.render",this);
        var name=this.options.name;
        this.$el.addClass("field-"+name);
        var model=this.context.model;
        var value=model.get(name);
        this.data.value=value;
        var field=model.get_field(name);
        if (!this.selection) {
            this.selection=field.selection;
            if (this.options.selection) {
                this.update_selection();
            }
        }
        //log("selection",this.selection);
        this.data.string=field.string;
        this.data.readonly=field.readonly||this.options.readonly||this.context.readonly;
        var attrs=this.eval_attrs();
        if (attrs.readonly!==undefined) {
            this.data.readonly=attrs.readonly;
        }
        var perms=get_field_permissions(model.name,name);
        if (!perms.perm_write) {
            this.data.readonly=true;
        }
        //log("readonly",this.data.readonly);
        var required=field.required||this.options.required;
        if (required && !this.data.readonly) {
            this.$el.addClass("nf-required-field");
        }
        if (required) {
            model.set_required(name);
        }
        if (this.options.inline) {
            this.$el.css({display: "inline"});
        }
        var that=this;
        var sel_group_vals={};
        var sel_groups=[];
        var sel_options=[];
        var group;
        for (var i in that.selection) {
            var v=that.selection[i];
            if (v[0]=="_group") {
                var label=v[1];
                group=sel_group_vals[label];
                if (!group) {
                    group={
                        "label": label,
                        "sel_options": []
                    }
                    sel_groups.push(group);
                    sel_group_vals[label]=group;
                }
            } else {
                var opt={
                    "value": v[0],
                    "string": v[1],
                    "selected": v[0]==value
                }
                if (group) {
                    group.sel_options.push(opt);
                } else {
                    sel_options.push(opt);
                }
                if (v[0]==value) that.data.value_string=v[1];
            }
        }
        if (sel_groups.length>0) {
            //log("sel_groups",sel_groups);
            that.data.sel_groups=sel_groups;
        } else {
            //log("sel_options",sel_options);
            that.data.sel_options=sel_options;
        }
        that.data.sel_options=sel_options;
        var form_layout=this.options.form_layout||"stacked";
        this.data.horizontal=form_layout=="horizontal";
        var pkg=this.options.pkg||field.pkg;
        if (!check_package(pkg)) {
            this.data.disabled=true;
        }
        NFView.prototype.render.call(that);
        var err=model.get_field_error(name);
        if (err) {
            that.$el.addClass("error");
        } else {
            that.$el.removeClass("error");
        }
        if (this.options.span && !this.options.span_input_only) { // XXX
            that.$el.addClass("col-sm-"+that.options.span);
        }
        if (that.options.invisible || attrs.invisible) {
            that.$el.hide();
        } else {
            that.$el.show();
        }
        if (this.options.width) {
            this.$el.find("select").css("width",this.options.width+"px");
            this.$el.css("width",this.options.width+"px");
        }
        this.$el.find("a.help").tooltip();
    },

    listen_selection: function() {
        var str=this.options.selection;
        if (!str) return;
        log("listen_selection",this,str);
        var re=/\w+\((.*)\)/;
        var m=re.exec(str);
        if (!m) return;
        var depends=m[1].split(",");
        log("==> depends",depends);
        var model=this.context.model;
        for (var i in depends) {
            var n=depends[i];
            log("...listen "+n);
            model.on("change:"+n,this.update_selection,this);
        }
    },

    update_selection: function() {
        var str=this.options.selection;
        if (!str) return;
        log("update_selection",this,str);
        var re=/(\w+)(\((.*)\))?/;
        var m=re.exec(str);
        var func=m[1];
        var arg_vals=[];
        var model=this.context.model;
        if (m[3]) {
            var args=m[3].split(",");
            var vals=model.get_vals();
            for (var i in args) {
                var n=args[i];
                var v=vals[n];
                arg_vals.push(v);
            }
        }
        var that=this;
        var ctx=clean_context(this.options.context);
        rpc_execute(model.name,func,arg_vals,{context:ctx},function(err,data) {
            that.selection=data;
            that.render();
        });
    },

    onchange: function() {
        var val=this.$el.find("select").val();
        var name=this.options.name;
        var model=this.context.model;
        model.set(name,val);
        this.$el.find("select").focus();
        var form=this.context.form;
        if (this.options.onchange) {
            var path=model.get_path(name);
            form.do_onchange(this.options.onchange,path);
        }
    },

    eval_attrs: function() {
        var str=this.options.attrs;
        //log("eval_attrs",this,str);
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
    },

    focus: function() {
        log("field_selection.focus",this);
        this.$el.find("select").focus();
    },

    blur: function() {
        this.trigger("blur");
    }
});

FieldSelection.register();
