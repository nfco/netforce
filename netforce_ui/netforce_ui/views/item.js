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

var Item=NFView.extend({
    _name: "item",
    tagName: "li",
    events: {
        "click a": "onclick",
        "touchstart a": "ontouch" // bootstrap bug: https://github.com/twitter/bootstrap/issues/4550
    },

    initialize: function(options) {
        NFView.prototype.initialize.call(this,options);
        this.listen_states();
    },

    render: function() {
        var that=this;
        var hide=false;
        var perm_model=that.options.perm_model;
        if (this.options.perm) {
            if (!check_other_permission(this.options.perm,this.options.perm_check_admin)) {
                hide=true;
            }
        }else if (perm_model && typeof(perm_model)==typeof('')) {
            var perms=perm_model.split(",");
            if (perms.length>1){
                var model=perms[0];
                var all_perm=[];
                for(var i=0; i<perms.length;i++){
                    var perm=perms[i];
                    all_perm.push(check_model_permission(model,perm));
                }
                hide=!(all_perm ? _.contains(all_perm,true) : true);
            }
        }
        if (this.options.action) {
            if (!check_menu_permission(this.options.action)) {
                hide=true;
            }
        }
        if (hide) {
            this.$el.hide();
        } else {
            this.$el.show();
        }
        if (!check_package(this.options.pkg)) {
            this.$el.addClass("disabled");
        }
        if (this.options.dropdown) {
            var data={
                context: this.data.context
            };
            this.data.content=this.options.inner(data);
            this.$el.addClass("dropdown");
        }
        NFView.prototype.render.call(this);
        if (this.options.states) {
            var model=this.context.model;
            var state=model.get("state");
            var states=this.options.states.split(",");
            if (!_.contains(states,state)) {
                this.$el.hide();
            }
        }
        if (this.options.disabled) {
            this.$el.addClass("disabled");
            this.$el.find('a').css({"color":"#cccccc"});
        }
        if(this.options.color){
            this.$el.find('a').css({"color":this.options.color});
        }

        if(this.context.model){
            var hide=is_hidden({type:"item", model:this.context.model.name, name: this.options.string});
            if(hide) this.$el.hide();
        }

    },

    ontouch: function(e) { // bootstrap bug
        e.stopPropagation();
    },

    onclick: function(e) {
        log("Item.onclick",this);
        log("string",this.options.string,"url",this.options.url);
        if (e.ctrlKey) return;
        if (!this.options.action && !this.options.url && !this.options.method) return;
        e.preventDefault();
        e.stopPropagation();
        if (!check_package(this.options.pkg)) return;
        if (this.options.confirm) {
            var res=confirm(this.options.confirm);
            if (!res) return;
        }
        var that=this;
        if (this.options.action) {
            var action={name:this.options.action};
            if (this.options.action_options) {
                if (this.options.action_options[0]=="{") {
                    if (this.context.model) {
                        var data=this.context.model.get_vals_all();
                    } else {
                        var data={};
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
            var model=this.context.model;
            if (model) {
                action.refer_id=model.id;
            }
            exec_action(action);
        } else if (this.options.url) {
            window.location=this.options.url;
        } else if (this.options.method) {
            log("method",this.options.method);
            var method=this.options.method;
            var model=this.context.model;
            var method_context=this.options.method_context;
            if (method_context) {
                method_context=qs_to_obj(method_context);
            } else {
                method_context={};
            }
            if (method=="_save") {
                model.save({},{
                    context: method_context,
                    success: function() {
                        set_flash("success","Changes saved successfully.");
                        if (that.options.next) {
                            exec_action({name:that.options.next});
                        } else {
                            model.trigger("reload");
                        }
                    },
                    error: function(err) {
                        set_flash("error",err.message);
                        render_flash();
                        that.context.model.set_field_errors(err.error_fields);
                    }
                });
            } else if (method=="_delete") {
                var res=confirm("Are you sure you want to delete this item?");
                if (!res) return;
                rpc_execute(model.name,"delete",[[model.id]],{},function(err,data) {
                    if (err) {
                        set_flash("error",err.message);
                        render_flash();
                        return;
                    }
                    log("delete success");
                    var next=that.options.next;
                    if (next) {
                        var action={name:next};
                        if (that.options.next_options) {
                            _.extend(action,qs_to_obj(that.options.next_options));
                        }
                        exec_action(action);
                    }
                });
            } else {
                log("calling model method",model);
                log("method context",method_context);
                model.save({},{ // save should not do anything if nothing changed
                    context: method_context,
                    success: function() {
                        rpc_execute(model.name,method,[[model.id]],{},function(err,data) {
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
                            if (data && data.context) {
                                set_context(data.context);
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
                                model.trigger("reload");
                            }
                        });
                    },
                    error: function(model,err) {
                        log("SAVE ERROR",err);
                        set_flash("error",err.message);
                        render_flash();
                    }
                });
            }
        }
    },

    listen_states: function() {
        var states=this.options.states;
        if (!states) return;
        var model=this.context.model;
        model.on("change:state",this.render,this);
    }
});

Item.register();
