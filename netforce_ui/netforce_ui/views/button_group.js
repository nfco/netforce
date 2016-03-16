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

var ButtonGroup=NFView.extend({
    _name: "button_group",
    className: "btn-group",
    events: {
        "click .main-btn": "click"
    },

    render: function() {
        //log("button_group.render",this);
        var data={
            context: this.data.context
        };
        this.data.content=this.options.inner(data);
        if (this.options.size=="large") {
            this.data.btn_size="lg";
        } else if (this.options.size=="small") {
            this.data.btn_size="sm";
        } else if (this.options.size=="extra_small") {
            this.data.btn_size="xs";
        }
        this.data.btn_type=this.options.type||"default";
        NFView.prototype.render.call(this);
        if (this.options.pull) {
            this.$el.addClass("pull-"+this.options.pull);
        }
        if (this.options.align) {
            this.$el.find("ul").addClass("pull-"+this.options.align);
        }
    },

    click: function(e) {
        e.preventDefault();
        e.stopPropagation();
        var that=this;
        if (this.options.method) {
            var method=this.options.method;
            var method_context=this.options.method_context;
            if (method_context) {
                method_context=qs_to_obj(method_context);
            } else {
                method_context={};
            }
            var model=this.context.model;
            if (method=="_save") {
                if (!model.check_required()) {
                    set_flash("error","Some required fields are missing");
                    render_flash();
                    return;
                }
                model.save({},{
                    context: method_context,
                    success: function() {
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
                        log("save error",model,err);
                        set_flash("error",err.message);
                        render_flash();
                        that.context.model.set_field_errors(err.error_fields);
                    }
                });
            } else {
                log("calling model method",model);
                model.save({},{ // save should not do anything if nothing changed
                    success: function() {
                        rpc_execute(model.name,method,[],{},function(err,data) {
                            if (err) {
                                set_flash("error",err);
                                render_flash();
                                return;
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
                        log("save error",err);
                        set_flash("error",err.message);
                        render_flash();
                    }
                });
            }
        }
    }
});

ButtonGroup.register();
