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

var FieldDateTime=NFView.extend({
    _name: "field_datetime",
    className: "form-group nf-field",
    events: {
        "change input": "onchange",
        "changeDate input": "onchange",
        "keydown input": "keydown",
        "focus input": "on_focus",
        "blur input": "blur"
    },

    initialize: function(options) {
        NFView.prototype.initialize.call(this,options);
        var name=this.options.name;
        var model=this.context.model;
        model.on("change:"+name,this.render,this);
        model.on("error",this.render,this);
        this.listen_attrs();
    },

    render: function() {
        //log("field_datetime.render",this);
        var that=this;
        var name=this.options.name;
        var model=this.context.model;
        var val=model.get(name);
        var val=format_datetime(val);
        this.data.value=val;
        var field=model.get_field(name);
        this.data.string=field.string;
        if (this.options.string) {
            this.data.string=this.options.string;
        }
        this.data.readonly=field.readonly||this.options.readonly||this.context.readonly;
        var attrs=this.eval_attrs();
        if (attrs.readonly!==undefined) {
            this.data.readonly=attrs.readonly;
        }
        this.disable_blur=true; // avoir blur in sheet when rerender due to onchange
        var form_layout=this.options.form_layout||"stacked";
        this.data.horizontal=form_layout=="horizontal";
        NFView.prototype.render.call(this);
        this.disable_blur=false;
        if (ui_params_db && ui_params_db.date_format) {
            var format2=ui_params_db.date_format+" HH:mm:ss";
        } else {
            var format2="YYYY-MM-DD HH:mm:ss";
        }
        var opts={
            format:format2,
            use_buddhist_date: ui_params_db && ui_params_db.use_buddhist_date
        };
        if (this.options.mode=="month") {
            opts.viewMode="months";
            opts.minViewMode="months";
        } else if (this.options.mode=="year") {
            opts.viewMode="years";
            opts.minViewMode="years";
        }
        this.$el.find("input").datetimepicker(opts);
        var required=false;
        if (field.required!=null) required=field.required;
        if (this.options.required!=null) required=this.options.required;
        if (attrs.required!=null) required=attrs.required;
        if (required && !this.data.readonly) {
            this.$el.addClass("nf-required-field");
            this.data.required=true;
        } else {
            this.data.required=false;
        }
        if (field.required && !this.data.readonly) {
            this.$el.addClass("nf-required-field");
            this.data.required=true;
        } else {
            this.data.required=false;
        }
        var err=model.get_field_error(name);
        if (err) {
            this.$el.addClass("error");
        } else {
            this.$el.removeClass("error");
        }
        if (this.options.invisible || attrs.invisible) {
            this.$el.hide();
        } else {
            this.$el.show();
        }
        if (this.options.span && !this.options.span_input_only) { // XXX
            this.$el.addClass("col-sm-"+this.options.span);
        }
        if (this.options.width) {
            this.$el.find("input").width(this.options.width-8);
            this.$el.width(this.options.width);
        }
        if (this.options.nomargin) {
            this.$el.find("input").css({margin:"0"});
            this.$el.css({margin:"0"});
        }
        return this;
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

    onchange: function() {
        log("field_datetime.onchange",this);
        var val=this.$el.find("input").val();
        if (!val) val=null;
        log("val1",val);
        val=parse_datetime(val);
        log("val2",val);
        var name=this.options.name;
        var model=this.context.model;
        model.set(name,val,{silent:true});
        if (this.options.onchange) {
            var path=model.get_path(name);
            var form=this.context.form;
            form.do_onchange(this.options.onchange,path);
        }
    },

    eval_attrs: function() {
        var str=this.options.attrs;
        //log("field_datetime.eval_attrs",this,str);
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
    },

    on_focus: function(e) {
        register_focus(e.target);
    },

    blur: function() {
        if (this.disable_blur) return;
        log("field_datetime.blur");
        this.$el.find("input").data("DateTimePicker").hide();
        this.trigger("blur");
    },

    focus: function() {
        this.$el.find("input").focus();
    }
});

FieldDateTime.register();
