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

var Button=NFView.extend({
    _name: "button",
    tagName: "button",
    className: "btn",
    events: {
        "click": "pre_click"
    },

    initialize: function(options) {
        NFView.prototype.initialize.call(this,options);
        this.listen_states();
        this.listen_attrs();
    },

    render: function() {
        //log("button.render",this);
        var that=this;
        var name=this.options.string;
        var model=this.context.model;
        if (this.options.inner) {
            this.data.content=this.options.inner(this.data);
        }
        this.$el.css({whiteSpace: "nowrap"});
        if (this.options["class"]) {
            this.$el.addClass(this.options["class"]);
        }
        if (this.options.size=="large") {
            this.$el.addClass("btn-lg");
        } else if (this.options.size=="small") {
            this.$el.addClass("btn-sm");
        } else if (this.options.size=="extra_small") {
            this.$el.addClass("btn-xs");
        }
        if (this.options.type) {
            this.$el.addClass("btn-"+this.options.type);
        } else {
            this.$el.addClass("btn-default");
        }
        NFView.prototype.render.call(this);
        if (this.options.pull) {
            this.$el.addClass("pull-"+this.options.pull);
        }
        if (this.options.select) {
            var collection=this.context.collection;
            if (collection.length==0) {
                this.$el.hide();
            }
        }
        if (this.options.action=="_search") {
            var collection=this.context.collection;
            var that=this;
            collection.on("hide_search",function() {
                that.$el.show();
            });
        }
        var perm_model=this.options.perm_model;
        if (this.options.perm) {
            this.has_perm=false;
            this.$el.hide();
            if (check_other_permission(this.options.perm)) {
                this.has_perm=true;
                if (this.check_visible()) {
                    this.$el.show();
                }
            }
        }else if (perm_model && typeof(perm_model)==typeof('')) {
            var perms=perm_model.split(",");
            if (perms.length>1){
                var model=perms[0];
                var all_perm=[];
                for(var i=1; i<perms.length;i++){
                    var perm=perms[i];
                    all_perm.push(check_model_permission(model,perm));
                }
                this.has_perm=all_perm ? _.contains(all_perm,true) : true;
                if (!this.check_visible()) {
                    this.$el.hide();
                } else {
                    this.$el.show();
                }
            }
        } else {
            this.has_perm=true;
            if (!this.check_visible()) {
                this.$el.hide();
            } else {
                this.$el.show();
            }
        }

        if(model && name){
            var hide=is_hidden({type: 'button', model: model.name, name: name});
            if(hide) this.$el.hide();
        }
    },

    check_visible: function() {
        if (!this.has_perm) return false;
        var attrs=this.eval_attrs();
        if (attrs.invisible) {
            return false;
        }
        if (this.options.states) {
            var model=this.context.model;
            var state=model.get("state");
            var states=this.options.states.split(",");
            if (!_.contains(states,state)) {
                return false;
            }
        }
        return true;
    },

    start_loading: function() {
        var w=this.$el.width();
        this.$el.addClass("disabled");
        this.$el.removeClass("btn-primary btn-success btn-default");
        this.$el.addClass("btn-default");
        this.$el.empty();
        $("<img/>").attr("src","/static/img/spinner.gif").appendTo(this.el);
        this.$el.width(w);
        this.$el.blur();
        this.loading=true;
    },

    stop_loading: function() {
        this.$el.removeClass("disabled");
        this.render();
        this.loading=false;
    },

    pre_click: function(e) {
        log("button click",this);
        var that=this;
        if (this.options.onclick) {
            this.options.onclick();
            e.preventDefault();
            return;
        }
        if (this.loading) return;
        if (this.options.method || this.options.action) {
            e.preventDefault();
            e.stopPropagation();
        }
        var model=this.context.model;
        if(model && model._disable_save){
           setTimeout(function(){
                if (model._disable_save) {
                    set_flash("error","Failed to save data, please try again");
                    render_flash();
                    return;
                }else{
                    that.click(e);
                }
           },NF_TIMEOUT*1000)
        }else{
            that.click(e);
        }
    },

    click: function(e) {
        log("button click",this);
        if (this.options.onclick) {
            this.options.onclick();
            e.preventDefault();
            return;
        }
        if (this.loading) return;
        if (this.options.method || this.options.action) {
            e.preventDefault();
            e.stopPropagation();
        }
        if (this.options.confirm) {
            var res=confirm(this.options.confirm);
            if (!res) return;
        }
        var that=this;
        if (this.options.method) {
            var method=this.options.method;
            var method_options={};
            if (this.options.method_options) {
                method_options=qs_to_obj(this.options.method_options);
            }
            var method_context=this.options.method_context;
            if (method_context) {
                method_context=qs_to_obj(method_context);
            } else {
                method_context={};
            }
            var model=this.context.model;
            var collection=this.context.collection;
            if (method=="_save") {
                if (!model.check_required()) {
                    set_flash("error","Some required fields are missing");
                    render_flash();
                    return;
                }
                that.start_loading();
                var ctx=clean_context(this.context);
                model.save({},{
                    context: ctx,
                    success: function() {
                        that.stop_loading();
                        set_flash("success","Changes saved successfully.");
                        if (that.options.next) {
                            log("NEXT",that.options.next);
                            next=that.options.next;
                            if (_.isFunction(next)) {
                                next();
                                return;
                            }
                            if (next=="_reload") {
                                window.location.reload(); // XXX
                                return;
                            }
                            var action={name:next};
                            if (that.options.next_options) {
                                _.extend(action,qs_to_obj(that.options.next_options));
                            }
                            exec_action(action);
                        } else {
                            model.trigger("reload");
                        }
                    },
                    error: function(model,err) {
                        log("save error",err);
                        that.stop_loading();
                        set_flash("error",err.message);
                        render_flash();
                        that.context.model.set_field_errors(err.error_fields);
                    }
                });
            } else if (method=="_delete") {
                if (collection) {
                    var ids=[];
                    collection.each(function(m) {
                        if (m.get("_selected")) ids.push(m.id);
                    });
                    if (ids.length==0) {
                        set_flash("error","No items selected.");
                        render_flash();
                        return;
                    }
                    if (!this.options.confirm) {
                        var res=confirm("Are you sure you want to delete selected items?");
                        if (!res) return;
                    }
                    nf_execute(collection.name,"delete",[ids],{},function(err,data) {
                        if (err) {
                            set_flash("error",err.message);
                            render_flash();
                            return;
                        }
                        log("delete success");
                        collection.remove(ids);
                        collection.trigger("reset");
                    });
                } else {
                    var res=confirm("Are you sure you want to delete this item?");
                    if (!res) return;
                    nf_execute(model.name,"delete",[[model.id]],{},function(err,data) {
                        if (err) {
                            set_flash("error",err.message);
                            render_flash();
                            return;
                        }
                        log("delete success");
                        var next=that.options.next;
                        if (!next && data) next=data.next;
                        if (next) {
                            if (_.isString(next)) {
                                var action={name:next};
                            } else {
                                var action=next;
                            }
                            if (that.options.next_options) {
                                _.extend(action,qs_to_obj(that.options.next_options));
                            }
                            exec_action(action);
                        }
                    });
                }
            } else if (method=="_archive") {
                var ctx=qs_to_obj(this.options.method_context);
                var field=ctx.field;
                var ids=[];
                collection.each(function(m) {
                    if (m.get("_selected")) ids.push(m.id);
                });
                if (ids.length==0) {
                    set_flash("error","No items selected.");
                    render_flash();
                    return;
                }
                rpc_execute(collection.name,"write",[ids,{active: false}],{},function(err,data) {
                    if (err) {
                        set_flash("error",err.message);
                        render_flash();
                        return;
                    }
                    collection.trigger("reload");
                });
            } else if (method=="_restore") {
                var ctx=qs_to_obj(this.options.method_context);
                var field=ctx.field;
                var ids=[];
                collection.each(function(m) {
                    if (m.get("_selected")) ids.push(m.id);
                });
                if (ids.length==0) {
                    set_flash("error","No items selected.");
                    render_flash();
                    return;
                }
                rpc_execute(collection.name,"write",[ids,{active: true}],{},function(err,data) {
                    if (err) {
                        set_flash("error",err.message);
                        render_flash();
                        return;
                    }
                    collection.trigger("reload");
                });
            } else if (method=="_remove") {
                log("_remove");
                var ctx=qs_to_obj(this.options.method_context);
                var field=ctx.field;
                var ids=[];
                collection.each(function(m) {
                    if (m.get("_selected")) ids.push(m.id);
                });
                var vals={};
                vals[field]=null;
                rpc_execute(collection.name,"write",[ids,vals],{},function(err,data) {
                    if (err) {
                        set_flash("error",err.message);
                        render_flash();
                        return;
                    }
                    log("remove success");
                    collection.trigger("reload");
                });
            } else if (method=="_export") {
                var model_name=collection.model_name;
                var ids=[];
                collection.each(function(m) {
                    if (m.get("_selected")) ids.push(m.id);
                });
                if (_.isEmpty(ids)) {
                    var condition=collection.search_condition||[];
                } else {
                    var condition=[["id","in",ids]];
                }
                var filename=model_name+".csv";
                var action={
                    "name": "export_data", // XXX: should not need name
                    "type": "export",
                    "model": model_name,
                    "condition": condition,
                    "filename": filename
                }
                exec_action(action);
            } else if (method=="_export2") {
                var model_name=collection.name;
                var ids=[];
                collection.each(function(m) {
                    if (m.get("_selected")) ids.push(m.id);
                });
                if (_.isEmpty(ids)) {
                    var condition=collection.search_condition||[];
                } else {
                    var condition=[["id","in",ids]];
                }
                var action={
                    "view_cls": "export",
                    "model": model_name,
                    "condition": condition,
                    "menu": "gen_menu" // XXX
                }
                exec_action(action);
            } else {
                if (model) {
                    log("calling model method",model);
                    if (!model.check_required()) {
                        set_flash("error","Some required fields are missing");
                        render_flash();
                        return;
                    }
                    if (method_options.nosave) {
                        var data=model.toJSON();
                        var ctx={data:data};
                        this.start_loading();
                        rpc_execute(model.name,method,[],{context:ctx},function(err,data) {
                            that.stop_loading();
                            if (err) {
                                set_flash("error",err.message);
                                render_flash();
                                return;
                            }
                            if (data && data.flash) {
                                if (_.isString(data.flash)) {
                                    set_flash("success",data.flash);
                                } else if (_.isObject(data.flash)) {
                                    set_flash(data.flash.type,data.flash.message);
                                }
                            }
                            if (data && data.cookies) {
                                set_cookies(data.cookies);
                            }
                            var next=that.options.next;
                            if (!next && data) next=data.next;
                            if (next) {
                                if (_.isString(next)) {
                                    var action={name:next};
                                } else {
                                    var action=next;
                                }
                                if (that.options.next_options) {
                                    _.extend(action,qs_to_obj(that.options.next_options));
                                }
                                exec_action(action);
                            }
                        });
                    } else {
                        that.start_loading();
                        model.save({},{ // save should not do anything if nothing changed
                            context: method_context,
                            success: function() {
                                rpc_execute(model.name,method,[[model.id]],{},function(err,data) {
                                    that.stop_loading();
                                    if (err) {
                                        set_flash("error",err.message);
                                        model.trigger("reload");
                                        return;
                                    }
                                    if (data && data.flash) {
                                        if (_.isString(data.flash)) {
                                            set_flash("success",data.flash);
                                        } else if (_.isObject(data.flash)) {
                                            set_flash(data.flash.type,data.flash.message);
                                        }
                                    }
                                    if (data && data.cookies) {
                                        set_cookies(data.cookies);
                                    }
                                    if (that.options.next_url) {
                                        window.location.href=that.options.next_url;
                                        return;
                                    }
                                    var next=that.options.next;
                                    if (!next && data) next=data.next;
                                    
                                    if (data && data.next_url){
                                        window.location.href=data.next_url;
                                        return;
                                    }

                                    if (next=="_close") {
                                        $(".modal").modal("hide");
                                        return;
                                    }
                                    if (next) {
                                        if (_.isString(next)) {
                                            var action={name:next};
                                        } else {
                                            var action=next;
                                        }
                                        if (that.options.next_options) {
                                            _.extend(action,qs_to_obj(that.options.next_options));
                                        }
                                        exec_action(action);
                                    } else {
                                        var opts={};
                                        if (data && data.focus_field) {
                                            opts.focus_field=data.focus_field;
                                        }
                                        model.trigger("reload",opts);
                                        if (that.context.collection) {
                                            that.context.collection.trigger("reload"); // for grid view
                                        }
                                    }
                                });
                            },
                            error: function(model,err) {
                                log("save error",err);
                                that.stop_loading();
                                set_flash("error",err.message);
                                render_flash();
                            }
                        });
                    }
                } else if (collection) {
                    log("calling collection method");
                    if (that.options.static_method) {
                        var args=[];
                    } else {
                        var ids=[];
                        collection.each(function(m) {
                            if (m.get("_selected")) ids.push(m.id);
                        });
                        if (ids.length==0) {
                            set_flash("error","No items selected.");
                            render_flash();
                            return;
                        }
                        var args=[ids];
                    }
                    var ctx;
                    if (this.options.method_context) {
                        ctx=qs_to_obj(this.options.method_context);
                    } else {
                        ctx={};
                    }
                    rpc_execute(collection.name,method,args,{context:ctx},function(err,data) {
                        if (err) {
                            set_flash("error",err.message);
                            render_flash();
                            return;
                        }
                        if (data && data.flash) {
                            set_flash("success",data.flash);
                        }
                        var next=that.options.next;
                        if (!next && data) next=data.next;
                        if (next) {
                            if (_.isString(next)) {
                                var action={name:next};
                            } else {
                                var action=next;
                            }
                            if (that.options.next_options) {
                                _.extend(action,qs_to_obj(that.options.next_options));
                            }
                            exec_action(action);
                        } else {
                            collection.trigger("reload");
                        }
                    });
                } else {
                    log("calling class method");
                    that.start_loading();
                    rpc_execute(that.options.model,method,[],{},function(err,data) {
                        that.stop_loading();
                        if (err) {
                            set_flash("error",err.message);
                            render_flash();
                            return;
                        }
                        if (data && data.flash) {
                            set_flash("success",data.flash);
                        }
                        var next=that.options.next;
                        if (!next && data) next=data.next;
                        if (next) {
                            if (_.isString(next)) {
                                var action={name:next};
                            } else {
                                var action=next;
                            }
                            if (that.options.next_options) {
                                _.extend(action,qs_to_obj(that.options.next_options));
                            }
                            exec_action(action);
                        }
                    });
                }
            }
        } else if (this.options.action) {
            var action_name=this.options.action;
            if (action_name=="_close") {
                $(".modal").modal("hide");
            } else if (action_name=="_search") {
                var collection=this.context.collection;
                collection.trigger("show_search");
                this.$el.hide();
            } else if (action_name=="_save") {
                var model=this.context.model;
                model.save({},{
                    success: function() {
                        set_flash("success","Changes saved successfully.");
                        if (that.options.next) {
                            exec_action({name:that.options.next});
                        }
                    },
                    error: function(model,err) {
                        log("save error",err);
                        set_flash("error",err.message);
                        render_flash();
                    }
                });
            } else if (action_name=="_save_local") {
                var collection=this.context._parent_context.collection;
                log("collection",collection);
                var model=this.context.model;
                collection.add(model);
                $(".modal").modal("hide");
            } else {
                var action={name:action_name};
                if (this.options.action_options) {
                    if (this.options.action_options[0]=="{") {
                        if (this.context.model) {
                            var data=this.context.model.get_vals_all();
                        } else {
                            var data={}; // XXX
                        }
                        var opts=eval_json(this.options.action_options,data);
                        _.extend(action,opts);
                    } else { // XXX: deprecated
                        _.extend(action,qs_to_obj(this.options.action_options));
                    }
                }
                if (this.options.action_context) {
                    action.context=qs_to_obj(this.options.action_context); // XXX
                }
                if (this.options.select) {
                    var collection=this.context.collection;
                    var ids=[];
                    collection.each(function(m) {
                        if (m.get("_selected")) ids.push(m.id);
                    });
                    if (ids.length==0) {
                        set_flash("error","No items selected.");
                        render_flash();
                        return;
                    }
                    action.ids=ids;
                }
                if (this.context.model) { // XXX
                    log("saving model before exec action...");
                    /*this.context.model.save({},{
                        success: function() {
                            action.refer_id=that.context.model.id;
                            exec_action(action);
                        }
                    });*/ // XXX: check this...
                    if (!this.context.model.check_required()) {
                        set_flash("error","Some required fields are missing");
                        render_flash();
                        return;
                    }else{
                        action.refer_id=this.context.model.id;
                        exec_action(action);
                    }
                } else {
                    exec_action(action); // XXX: parent_context
                }
            }
        }
    },

    listen_states: function() {
        var states=this.options.states;
        if (!states) return;
        var model=this.context.model;
        model.on("change:state",this.render,this);
    },

    eval_attrs: function() {
        var str=this.options.attrs;
        //log("button.eval_attrs",this,str);
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
    }
});

Button.register();
