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

var Related=NFView.extend({
    _name: "related",
    events: {
        "click .nf-btn-add": "add_item",
        "click .nf-btn-delete": "delete_items"
    },

    initialize: function(options) {
        //log("related.initialize",this);
        NFView.prototype.initialize.call(this,options);
        var that=this;
        this.model_name=this.options.model;
        this.field_name=this.options.field_name;
        if (!this.field_name) throw "No field_name";
        var field=get_field(this.model_name,this.field_name);
        this.relation=field.relation;
        this.relfield=field.relfield;
        this.data.string=field.string;
        this.form_layout=this.options.form_layout;
        if (this.options.list_layout) {
            var layout=this.options.list_layout;
        } else if (this.options.list_view_xml) {
            var list_view=get_xml_layout({name:this.options.list_view_xml});
            var layout=list_view.layout;
        } else {
            var list_view=get_xml_layout({model:this.relation,type:"list"});
            var layout=list_view.layout;
        }
        if (_.isString(layout)) {
            var doc=$.parseXML(layout);
            this.$list=$(doc).children();
        } else {
            this.$list=layout;
        }
        this.listen_attrs();
        this.data.render_list_head=function(ctx) { return that.render_list_head.call(that,ctx); };
    },

    render: function() {
        //log("related.render",this);
        var that=this;
        var field_names=[];
        var cols=[];
        var model=this.context.model;

        this.$list.find("field").each(function() {

            field_name=$(this).attr("name");

            var hide=is_hidden({type: 'field', model: that.relation, name: field_name});
            if(hide) return;

            field_names.push(field_name);
            if (!$(this).attr("invisible")) {
                cols.push({
                    col_type: "field",
                    name:field_name,
                    target: $(this).attr("target"),
                    show_sum: $(this).attr("sum"),
                    preview: $(this).attr("preview")
                });
            }
        });
        this.data.colors=this.$list.attr("colors");
        this.data.cols=cols;
        var field=get_field(this.model_name,this.field_name);
        if (field.type=="one2many") {
            var relfield=get_field(this.relation,this.relfield);
            if (relfield.type=="many2one") {
                var condition=[[this.relfield,"=",model.id]];
            } else if (relfield.type=="reference") {
                var condition=[[this.relfield,"=",model.name+","+model.id]];
            } else {
                throw "Invalid related field type for related list: "+this.relfield+"/"+this.relation;
            }
            var limit=10;
            rpc_execute(that.relation,"search_read",[condition,field_names],{limit:limit,count:true},function(err,data) {
                that.collection=new NFCollection(data[0],{name:that.relation});
                that.collection.count=data[1];
                that.collection.condition=condition;
                that.collection.fields=field_names;
                that.collection.limit=limit;
                that.collection.parent_model=that.context.model;
                that.collection.on("click",that.line_click,that);
                that.collection.on("reload",that.render,that);
                that.data.context.data=data[0];
                that.data.context.collection=that.collection;
                that.data.context.model=null; // XXX
                that.data.count=data[1];
                that.data.model_perm_create=check_model_permission(that.relation,"create");
                that.data.model_perm_delete=check_model_permission(that.relation,"delete");
                if (that.options.readonly) {
                    that.data.model_perm_create=false;
                    that.data.model_perm_delete=false;
                }
                NFView.prototype.render.call(that);
                if (that.collection.length==0) {
                    that.$el.find(".btn-delete").hide();
                }
                if(that.options.noadd){
                    that.$el.find(".nf-btn-add").hide();
                }
                if(that.options.nodelete){
                    that.$el.find(".nf-btn-delete").hide();
                }
            });
        } else if (field.type=="many2many") { // XXX
            rpc_execute(model.name,"read",[[model.id],[this.field_name]],{},function(err,data) {
                var ids=data[0][that.field_name];
                rpc_execute(that.relation,"read",[ids,field_names],{},function(err,data) {
                    that.collection=new NFCollection(data,{name:that.relation});
                    that.collection.fields=field_names;
                    that.collection.parent_model=that.context.model;
                    that.collection.on("click",that.line_click,that);
                    that.collection.on("reload",that.render,that);
                    that.data.context.data=data;
                    that.data.context.collection=that.collection;
                    that.data.context.model=null; // XXX
                    that.data.model_perm_create=check_model_permission(that.relation,"create");
                    that.data.model_perm_delete=check_model_permission(that.relation,"delete");
                    if (that.options.readonly) {
                        that.data.model_perm_create=false;
                        that.data.model_perm_delete=false;
                    }
                    NFView.prototype.render.call(that);
                    if (that.collection.length==0) {
                        that.$el.find(".btn-delete").hide();
                    }
                });
            });
        } else {
            throw "Invalid field type for related view: "+this.field_name;
        }
        var attrs=this.eval_attrs();
        if (attrs.invisible) {
            this.$el.hide();
        } else {
            this.$el.show();
        }
        return this;
    },

    render_list_head: function(context) {
        //log("list_view.render_list_head",this,context);
        var that=this;
        var html=$("<div/>");
        this.$list.find("head").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="button") {
                var opts={
                    string: $el.attr("string"),
                    action: $el.attr("action"),
                    action_options: $el.attr("action_options"),
                    size: $el.attr("size")||"small",
                    type: $el.attr("type"),
                    next: $el.attr("next"),
                    icon: $el.attr("icon"),
                    perm: $el.attr("perm"),
                    context: context
                };

                var hide=is_hidden({type: 'button', model: that.relation, name: opts.string});
                if(hide) return;

                if ($el.attr("method")) {
                    opts.onclick=function() {
                        that.call_method($el.attr("method"));
                    };
                }
                if (!$el.attr("noselect")) {
                    opts.select=true;
                }

                var view=Button.make_view(opts);
                html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            }
        });
        return html.html();
    },

    add_item: function() {
        log("related.add_item",this);
        var that=this;
        var action_name=this.options.action;
        log("action_name",action_name);
        if (action_name) {
            var action={
                name: action_name,
                mode: "form"
            };
            var field=get_field(this.options.model,this.options.field_name);
            if (field.relfield) {
                var relfield=get_field(field.relation,field.relfield);
                if (relfield.type=="many2one") {
                    var val=this.context.model.id;
                    action.defaults={};
                    action.defaults[field.relfield]=val;
                } else if (relfield.type=="reference") {
                    var val=this.context.model.name+","+this.context.model.id;
                    action.defaults={};
                    action.defaults[field.relfield]=val;
                }
            }
            exec_action(action);
        } else {
            this.$el.find(".btn-toolbar").hide();
            var opts={
                model: this.relation,
                layout: this.options.form_layout,
                relfield: this.relfield,
                parent_id: this.context.model.id,
                parent_model: this.model_name,
                parent_data: this.context.model.get_vals(),
                context: this.data.context
            };
            var view_cls=get_view_cls("inline_form");
            var view=view_cls.make_view(opts);
            view.render();
            this.$el.find(".add-form").empty();
            this.$el.find(".add-form").append(view.el);
            view.on("save",function() {
                remove_view_instance(view.cid);
                var model=that.context.model;
                model.trigger("reload");
            });
            view.on("cancel",function() {
                that.$el.find(".btn-toolbar").show();
                remove_view_instance(view.cid);
            });
        }
    },

    delete_items: function() {
        log("related.delete_items",this);
        var that=this;
        var ids=[];
        this.collection.each(function(m) {
            if (m.get("_selected")) ids.push(m.id);
        });
        if (ids.length==0) {
            alert("No items selected");
            return;
        }
        rpc_execute(this.relation,"delete",[ids],{},function(err,data) {
            var model=that.context.model;
            model.trigger("reload");
        });
    },

    edit_item: function(active_id) {
        log("related.edit_item",this,active_id);
        var that=this;
        if (this.options.readonly) return;
        this.$el.find(".btn-toolbar").hide();
        var opts={
            model: this.relation,
            layout: this.options.form_layout,
            active_id: active_id,
            context: this.data.context
        };
        var view_cls=get_view_cls("inline_form");
        var view=view_cls.make_view(opts);
        view.render();
        this.$el.find(".add-form").empty();
        this.$el.find(".add-form").append(view.el);
        view.on("save",function() {
            remove_view_instance(view.cid);
            var model=that.context.model;
            model.trigger("reload");
        });
        view.on("cancel",function() {
            that.$el.find(".btn-toolbar").show();
            remove_view_instance(view.cid);
        });
    },

    line_click: function(model) {
        log("related.line_click",this,model);
        if (this.$list.attr("action")) {
            var action={name:this.$list.attr("action")};
            if (this.$list.attr("action_options")) {
                var action_options=qs_to_obj(this.$list.attr("action_options"));
                _.extend(action,action_options);
            }
            action.active_id=model.id;
        } else if (this.options.click_action) { // XXX
            var action={name:this.options.click_action};
            action.active_id=model.id;
        } else if (this.options.action) {
            var action={name:this.options.action};
            action.mode="form"; // XXX
            action.active_id=model.id;
        } else {
            var model_name=model.name;
            var action=find_details_action(model_name,model.id);
            if (!action || this.form_layout) {
                this.edit_item(model.id);
                return;
            }
        }
        exec_action(action);
    },

    eval_attrs: function() {
        var str=this.options.attrs;
        //log("related.eval_attrs",this,str);
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

    call_method: function(method,context) {
        log("related.call_method",this);
        var that=this;
        if (!context) context={};
        var collection=this.collection;
        var ids=[];
        collection.each(function(m) {
            if (m.get("_selected")) ids.push(m.id);
        });
        if (ids.length==0) {
            set_flash("error","No items selected.");
            render_flash();
            return;
        }
        rpc_execute(collection.name,method,[ids],{context:context},function(err,data) {
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
                var model=that.context.model;
                model.trigger("reload");
            }
        });
    }
});

Related.register();
