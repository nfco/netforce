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

var FieldBoolean=NFView.extend({
    _name: "field_boolean",
    className: "form-group nf-field",
    events: {
        "change input": "onchange",
        "click input": "click",
        "blur select": "blur",
        "change select": "onchange_select",
        "focus input": "on_focus",
        "keydown input": "keydown"
    },

    initialize: function(options) {
        var that=this;
        NFView.prototype.initialize.call(this,options);
        var name=this.options.name;
        var model=this.context.model;
        model.on("change:"+name,function() {
            log("field_boolean.rerender");
            that.render();
        },this);
        this.listen_attrs();
    },

    render: function() {
        //log("field_boolean render",this.options.name,this);
        var name=this.options.name;
        var model=this.context.model;
        this.data.value=model.get(name);
        var field=model.get_field(name);
        this.data.string=field.string;
        if (this.options.string) {
            this.data.string=this.options.string;
        }
        var readonly=field.readonly||this.options.readonly||this.context.readonly;
        var form_layout=this.options.form_layout||"stacked";
        this.data.horizontal=form_layout=="horizontal";
        NFView.prototype.render.call(this);
        var attrs=this.eval_attrs();
        if (readonly) {
            this.$el.find("input").attr("disabled","disabled");
        }
        if (this.options.invisible || attrs.invisible) {
            this.$el.hide();
        } else {
            this.$el.show();
        }
        if (this.options.span) {
            this.$el.addClass("col-sm-"+this.options.span);
        }
        if (this.options.offset) {
            this.$el.addClass("offset"+this.options.offset);
        }
        if (this.options.width) {
            this.$el.find("select").width(this.options.width);
            this.$el.width(this.options.width);
        }
        if (this.options.nomargin) {
            this.$el.find("input").css({margin:"0"});
            this.$el.css({margin:"0"});
        }
        this.$el.find("a.help").tooltip();
    },

    click: function(e) {
        e.stopPropagation();
    },

    onchange: function() {
        log("field_boolean.onchange",this);
        var val=this.$el.find("input").is(":checked");
        var name=this.options.name;
        var model=this.context.model;
        log("val",val);
        model.set(name,val);
        this.$el.find("input").focus();
        if (this.options.onchange) {
            var path=model.get_path(name);
            var form=this.context.form;
            form.do_onchange(this.options.onchange,path);
        }
    },

    onchange_select: function() {
        var val=this.$el.find("select").val();
        if (val=="1") val=true;
        else if (val=="0") val=false;
        else val=null;
        var name=this.options.name;
        var model=this.context.model;
        model.set(name,val);
        if (this.options.onchange) {
            var path=model.get_path(name);
            var form=this.context.form;
            form.do_onchange(this.options.onchange,path);
        }
    },

    focus: function() {
        this.$el.find("select").focus();
    },

    blur: function() {
        log("XXX boolean blur");
        this.trigger("blur");
    },

    on_focus: function(e) {
        $(e.target).select();
        register_focus(e.target);
    },

    keydown: function (e) {
        if (e.keyCode==13 && this.options.submit_form) return;
        if (e.keyCode==9||e.keyCode==13) {
            e.preventDefault();
            if (e.shiftKey) {
                this.trigger("focus_prev");
                if (!this.options.disable_focus_change) {
                    focus_prev();
                }
            } else {
                this.trigger("focus_next");
                if (!this.options.disable_focus_change) {
                    focus_next();
                }
            }
        } else if (e.keyCode==40) {
            this.trigger("focus_down");
        } else if (e.keyCode==38) {
            this.trigger("focus_up");
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

FieldBoolean.register();
