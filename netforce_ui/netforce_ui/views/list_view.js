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

var ListView=NFView.extend({
    _name: "list_view",
    events: {
        "click .search-btn": "click_search",
        "click ul.nav-tabs a": "click_tab"
    },

    initialize: function(options) {
        //log("list_view.initialize",this);
        var that=this;
        NFView.prototype.initialize.call(this,options);
        if (!this.options.model) throw "ListView: missing model";
        if (this.options.list_layout) {
            var layout=this.options.list_layout;
        } else {
            if (this.options.view_xml) {
                var list_view=get_xml_layout({name:this.options.view_xml});
            } else {
                var list_view=get_xml_layout({model:this.options.model,type:"list"});
            }
            var layout=list_view.layout;
        }
        if (_.isString(layout)) {
            var doc=$.parseXML(layout);
            this.$list=$(doc).children();
        } else {
            this.$list=layout;
        }
        this.data.colors=this.$list.attr("colors");
        this.data.render_list_head=function(ctx) { return that.render_list_head.call(that,ctx); };
        this.data.render_list_top=function(ctx) { return that.render_list_top.call(that,ctx); };
        this.data.on_click_item=_.bind(this.on_click_item,this);
        if (this.options.tabs) {
            var tabs=this.options.tabs;
            if (_.isString(tabs)) {
                var tabs=JSON.parse(tabs);
            }
            this.data.tabs=[];
            var tab_no=0;
            var hide_tabs=[];
            _.each(tabs,function(tab) {
                var hide=is_hidden({type:"tab_action", model:that.options.model, name: tab[0]});
                if(hide) return;
                hide_tabs.push(tab);
                that.data.tabs.push({
                    string: tab[0],
                    condition: tab[1],
                    tab_no: tab_no,
                    action: that.options.action_name,
                    action_opts: (tab[0]!="All"&&tab[0]!="Active")?"tab="+tab[0]:"" // XXX
                });
                tab_no++;
            });
        }

        this.options.tabs=hide_tabs; // for hidden

        this.modes=this.options.modes;
        if (!this.modes) this.modes="list,form";
        if (_.isString(this.modes)) {
            this.modes=this.modes.split(",");
        }
        this.search_condition=this.options.search_condition;
        if (this.options.reload_event) {
            nf_listen(this.options.reload_event,function() {
                log("reload view",this);
                that.render();
            });
        }
        this.active_id=this.options.active_id;
        this.tab_no=parseInt(this.options.tab_no);
    },

    render: function() {
        //log("list_view.render",this);
        var that=this;
        var model_name=this.options.model;
        var field_names=[];
        var cols=[];
        this.data.noselect=this.options.noselect || this.$list.attr("noselect");
        this.$list.children().each(function() {
            var tag=$(this).prop("tagName");
            if (tag=="field") {
                var name=$(this).attr("name");

                var hide=is_hidden({type:tag, model:that.options.model, name: name});
                if(hide) return;

                var field=get_field(that.options.model,name);
                field_names.push(name);
                if (!$(this).attr("invisible")) {
                    var col={
                        col_type: "field",
                        name: name,
                        link: $(this).attr("link"),
                        target: $(this).attr("target"),
                        preview: $(this).attr("preview"),
                        view: $(this).attr("view")
                    };
                    if (field.type=="float") {
                        col.align="right";
                    }
                    if (field.store) {
                        col.can_sort=true;
                    }
                    cols.push(col);
                }
            } else if (tag=="button") {
                var col={
                    col_type: "button",
                    string: $(this).attr("string"),
                    method: $(this).attr("method"),
                    type: $(this).attr("type"),
                    icon: $(this).attr("icon")
                }
                cols.push(col);
            }
        });
        this.data.cols=cols;
        var model=get_model_cls(model_name);
        var condition=this.options.condition||[];
        if (_.isString(condition)) {
            var ctx=clean_context(_.extend({},this.context,this.options));
            condition=eval_json(condition,ctx);
        }
        var search_condition=this.search_condition||[];
        if (_.isString(search_condition)) {
            search_condition=JSON.parse(search_condition);
        }
        if (search_condition.length>0) {
            if (condition.length>0) {
                condition=[condition,search_condition];
            } else {
                condition=search_condition;
            }
        }
        var tab_condition=null;
        if (this.options.tabs) {
            var tabs=this.options.tabs;
            if (_.isString(tabs)) {
                tabs=JSON.parse(tabs);
            }
            var tab_no=this.tab_no||0;
            var tab=tabs[tab_no];
            var tab_condition=tab[1];
            if (_.isObject(tab_condition)) {
                condition=condition.concat([tab_condition]);
            }
        }
        if (!_.isString(tab_condition)) {
            this.data.show_list=true;
        } else {
            this.data.show_list=false;
        }

        var h=window.location.hash.substr(1);
        var action=qs_to_obj(h);
        if(action && action.limit){
            this.options.limit=action.limit;
        }

        var opts={
            field_names: field_names,
            order: this.options.order,
            offset: this.options.offset,
            limit: this.options.limit||100,
            count: true
        }
        // unlimited -1
        if(opts.limit<0){
            delete opts.limit;
        }

        if (that.options.show_full) {
            this.data.header_scroll=true;
        }
        log("yes2 ", tab_condition, condition);
        if (!_.isString(tab_condition)) {
            this.render_waiting();
            rpc_execute(model_name,"search_read",[condition],opts,function(err,data) {
                that.collection=new NFCollection(data[0],{name:model_name});
                that.collection.fields=field_names;
                that.collection.condition=condition;
                that.collection.order=that.options.order;
                that.collection.search_condition=condition; // XXX: check this
                if (that.options.show_full||that.options.show_pagination) { // FIXME
                    that.collection.count=data[1];
                    that.collection.offset=parseInt(that.options.offset);
                    that.collection.limit=that.options.limit||100;
                }
                that.collection.on("click",that.line_click,that);
                that.collection.on("reload",that.reload,that);
                that.data.context.data=data;
                that.data.context.collection=that.collection;
                that.data.context.model=null; // XXX
                that.data.context.model_name=model_name;
                if (that.$list.attr("group_fields")) {
                    that.data.group_fields=that.$list.attr("group_fields").split(",");
                }
                that.data.active_id=that.active_id;
                NFView.prototype.render.call(that);
                if (that.search_condition) {
                    that.show_search();
                }
                that.show_active_tab();
            });
        } else {
            NFView.prototype.render.call(this);
            this.show_active_tab();
            var action_name=tab_condition;
            var action=get_action(action_name);
            var view_cls=get_view_cls(action.view_cls||"action");
            var view=new view_cls({options:action});
            view.render();
            this.$el.append(view.el);
        }
        return this;
    },

    reload: function() {
        this.render();
    },

    render_waiting: function() {
        var img=$("<img/>").attr("src","/static/img/spinner.gif");
        this.$el.empty();
        this.$el.append(img);
    },

    render_list_head: function(context) {
        //log("list_view.render_list_head",this,context);
        var that=this;
        var html=$("<div/>");
        if ((this.options.show_full || this.options.show_search) && !this.$list.attr("no_search")) { // XXX
            if (_.isEmpty(this.options.search_condition)) {
                html.append('<button type="button" class="btn btn-sm btn-default pull-right search-btn" style="white-space:nowrap;"><i class="icon-search"></i> '+ translate("Search")+"</button>");
            }
        }
        if (this.options.show_full||this.options.show_default_buttons) { // XXX
            if (!this.$list.find("head").attr("replace")) {
                if (check_model_permission(this.options.model,"delete")) {
                    var opts={
                        string: "Delete",
                        type: "danger",
                        size: "small",
                        method: "_delete",
                        context: context
                    };
                    var view=Button.make_view(opts);
                    html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                }
                if (has_field(this.options.model,"active") && check_model_permission(this.options.model,"write"))  {
                    var show_archived=false;
                    if (this.options.tabs) {
                        var tabs=this.options.tabs;
                        if (_.isString(tabs)) {
                            tabs=JSON.parse(tabs);
                        }
                        var tab_no=this.tab_no||0;
                        var tab=tabs[tab_no];
                        show_archived=tab[0]=="Archived"; // XXX
                    }
                    if (show_archived) {
                        var opts={
                            string: "Restore",
                            size: "small",
                            method: "_restore",
                            context: context
                        };
                    } else {
                        var opts={
                            string: "Archive",
                            size: "small",
                            method: "_archive",
                            context: context
                        };
                    }
                    var view=Button.make_view(opts);
                    html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                }
                if(allow_import_export(that.context)){
                    var opts={
                        string: "Export",
                        size: "small",
                        method: "_export2",
                        context: context
                    };
                    var view=Button.make_view(opts);
                    html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                }
            }
        }
        var that = this;
        this.$list.find("head").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="button") {
                var model = that.options.model;
                var name = $el.attr("string");

                var hide=is_hidden({type:'button', model:model, name: name});
                if(hide) return;

                var opts={
                    string: $el.attr("string"),
                    method: $el.attr("method"),
                    action: $el.attr("action"),
                    action_options: $el.attr("action_options"),
                    size: $el.attr("size")||"small",
                    type: $el.attr("type"),
                    next: $el.attr("next"),
                    icon: $el.attr("icon"),
                    perm: $el.attr("perm"),
                    perm_model: $el.attr("perm_model"),
                    confirm: $el.attr("confirm"),
                    context: context
                };
                if (!$el.attr("noselect")) {
                    opts.select=true;
                }
                var view=Button.make_view(opts);
                html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            }
        });
        return html.html();
    },

    render_list_top: function(context) {
        //log("list_view.render_list_top",this,context);
        var that=this;
        var html=$("<div/>");
        if (!this.$list.find("top").attr("replace")) {
            if (check_model_permission(this.options.model,"create")) {
                var new_string="New";
                var model_cls=get_model(this.options.model);
                model_string=this.options.model_string||model_cls.string;
                if (model_string) {
                    new_string+=" "+model_string;
                }
                var opts={
                    string: new_string,
                    onclick: function() { that.trigger("change_mode",{mode:"form"}); },
                    icon: "plus-sign",
                    context: context
                };
                var view=Button.make_view(opts);
                html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");

                if(allow_import_export(that.context)){
                    var opts={
                        string: "Import",
                        action: "import_data",
                        action_options: "import_model="+that.options.model+"&next="+this.options.action_name,
                        icon: "download",
                        context: that.data.context
                    };
                    var view=Button.make_view(opts);
                    html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");

                    var opts={
                        string: "Match Field",
                        action: "match_field",
                        action_options: "import_model="+that.options.model+"&next="+this.options.action_name,
                        icon: "ok-sign",
                        context: that.data.context
                    };
                    var view=Button.make_view(opts);
                    html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                }
            }
        }
        this.$list.find("top").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="button") {
                context.model_name=that.options.model;
                var opts={
                    string: $el.attr("string"),
                    model: that.options.model,
                    method: $el.attr("method"),
                    static_method: true,
                    action: $el.attr("action"),
                    action_options: $el.attr("action_options"),
                    size: $el.attr("size"),
                    type: $el.attr("type"),
                    next: $el.attr("next"),
                    icon: $el.attr("icon"),
                    perm: $el.attr("perm"),
                    perm_model: $el.attr("perm_model"),
                    dropdown: $el.attr("dropdown"),
                    context: context
                };
                if (opts.action=="import_data" || opts.action=="export_data"){
                    if(!allow_import_export(that.context)) return;
                }
                if (opts.dropdown) {
                    var inner="";
                    $el.children().each(function() {
                        var $el2=$(this);
                        var tag=$el2.prop("tagName");
                        if (tag=="item") {
                            var opts2={
                                string: $el2.attr("string"),
                                method: $el2.attr("method"),
                                static_method: true,
                                action: $el2.attr("action"),
                                action_options: $el2.attr("action_options"),
                                perm: $el2.attr("perm"),
                                context: context
                            }
                            var view=Item.make_view(opts2);
                            inner+="<li id=\""+view.cid+"\" class=\"view\"></li>";
                        } else if (tag=="divider") {
                            inner+="<li class=\"divider\"></li>";
                        }
                    });
                    opts.inner=function() {return inner; };
                    var view=ButtonGroup.make_view(opts);
                } else {
                    var view=Button.make_view(opts);
                }
                html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
            }
        });
        if (_.contains(this.modes,"grid")) {
            var opts={
                string: "Grid",
                icon: "th",
                pull: "right",
                onclick: function() { that.trigger("change_mode",{"mode":"grid"}); },
                context: context
            };
            var view=Button.make_view(opts);
            html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
        }
        if (_.contains(this.modes,"calendar")) {
            var opts={
                string: "Calendar",
                icon: "calendar",
                pull: "right",
                onclick: function() { that.trigger("change_mode",{"mode":"calendar"}); },
                context: context
            };
            var view=Button.make_view(opts);
            html.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
        }
        return html.html();
    },

    line_click: function(model) {
        log("list_view.line_click",this,model);
        if (this.options.no_click) return;
        if (this.$list.attr("action")) {
            var action={name:this.$list.attr("action")};
            if (this.$list.attr("action_options")) {
                var action_options=qs_to_obj(this.$list.attr("action_options"));
                _.extend(action,action_options);
            }
            action.active_id=model.id;
            if (this.tab_no) {
                action.tab_no=this.tab_no;
            }
            if (this.search_condition) {
                action.search_condition=this.search_condition;
            }
            if (this.collection.offset) {
                action.offset=this.collection.offset;
            }
        } else if (this.options.action) {
            var action={name:this.options.action};
            if (this.options.action_options) {
                _.extend(action,this.options.action_options);
            }
            action.active_id=model.id;
            if (this.search_condition) {
                action.search_condition=this.search_condition; // XXX
            }
            if (this.tab_no) {
                action.tab_no=this.tab_no; // XXX: simplify this
            }
            if (this.collection.offset) {
                action.offset=this.collection.offset; // XXX: simplify this
            }
        } else if (_.contains(this.modes,"form")) {
            var action=find_details_action(this.options.model,model.id);
        }
        exec_action(action);
    },

    click_search: function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.show_search();
    },

    show_search: function(e) {
        log("list_view.show_search");
        var that=this;
        var opts={
            model: this.options.model
        };
        if (this.options.search_view_xml) {
            opts.view_xml=this.options.search_view_xml;
        } else if (this.options.search_layout) {
            opts.view_layout=this.options.search_layout;
        }
        var $el=this.$list.find("search");
        if ($el.length>0) {
            opts.view_layout=$el;
        }
        var view=new SearchView({options:opts});
        if (that.search_condition) {
            view.set_condition(that.search_condition);
        }
        view.render();
        this.$el.find(".search-btn").hide();
        this.$el.find(".search").append(view.el);
        view.on("close",function() {
            that.$el.find(".search-btn").show();
        });
        view.on("search",function() {
            that.search_condition=view.get_condition();
            that.collection.offset=0;
            that.render();

            var h=window.location.hash.substr(1);
            var action=qs_to_obj(h);
            action.search_condition=that.search_condition;
            if (_.isEmpty(action.search_condition)) delete action.search_condition;
            if (action.offset) delete action.offset;
            var h2=obj_to_qs(action);
            workspace.navigate(h2);
        });
    },

    click_tab: function(e) {
        log("list_view.click_tab",this,e);
        e.preventDefault();
        var tab_no=$(e.target).parent("li").data("tab");
        log("tab_no",tab_no);
        this.tab_no=tab_no;
        this.search_condition=null;
        this.active_id=null;
        this.render();

        var h=window.location.hash.substr(1);
        var action=qs_to_obj(h);
        action.tab_no=tab_no;
        if (action.search_condition) delete action.search_condition;
        if (action.active_id) delete action.active_id;
        if (action.offset) delete action.offset;
        var h2=obj_to_qs(action);
        workspace.navigate(h2);
    },

    show_active_tab: function() {
        var tab_no=this.tab_no||0;
        this.$el.find("li[data-tab="+tab_no+"]").addClass("active");
    },

    get_selected_ids: function() {
        var ids=[];
        this.$el.find(".list-line-select input:checked").each(function() {
            var id=$(this).closest("tr").data("model-id");
            ids.push(id);
        });
        return ids;
    },

    on_click_item: function(model_id) {
        this.trigger("click_item",{active_id:model_id});
    }
});

ListView.register();
