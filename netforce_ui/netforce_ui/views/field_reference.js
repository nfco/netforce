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

var FieldReference=NFView.extend({
    _name: "field_reference",
    className: "form-group nf-field",
    events: {
        "click button": "btn_click",
        "keydown input": "keydown", // check FF (keypress?)
        "keydown select": "keydown_select",
        "blur input": "blur",
        "change select": "onchange_select",
        "focus input": "on_focus"
    },

    initialize: function(options) {
        NFView.prototype.initialize.call(this,options);
        var name=this.options.name;
        var model=this.context.model;
        model.on("change:"+name,this.render,this);
        this.listen_attrs();
    },

    render: function() {
        log("########################");
        log("ref.render",this);
        var name=this.options.name;
        var model=this.context.model;
        var value=model.get(name);
        if (value) {
            if (_.isArray(value)) val=value[0];
            else val=value;
            this.relation=val.split(",")[0];
        }
        if (value) {
            var val;
            if (_.isArray(value)) {
                val=value[0];
            } else {
                val=value;
            }
            var res=val.split(",");
            var relation=res[0];
            var id=res[1];
            var action=find_details_action(relation,id);
            if (this.options.click_action) {
                this.data.link_url="#name="+this.options.click_action+"&active_id="+this.context.data.id;
            } else if (action) {
                this.data.link_url="#"+obj_to_qs(action);
            } else {
                this.data.link_url=null;
            }
        } else {
            this.data.link_url=null;
        }
        if (this.options.disable_edit_link && !this.data.readonly) {
            this.data.link_url=null;
        }
        var that=this;
        var field=model.get_field(name);
        this.selection=field.selection;
        var model_name=model.name;
        if(model_name=="_search"){
            var h=window.location.hash.substr(1);
            var action=qs_to_obj(h);
            action=get_action(action.name);
            model_name=action.model;
        }
        var select_value=get_field_select({model: model_name, field: name});
        if(select_value) this.selection=select_value;

        this.data.string=field.string;
        if (this.options.string) {
            this.data.string=this.options.string;
        }
        var attrs=this.eval_attrs();
        this.data.readonly=field.readonly||this.options.readonly||this.context.readonly;
        var required=field.required||this.options.required||that.data.required;
        var form_layout=this.options.form_layout||"stacked";
        this.data.horizontal=form_layout=="horizontal";
        var do_render=function() {
            //log("do_render",that.relation,that.data.value_name);
            NFView.prototype.render.call(that);
            if (that.options.invisible || attrs.invisible) {
                that.$el.hide();
            } else {
                that.$el.show();
            }
            if (required) {
                that.$el.addClass("nf-required-field");
                model.set_required(name);
            }else{
                model.set_not_required(name);
            }
            var err=model.get_field_error(name);
            if (err) {
                that.$el.addClass("error");
            } else {
                that.$el.removeClass("error");
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
            that.$menu = $(t_menu).appendTo('body');
            that.$menu
                .on('click', $.proxy(that.menu_click, that))
                .on('mouseenter', 'li', $.proxy(that.menu_mouseenter, that));
            that.$el.find("a.help").tooltip();
        }
        if (value) {
            if (_.isArray(value)) {
                this.data.value_name=value[1];
                do_render();
            } else if (_.isString(value)) {
                var ids=[parseInt(value.split(",")[1])];
                rpc_execute(this.relation,"name_get",[ids],{},function(err,data) {
                    that.data.value_name=data[0][1];
                    do_render();
                });
            } else {
                throw "Invalid reference value: "+value;
            }
        } else {
            this.data.value_name="";
            do_render();
        }
    },

    onchange_select: function() {
        var val=this.$el.find("select").val();
        var model=this.context.model;
        this.relation=val;
        log("onchange_select",val);
        var name=this.options.name;
        var model=this.context.model;
        model.set(name,null);
    },

    btn_click: function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.lookup(true);
        this.$el.find("input").focus();
    },

    lookup_when_pause: function() {
        log("ref.lookup_when_pause");
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
        log("ref.lookup");
        if (show_all) {
            query="";
        } else {
            query = this.$el.find("input").val();
        }
        var that = this;
        this.lookup_query=query;
        if (this.relation) {
            rpc_execute(this.relation,"name_search",[query],{},function(err,data) {
                if (query!=that.lookup_query) return; // concurrent search
                that.lookup_loading=false;
                var items=[];
                for (var i in data) {
                    var r=data[i];
                    items.push({
                        value: r[0],
                        string: r[1]
                    });
                }
                that.render_menu(items).show();
                that.trigger("after_lookup");
            });
        } else {
            var models=_.pluck(this.selection,0);
            rpc_execute("model","name_search_multi",[query,models],{},function(err,data) {
                if (query!=that.lookup_query) return; // concurrent search
                that.lookup_loading=false;
                that.relation=data.model;
                var items=[];
                for (var i in data.values) {
                    var r=data.values[i];
                    items.push({
                        value: r[0],
                        string: r[1]
                    });
                }
                that.render_menu(items).show();
                that.trigger("after_lookup");
            });
        }
    },

    render_menu: function (items) {
        var cur_text = this.$el.find("input").val();
        var found=false;
        var t_item='<li><a href="#"></a></li>';
        var that = this;
        items = $(items).map(function (i, item) {
            i = $(t_item).attr('data-value', item.value).attr("data-string",item.string);
            i.find('a').html(that.highlighter(item.string));
            if (!found && item.string.toLowerCase().indexOf(cur_text.toLowerCase())!=-1) {
                i.addClass("active");
                found=true;
            }
            return i[0];
        });
        this.$menu.html(items);
        var sel_items=[];
        _.each(this.selection,function(sel) {
            if (sel[0]==that.relation) {
                var $el=$('<li><a href="#"><b>'+sel[1]+'</b></a></li>');
            } else {
                var $el=$('<li><a href="#">'+sel[1]+'</a></li>');
            }
            $el.addClass("nf-select-relation");
            $el.attr("data-value",sel[0]);
            sel_items.push($el[0])
        });
        sel_items.push($('<li class="divider"></li>')[0]);
        this.$menu.prepend(sel_items);
        return this;
    },

    highlighter: function (item) {
        return item.replace(new RegExp('(' + this.lookup_query + ')', 'ig'), function ($1, match) {
            return '<strong>' + match + '</strong>'
        });
    },

    show: function () {
        var pos = $.extend({}, this.$el.find(".input-group").offset(), {
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
        this.shown = true;
        return this
    },

    hide: function () {
        this.$menu.hide();
        this.shown = false;
        return this;
    },

    menu_click: function (e) {
        e.stopPropagation();
        e.preventDefault();
        this.select_item();
    },

    menu_mouseenter: function (e) {
        this.$menu.find('.active').removeClass('active');
        $(e.currentTarget).addClass('active');
    },

    select_current: function(cb) {
        log("#################################");
        log("ref.select_current");
        var that=this;
        if (this.lookup_loading) {
            log("select_current1");
            this.once("after_lookup",function() {
                log("ref.after_lookup");
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
        log("ref.select_item");
        var $el=this.$menu.find(".active");
        if ($el.hasClass("nf-select-relation")) {
            var val=$el.attr("data-value");
            var model=this.context.model;
            this.relation=val;
            log("change relation",val);
            var name=this.options.name;
            var model=this.context.model;
            this.hide();
            model.set(name,null);
            this.focus();
            return;
        }
        var val_id=parseInt($el.attr("data-value"));
        var val_str=$el.attr("data-string");
        var name=this.options.name;
        this.$el.find("input").val(val_str);
        this.hide();
        var model=this.context.model;
        log("set",model,[this.relation+","+val_id,val_str]);
        model.set(name,[this.relation+","+val_id,val_str]);
        this.focus();
        var form=this.context.form;
        if (this.options.onchange) {
            var path=model.get_path(name);
            form.do_onchange(this.options.onchange,path);
        }
    },

    keydown: function (e) {
        var that=this;
        switch(e.keyCode) {
            case 9: // tab
            case 13: // enter
                this.select_current(function(err) {
                    log("ref.select_current CB");
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
        var that = this;
        setTimeout(function () {
            if (that.$el.find("input").is(":focus")) return;
            that.hide(); 
            var name=that.options.name;
            var model=that.context.model;
            var val=model.get(name);
            var val_str=val?val[1]:"";
            if (that.$el.find("input").val()!=val_str) {
                that.$el.find("input").val("");
                model.set(name,null);
            }
            that.trigger("blur");
        }, 150);
    },

    focus: function() {
        this.$el.find("input").focus();
    },

    on_focus: function(e) {
        log("ref.on_focus",e.target);
        $(e.target).select();
        register_focus(e.target);
    },

    keydown_select: function (e) {
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
        //log("field_many2one.eval_attrs",this,str);
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
    }
});

FieldReference.register();
