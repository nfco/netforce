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

var Search=NFView.extend({
    _name: "search",
    events: {
        "click .close": "close",
        "click .search-go": "do_search",
        "click .search-clear": "do_clear"
    },

    initialize: function(options) {
        var that=this;
        NFView.prototype.initialize.call(this,options);
        var collection=this.context.collection;
        collection.on("show_search",this.show_search,this);
        if (!_.isEmpty(collection.search_condition)) {
            this.show_search=true;
        } else {
            this.show_search=false;
        }
        this.fields=this.options.fields;
        if (_.isEmpty(this.fields) && this.options.inner) {
            var content=this.options.inner({context: this.context});
            var layout="<search>"+content+"</search>";
            var doc=$.parseXML(layout);
            this.fields=[];
            $(doc).find("search").children().each(function() {
                var $el=$(this);
                var tag=$el.prop("tagName");
                if (tag=="field") {
                    var name=$el.attr("name");
                    var select=$el.attr("select");
                    that.fields.push({
                        name: name,
                        select: select,
                        perm: $el.attr("perm")
                    });
                }
            });
        }
        if (_.isEmpty(this.fields)) {
            var collection=this.context.collection;
            var model_cls=get_model(collection.name);
            var req_fields=[];
            var other_fields=[];
            _.each(model_cls.fields,function(f,n) {
                if (f.search) {
                    if (f.required) {
                        req_fields.push(n);
                    } else {
                        other_fields.push(n);
                    }
                }
            });
            req_fields=_.sortBy(req_fields,function(n) {return model_cls.fields[n].string});
            other_fields=_.sortBy(other_fields,function(n) {return model_cls.fields[n].string});
            this.fields=[];
            _.each(req_fields,function(n) {
                that.fields.push({name:n});
            });
            _.each(other_fields,function(n) {
                that.fields.push({name:n});
            });
        }
    },

    render: function() {
        //log("search.render",this);
        if (!this.show_search) return;
        var that=this;
        var collection=this.context.collection;
        var search_model=new NFModel({},{name:"_search"});
        _.each(this.fields,function(f) {
            var model_cls=get_model(collection.name);
            var orig_field=model_cls.fields[f.name];
            //log("orig_field",orig_field);
            var search_field=null;
            if (orig_field.type=="char") search_field={type:"char",string:orig_field.string};
            else if (orig_field.type=="selection") search_field={type:"selection",selection:orig_field.selection,string:orig_field.string};
            else if (orig_field.type=="many2one") {
                if (f.select) {
                    search_field={type:"many2one",relation:orig_field.relation,string:orig_field.string};
                } else {
                    search_field={type:"char",string:orig_field.string};
                }
            } else if (orig_field.type=="text") search_field={type:"char",string:orig_field.string};
            else if (orig_field.type=="reference") search_field={type:"char",string:orig_field.string};
            else if (orig_field.type=="float") search_field={type:"float_range",string:orig_field.string};
            else if (orig_field.type=="decimal") search_field={type:"float_range",string:orig_field.string};
            else if (orig_field.type=="integer") search_field={type:"float_range",string:orig_field.string}; // XXX
            else if (orig_field.type=="date" || orig_field.type=="datetime") search_field={type:"date_range",string:orig_field.string};
            else if (orig_field.type=="boolean") search_field={type:"selection",selection:[["yes","Yes"],["no","No"]],string:orig_field.string};
            if (!search_field) return;
            search_model.fields[f.name]=search_field;
        });
        this.data.context.model=search_model;
        var condition=collection.search_condition;
        if (condition) {
            for (var i in condition) {
                var clause=condition[i];
                var model_cls=collection.model;
                var n=clause[0];
                var f=model_cls.fields[n];
                if (!f) {
                    throw "Invalid search field: "+n;
                }
                var op=clause[1];
                var v=clause[2];
                if (f.type=="char") {
                    if (v) v=v.replace(/%/g,"");
                    search_model.set(n,v);
                } else if (f.type=="many2one") {
                    if (_.isNumber(v)) {
                        rpc_execute(f.relation,"name_get",[[v]],{},function(err,data) {
                            v=data[0][1];
                            search_model.set(n,v);
                        });
                    } else if (_.isString(v)) {
                        v=v.replace(/%/g,"");
                        search_model.set(n,v);
                    }
                } else if (f.type=="float") {
                    var r=search_model.get(n)||[null,null];
                    if (op==">=") r[0]=v;
                    else if (op=="<=") r[1]=v;
                    search_model.set(n,r);
                } else if (f.type=="date") {
                    var r=search_model.get(n)||[null,null];
                    if (op==">=") r[0]=v;
                    else if (op=="<=") r[1]=v;
                    search_model.set(n,r);
                }
            }
        }
        this.data.fields=this.fields;
        NFView.prototype.render.call(this);
    },

    close: function() {
        this.show_search=false;
        this.$el.empty();
        var collection=this.context.collection;
        collection.trigger("hide_search");
    },

    do_search: function() {
        log("do_search");
        var model=this.data.context.model;
        var vals=model.toJSON();
        log("vals",vals);
        var condition=[];
        for (var n in vals) {
            var v=vals[n];
            if (!v) continue;
            var f=get_field(this.context.collection.name,n);
            var sf=model.get_field(n);
            if ((f.type=="float") || (f.type=="date") || (f.type=='decimal')) {
                if (v[0]) {
                    var clause=[n,">=",v[0]];
                    condition.push(clause);
                }
                if (v[1]) {
                    var clause=[n,"<=",v[1]];
                    condition.push(clause);
                }
            } else if ((f.type=="many2one") && (sf.type=="many2one")) {
                var clause=[n,"=",v[0]];
                condition.push(clause);
            } else if (f.type=="boolean") {
                if (v=="yes") {
                    condition.push([[n,"=",true]]);
                } else if (v=="no") {
                    condition.push([[n,"=",false]]);
                }
            } else if (f.type=="selection") {
                var clause=[n,"=",v];
                condition.push(clause);
            } else {
                var clause=[n,"ilike",v];
                condition.push(clause);
            }
        }
        log("condition",condition);
        var collection=this.context.collection;
        collection.search_condition=condition;
        collection.get_data();
        if (this.options.navigate) {
            var h=window.location.hash.substr(1);
            var action=qs_to_obj(h);
            action.search_condition=condition;
            var h2=obj_to_qs(action);
            workspace.navigate(h2);
        }
    },

    do_clear: function() {
        log("do_clear",this);
        //var m=this.data.context.model;
        //log("xxx attrs",_.clone(m.attributes));
        //log("model",m);
        //m._computeChanges(); // XXX
        //m.clear();
        var model=this.data.context.model;
        var vals=model.toJSON();
        log("old_vals",_.clone(vals));
        for (var n in vals) {
            vals[n]=null;
        }
        log("clear_vals",vals);
        model.set(vals);
    },

    parse_code: function() {
        log("search parse_code",this,this.view_code);
    },

    show_search: function() {
        log("search.show_search",this);
        this.show_search=true;
        this.render();
    }
});

Search.register();
