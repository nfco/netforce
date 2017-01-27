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

var Board=NFView.extend({
    _name: "board",

    render: function() {
        //log("board.render",this);
        var that=this;
        var view_name=this.options.view_xml;

        var action=get_action(view_name);
        var menu_view=get_xml_layout({name:action.menu});
        var doc_view=$.parseXML(menu_view.layout);
        var cur_mainmenu=$(doc_view).find("menu").attr("string");

        var board_view=get_xml_layout({name:view_name});
        var doc=$.parseXML(board_view.layout);
        this.data.title=this.options.string||$(doc).find(":root").attr("title")||this.context.company_name;
        window.xxx=$(doc);
        this.data.vpanels=[];
        $el=$(doc).find("alert");
        if ($el.length>0) {
            this.data.alert_action=$el.attr("action");
        }
        $(doc).find("vpanel").each(function() {
            var $el=$(this);
            var vpanel={
                widgets: []
            };
            $el.find("widget").each(function() {
                var $el2=$(this);
                var action=$el2.attr("action");
                if (!check_menu_permission(action)) return;
                var widget={
                    string: $el2.attr("string"),
                    action: action
                };

                var hide=is_hidden({type:"dashboard", board_str: cur_mainmenu, name: widget.string});
                if(!hide){
                    vpanel.widgets.push(widget);
                }

            });
            if (vpanel.widgets.length>0) {
                that.data.vpanels.push(vpanel);
            }
        });
        //log("vpanels",this.data.vpanels);
        this.data.hpanels=[];
        $(doc).find("hpanel").each(function() {
            var $el=$(this);
            var hpanel={
                widgets: []
            };
            $el.find("widget").each(function() {
                var $el2=$(this);
                var action=$el2.attr("action");
                if (!check_menu_permission(action)) return;
                var widget={
                    string: $el2.attr("string"),
                    span: $el2.attr("span")||6,
                    action: action
                };

                var hide=is_hidden({type:"dashboard", board_str: cur_mainmenu, name: widget.string});
                if(!hide){
                    hpanel.widgets.push(widget);
                }

            });
            if (hpanel.widgets.length>0) {
                that.data.hpanels.push(hpanel);
            }
        });
        NFView.prototype.render.call(this);
    }
});

Board.register();
