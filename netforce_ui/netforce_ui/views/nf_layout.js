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

var NFLayout=NFView.extend({
    _name: "nf_layout",

    render: function() {
        //log("nf_layout.render",this);
        var that=this;
        var mainmenu_view=get_xml_layout({name:"main_menu"});
        var doc=$.parseXML(mainmenu_view.layout);
        this.data.mainmenu_items=[];
        $(doc).find("menu").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="item") {
                var item={
                    string: $el.attr("string"),
                    action: $el.attr("action"),
                    perm: $el.attr("perm"),
                    perm_check_admin: $el.attr("perm_check_admin"),
                    pkg: $el.attr("pkg"),
                    url: $el.attr("url"),
                    color: $el.attr("color"),
                    disabled: $el.attr("disabled")
                };
                var hide=is_hidden({type:"main_menu", name: item.string});
                if(!hide){
                    that.data.mainmenu_items.push(item);
                }
            }
        });
        //log("mainmenu_items",this.data.mainmenu_items);

        var menu_view=get_xml_layout({name:this.options.view_xml});
        var doc=$.parseXML(menu_view.layout);
        var cur_mainmenu=$(doc).find("menu").attr("string");

        this.data.menu_items=[];
        $(doc).find("menu").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            if (tag=="item") {
                var item={
                    string: $el.attr("string"),
                    action: $el.attr("action"),
                    action_options: $el.attr("action_options"),
                    url: $el.attr("url"),
                    color: $el.attr("color"),
                    perm: $el.attr("perm"),
                    perm_check_admin: $el.attr("perm_check_admin"),
                    pkg: $el.attr("pkg"),
                    icon: $el.attr("icon"),
                    submenu_items: []
                };

                function add_submenu(item2){
                    var hide=is_hidden({type:"sub_menu", board_str: cur_mainmenu, name: item2.string});
                    if(!hide){
                        item.submenu_items.push(item2);
                    }
                    return hide;
                }

                var hide_item=false;
                $el.children().each(function() {
                    var $el2=$(this);
                    var tag=$el2.prop("tagName");
                    if (tag=="item") {
                        var item2={
                            type: "item",
                            string: $el2.attr("string"),
                            action: $el2.attr("action"),
                            action_options: $el2.attr("action_options"),
                            url: $el2.attr("url"),
                            color: $el.attr("color"),
                            perm: $el2.attr("perm"),
                            perm_check_admin: $el2.attr("perm_check_admin"),
                            pkg: $el2.attr("pkg")
                        };
                        if (item2.action && !check_menu_permission(item2.action)) {
                            hide_item=true;
                            return;
                        }
                        hide_item=add_submenu(item2);
                    } else if (tag=="divider") {
                        var item2={
                            hide: hide_item,
                            type: "divider"
                        };
                        add_submenu(item2);
                    } else if (tag=="header") {
                        var item2={
                            type: "header",
                            string: $el2.attr("string")
                        };
                        add_submenu(item2);
                    }
                });

                // clear divider if not use
                var sub_items=[];
                _.each(item.submenu_items, function(item){
                    if(!item.hide){
                        sub_items.push(item);
                    }else if(!_.isEmpty(sub_items) && sub_items[sub_items.length-1].type!='divider'){
                        sub_items.push(item);
                    }
                });

                while(true){
                    if(!_.isEmpty(sub_items) && sub_items[sub_items.length-1].type=='divider'){
                        sub_items=sub_items.splice(0,sub_items.length-1);
                    }else if(!_.isEmpty(sub_items) && sub_items[sub_items.length-1].type=='header'){
                        sub_items=sub_items.splice(0,sub_items.length-1);
                    }else{
                        break;
                    }
                }

                item.submenu_items=sub_items;

                if (!item.action && !item.url && item.submenu_items.length==0) return;

                var hide=is_hidden({type:"sub_menu", board_str: cur_mainmenu, name: item.string});
                if(!hide){
                    that.data.menu_items.push(item);
                }

            }
        });
        log("menu_items",this.data.menu_items);
        this.data.title=$(doc).find("menu").attr("string");

        var ctx=get_global_context();
        var cur_lang_code=ctx.locale;
        this.data.active_langs=[];
        _.each(ui_params_db.active_languages,function(l) {
            that.data.active_langs.push({
                name: l.name,
                flag: get_lang_flag(l.code),
                action: "change_lang",
                action_options: "locale="+l.code
            });
            if (l.code==cur_lang_code) {
                that.data.cur_lang_name=l.name;
                that.data.cur_lang_flag=get_lang_flag(l.code);
            }
        });
        var version=nf_get_version();
        this.data.version=version?"v"+version:null;

        if (ui_params_db && ui_params_db.menu_icon) {
            this.data.icon_url="/static/db/"+this.context.dbname+"/files/"+ui_params_db.menu_icon;
        } else {
            this.data.icon_url="/static/img/menu_icon.png";
        }
        NFView.prototype.render.call(this);
    }
});

NFLayout.register();
