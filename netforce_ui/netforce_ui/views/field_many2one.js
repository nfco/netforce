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

var FieldMany2One=NFView.extend({
    _name: "field_many2one",
    className: "form-group nf-field",
    events: {
        "mousedown button": "btn_mousedown",
        "keydown input": "keydown", // check FF (keypress?)
        "blur input": "blur",
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
    },

    render: function() {
        log("############");
        log("field_many2one.render",this);
        var that=this;
        if (this.options.perm) {
            this.$el.hide();
            if (check_other_permission(this.options.perm)) {
                this.$el.show();
            }
        }
        var name=this.options.name;
        this.$el.addClass("field-"+name);
        var model=this.context.model;
        var value=model.get(name);
        var field=model.get_field(name);
        if (value && this.options.link) { // remove this later
            var id;
            if (_.isArray(value)) {
                id=value[0];
            } else {
                id=value;
            }
            this.data.link_url="#name="+this.options.link+"&mode=form&active_id="+id;
        } else if (value && this.options.action) { // remove this later
            var action={"name": this.options.action};
            if (this.options.action_options) {
                _.extend(action,qs_to_obj(this.options.action_options));
            }
            var id;
            if (_.isArray(value)) {
                id=value[0];
            } else {
                id=value;
            }
            action.active_id=id;
            this.data.link_url="#"+obj_to_qs(action);
        } else if (value && !this.options.nolink) {
            var id;
            if (_.isArray(value)) {
                id=value[0];
            } else {
                id=value;
            }
            var action=find_details_action(field.relation,id);
            if (action) {
                this.data.link_url="#"+obj_to_qs(action);
            }
        } else {
            this.data.link_url=null;
        }
        this.data.string=field.string;
        if (this.options.string) {
            this.data.string=this.options.string;
        }
        var perms=get_field_permissions(this.context.model.name,this.options.name);
        this.data.readonly=field.readonly||this.options.readonly||this.context.readonly||!perms.perm_write;
        if (this.options.disable_edit_link && !this.data.readonly) {
            this.data.link_url=null;
        }
        var attrs=this.eval_attrs();
        if (attrs.readonly!==undefined) {
            this.data.readonly=attrs.readonly;
        }
        if (value && value[1]=="Permission denied") { // XXX
            this.data.readonly=true;
        }
        var required=false;
        if (field.required!=null) required=field.required;
        if (this.options.required!=null) required=this.options.required;
        if (attrs.required!=null) required=attrs.required;
        //log("XXXXXXXXXXXXXXXXXX",required);
        if (required && !this.data.readonly) {
            this.data.required=true;
        } else {
            this.data.required=false;
        }
        this.relation=field.relation;
        this.field_condition=field.condition||[];
        var form_layout=this.options.form_layout||"stacked";
        this.data.horizontal=form_layout=="horizontal";
        var pkg=this.options.pkg||field.pkg;
        if (!check_package(pkg)) {
            this.data.disabled=true;
        }
        var do_render=function() {
            that.disable_blur=true;
            NFView.prototype.render.call(that);
            that.disable_blur=false;
            if (that.data.required && !that.data.readonly) {
                that.show_required();
            }
            if (that.data.required) {
                model.set_required(name);
            } else {
                model.set_not_required(name);
            }
            var err=model.get_field_error(name);
            if (err) {
                that.$el.addClass("error");
            } else {
                that.$el.removeClass("error");
            }
            if (that.options.invisible || attrs.invisible || !perms.perm_read) {
                that.$el.hide();
            } else {
                that.$el.show();
            }
            if (that.options.span && !that.options.span_input_only) { // XXX
                that.$el.addClass("col-sm-"+that.options.span);
            }
            if (that.options.width) {
                that.$el.find("input").css("width",that.options.width-20+"px");
                that.$el.css("width",that.options.width+"px");
            }
            if (that.options.nomargin) {
                that.$el.find("input").css({margin:"0"});
                that.$el.css({margin:"0"});
                that.$el.find(".input-append").css({margin:"0"});
            }
            var t_menu='<ul class="typeahead dropdown-menu"></ul>';
            that.$menu = $(t_menu).appendTo(that.$el.find(".nf-controls"));
            that.$menu
                .on('mousedown',$.proxy(that.menu_mousedown, that))
                .on('mouseenter', 'li', $.proxy(that.menu_mouseenter, that))
                .on("click",function(e) {e.preventDefault();});
            if (!that.data.readonly) {
                that.$el.find("input").focus();
            }
        }
        if (value) {
            if (_.isArray(value)) {
                this.data.value_name=value[1];
                do_render();
            } else if (_.isNumber(value)) {
                var ids=[value];
                rpc_execute(this.relation,"name_get",[ids],{},function(err,data) {
                    that.data.value_name=data[0][1];
                    model.set(name,[value,data[0][1]],{silent:true});
                    do_render();
                });
            } else if (_.isString(value)) {
                rpc_execute(this.relation,"name_search",[value],{limit:100},function(err,data) {
                    that.data.value_name=data[0][1];
                    model.set(name,[value,data[0][1]],{silent:true});
                    do_render();
                });
            } else {
                throw "Invalid many2one value: "+value;
            }
        } else {
            this.data.value_name="";
            do_render();
        }
    },

    show_required: function() {
        this.$el.find(".label-text").append(" <span style='color:#e32'>*</span>");
    },

    btn_mousedown: function(e) {
        e.preventDefault();
        e.stopPropagation();
        var name=this.options.name;
        var model=this.context.model;
        var field=model.get_field(name);
        var pkg=this.options.pkg||field.pkg;
        if (!check_package(pkg)) {
            return;
        }
        this.lookup(true);
        this.$el.find("input").focus();
    },

    eval_condition: function() {
        log("eval_condition",this);
        var form=this.context.form;
        var model=this.context.model;
        var path=model.get_field_path(this.options.name);
        if (form) {
            var form_attrs=form.get_field_attrs(path);
            if (form_attrs && form_attrs.condition) {
                return form_attrs.condition;
            }
        }
        var condition=this.field_condition;
        var _conv=function(vals) {
            for (var k in vals) {
                var v=vals[k];
                if (_.isArray(v) && _.isString(v[1])) { // XXX: m2o
                    v=v[0];
                }
                vals[k]=v;
            }
        }
        var view_cond_s=this.options.condition;
        var attrs=this.eval_attrs();
        if (attrs.condition) {
            view_cond_s=attrs.condition;
        }
        if (view_cond_s) {
            var cond_str=html_decode(view_cond_s);
            log("cond_str",cond_str);
            var model=this.context.model;
            var ctx=model.toJSON();
            _conv(ctx);
            if (this.context.collection) {
                var parent_model=this.context.collection.parent_model;
                if (parent_model) {
                    ctx.parent=parent_model.toJSON();
                    _conv(ctx.parent);
                }
            }
            ctx.context=this.context;
            log("ctx",ctx);
            var view_cond=new Function("with (this) { return "+cond_str+"; }").call(ctx);
            log("view_cond",view_cond);
            if (condition.length>0) {
                condition=[condition,view_cond];
            } else {
                condition=view_cond;
            }
        }
        return condition;
    },

    eval_context: function() {
        log("eval_context",this);
        var _conv=function(vals) {
            for (var k in vals) {
                var v=vals[k];
                if (_.isArray(v) && _.isString(v[1])) { // XXX: m2o
                    v=v[0];
                }
                vals[k]=v;
            }
        }
        if (!this.options.context_attr) return {};
        var ctx_str=html_decode(this.options.context_attr);
        log("ctx_str",ctx_str);
        var model=this.context.model;
        var vals=model.toJSON();
        _conv(vals);
        if (this.context.collection) {
            var parent_model=this.context.collection.parent_model;
            if (parent_model) {
                vals.parent=parent_model.toJSON();
                _conv(vals.parent);
            }
        }
        vals.context=this.context;
        log("vals",vals);
        var view_ctx=new Function("with (this) { return "+ctx_str+"; }").call(vals);
        log("view_ctx",view_ctx);
        return view_ctx;
    },

    lookup_when_pause: function() {
        log("m2o.lookup_when_pause");
        var that=this;
        this.lookup_loading=true;
        if (this.lookup_timer) {
            clearTimeout(this.lookup_timer);
        }
        this.lookup_timer=setTimeout(function() {
            that.lookup_timer=null;
            that.lookup();
        },100);
    },

    lookup: function (show_all) {
        log("m2o.lookup");
        if (show_all) {
            query="";
        } else {
            query = this.$el.find("input").val();
        }
        var that = this;
        this.lookup_query=query;
        var ctx=this.eval_context();
        if (this.options.search_mode) {
            ctx.search_mode="suffix";
        }
        rpc_execute(this.relation,"name_search",[query],{condition:this.eval_condition(),limit:100,context:ctx},function(err,data) {
            if (query!=that.lookup_query) return; // concurrent search
            that.lookup_loading=false;
            var items=[];
            for (var i in data) {
                var r=data[i];
                items.push({
                    value: r[0],
                    string: r[1],
                    image: r[2]
                });
            }
            that.render_menu(items).show_menu();
            that.trigger("after_lookup");
        });
    },

    render_menu: function (items) {
        log("render_menu",items);
        var cur_text = this.$el.find("input").val();
        if (this.options.create && _.isEmpty(items) && cur_text) {
            var html='<li data-value="_create" data-string="'+cur_text+'"><a href="#">Create "<b>'+cur_text+'</b>"</a></li>';
            this.$menu.html(html);
        } else {
            var found=false;
            var t_item='<li><a href="#"></a></li>';
            var that = this;
            items = $(items).map(function (i, item) {
                i = $(t_item).attr('data-value', item.value).attr("data-string",item.string).attr("data-image",item.image);
                i.find('a').html(that.highlighter(item.string));
                if (that.options.show_image) {
                    var html='<div class="m2o-menu-image"><img src="/static/db/'+that.context.dbname+'/files/'+item.image+'" style="max-width:150px;max-height:100px"/></div>';
                    i.find("a").append(html);
                }
                if (!found && item.string.toLowerCase().indexOf(cur_text.toLowerCase())!=-1) {
                    i.addClass("active");
                    found=true;
                }
                return i[0];
            });
            if (!cur_text) {
                var mr=get_model(this.relation);
                if (mr.string) {
                    var item=$('<li data-value="_create_link"><a href="#" style="font-weight:bold">New '+mr.string+'</a></li>');
                    items=[item[0]].concat(items);
                }
            }
            this.$menu.html(items);
        }
        return this;
    },

    highlighter: function (item) {
        return item.replace(new RegExp('(' + this.lookup_query + ')', 'ig'), function ($1, match) {
            return '<strong>' + match + '</strong>'
        });
    },

    show_menu: function () {
        var pos = $.extend({}, this.$el.find(".input-group").position(), {
            height: this.$el.find(".input-group")[0].offsetHeight
        });
        this.$menu.css({
            top: pos.top + pos.height,
            left: pos.left,
            maxHeight: 250,
            overflow: "auto",
            marginTop: 0
        });
        this.$menu.show();
        this.menu_shown = true;
        return this
    },

    hide_menu: function () {
        this.$menu.hide();
        this.menu_shown = false;
        return this;
    },

    menu_mousedown: function(e) {
        log("field_many2one.menu_mousedown");
        e.stopPropagation();
        e.preventDefault();
        if ($(e.target).parents("li").length==0) { // menu scrollbar
            this.$el.find("input").focus();
            return;
        }
        this.select_item();
    },

    menu_mouseenter: function (e) {
        this.$menu.find('.active').removeClass('active');
        $(e.currentTarget).addClass('active');
    },

    select_current: function(cb) {
        log("#################################");
        log("m2o.select_current");
        var that=this;
        if (this.lookup_loading) {
            log("select_current1");
            this.once("after_lookup",function() {
                log("m2o.after_lookup");
                that.select_item();
                cb();
            });
        } else {
            log("select_current2");
            this.select_item();
            cb();
        }
    },

    select_item: function () {
        log("field_many2one.select_item");
        var val=this.$menu.find(".active").attr("data-value");
        if (!val) return;
        var val_str=this.$menu.find(".active").attr("data-string");
        var val_img=this.$menu.find(".active").attr("data-image");
        log("m2o select_item",val,val_str,val_img);
        var that=this;
        if (val=="_create") {
            log("m2o create",val_str);
            this.hide_menu();
            rpc_execute(this.relation,"name_create",[val_str],{},function(err,data) {
                if (err) throw "Failed to create model";
                var val_id=data;
                var model=that.context.model;
                var name=that.options.name;
                model.set(name,[val_id,val_str]);
                var form=that.context.form;
                if (that.options.onchange) {
                    var path=model.get_path(name);
                    form.do_onchange(that.options.onchange,path);
                }
            });
        } else if (val=="_create_link") {
            this.hide_menu();
            var action=find_new_action(this.relation);
            var link_url="#"+obj_to_qs(action);
            window.open(link_url);
        } else {
            var val_id=parseInt(val);
            var name=this.options.name;
            this.$el.find("input").val(val_str);
            this.hide_menu();
            var model=this.context.model;
            if (this.options.show_image) {
                model.set(name,[val_id,val_str,val_img]);
                log("m2o set",name,[val_id,val_str,val_img]);
            } else {
                model.set(name,[val_id,val_str]);
                log("m2o set",name,[val_id,val_str]);
            }
            this.$el.find("input").focus();
            var form=this.context.form;
            if (this.options.onchange) {
                var path=model.get_path(name);
                form.do_onchange(this.options.onchange,path);
            }
        }
    },

    keydown: function (e) {
        var that=this;
        switch(e.keyCode) {
            case 9: // tab
            case 13: // enter
                this.select_current(function(err) {
                    log("select_current CB");
                    if (e.shiftKey) {
                        that.trigger("focus_prev");
                        if (!that.options.disable_focus_change) {
                            focus_prev();
                        }
                    } else {
                        that.trigger("focus_next");
                        if (!that.options.disable_focus_change) {
                            focus_next();
                        }
                    }
                });
                if (!(e.keyCode==13 && this.options.submit_form)) {
                    e.preventDefault();
                }
                break;
            case 27: // escape
                if (!this.menu_shown) return;
                this.hide_menu();
                break;
            case 38: // up arrow
                  e.preventDefault();
                  if (this.menu_shown) {
                    this.prev();
                  } else {
                    this.trigger("focus_up");
                  }
                  break;
            case 40: // down arrow
                  e.preventDefault();
                  if (this.menu_shown) {
                    this.next();
                  } else {
                    this.trigger("focus_down");
                  }
                  break;
            default:
                this.lookup_when_pause();
        }
    },

    next: function (event) {
        var active = this.$menu.find('.active').removeClass('active');
        var next = active.next();
        if (!next.length) {
            next = $(this.$menu.find('li')[0]);
        }
        next.addClass('active');
    },

    prev: function (event) {
        var active = this.$menu.find('.active').removeClass('active');
        var prev = active.prev();
        if (!prev.length) {
            prev = this.$menu.find('li').last();
        }
        prev.addClass('active');
    },

    blur: function (e) {
        log("m2o.blur");
        if (this.disable_blur) return;
        if (this.$el.find("input").is(":focus")) return;
        var that=this;
        var name=this.options.name;
        var model=this.context.model;
        var val=model.get(name);
        var val_str=val?val[1]:"";
        val_str=$("<input type='text'/>").val(val_str).val(); // to filter special chars like newline
        var inp_str=that.$el.find("input").val();
        if (inp_str!=val_str) {
            log("inp_str",inp_str);
            log("val_str",val_str);
            that.$el.find("input").val("");
            log(name+" <- "+null);
            model.set(name,null);
        }
        this.hide_menu(); 
        log("m2o.blur before trigger");
        this.trigger("blur");
    },

    focus: function() {
        this.$el.find("input").focus();
    },

    on_focus: function(e) {
        log("m2o.on_focus");
        register_focus(e.target);
    },

    eval_attrs: function() {
        var str=this.options.attrs;
        //log("field_many2one.eval_attrs",this,str);
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

    listen_attrs: function() {
        var str=this.options.attrs;
        //log("field_many2one.listen_attrs",this,str);
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
        $("body").append(view.el);
        view.render();
    }
});

FieldMany2One.register();
