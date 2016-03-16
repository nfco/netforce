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

var FieldText=NFView.extend({
    _name: "field_text",
    className: "form-group nf-field",
    events: {
        "change textarea": "onchange",
        "blur textarea": "blur",
        "keyup textarea": "keyup",
        "focus textarea": "on_focus",
        "click .view-source": "view_source",
        "keydown textarea": "keydown"
    },

    initialize: function(options) {
        NFView.prototype.initialize.call(this,options);
        var name=this.options.name;
        var model=this.context.model;
        model.on("change:"+name,this.render,this);
        if (this.options.inner) {
            this.template=this.options.inner;
        }
        this.listen_attrs();
    },

    render: function() {
        log("field_text.render",this);
        var name=this.options.name;
        var model=this.context.model;
        this.data.value=model.get(name);
        var field=model.get_field(name);
        this.data.string=field.string;
        this.data.readonly=field.readonly||this.options.readonly||this.context.readonly;
        var has_focus=this.$el.find("textarea").is(":focus");
        this.disable_blur=true;
        var form_layout=this.options.form_layout||"stacked";
        this.data.horizontal=this.options.form_layout=="horizontal";
        NFView.prototype.render.call(this);
        this.disable_blur=false;
        if (has_focus) this.$el.find("textarea").focus();
        var attrs=this.eval_attrs();
        if (this.options.invisible || attrs.invisible) {
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
        if (this.options.span && !this.options.span_input_only) {
            this.$el.addClass("col-sm-"+this.options.span);
            this.$el.find("textarea").addClass("col-sm-"+this.options.span);
        }
        if (this.options.width) {
            this.$el.find("textarea").css("width",this.options.width+"px");
        }
        this.$el.find("textarea").css("height",(this.options.height||70)+"px");
        if (this.options.nomargin) {
            this.$el.find("textarea").css({margin: 0});
            this.$el.css({margin: 0});
        }
        if (this.options.autoresize) {
            this.$el.find("textarea").css({resize:"none"});
            var width=this.$el.find("textarea").width();
            var height=this.$el.find("textarea").height();
            var text=this.$el.find("textarea").val();
            this.$mirror=$("<div/>").css({whiteSpace:"pre-wrap",wordWrap:"break-word",padding:"2px 4px",fontSize:"12px",visibility:"hidden"});
            this.$mirror.text(text);
            this.$mirror.width(width);
            this.$el.find("textarea").css({position:"absolute"});
            this.$el.find(".mirror-cont").append(this.$mirror);
            this.$el.find("textarea").height(height+20);
        }
        var that=this;
        if (this.options.wysi) {
            var el=that.$el.find("textarea")[0];
            var editor=CKEDITOR.replace(el,{
                width: this.options.width||300,
                height: this.options.height||70,
                filebrowserUploadUrl:  '/ck_upload',
                allowedContent: true // XXX
            });
            if (editor) {
                editor.on("change",function(e) {
                    var val=editor.getData();
                    log("ckeditor change");
                    var name=that.options.name;
                    var model=that.context.model;
                    model.set(name,val,{silent:true});
                });
            } else {
                log("ERROR! can't create ckeditor!");
            }
        }
    },

    onchange: function() {
        log("field_text.onchange");
        var val=this.$el.find("textarea").val();
        var name=this.options.name;
        var model=this.context.model;
        model.set(name,val,{silent:true});
    },

    focus: function() {
        log("field_text.focus");
        this.$el.find("textarea").focus();
    },

    blur: function(e) {
        log("field_text.blur");
        if (this.disable_blur) return; // because chrome fires blur event when element is removed (during rerender for ex)
        this.trigger("blur");
    },

    keyup: function(e) {
        log("field_text.keyup",e.keyCode);
        if (!this.$mirror) return;
        var v=this.$el.find("textarea").val();
        this.$mirror.text(v);
        var h=this.$mirror.height();
        log("TTTTTTTTTTTTTT",v,h);
        this.$el.find("textarea").height(h+20);
    },

    on_focus: function(e) {
        log("field_text.on_focus",this);
        var that=this;
        register_focus(e.target);
        if (this.options.onfocus) {
            var name=this.options.name;
            var model=this.context.model;
            var path=model.get_path(name);
            var form=this.context.form;
            form.do_onfocus(that.options.onfocus,path);
        }
    },

    view_source: function(e) {
        log("view_source");
        e.preventDefault();
        e.stopPropagation();
        if (this.$el.find(".editor").is(":visible")) {
            var val=this.$el.find(".editor").html();
            this.$el.find("textarea").text(val);
            this.$el.find(".editor").hide();
            this.$el.find("textarea").show();
        } else {
            var val=this.$el.find("textarea").val();
            this.$el.find(".editor").html(val);
            this.$el.find("textarea").hide();
            this.$el.find(".editor").show();
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

    keydown: function (e) {
        log("field_text.keydown",e.keyCode);
        if (e.keyCode==9) {
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
        }
    }
});

FieldText.register();
