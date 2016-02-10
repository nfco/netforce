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

var SearchView=NFView.extend({
    _name: "search_view",
    events: {
        "click .close": "close",
        "click .search-btn": "do_search",
        "click .clear-btn": "do_clear"
    },

    initialize: function(options) {
        ///log("search_view.initialize",this);
        var that=this;
        NFView.prototype.initialize.call(this,options);
        if (!this.options.model) throw "SearchView: missing model";
        if (this.options.view_layout) {
            var layout=this.options.view_layout;
        } else {
            if (this.options.view_xml) {
                var search_view=get_xml_layout({name:this.options.view_xml});
            } else {
                var search_view=get_xml_layout({model:this.options.model,type:"search",noerr:true});
                if (!search_view) {
                    search_view=get_default_search_view(this.options.model);
                }
            }
            var layout=search_view.layout;
        }
        if (_.isString(layout)) {
            var doc=$.parseXML(layout);
            this.$layout=$(doc).children();
        } else {
            this.$layout=layout;
        }
        this.data.render_search_body=function(ctx) { return that.render_search_body.call(that,ctx); };
        this.model=new NFModel({},{name:"_search"});
        this.data.context.model=this.model;
        this.data.context.collection=null;
        var model_cls=get_model(this.options.model);
        this.$layout.find("field").each(function() {
            var $el=$(this);
            var name=$el.attr("name");
            log("conv field: "+name);
            var orig_field=model_cls.fields[name];
            var search_field;
            if (orig_field.type=="char") search_field={type:"char",string:orig_field.string};
            else if (orig_field.type=="selection") search_field={type:"selection",selection:orig_field.selection,string:orig_field.string};
            else if (orig_field.type=="many2one") {
                if ($el.attr("noselect")) {
                    search_field={type:"char",string:orig_field.string};
                } else {
                    search_field={type:"many2one",relation:orig_field.relation,string:orig_field.string};
                }
            } else if (orig_field.type=="text") search_field={type:"char",string:orig_field.string};
            else if (orig_field.type=="reference") search_field={type:"char",string:orig_field.string};
            else if (orig_field.type=="float") search_field={type:"float_range",string:orig_field.string};
            else if (orig_field.type=="decimal") search_field={type:"float_range",string:orig_field.string};
            else if (orig_field.type=="integer") search_field={type:"float_range",string:orig_field.string}; // XXX
            else if (orig_field.type=="date" || orig_field.type=="datetime") search_field={type:"date_range",string:orig_field.string};
            else if (orig_field.type=="boolean") search_field={type:"selection",selection:[["yes","Yes"],["no","No"]],string:orig_field.string};
            else if (orig_field.type=="many2many") {
                search_field={type:"many2one",relation:orig_field.relation,string:orig_field.string};
            }
            else throw "Can't search field: "+name;
            that.model.fields[name]=search_field;
        });
    },

    render: function() {
        ///log("search_view.render",this);
        NFView.prototype.render.call(this);
        return this;
    },

    render_search_body: function(context) {
        //log("render_search_body",this,context);
        var that=this;
        var body=$("<div/>");
        var row=$('<div class="row"/>');
        body.append(row);
        var col=0;
        this.$layout.children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="field") {
                var name=$el.attr("name");
                var cell=$('<div class="col-sm-2"/>');
                if (col+2>11) { // XXX
                    row=$('<div class="row"/>');
                    body.append(row);
                    col=0;
                }
                row.append(cell);
                var opts={
                    name: name,
                    context: context
                };
                var view=Field.make_view(opts);
                cell.append("<div id=\""+view.cid+"\" class=\"view\"></div>");
                col+=2;
            } else if (tag=="newline") {
                row=$('<div class="row"/>');
                body.append(row);
                col=0;
            }
        });
        var cell=$('<div class="span2" style="padding-top:10px"/>');
        if (col+2>11) { // XXX
            row=$('<div class="row"/>');
            body.append(row);
            col=0;
        }
        row.append(cell);
        cell.append('<button class="btn btn-primary search-btn">Search</button> ');
        cell.append('<a class="btn btn-default clear-btn">Clear</a>');
        return body.html();
    },

    close: function() {
        this.trigger("close");
        remove_view_instance(this.cid);
    },

    get_condition: function() {
        log("search_view.get_condition",this);
        var that=this;
        var model_cls=get_model(this.options.model);
        var condition=[];
        this.$layout.find("field").each(function() {
            var $el=$(this);
            var n=$el.attr("name");
            var v=that.model.get(n);
            if (!v) return;
            var f=model_cls.fields[n];
            var sf=that.model.get_field(n);
            if ((f.type=="float") || (f.type=="date") || (f.type=="decimal")) {
                if (v[0]) {
                    var clause=[n,">=",v[0]];
                    condition.push(clause);
                }
                if (v[1]) {
                    var clause=[n,"<=",v[1]];
                    condition.push(clause);
                }
            } else if (f.type=="datetime") {
                if (v[0]) {
                    var clause=[n,">=",v[0]+" 00:00:00"];
                    condition.push(clause);
                }
                if (v[1]) {
                    var clause=[n,"<=",v[1]+" 23:59:59"];
                    condition.push(clause);
                }
            } else if ((f.type=="many2one") && (sf.type=="many2one")) {
                if ($el.attr("child_of")) {
                    var clause=[n,"child_of",v[0]];
                } else {
                    var clause=[n,"=",v[0]];
                }
                condition.push(clause);
            } else if (f.type=="boolean") {
                if (v=="yes") {
                    condition.push([[n,"=",true]]);
                } else if (v=="no") {
                    condition.push([[n,"=",false]]);
                }
            } else if (f.type=="many2many") {
                if ($el.attr("child_of")) {
                    var clause=[n+".id","child_of",v[0]];
                } else {
                    var clause=[n+".id","=",v[0]];
                }
                condition.push(clause);
            } else if (f.type=="selection") {
                var clause=[n,"=",v];
                condition.push(clause);
            } else {
                var clause=[n,"ilike",v];
                condition.push(clause);
            }
        });
        log("=> condition",condition);
        return condition;
    },

    set_condition: function(condition) {
        log("search_view.set_condition",this,condition);
        var that=this;
        var model_cls=get_model(this.options.model);
        for (var i in condition) {
            var clause=condition[i];
            var n=clause[0];
            if (n.indexOf(".id")!=-1) {
                n=n.replace(".id","");
            }
            var f=model_cls.fields[n];
            log("clause",clause,n,f);
            var op=clause[1];
            var v=clause[2];
            if (f.type=="char") {
                if (v) v=v.replace(/%/g,"");
                that.model.set(n,v);
                log(n,"<-",v);
            } else if (f.type=="many2one") {
                if (_.isNumber(v)) {
                    that.model.set(n,v);
                    log(n,"<-",v);
                } else if (_.isString(v)) {
                    v=v.replace(/%/g,"");
                    that.model.set(n,v);
                    log(n,"<-",v);
                }
            } else if ((f.type=="date")||(f.type=="float")) {
                var r=that.model.get(n)||[null,null];
                if (op==">=") r[0]=v;
                else if (op=="<=") r[1]=v;
                that.model.set(n,r);
                log(n,"<-",r);
            } else if (f.type=="datetime") {
                var r=that.model.get(n)||[null,null];
                if (op==">=") r[0]=v.substr(0,10);
                else if (op=="<=") r[1]=v.substr(0,10);
                that.model.set(n,r);
                log(n,"<-",r);
            } else if (f.type=="many2many") {
                if (_.isNumber(v)) {
                    that.model.set(n,v);
                    log(n,"<-",v);
                }
            } else if (f.type=="selection") {
                that.model.set(n,v);
                log(n,"<-",v);
            }
        }
    },

    do_search: function(e) {
        log("search_view.do_search",this);
        e.preventDefault();
        e.stopPropagation();
        this.trigger("search");
    },

    do_clear: function(e) {
        log("search_view.do_clear",this);
        e.preventDefault();
        e.stopPropagation();
        this.model.clear();
        this.render();
    }
});

SearchView.register();
