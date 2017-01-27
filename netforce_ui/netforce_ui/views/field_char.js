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

var FieldChar=NFView.extend({
    _name: "field_char",
    className: "form-group nf-field",
    events: {
        "change input": "onchange",
        "blur input": "blur",
        "keydown input": "keydown",
        "focus input": "on_focus",
        "contextmenu input": "on_contextmenu"
    },

    initialize: function(options) {
        NFView.prototype.initialize.call(this,options);
        var name=this.options.name;
        var model=this.context.model;
        model.on("change:"+name,this.render,this);
        model.on("error",this.render,this);
        this.listen_attrs();
        if (this.options.inner) {
            this.template=this.options.inner;
        }
    },

    render: function() {
        var name=this.options.name;
        this.$el.addClass("field-"+name);
        var model=this.context.model;
        this.data.value=model.get(name);
        var field=model.get_field(name);
        this.data.string=field.string;
        this.data.placeholder=this.options.placeholder;
        this.data.size=this.options.size || field.size;
        if (this.options.string) {
            this.data.string=this.options.string;
        }
        this.data.readonly=field.readonly||this.options.readonly||this.context.readonly;
        var attrs=this.eval_attrs();
        if (attrs.readonly!==undefined) {
            this.data.readonly=attrs.readonly;
        }
        var perms=get_field_permissions(model.name,name);
        if (!perms.perm_write) {
            this.data.readonly=true;
        }
        if (this.options.password) this.data.input_type="password";
        else if (field.password) this.data.input_type="password";
        else if (this.options.email && Modernizr.inputtypes.email) this.data.input_type="email";
        else this.data.input_type="text";
        var form_layout=this.options.form_layout||"stacked";
        this.data.horizontal=form_layout=="horizontal";
        var pkg=this.options.pkg||field.pkg;
        if (!check_package(pkg)) {
            this.data.disabled=true;
        }
        var field_default=this.context.field_default;
        var fd=model.name+","+name+","+this.context.user_id;
        if(field_default && field_default[fd]){
            this.data.default_value=true;
        }
        NFView.prototype.render.call(this);
        if (this.options.invisible || attrs.invisible || !perms.perm_read) {
            this.$el.hide();
        } else {
            this.$el.show();
        }
        var required=false;
        if (field.required!=null) required=field.required;
        if (this.options.required!=null) required=this.options.required;
        if (attrs.required!=null) required=attrs.required;
        if (required && !this.data.readonly) {
            this.$el.addClass("nf-required-field");
        }
        if (required) {
            model.set_required(name);
        } else {
            model.set_not_required(name);
        }
        var err=model.get_field_error(name);
        if (err) {
            this.$el.addClass("error");
        } else {
            this.$el.removeClass("error");
        }
        if (this.options.span && !this.options.span_input_only) { // XXX
            this.$el.addClass("col-sm-"+this.options.span);
        }
        if (this.options.offset) {
            this.$el.addClass("offset"+this.options.offset);
        }
        if (this.options.width) {
            this.$el.find("input").css("width",this.options.width+"px");
            this.$el.css("width",this.options.width+"px");
        }
        if (this.options.nomargin) {
            this.$el.find("input").css({margin:"0"});
            this.$el.css({margin:"0"});
        }
        if (this.options.align) {
            this.$el.find("input").css({textAlign: this.options.align});
        }
        this.$el.find("a.help").tooltip();
    },

    onchange: function() {
        log("field_char onchange");
        var val=this.$el.find("input").val();
        if (!val) val=null;
        if (this.options.tolower) {
            if (val) val=val.toLowerCase();
        }
        var name=this.options.name;
        var model=this.context.model;
        log("name",name,"val",val);
        model.set(name,val,{silent:true});
        if (this.options.onchange) {
            var path=model.get_path(name);
            var form=this.context.form;
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
        for (var attr in expr) { // XXX
            var cond=expr[attr];
            if (cond.length>0 && cond[0]=="or") {
                var mode="or";
                conds=cond.splice(1);
            } else {
                var mode="and";
                conds=cond;
            }
            var attr_val=mode=="and"?true:false;
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
                if (mode=="and" && !clause_v) {
                    attr_val=false;
                    break;
                } else if (mode=="or" && clause_v) {
                    attr_val=true;
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
        this.$el.find("input").focus();
    },

    on_focus: function(e) {
        register_focus(e.target);
    },

    blur: function() {
        this.trigger("blur");
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

    on_contextmenu: function(e) {
        log("on_contextmenu");
        e.preventDefault();
        var view_cls=get_view_cls("contextmenu");
        var opts={
            click_event:e,
            model: this.context.model,
            field_name: this.options.name
        };
        var view=view_cls.make_view(opts);
        log("view",view,view.el);
        if($(".modal").hasClass("in")){
            $(".modal").append(view.el);
        }else{
            $("body").append(view.el);
        }
        view.render();
    }
});

FieldChar.register();
