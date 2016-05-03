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

NF_TIMEOUT=1; // seconds

window.log=function() {
    if (this.console) {
        console.log(Array.prototype.slice.call(arguments));
    }
};

function clean_context(ctx) { // XXX: make this not needed
    //log("CLEAN_CONTEXT",ctx);
    var c=_.clone(ctx);
    for (var k in c) {
        if (k[0]=="_" || k=="context" || k=="model" || k=="collection" || k=="form" || k=="meta" || k=="target") delete c[k];
    }
    var s=JSON.stringify(c); // XXX
    s=s.replace(/[\u0100-\uFFFF]/g,''); // remove unicode
    c=JSON.parse(s);
    //log("clean ->",c);
    return c;
}

function eval_json(str,ctx) {
    //log("eval_json",str,ctx);
    try {
        if (!_.isString(str)) return str;
        var v=new Function("with (this) { return "+str+"; }").call(ctx); // XXX
    } catch (err) {
        log("json",str,ctx);
        throw "Failed to evaluate JSON expression: "+err.message;
    }
    //log("=> ",v);
    return v;
}

function eval_condition(cond_str,ctx) { // XXX: remove later
    return eval_json(cond_str,ctx);
}

function rpc_execute(model,method,args,opts,cb) {
    log("RPC",model,method,args,opts);
    var params=[model,method];
    params.push(args);
    if (opts) {
        params.push(opts);
    }
    $.ajax({
        url: "/json_rpc",
        type: "POST",
        data: JSON.stringify({
            id: (new Date()).getTime(),
            method: "execute",
            params: params
        }),
        dataType: "json",
        contentType: "application/x-www-form-urlencoded; charset=UTF-8",
        success: function(data) {
            if (data.error) {
                log("RPC ERROR",model,method,data.error.message);
            } else {
                log("RPC OK",model,method,data.result);
            }
            if (cb) {
                cb(data.error,data.result);
            }
        },
        error: function() {
            log("RPC ERROR",model,method);
        }
    });
}

function nf_execute(model,method,args,opts,cb) {
    var m=get_model(model);
    if (m.offline) {
        nf_execute_local(model,method,args,opts,cb);
    } else {
        rpc_execute(model,method,args,opts,cb);
    }
}

function do_popup(action,context) {
    log("do_popup",action,context);
    var url="/action?name="+action;
    if (context) {
        url+="&"+$.param(context);
    }
    $.get(url,function(data) {
        $(data).appendTo("body").modal({show:true});
        $(document).trigger("nf_init");
    });
}

function do_window(action,context) {
    log("do_window",action,context);
    var url="/action?name="+action;
    if (context) {
        url+="&"+$.param(context);
    }
    window.location.href=url;
}

function cancel_modal() {
    log("cancel_modal");
    //$(".modal").modal("hide");
    $(".modal").remove(); // XXX
    $(".modal-backdrop").remove(); // XXX
}

function search_panel() {
    $(".search-panel-btn").hide();
    $(".search-panel").show();
    $(".search-panel").bind("close",function() {
        $(".search-panel-btn").show();
    });
}

function do_window(action,context) {
    log("do_window",action,context);
    var url="/action?name="+action;
    if (context) {
        url+="&"+$.param(context);
    }
    window.location.href=url;
}

function submit_modal(params) {
    //log("submit_modal");
    var data=$(".modal form").serialize();
    if (!params) params={};
    params.ajax=1;
    data+="&"+$.param(params);
    $.ajax({
        type: "POST",
        url: "/action",
        data: data,
        success: function(data,textStatus,xhr) {
            $(".modal").modal("hide");
            var action=JSON.parse(data);
            exec_action(action);
        },
        error: function() {
            alert("Error: ajax");
        }
    });
}

function submit_form(el,params,options) {
    //alert("submit_form: "+params);
    log("submit_form",el,params,options);
    if (!options) options={};
    form=$(el).parents("form")[0];
    if (!form) throw "form not found";
    log("form",form);
    for (var k in params) {
        var v=params[k];
        var inp=$("<input/>").attr("type","hidden").attr("name",k).val(v);
        $(form).append(inp);
    }
    if (params.ajax) {
        var data=$(form).serialize();
        log("data",data);
        var method=$(form).attr("method");
        var action=$(form).attr("action");
        $.ajax({
            type: method,
            url: action,
            data: data,
            success: function(data) {
                if (data.length===0) {
                    window.location.reload();
                } else if (data[0]=="<") {
                    if (options.target) {
                        $(options.target).html(data);
                    } else {
                        var body=data.match(/<body>([\s\S]*)<\/body>/)[1];
                        $("body").html(body);
                        $(document).trigger("nf_init");
                    }
                } else {
                    var action=JSON.parse(data);
                    action.target=options.target;
                    exec_action(action);
                }
            },
            error: function(jqXHR,textStatus,errorThrown) {
                log("error",textStatus,errorThrown);
                alert("Form submit failed: "+textStatus+" ("+errorThrown+")");
            }
        });
    } else {
        $(form).submit();
    }
}

function html_decode(s) {
    return $("<div/>").html(s).text();
}

function do_onclick(e) {
    log("do_onclick",e,this);
    e.preventDefault();
    var onclick=html_decode($(this).data("onclick"));
    eval("var f=function(){"+onclick+"}");
    f.call(e.currentTarget);
}

function bind_onclick() {
    $("body").on("click","[data-onclick]",do_onclick);
}

function format_money(n, c, d, t) {
    var c = isNaN(c = Math.abs(c)) ? 2 : c, d = d == undefined ? "." : d, t = t == undefined ? "," : t, s = n < 0 ? "-" : "", i = parseInt(n = Math.abs(+n || 0).toFixed(c)) + "", j = (j = i.length) > 3 ? j % 3 : 0;
    var res=s + (j ? i.substr(0, j) + t : "") + i.substr(j).replace(/(\d{3})(?=\d)/g, "$1" + t) + (c ? d + Math.abs(n - i).toFixed(c).slice(2) : "");
    return remove_extra_zeros(res,2);
}

function remove_extra_zeros(s,min_digits) {
    var i=s.indexOf(".");
    if (i==-1) return s;
    var last=i+min_digits;
    i=last+1;
    while (i<s.length) {
        if (s[i]!="0") last=i;
        i++;
    }
    return s.slice(0,last+1);
}

Handlebars.registerHelper("currency",function(v,options) {
    var scale;
    if (options.hash && options.hash.scale!=null) {
        scale=options.hash.scale;
    } else {
        scale=2;
    }
    /*if (typeof(v)!="number") return "";*/
    if (isNaN(v)) return v; // XXX
    if (v>-0.00001 && v<0.00001) v=0; // XXX
    if (v==0 && options.hash && options.hash.zero!=null) return options.hash.zero;
    if (v<0) {
        var s="("+format_money(-v,scale)+")";
    } else {
        var s=format_money(v,scale);
    }
    return s;
});

Handlebars.registerHelper("currency_abs",function(v,options) {
    var scale;
    if (options.hash && options.hash.scale!=null) {
        scale=options.hash.scale;
    } else {
        scale=2;
    }
    if (typeof(v)!="number") return "";
    if (v>-0.00001 && v<0.00001) v=0; // XXX
    if (v==0 && options.hash && options.hash.zero!=null) return options.hash.zero;
    if (v<0) {
        var s=format_money(-v,scale);
    } else {
        var s=format_money(v,scale);
    }
    return s;
});

Handlebars.registerHelper("fmt_date",function(v,options) {
    return format_date(v,options);
});

Handlebars.registerHelper("time_ago",function(v) {
    var d=new Date(v);
    var m=moment(d);
    return m.fromNow();
});

Handlebars.registerHelper("length",function(v) {
    if (_.isArray(v)) {
        return v.length;
    }
    return "";
});

Handlebars.registerHelper("view",function(name,options) { // XXX
    var view_cls=get_view_cls(name);
    var ctx=options.hash.context;
    var opts;
    if (options.hash.options) { // XXX
        opts=_.clone(options.hash.options);
        var new_ctx=opts.context;
        opts.context=_.clone(ctx);
        if (new_ctx) {
            _.extend(opts.context,new_ctx);
        }
    } else if (ctx && ctx._view_opts) { // XXX
        opts=ctx._view_opts;
        delete ctx._view_opts;
    } else { // XXX
        opts=_.clone(options.hash);
        opts.context=_.clone(ctx);
    }
    opts.inner=options.fn;
    opts.inverse=options.inverse;
    var view=view_cls.make_view(opts);
    var tag=view.tagName;
    return new Handlebars.SafeString('<'+tag+' id="'+view.cid+'" class="view"></'+tag+'>');
});

Handlebars.registerHelper("action",function(options) { // XXX
    var name=options.hash.name;
    var ctx=options.hash.context;
    if (!name) throw "Missing action name";
    if (!check_menu_permission(name)) return "";
    var action=get_action(name);
    action.context=ctx;
    var view_cls_name=action.view_cls||"action";
    var view_cls=get_view_cls(view_cls_name);
    var view=view_cls.make_view(action);
    var tag=view.tagName;
    return new Handlebars.SafeString('<'+tag+' id="'+view.cid+'" class="view"></'+tag+'>');
});

Handlebars.registerHelper("ifeq",function(val1,val2,options) {
    if (val1==val2) {
        return options.fn(this);
    } else {
        return options.inverse(this);
    }
});

Handlebars.registerHelper("ifneq",function(val1,val2,options) {
    if (val1!=val2) {
        return options.fn(this);
    } else {
        return options.inverse(this);
    }
});

Handlebars.registerHelper("ifin",function(val) {
    var vals=Array.prototype.slice.call(arguments,1,arguments.length-1);
    var options=arguments[arguments.length-1];
    var found=_.any(vals,function(x) {
        return x==val;
    });
    if (found) {
        return options.fn(this);
    } else {
        return options.inverse(this);
    }
});

Handlebars.registerHelper("ifcontains",function(list,val,options) {
    if (_.contains(list,val)) {
        return options.fn(this);
    } else {
        return options.inverse(this);
    }
});

function translate(v) {
    if (!v) return v;
    if (!ui_params_db) return v;
    var ctx=get_global_context();
    var cur_lang=ctx.locale||"en_US";
    var translations=ui_params_db.translations[cur_lang];
    if (!translations) return v;
    var trans=translations[v];
    if (!trans) {
        if (cur_lang=="en_US") {
            return new Handlebars.SafeString(v); // XXX
        } else {
            return new Handlebars.SafeString("?"+v);
        }
    }
    return new Handlebars.SafeString(trans); // XXX
}

Handlebars.registerHelper("t",function(v) {
    return translate(v);
});

Handlebars.registerHelper("include",function(name,options) {
    var tmpl=get_template(name);
    var ctx=options.hash.context;
    var html=tmpl({context:ctx});
    return new Handlebars.SafeString(html);
});

Handlebars.registerHelper("json",function(v) {
    var s=JSON.stringify(v);
    return new Handlebars.SafeString(s);
});

Handlebars.registerHelper("set",function(obj,attr,val) {
    obj[attr]=val;
});

Handlebars.registerHelper("loop",function(options) {
    var ctx=options.hash.context;
    var collection=ctx.collection;
    if (collection && collection.length>0) {
        var content="";
        collection.each(function(model) {
            var ctx2=_.clone(ctx);
            ctx2.model=model;
            ctx2.data=model.toJSON();
            var html=options.fn({context:ctx2});
            content+=html;
        });
    } else {
        content=options.inverse(ctx);
    }
    return content;
});

Handlebars.registerHelper("field_label",function(name,options) {
    var ctx=options.hash.context;
    if (ctx.model) {
        model_name=ctx.model.name;
    } else if (ctx.collection) {
        model_name=ctx.collection.name;
    }
    var field=get_field(model_name,name);
    return translate(field.string);
});

function format_date(val,options) {
    if (!val) return null;
    if (ui_params_db && ui_params_db.use_buddhist_date) {
        var year=parseInt(val.substr(0,4));
        var year2=year+543;
        val=""+year2+val.substr(4);
    }
    if (options && options.hash && options.hash.fmt) {
        var fmt=options.hash.fmt;
    } else {
        if (ui_params_db && ui_params_db.date_format) {
            var fmt=ui_params_db.date_format;
        } else {
            var fmt="YYYY-MM-DD";
        }
    }
    var val2=moment(val,"YYYY-MM-DD").format(fmt);
    return val2;
}

function parse_date(val) {
    if (!val) return null;
    if (ui_params_db.date_format) {
        var fmt=ui_params_db.date_format;
    } else {
        var fmt="YYYY-MM-DD";
    }
    var val2=moment(val,fmt).format("YYYY-MM-DD");
    if (ui_params_db && ui_params_db.use_buddhist_date) {
        var year=parseInt(val2.substr(0,4));
        var year2=year-543;
        val2=""+year2+val2.substr(4);
    }
    return val2;
}

function format_datetime(val) {
    if (!val) return null;
    if (ui_params_db && ui_params_db.use_buddhist_date) {
        var year=parseInt(val.substr(0,4));
        var year2=year+543;
        val=""+year2+val.substr(4);
    }
    if (ui_params_db && ui_params_db.date_format) {
        var fmt=ui_params_db.date_format+" HH:mm:ss";
    } else {
        var fmt="YYYY-MM-DD HH:mm:ss";
    }
    var val2=moment(val,"YYYY-MM-DD HH:mm:ss").format(fmt);
    return val2;
}

function parse_datetime(val) {
    if (!val) return null;
    if (ui_params_db.date_format) {
        var fmt=ui_params_db.date_format+" HH:mm:ss";
    } else {
        var fmt="YYYY-MM-DD HH:mm:ss";
    }
    var val2=moment(val,fmt).format("YYYY-MM-DD HH:mm:ss");
    if (ui_params_db && ui_params_db.use_buddhist_date) {
        var year=parseInt(val2.substr(0,4));
        var year2=year-543;
        val2=""+year2+val2.substr(4);
    }
    return val2;
}

function escapeHTML( string ) {
    var pre = document.createElement('pre');
    var text = document.createTextNode( string );
    pre.appendChild(text);
    return pre.innerHTML;
}

function field_value(name,context,link,target,m2o_link,click_action,show_image,scale) { // XXX: link/target as options
    var model=context.model;
    if (!model) throw "Model not found, can't get value of field '"+name+"'";
    var field=model.get_field(name);
    var type=field.type;
    var val=model.get(name);
    if (val!=null) {
        if (type=="float" || type=="decimal") {
            if (val) {
                if (val>=-0.00001) {
                    val=format_money(val,scale!=null?scale:field.scale);
                } else {
                    val="("+format_money(-val,scale!=null?scale:field.scale)+")";
                }
            }
        } else if (type=="date") {
            val=format_date(val);
        } else if (type=="datetime") {
            val=format_datetime(val);
        } else if (type=="many2one") {
            if (link) {
                var link_url="#name="+link+"&mode=form&active_id="+val[0];
                val='<a href="'+link_url+'">'+val[1]+'</a>';
            } else if (m2o_link) {
                var id=val[0];
                if (show_image) {
                    val=""+(val[1]||"")+'<div><img src="/static/db/'+context.dbname+'/files/'+val[2]+'" style="max-width:100px;max-height:80px"/></div>';
                } else {
                    val=""+val[1];
                }
                var action;
                if (click_action) {
                    action={
                        name: click_action,
                        active_id: id
                    };
                } else {
                    action=find_details_action(field.relation,id);
                    log("######################",field.relation,action);
                }
                if (action) {
                    var link_url="#"+obj_to_qs(action);
                    val+=" <a href='"+link_url+"' style='text-decoration:none;margin-left:5px' tabindex='-1' target='_blank'><i class='icon-arrow-right'></i></a>"
                }
            } else {
                val=val[1];
            }
        } else if (type=="reference") {
            if (m2o_link) {
                var res=val[0].split(",");
                var relation=res[0];
                var id=parseInt(res[1]);
                val=""+val[1];
                var action=find_details_action(relation,id);
                if (action) {
                    var link_url="#"+obj_to_qs(action);
                    val+=" <a href='"+link_url+"' style='text-decoration:none;margin-left:5px' tabindex='-1' target='_blank'><i class='icon-arrow-right'></i></a>"
                }
            } else {
                val=val[1];
            }
        } else if (type=="selection") {
            for (var i in field.selection) {
                var v=field.selection[i];
                if (v[0]==val) {
                    val=v[1];
                    break;
                }
            }
        } else if (type=="boolean") {
            val=val?"Yes":"No";
        } else if (type=="file") {
            var re=/^(.*),(.*?)(\..*)?$/;
            var m=re.exec(val);
            if (m) {
                var base=m[1];
                var ext=m[3];
                var filename=base;
                if (ext) filename+=ext;
            } else {
                var filename=val;
            }
            if (context.no_link) {
                val=filename;
            } else {
                if (context.preview && filename.match(/\.png$|\.jpg$|\.jpeg$|\.gif$/i)) {
                    val='<a href="/static/db/'+context.dbname+'/files/'+val+'"><img class="thumbnail thumbnail-small" src="/static/db/'+context.dbname+'/files/'+encodeURIComponent(val)+'" style="max-width:100px;max-height:100px"/></a>';
                } else {
                    val='<a href="/static/db/'+context.dbname+'/files/'+encodeURIComponent(val)+'" target="'+(target||"")+'">'+filename+"</a>";
                }
            }
        } else if (type=="text") {
            val=escapeHTML(val); // XXX
            return '<div style="white-space:pre-wrap">'+val+'</div>';
        }
    }
    return val;
}

function render_field_value(val,field) {
    var s;
    if (field.type=="float") {
        if (val!=null) {
            s=format_money(val,field.scale);
        } else {
            s="";
        }
    } else if (field.type=="many2one") {
        if (val) {
            s=val[1];
        } else {
            s="";
        }
    } else if (field.type=="selection") {
        if (val) {
            s="";
            _.each(field.selection,function(o) {
                if (o[0]==val) {
                    s=o[1];
                }
            });
        } else {
            s="";
        }
    } else {
        s=""+val;
    }
    return s;
}

Handlebars.registerHelper("field_value",function(name,options) {
    var ctx=options.hash.context;
    var link=options.hash.link;
    var target=options.hash.target;
    var m2o_link=options.hash.m2o_link;
    var click_action=options.hash.click_action;
    var show_image=options.hash.show_image;
    var scale=options.hash.scale;
    if (options.hash.preview) {
        ctx.preview=options.hash.preview; // XXX
    }
    var val=field_value(name,ctx,link,target,m2o_link,click_action,show_image,scale); // XXX
    if (!val) return val;
    return new Handlebars.SafeString(val);
});

Handlebars.registerHelper('each', function(context, options) {
  var fn = options.fn, inverse = options.inverse;
  var ret = "";

  if(context && context.length > 0) {
    for(var i=0, j=context.length; i<j; i++) {
      var ctx=_.clone(context[i]);
      ctx.context=options.hash.context;
      ret = ret + fn(ctx);
    }
  } else {
    ret = inverse(this);
  }
  return ret;
});

Handlebars.registerHelper('render', function(fn, options) {
    return fn(this);
});

function get_lang_flag(code) {
    switch (code) {
        case 'km_KH': return "flag_kh_16.png";
        case 'zh_CN': return "flag_cn_16.png";
        case 'nl_NL': return "flag_nl_16.png";
        case 'en_US': return "flag_uk_16.png";
        case 'fr_FR': return "flag_fr_16.png";
        case 'hi_IN': return "flag_in_16.png";
        case 'id_ID': return "flag_id_16.png";
        case 'ja_JP': return "flag_jp_16.png";
        case 'ko_KR': return "flag_kr_16.png";
        case 'my_MM': return "flag_mm_16.png";
        case 'ne_NP': return "flag_np_16.png";
        case 'pl_PL': return "flag_pl_16.png";
        case 'sk_SK': return "flag_sk_16.png";
        case 'th_TH': return "flag_th_16.png";
        case 'vi_VN': return "flag_vn_16.png";
        default: return "";
    }
}

Handlebars.registerHelper('each_group', function(list_val, group_field, options) {
    var fn=options.fn;
    var inverse=options.inverse;
    var context=options.hash.context;
    var sum=options.hash.sum;
    var sum_fields=[];
    if (sum) {
        sum_fields=sum.split(",");
    }
    var ret="";
    var groups={};
    var group_list=[]
    for (var i=0; i<list_val.length; i++) {
        var vals=list_val[i];
        var v=vals[group_field];
        var group=groups[v];
        if (!group) {
            group={};
            group[group_field]=v;
            group.group_items=[];
            group.context=context;
            group.sum={};
            for (var j=0; j<sum_fields.length; j++) {
                var f=sum_fields[j];
                group.sum[f]=0;
            }
            groups[v]=group;
            group_list.push(v);
        }
        group.group_items.push(vals);
        for (var j=0; j<sum_fields.length; j++) {
            var f=sum_fields[j];
            var v=vals[f];
            if (v) group.sum[f]+=v;
        }
    }
    if (group_list.length>0) {
        for (var i=0; i<group_list.length; i++) {
            var v=group_list[i];
            var group=groups[v];
            ret+=fn(group);
        }
    } else {
        ret=inverse(this);
    }
    return ret;
});

Handlebars.registerHelper("call",function(func) {
    var args=Array.prototype.slice.call(arguments,1);
    var html=func.apply(this,args);
    return new Handlebars.SafeString(html);
});

Handlebars.registerHelper("new_ctx",function(options) {
    var ctx=_.clone(options.hash.context||{});
    var html=options.fn({context:ctx});
    return html;
});

Handlebars.registerHelper("if_perm",function(perm,options) { // TODO!!!
    var ctx=get_global_context();
    var user_id=ctx.user_id;
    var has_perm=!perm||user_id==1;
    if (perm && perm[0]=="!") has_perm=!has_perm; // XXX
    if (has_perm) {
        return options.fn(this);
    } else {
        return options.inverse(this);
    }
});

Handlebars.registerHelper("unless_perm",function(perm,options) { // TODO!!!
    var ctx=get_global_context();
    var user_id=ctx.user_id;
    if (perm && user_id!=1) {
        return options.fn(this);
    } else {
        return options.inverse(this);
    }
});

Handlebars.registerHelper("ifgt",function(val1,val2,options) {
    if (val1>val2) {
        return options.fn(this);
    } else {
        return options.inverse(this);
    }
});



$(document).ready(function() {
    if (window.ready_done) return; // prevent multiple call of ready (in case body reload that contains script)
    bind_onclick();
    $(document).trigger("nf_init");
    window.ready_done=true;
});

function set_cookie(name,value,days) {
    log("set_cookie",name,value,days);
    if (days) {
        var date = new Date();
        date.setTime(date.getTime()+(days*24*60*60*1000));
        var expires = "; expires="+date.toGMTString();
    }
    else var expires = "";
    var cookie=name+"="+encodeURIComponent(value)+expires+"; path=/";
    log("cookie",cookie);
    document.cookie = cookie;
}

function get_cookies() {
    var data={};
    var ca = document.cookie.split(';');
    for(var i=0;i < ca.length;i++) {
        var c = ca[i];
        while (c.charAt(0)==' ') c = c.substring(1,c.length);
        var ind=c.indexOf("=");
        var name=c.substring(0,ind);
        var val=c.substring(ind+1,c.length);
        data[name]=decodeURIComponent(val);
    }
    return data;
}

function clear_cookie(name) {
    set_cookie(name,"",-1);
}

function set_cookies(data) {
    log("set_cookies",data);
    for (var n in data) {
        var v=data[n];
        if (v) {
            var val;
            var days;
            if (_.isArray(v)) {
                val=v[0];
                days=v[1];
            } else {
                val=v;
                days=null;
            }
            set_cookie(n,val,days);
        } else {
            clear_cookie(n);
        }
    }
}

window.nf_global_context={};

function get_global_context() {
    var ctx=_.extend({},nf_global_context,get_cookies());
    return ctx;
}

function set_global_context(k,v) {
    nf_global_context[k]=v;
}

function clear_global_context() {
    window.nf_global_context={};
}

var nf_root=null;

function set_root(root) {
    nf_root=root;
}

var nf_referer;

function check_action(action,context) {
    if (!context) context={};
    if (action.name=="login" || action.name=="manage_db" || action.name=="create_db" || action.name=="copy_db" || action.name=="upgrade_db" || action.name=="delete_db") return true; // XXX
    if (!context.user_id) {
        exec_action({name:"login"});
        return false;
    }
    return true;
}

function download_url(url) {
    log("download_url",url);
    window.location.href=url;
    //window.open(url,"_blank"); // xxx
    //$("<iframe></iframe>").css({display:"none"}).attr({src:url}).appendTo("body");
}

function exec_action(action) {
    log("exec_action2",action);
    async.parallel([load_ui_params,load_ui_params_db,load_ui_params_user],function(err) {
        exec_action_ready(action);
    });
}

var ui_params=null;
var ui_params_db=null;

var nf_ui_params_file="ui_params.json";
var nf_ui_params_db_file="ui_params_db.json";

function load_ui_params(cb) {
    log("load_ui_params");
    if (ui_params) {
        cb();
        return;
    }
    $.ajax({
        url: "/static/"+nf_ui_params_file,
        type: "GET",
        //beforeSend: function(xhr){xhr.setRequestHeader('Cache-Control', 'max-age=1');},
        dataType: "json",
        success: function(data) {
            ui_params=data;
            log("Base UI params loaded");
            set_models(); 
            set_layouts();
            set_actions();
            set_templates();
            cb();
        },
        error: function() {
            log("Failed to get base UI params");
        }
    });
}

nf_models=null;

function set_models() {
    if (ui_params) {
        nf_models=_.clone(ui_params.models);
    } else {
        nf_models={};
    }
    if (ui_params_db) {
        _.each(ui_params_db.models,function(m2,model) {
            if (ui_params) {
                var m1=ui_params.models[model];
            } else {
                var m1=null;
            }
            if (!m1) {
                nf_models[model]=m2;
                return;
            }
            if (m2.string) {
                m1.string=m2.string;
            }
            _.extend(m1.fields,m2.fields);
        });
    }
}

nf_layouts=null;

function set_layouts() {
    if (ui_params) {
        nf_layouts=_.clone(ui_params.layouts);
    } else {
        nf_layouts={};
    }
    if (ui_params_db) {
        _.extend(nf_layouts,ui_params_db.layouts)
    }
}

nf_actions=null;

function set_actions() {
    if (ui_params) {
        nf_actions=_.clone(ui_params.actions);
    } else {
        nf_actions={};
    }
    if (ui_params_db) {
        _.extend(nf_actions,ui_params_db.actions)
    }
}

nf_templates=null;

function set_templates() {
    if (ui_params) {
        nf_templates=_.clone(ui_params.templates);
    } else {
        nf_templates={};
    }
    if (ui_params_db) {
        _.extend(nf_templates,ui_params_db.templates)
    }
}

function load_ui_params_db(cb) {
    log("load_ui_params_db");
    if (ui_params_db) {
        cb();
        return;
    }
    var ctx=get_global_context();
    if (!ctx.dbname) {
        ui_params_db=null;
        cb();
        return;
    }
    $.ajax({
        url: "/static/db/"+ctx.dbname+"/"+nf_ui_params_db_file,
        type: "GET",
        dataType: "json",
        success: function(data) {
            ui_params_db=data;
            log("Database UI params loaded");
            set_models(); 
            set_layouts();
            set_actions();
            set_templates();
            nf_open_db();
            cb();
        },
        error: function() {
            log("Failed to get database UI params");
        }
    });
}

function close_modals() {
    $(".modal").modal("hide");
    $(".nf-modal-container").remove();
}

function exec_action_ready(action) {
    log("exec_action_ready",action);
    close_modals();
    var global_ctx=get_global_context();
    log("global_ctx",global_ctx)
    if (!check_action(action,global_ctx)) {
        log("Action not allowed: "+action.name);
        return;
    }
    if (action.name) {
        if (!check_menu_permission(action.name)) {
            log("Permission denied, can not execute action: "+action.name);
            return;
        }
        var action_opts=_.clone(get_action(action.name));
        _.extend(action_opts,action);
        action_opts.name=action.name;
    } else {
        var action_opts=_.clone(action);
    }
    if (action_opts.confirm) {
        var res=confirm(action_opts.confirm);
        if (!res) return;
    }
    if (action_opts.context) {
        if (_.isString(action_opts.context)) {
            var ctx=_.extend({},global_ctx,action);
            action_opts.context=eval_json(action_opts.context,ctx);
        }
        action_opts.context=_.extend({},global_ctx,action_opts.context);
    } else {
        action_opts.context=_.clone(global_ctx);
    }
    if (action_opts.options) {
        if (_.isString(action_opts.options)) {
            var ctx=_.extend({},global_ctx,action);
            action_opts.options=eval_json(action_opts.options,ctx);
        }
        _.extend(action_opts,action_opts.options);
    }
    log("=> action_opts",action_opts);
    if (action_opts.type=="reload") {
        window.location.reload();
        return;
    } else if (action_opts.type=="export") { // XXX
        var url="/export?name="+action.name;
        var opts={};
        for (var k in action) { // XXX
            if (k!="name") opts[k]=action[k];
        }
        if (!_.isEmpty(opts)) {
            var qs=obj_to_qs(opts);
            url+="&"+qs;
        }
        download_url(url);
        return;
    } else if (action_opts.type=="report" || action_opts.type=="report_jasper" || action_opts.type=="report_xls" || action_opts.type=="report_doc" || action_opts.type=="report_txt" || action_opts.type=="report_odt" || action_opts.type=="report_ods" || action_opts.type=="report_odt2" || action_opts.type=="report_file") { // XXX
        var url="/report";
        var opts={};
        for (var k in action) { // XXX
            opts[k]=action[k];
        }
        if (!_.isEmpty(opts)) {
            var qs=obj_to_qs(opts);
            url+="?"+qs;
        }
        download_url(url);
        return;
    } else if (action_opts.type=="download") {
        var url=action_opts.url;
        download_url(url);
        return;
    } else if (action_opts.type=="download_file") {
        var filename=action_opts.filename;
        var url="http://"+window.location.host+"/static/db/"+global_ctx.dbname+"/files/"+filename;
        download_url(url);
        return;
    } else if (action_opts.type=="method") {
        var model=action_opts.model;
        var method=action_opts.method;
        var active_id=action_opts.active_id;
        if (_.isString(active_id)) {
            active_id=parseInt(active_id);
        }
        var args=[];
        if (active_id) args.push([active_id]);
        var opts={};
        opts.context={action:action_opts};
        if (action_opts.context) {
            _.extend(opts.context,action_opts.context);
        }
        rpc_execute(model,method,args,opts,function(err,data) {
            if (err) {
                throw "Error: "+err;
            }
            if (data && data.cookies) {
                set_cookies(data.cookies);
            }
            if (data && data.flash) {
                if (_.isString(data.flash)) {
                    set_flash("success",data.flash);
                } else if (_.isObject(data.flash)) {
                    set_flash(data.flash.type,data.flash.message);
                }
            }
            var next=data.next;
            if (next) {
                if (_.isString(next)) {
                    var action={name:next};
                } else {
                    var action=next;
                }
                exec_action(action);
            }
        });
        return;
    } else if (action_opts.type=="post") {
        var url=action_opts.url;
        var data=action_opts.data;
        var form=$("<form>").attr({method:"post",action:url}).appendTo("body");
        for (var k in data) {
            var v=data[k];
            $("<input>").attr({type:"hidden",name:k,value:v}).appendTo(form);
        }
        form.submit();
        return;
    } else if (action_opts.type=="url") {
        var url=action_opts.url;
        var m=url.match(/\/ui#(.*)/);
        if (m) { // force reload even if only hash changes...
            workspace.navigate(m[1]); // XXX
            window.top.location.reload();
        } else {
            window.top.location=url;
        }
        return;
    } else if (action_opts.type=="email") {
        var url="mailto:"+action_opts.to;
        params={}
        if (action_opts.subject) {
            params.subject=action_opts.subject;
        }
        if (action_opts.bcc) {
            params.bcc=action_opts.bcc;
        }
        if (!_.isEmpty(params)) {
            url+="?"+obj_to_qs(params);
        }
        window.open(url);
        return;
    }
    if (!action_opts.target) {
        var qs=obj_to_qs(action);
        log("navigate",qs);
        workspace.navigate(qs);
        clear_view_instances();
        if (window.reload_timeout) {
            clearTimeout(window.reload_timeout);
        }
        if (action_opts.reload) {
            var reload=parseInt(action_opts.reload);
            log("reload in "+reload+" seconds...");
            window.reload_timeout=setTimeout(function() {
                window.location.reload(); // XXX
                //exec_action(action); // check why this doesn't work normally
            },reload*1000);
        }
    }
    var view_cls_name=action_opts.view_cls||action_opts.view; // XXX: 'view_cls' will be deprecated and renamed to 'view'
    if (!view_cls_name) throw "Missing view class in action: "+action_opts.name;
    var view_cls=get_view_cls(view_cls_name);
    var view=view_cls.make_view(action_opts);
    var menu=action_opts.menu;
    if (menu) {
        var view_cls=get_view_cls("nf_layout");
        var opts={
            view_xml: menu,
            show_feedback: action_opts.view_cls=="board",
            context: global_ctx
        };
        var menu_view=new view_cls({options:opts});
        var tag=view.tagName;
        menu_view.data.context.content='<'+tag+' id="'+view.cid+'" class="view"></'+tag+'>';
        view=menu_view;
    } else if (action_opts.layout) { // XXX: deprecated
        var layout_action_name=action_opts.layout;
        while (layout_action_name) {
            var layout_action=get_action(layout_action_name);
            var view_cls_name=layout_action.view_cls||layout_action.view; // XXX: 'view_cls' will be deprecated and renamed to 'view'
            if (!view_cls_name) throw "Missing view class in action: "+layout_action.name;
            var view_cls=get_view_cls(view_cls_name);
            layout_action.context=global_ctx;
            var layout_view=new view_cls({options:layout_action});
            var tag=view.tagName;
            layout_view.data.context.content='<'+tag+' id="'+view.cid+'" class="view"></'+tag+'>';
            view=layout_view;
            layout_action_name=layout_action.layout;
        }
    }
    view.render();
    if (action_opts.target=="_popup") {
        var modal_cont=$("<div/>").addClass("nf-modal-container");
        view.$el.addClass("modal");
        modal_cont.append(view.$el);
        $("body").append(modal_cont);
        view.$el.modal();
    } else if (action_opts.target) {
        log("action target",action_opts.target);
        if (_.isString(action_opts.target)) {
            var $el=$("#"+action_opts.target);
        } else {
            var $el=$(action_opts.target);
        }
        $el.empty();
        $el.append(view.el);
    } else {
        if (nf_root) {
            $("#"+nf_root).empty();
            $("#"+nf_root).append(view.el);
        } else {
            $("body").empty();
            $("body").append(view.el);
        }
    }
    return view;
}

////////////////////////////////////////////////////////////////////////////////////////////////////
/// VIEW ///////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

nf_view_classes={}
nf_view_instances={}

function get_view_cls(name) {
    var view=nf_view_classes[name];
    if (!view) throw "View class not found: "+name;
    return view;
}

function get_view_inst(name) {
    var view=nf_view_instances[name];
    if (!view) throw "View instance not found: "+name;
    return view;
}

function clear_view_instances() {
    for (var name in nf_view_instances) {
        remove_view_instance(name);
    }
}

function remove_view_instance(name) {
    var view=nf_view_instances[name];
    if (!view) throw "Can't remove view instance: "+name;
    delete nf_view_instances[name];
    view.remove();
}

window.NFView=Backbone.View.extend({
    initialize: function(options) {
        if (!options) options={};
        this.options=options.options||{};
        this.context=this.options.context||{};
        this.data={};
        this.data.options=this.options;
        this.data.context=_.clone(this.context);
        nf_view_instances[this.cid]=this;
        this.subviews={};
    },

    render: function() {
        //log("NFView.render",this,this._name);
        this.remove_subviews();
        if (!this.template) {
            this.template=get_template(this._name);
            if (!this.template) throw "No template";
        }
        //try {
            var html=this.template(this.data);
        //} catch (err) {
        //    log("view render error",this,err);
        //    throw "Failed to render template of view '"+this._name+"': "+err.message;
        //}
        this.$el.html(html);
        var that=this;
        this.$el.find(".view").each(function() {
            var view_id=$(this).attr("id");
            //log("render sub",view_id);
            var view=get_view_inst(view_id);
            view.render();
            $(this).replaceWith(view.$el);
            that.subviews[view_id]=view;
        });
        return this;
    },

    remove_subviews: function() {
        for (var view_id in this.subviews) {
            var view=this.subviews[view_id];
            view.remove_subviews();
            remove_view_instance(view_id);
        }
        this.subviews={};
    }
},
{
    register: function() {
        nf_view_classes[this.prototype._name]=this;
    },

    make_view: function(options) {
        var view=new this({options:options});
        return view;
    }
});

////////////////////////////////////////////////////////////////////////////////////////////////////
/// MODEL //////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

function get_model(name) {
    var models=nf_models;
    var model=models[name];
    if (!model) throw "Model not found: "+name;
    return model;
}

function get_model_cls(name) { // XXX
    return get_model(name);
}

function get_field(model_name,field_name) {
    if (field_name=='id') return {};
    var models=nf_models;
    var model=models[model_name];
    if (!model) throw "Model not found: "+model_name;
    var field=model.fields[field_name];
    if (!field) throw "Field not found: "+model_name+"."+field_name;
    return field;
}

function get_field_path(model_name,field_name) {
    var fnames=field_name.split(".");
    for (var i=0; i<fnames.length-1; i++) {
        var fname=fnames[i];
        var field=get_field(model_name,fname);
        if (field.type!="many2one" && field.type!="one2many") {
            throw "Invalid field path: "+field_name;
        }
        model_name=field.relation;
    }
    var fname=fnames[fnames.length-1];
    return get_field(model_name,fname);
}

function has_field(model_name,field_name) {
    var models=nf_models;
    var model=models[model_name];
    if (!model) throw "Model not found: "+model_name;
    var field=model.fields[field_name];
    if (!field) return false;
    return true;
}

window.NFModel=Backbone.Model.extend({
    orig_data: {},

    initialize: function(attributes,options) {
        log("NFModel.initialize",attributes,options);
        if (!options || !options.name) {
            throw "Missing model name in new model instance";
        }
        log("name",options.name);
        this.name=options.name;
        this.fields={}; // fields specific to this model instance (used for search view for ex.)
        Backbone.Model.prototype.initialize.call(this,attributes,options);
    },

    get_field: function(name) {
        var f=this.fields[name];
        if (f) return f;
        return get_field(this.name,name);
    },

    set_orig_data: function(data) {
        var vals={};
        for (var n in data) {
            if (n=="id") continue;
            var v=data[n];
            var field=this.get_field(n);
            if (field.type=="many2one") {
                if (_.isArray(v)) v=v[0];
            } else if (field.type=="reference") {
                if (_.isArray(v)) v=v[0];
            }
            vals[n]=v;
        }
        this.orig_data=vals;
    },

    get_change_vals: function() { // XXX: FIXME
        log("NFModel.get_change_vals",this);
        var data=this.toJSON();
        var vals={};
        for (var n in data) {
            if (n=="id") continue;
            var v=data[n];
            var v_orig;
            if (this.orig_data) v_orig=this.orig_data[n];
            else v_orig=null;
            var f=this.get_field(n);
            if (f.type=="many2one") {
                if (_.isArray(v)) v=v[0];
                if (v!=v_orig) vals[n]=v;
            } else if (f.type=="one2many") {
                if (v && !_.isArray(v)) {
                    v=v.get_change_vals();
                    if (!_.isEmpty(v)) {
                        vals[n]=v;
                    }
                }
            } else if (f.type=="many2many") {
                v=[["set",v||[]]];
                vals[n]=v;
            } else if (f.type=="reference") {
                if (_.isArray(v)) v=v[0];
                if (v!=v_orig) vals[n]=v;
            } else {
                if (v!=v_orig) vals[n]=v;
            }
        }
        log("=> change vals",vals);
        return vals;
    },

    get_vals: function() {
        var data=this.toJSON();
        var vals={};
        for (var n in data) {
            if (n=="id") continue;
            var v=data[n];
            var f=this.get_field(n);
            if (f.type=="many2one" || f.type=="reference") {
                if (_.isArray(v)) v=v[0];
            } else if (f.type=="one2many") {
                if (!v) continue;
                v=v.get_vals();
            }
            vals[n]=v;
        }
        return vals;
    },

    get_vals_all: function() { // include "id" in values
        var data=this.toJSON();
        var vals={};
        for (var n in data) {
            var v=data[n];
            if (n!="id") {
                var f=this.get_field(n);
                if (f.type=="many2one") {
                    if (_.isArray(v)) v=v[0];
                } else if (f.type=="one2many") {
                    if (!v) continue;
                    v=v.get_vals();
                }
            }
            vals[n]=v;
        }
        return vals;
    },

    get_path_value: function(path) {
        log("NFModel.get_path_value",path);
        var comps=path.split(".");
        var n=comps[0];
        var v;
        if (n=="parent") {
            var parent_model=this.collection.parent_model;
            if (!parent_model) throw "Parent model not found";
            v=parent_model.get_path_value(path.substr(7));
        } else {
            v=this.get(n);
        }
        log("==>",v);
        return v;
    },

    set_vals: function(vals) {
        log("model set_vals",vals);
        for (var n in vals) {
            var v=vals[n];
            var f=this.get_field(n);
            if (_.isEmpty(f)) continue;
            if (f.type=="many2one") {
                if (_.isNumber(v)) {
                    var old_v=this.get(n);
                    if (_.isArray(old_v) && old_v[0]==v) {
                        v=old_v;
                    }
                }
                this.set(n,v);
            } else if (f.type=="one2many") {
                var col=this.get(n);
                if (col instanceof NFCollection) {
                    col.set_vals(v);
                }
            } else {
                this.set(n,v);
            }
        }
    },

    set_fields: function(fields) {
        log("model set_fields",fields);
        for (var path in fields) {
            var comps=path.split(".");
            var n=comps[0];
            var new_f=fields[n];
            var cur_f=this.fields[n];
            if (!cur_f) {
                var f=get_field(this.name,n);
                cur_f=_.clone(f);
                this.fields[n]=cur_f;
            }
            if (comps.length==1) {
                _.extend(cur_f,new_f);
            }
        }
    },

    get_path: function(field_name) {
        var path;
        if (this.collection) {
            var found=false;
            for (var i=0; i<this.collection.models.length; i++) {
                var m=this.collection.models[i];
                if (m.cid==this.cid) {
                    found=true;
                    break;
                }
            }
            if (!found) throw "Model not found!";
            path=this.collection.get_path()+"."+i;
        } else {
            path="";
        }
        if (field_name) {
            if (path) path+="."+field_name;
            else path=field_name;
        }
        return path;
    },

    get_field_path: function(field_name) {
        var path;
        if (this.collection) {
            path=this.collection.get_path();
        } else {
            path="";
        }
        if (field_name) {
            if (path) path+="."+field_name;
            else path=field_name;
        }
        return path;
    },

    set_required: function(n) {
        if (!this.required_fields) this.required_fields={};
        this.required_fields[n]=true;
    },

    set_not_required: function(n) {
        if (!this.required_fields) this.required_fields={};
        if (this.required_fields[n]) {
            delete this.required_fields[n];
        }
    },

    set_meta: function(meta) { // XXX: remove this
        log("model set_meta",this,meta);
        for (var n in meta) {
            var fmeta=meta[n];
            var f=this.dyn_meta[n];
            if (!f) {
                f={};
                this.dyn_meta[n]=f;
            }
            for (var k in fmeta) {
                f[k]=fmeta[k];
            }
            this.trigger("change:"+n);
        }
        log("dyn_meta",this.dyn_meta,this);
    },

    check_required: function() {
        log("check_required",this);
        if (!this.required_fields) this.required_fields={};
        if (!this.id) {
            var data=this.toJSON();
            var empty=true;
            for (var k in data) {
                var v=data[k];
                if (v!==null && v!==undefined) {
                    empty=false;
                    break;
                }
            }
            if (empty) return true; // FIXME: doesn't work (ex if empty form)
        }
        var errors={};
        var ok=true;
        var model_cls=get_model(this.name);
        for (var n in model_cls.fields) {
            var f=this.get_field(n);
            var required=this.required_fields[n];
            var v=this.get(n);
            //log("n",n,"req",required,"v",v);
            if (required){
                var t=typeof(v);
                if(t!='number' && _.isEmpty(v)){
                    errors[n]="Missing value";
                    ok=false;
                }else if(t=='number' && v==null){
                    errors[n]="Missing value";
                    ok=false;
                }
            }
            if (f.type=="one2many") {
                if (v instanceof NFCollection) {
                    if (!v.check_required()) ok=false;
                }
            }
        }
        log("errors",errors);
        this.set_field_errors(errors);
        log("ok",ok);
        return ok;
    },

    set_field_errors: function(err) {
        log("set_field_errors",err);
        this.field_errors={}
        if (!err) return;
        for (var n in err) {
            var v=err[n];
            var f=this.get_field(n);
            if (f.type=="one2many") {
                var col=this.get(n);
                if (col instanceof NFCollection) {
                    col.set_field_errors(v);
                }
            } else {
                this.field_errors[n]=v;
            }
        }
        this.trigger("error");
    },

    get_field_error: function(name) {
        if (!this.field_errors) return null;
        return this.field_errors[name];
    }
});

////////////////////////////////////////////////////////////////////////////////////////////////////
/// COLLECTION /////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

window.NFCollection=Backbone.Collection.extend({
    model: NFModel,
    orig_ids: null,
    condition: [],
    search_condition: [],
    fields: null,
    limit: 100,
    offset: 0,

    initialize: function(models,options) {
        log("NFCollection.initialize",models,options);
        if (!options || !options.name) {
            throw "Missing model name in new collection instance";
        }
        this.name=options.name;
        log("name",options.name);
        Backbone.Collection.prototype.initialize.call(this,models,options);
    },

    get_change_vals: function() {
        var ops=[];
        this.each(function(m) {
            var vals=m.get_change_vals();
            if (m.id) {
                if (!_.isEmpty(vals)) {
                    ops.push(["write",[m.id],vals]);
                }
            } else {
                var empty=_.all(vals,function(v) { return !v; });
                if (!empty) {
                    ops.push(["create",vals]);
                }
            }
        });
        var that=this;
        var del_ids=[];
        _.each(this.orig_ids,function(id) {
            var m=that.get(id);          
            if (!m) {
                del_ids.push(id);
            }
        });
        if (del_ids.length>0) {
            ops.push(["delete",del_ids]);
        }
        return ops;
    },

    check_required: function() {
        var ok=true;
        this.each(function(m) {
            if (!m.check_required()) ok=false;
        });
        return ok;
    },

    get_vals: function() {
        var vals=[];
        this.each(function(m) {
            var m_vals=m.get_vals();
            vals.push(m_vals);
        });
        return vals;
    },

    set_vals: function(vals) { // XXX: what if different length?
        log("collection set_vals",vals);
        for (var i=0; i<vals.length; i++) {
            var v=vals[i];
            var m=this.models[i];
            if (!m) {
                m=new NFModel({},{name:this.name});
                this.add(m);
            }
            m.set_vals(v);
        }
    },

    set_field_errors: function(err) { // XXX: what if different length?
        for (var i=0; i<err.length; i++) {
            var v=err[i];
            var m=this.models[i];
            m.set_field_errors(v);
        }
    },

    get_path: function() {
        var path;
        if (this.parent_model) {
            path=this.parent_model.get_path();
            if (path) path+="."+this.parent_field;
            else path=this.parent_field;
        } else {
            path="";
        }
        return path;
    },

    is_searched: function() {
        return false;
    },

    get_data: function(cb) {
        log("NFCollection get_data",this);
        var cond=this.condition||[];
        log("XXXXXXXXXXXXXX",cond);
        if (!_.isEmpty(this.search_condition)) {
            if (!_.isEmpty(cond)) {
                cond=[cond,this.search_condition];
            } else {
                cond=this.search_condition;
            }
        }
        var that=this;
        var opts={
            field_names: this.fields,
            limit: this.limit,
            offset: this.offset,
            order: this.order
        };
        rpc_execute(this.name,"search_read",[cond],opts,function(err,data) {
            log("NFCollection got data",that,data);
            that.reset(data,{name:that.name});
            if (cb) cb(err,data);
        });
    },

    nf_pluck: function(field_name) {
        return this.filter(function(m) {return m.get(field_name)}).map(function(m) {return m.get(field_name)[0]});
    }
})

////////////////////////////////////////////////////////////////////////////////////////////////////
/// ACTION /////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

function get_action(name) {
    log("get_action",name);
    var actions=nf_actions;
    var action=actions[name];
    if (!action) throw "Action not found: "+name;
    //log("=> ",action);
    return action;
}

function find_action(options) {
    log("find_action",JSON.stringify(options));
    var actions=nf_actions;
    var min_pri=null;
    var found_action=null;
    for (var name in actions) {
        var action=actions[name];
        if (options.model && action.model!=options.model) continue;
        var view=action.view||action.view_cls; // XXX: remove view_cls later
        if (options.view && view!=options.view) continue;
        var pri=parseInt(action.priority)||10;
        if (min_pri==null || pri<min_pri) {
            min_pri=pri;
            found_action=name;
        }
    }
    return found_action;
}

function find_details_action(model,active_id) {
    log("find_details_action",model,active_id);
    var action_name=find_action({model:model,view:"multi_view"});
    if (!action_name) return null;
    var action=get_action(action_name);
    var pri=parseInt(action.priority)||10;
    var action_name2=find_action({model:model});
    var action2=get_action(action_name2);
    var pri2=parseInt(action2.priority)||10;
    if (pri2<pri) { // if there is action with lower priority than multi_view, use that action
        action_name=action_name2;
        action=action2;
    }
    var modes=(action.modes||"list,form").split(",");
    var a={
        name: action_name,
        active_id: active_id
    };
    if (_.contains(modes,"page")) {
        a.mode="page";
    } else if (_.contains(modes,"form")) {
        a.mode="form";
    }
    return a;
}

function find_new_action(model) {
    log("find_new_action",model);
    var action_name=find_action({model:model,view:"multi_view"});
    if (!action_name) return null;
    var action=get_action(action_name);
    var modes=(action.modes||"list,form").split(",");
    var a={
        name: action_name,
        mode: "form"
    };
    return a;
}

////////////////////////////////////////////////////////////////////////////////////////////////////
/// TEMPLATE ///////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

nf_templates_compiled={}

function get_template(name) {
    var tmpl=nf_templates_compiled[name];
    if (tmpl) return tmpl;
    if (!nf_templates) throw "Templates not loaded";
    tmpl_src=nf_templates[name];
    if (!tmpl_src) throw "Template not found: "+name;
    tmpl=Handlebars.compile(tmpl_src);
    nf_templates_compiled[name]=tmpl;
    return tmpl;
}

////////////////////////////////////////////////////////////////////////////////////////////////////
/// XML LAYOUTS ////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

function get_xml_layout(opts) {
    log("get_xml_layout",JSON.stringify(opts));
    if (!opts) opts={};
    var found_view=null;
    var found_pri=999;
    if (!opts.name && !opts.model) throw "Invalid view query";
    var layouts=nf_layouts;
    for (var n in layouts) { // XXX: speed
        var view=layouts[n];
        if (opts.name && view.name!=opts.name) continue;
        if (opts.model && view.model!=opts.model) continue;
        if (opts.type && view.type!=opts.type) continue;
        if (opts.inherit) continue;
        var pri=view.priority||10;
        if (pri<found_pri) {
            found_view=view;
            found_pri=pri;
        }
    }
    if (found_view) {
        //log("found view",found_view);
        return apply_view_inherits(found_view);
    } else {
        if (!opts.noerr) {
            throw "View layout not found: "+JSON.stringify(opts);
        }
    }
}

function apply_view_inherits(view_orig) {
    var doc=$.parseXML(view_orig.layout);
    var layouts=nf_layouts;
    for (var n in layouts) { // XXX: speed
        var view=layouts[n];
        if (view.inherit!=view_orig.name) continue;
        log("view inherit",view_orig.name,"->",view.name);
        do_inherit(doc,view.layout);
    }
    var view=_.clone(view_orig);
    view.layout=(new XMLSerializer()).serializeToString(doc);
    return view;
}

function do_inherit(parent_doc,xml) {
    try {
        var doc=$.parseXML(xml);
        $(doc).find("inherit").children().each(function() {
            var $el=$(this);
            var tag=$el.prop("tagName");
            var sel=tag;
            _.each($el[0].attributes,function(attr) {
                if (attr.name=="position") return;
                sel+='['+attr.name+'=\"'+attr.value+'"'+']';
            });
            //log("sel",sel);
            var $el_p=$(parent_doc).find(sel).first();
            if (!$el_p) throw "Inherit element not found: "+sel;
            var pos=$el.attr("position");
            if (pos=="after") {
                $el.children().clone().insertAfter($el_p);
            } else if (pos=="before") {
                $el.children().clone().insertBefore($el_p);
            } else if (pos=="append") {
                $el.children().clone().appendTo($el_p);
            } else if (pos=="prepend") {
                $el.children().clone().prependTo($el_p);
            } else if (pos=="replace") {
                $el_p.replaceWith($el.children().clone());
            } else {
                throw "Invalid inherit position: "+pos;
            }
        });
    } catch (err) {
        log("Inherit failed!",err);
    }
}

function get_default_search_view(model) {
    var req_fields=[];
    var other_fields=[];
    var model_cls=get_model(model);
    _.each(model_cls.fields,function(f,n) {
        if (f.search) {
            if (f.required) {
                req_fields.push(n);
            } else {
                other_fields.push(n);
            }
        }
    });
    req_fields=_.sortBy(req_fields,function(n) {return get_field(model,n).string});
    other_fields=_.sortBy(other_fields,function(n) {return get_field(model,n).string});
    var fields=[];
    _.each(req_fields,function(n) {
        fields.push({name:n});
    });
    _.each(other_fields,function(n) {
        fields.push({name:n});
    });
    var layout="<search>";
    _.each(fields,function(f) {
        layout+='<field name="'+f.name+'"/>';
    });
    layout+="</search>";
    var view={
        layout: layout
    }
    return view;
}

////////////////////////////////////////////////////////////////////////////////////////////////////
/// PERMISSIONS ////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

var ui_params_user=null;
var nf_user_id=null;

function load_ui_params_user(cb) {
    log("load_ui_params_user");
    var ctx=get_global_context();
    var user_id=ctx.user_id;
    if (!ctx.dbname || !ctx.user_id) {
        log("xxx1");
        cb();
        return;
    }
    if (nf_user_id==user_id && ui_params_user) {
        log("xxx2");
        cb();
        return;
    }
    nf_user_id=user_id;
    ui_params_user=null;
    rpc_execute("base.user","get_ui_params",[],{},function(err,res) {
        if (err) throw "Failed to get user UI params";
        log("User UI params loaded");
        ui_params_user=res;
        cb();
    });
}

function get_field_permissions(model,name) {
    if (ui_params_user) {
        var perms=_.find(ui_params_user.field_perms,function(p) { return p.model==model && p.field==name });
    } else {
        var perms=null;
    }
    return {
        perm_read: perms?perms.perm_read:true,
        perm_write: perms?perms.perm_write:true
    }
}

function check_other_permission(perm,perm_check_admin) {
    if (!perm) return true;
    var ctx=get_global_context();
    var user_id=ctx.user_id;
    if (user_id==1 && !perm_check_admin) return true;
    if (!ui_params_user) return false;
    return _.contains(ui_params_user.other_perms,perm);
}

function check_model_permission(model,perm) {
    log("check_model_permission",model,perm);
    var ctx=get_global_context();
    var user_id=ctx.user_id;
    if (user_id==1) return true;
    if (!ui_params_user) return false;
    var perms=_.find(ui_params_user.model_perms,function(p) { return p.model==model; });
    if (!perms) {
        if (ui_params_user.default_model_perms=="full") {
            perms={
                perm_read: true,
                perm_create: true,
                perm_write: true,
                perm_delete: true
            };
        } else {
            perms={
                perm_read: false,
                perm_create: false,
                perm_write: false,
                perm_delete: false
            };
        }
    }
    return perms["perm_"+perm];
}

function check_menu_permission(action_name) {
    var ctx=get_global_context();
    var user_id=ctx.user_id;
    if (user_id==1) return true;
    var action=get_action(action_name);
    if (action_name=="login" || action_name=="logout") { // XXX: find some other way to do this
        return true;
    }
    var default_menu_access="visible";
    if (ui_params_user) {
        default_menu_access=ui_params_user.default_menu_access||"visible";
        var perms=_.find(ui_params_user.menu_perms,function(p) { return p.action==action_name; });
        if (!perms && action.menu) {
            perms=_.find(ui_params_user.menu_perms,function(p) { return p.menu==action.menu && !p.action; });
        }
    } else {
        var perms=null;
    }
    var access=perms?perms.access:default_menu_access;
    return access=="visible";
}

function check_package(pkg) {
    if (!pkg) return true;
    var pkg_list=pkg.split(",");
    var ctx=get_global_context();
    var db_pkg=ctx["package"];
    if (!db_pkg) return false;
    var db_pkg_list=db_pkg.split(",");
    var res=_.intersection(pkg_list,db_pkg_list).length>0;
    return res;
}

////////////////////////////////////////////////////////////////////////////////////////////////////
/// SYNC ///////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

Backbone.sync = function(method, model, options) {
    var context=options.context||{};
    switch (method) {
        case "create":
            var vals=model.get_change_vals();
            if (!model.check_required()) {
                options.error({message:"Some required fields are missing"});
                return;
            }
            nf_execute(model.name,"create",[vals],{context:context},function(err,data) {
                if (err) {
                    options.error(err);
                    return;
                }
                var id=data;
                options.success({id: id});
            });
            break;
        case "update":
            var json=model.get_change_vals();
            var vals={};
            for (n in json) {
                if (n!="id") vals[n]=json[n];
            }
            var opts={context:context};
            if (model.read_time) {
                opts.check_time=model.read_time;
            }
            if (_.isEmpty(vals)) {
                options.success();
            } else {
                if (!model.check_required()) {
                    options.error({message:"Some required fields are missing"});
                    return;
                }
                log("*********************************************");
                log("WRITING CHANGES",vals);
                nf_execute(model.name,"write",[[model.id],vals],opts,function(err,data) {
                    if (err) {
                        options.error(err);
                        return;
                    }
                    options.success(data);
                });
            }
            break;
        case "delete":
            nf_execute(model.name,"delete",[[model.id]],{context:context},function(err,data) {
                if (err) {
                    options.error(err);
                    return;
                }
                options.success(data);
            });
            break;
    }
};

////////////////////////////////////////////////////////////////////////////////////////////////////
/// ROUTER /////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////

function qs_to_obj(query) {
    var vals = {};
    var pl=/\+/g;
    var search=/([^&=]+)=?([^&]*)/g;
    var decode=function (s) {
        return decodeURIComponent(s.replace(pl, " "));
    };
    while (match = search.exec(query)) {
       var k=decode(match[1]);
       var v=decode(match[2]);
       if (v[0]=="[") {
           v=JSON.parse(v);
       }
       var comps=k.split(".");
       var p=vals;
       for (var i in comps) {
            var n=comps[i];
            if (i==comps.length-1) {
                p[n]=v;
            } else {
                if (!p[n]) p[n]={};
                p=p[n];
            }
       }
    }
    //log("qs_to_obj",query,vals);
    return vals;
}

function obj_to_qs(action) {
    var params = [];
    function _write_dict(vals,prefix) {
        for(var n in vals) {
            var v=vals[n];
            if (_.isArray(v)) {
                params.push(encodeURIComponent(prefix+n) + "=" + encodeURIComponent(JSON.stringify(v)));
            } else if (_.isObject(v)) {
                _write_dict(v,prefix+n+".");
            } else {
                params.push(encodeURIComponent(prefix+n) + "=" + encodeURIComponent(v));
            }
        }
    }
    _write_dict(action,"");
    var qs=params.join("&");
    //log("obj_to_qs",action,qs);
    return qs;
}

var Workspace=Backbone.Router.extend({
    routes: {
        ":query": "action"
    },

    action: function(query) {
        log("router.action",query);
        var options=qs_to_obj(query);
        exec_action(options);
    }
});

workspace=new Workspace;

$(document).ready(function() {
    log("document.ready");
    Backbone.history.start();
});

///// REMOTE EVENT ///////////////////////

var nf_websocket=null;

function nf_create_websocket() {
    log("nf_create_websocket");
    nf_websocket=new WebSocket("ws://"+window.location.host+"/listen");
    _.extend(nf_websocket,Backbone.Events);
    var ctx=get_global_context();
    nf_websocket.user_id=ctx.user_id;
    nf_websocket.onmessage=function(e) {
        var msg=e.data;
        log("message",msg);
        var parts=msg.split(" ");
        if (parts[0]!="NOTIFY") {
            throw "Invalid websocket command";
        }
        var event_name=parts[1];
        nf_websocket.trigger(event_name);
    };
    nf_websocket.onclose=function() {
        nf_websocket=null;
    }
}

/*
function nf_listen(event_name,cb) {
    if (!Modernizr.websockets) return;
    var ctx=get_global_context();
    if (!nf_websocket || nf_websocket.user_id!=ctx.user_id) {
        if (nf_websocket) {
            nf_websocket.close();
            nf_websocket=null;
        }
        nf_create_websocket();
    }
    nf_websocket.on(event_name,cb);
}

function nf_unlisten(event_name) {
    if (!nf_websocket) return;
    nf_websocket.off(event_name);
}
*/

var nf_listen_obj={};
_.extend(nf_listen_obj,Backbone.Events);
var nf_poll_enable=false;

function nf_poll() {
    var global_ctx=get_global_context();
    if (nf_listen_obj.user_id!=global_ctx.user_id) {
        nf_listen_obj={};
        _.extend(nf_listen_obj,Backbone.Events);
        nf_poll_enable=false;
    }
    if (!nf_poll_enable) {
        setTimeout(nf_poll,3000);
        return;
    }
    log("POLL");
    $.ajax({
        url: "/listen_poll",
        cache: false,
        success: function(data) {
            log("POLL SUCCESS",data);
            _.each(data,function(event_name) {
                nf_listen_obj.trigger(event_name);
            });
            nf_poll();
        },
        error: function(req,stat,error) {
            if (stat=="timeout") {
                log("POLL TIMEOUT");
                nf_poll();
            } else {
                log("POLL ERROR");
                setTimeout(nf_poll,60000);
            }
        },
        dataType: "json",
        timeout: 60000
    });
}
//setTimeout(nf_poll,1000); // XXX: poll disabled

function nf_listen(event_name,cb) {
    var global_ctx=get_global_context();
    nf_listen_obj.user_id=global_ctx.user_id;
    nf_poll_enable=true;
    nf_listen_obj.on(event_name,cb);
}

function nf_unlisten(event_name) {
    nf_listen_obj.off(event_name);
}

///// SOUND /////////////////////////////

function nf_play_sound(url) {
    var el = document.createElement('audio');
    if (Modernizr.audio.ogg) {
        url=url.replace(".mp3",".ogg"); // XXX
    }
    el.setAttribute('src',url);
    el.play();
}

///// FOCUS /////////////////////////////

var focus_el=null;

function register_focus(el) {
    console.log("register_focus",el);
    focus_el=el;
}

function focus_next() {
    console.log("focus_next",focus_el);
    var els=$("input:visible[tabindex!=-1],textarea:visible[tabindex!=-1],select:visible[tabindex!=-1],button:visible[tabindex!=-1],a:visible[tabindex!=-1]")
    if (focus_el) {
        var i=els.index(focus_el);
        if (i==-1) throw "Current focus element not found";
        if (i<els.length-1) {
            var next=els.eq(i+1);
        } else {
            var next=els.eq(0);
        }
    } else {
        var next=els[0];
    }
    console.log("next",next);
    next.focus();
    focus_el=next[0];
}

/// SCROLL HEADERS ////////////////////////////

function set_scroll_headers() {
    var head=$(".scroll-header").first();
    if (head.length==0) return;
    var view_top=$(window).scrollTop();
    var view_bottom=view_top+$(window).height();
    var view_left=$(window).scrollLeft();
    var head_top=head.offset().top;
    var head_bottom=head_top+head.height();
    var head_left=head.offset().left;
    if (view_top>head_bottom) {
        var head2=$('<div class="scroll-header-copy" style="background-color:#eee;overflow:hidden"/>');
        head2.css({position:"fixed",top:0,left:head_left-view_left,height:head.height()});
        head.find("th").each(function() {
            var w=$(this).outerWidth();
            var h=$(this).height();
            var text=$(this).text();
            var h=$("<span>").text(text).css({padding:5,fontWeight:"bold","float":"left","white-space":"normal",width:w+"px","line-height":h+"px"}).appendTo(head2);
            if ($(this).css("text-align")=="right") {
                h.css({"text-align":"right"});
            }
        });
        $("body").find(".scroll-header-copy").remove();
        $("body").append(head2);
    } else {
        $("body").find(".scroll-header-copy").remove();
    }
}

var nf_scroll_timeout=null;

$(window).on("scroll",function() {
    log("scroll");
    if (nf_scroll_timeout) {
        clearTimeout(nf_scroll_timeout);
    }
    nf_scroll_timeout=setTimeout(function() {
        set_scroll_headers();
    },300);
});

function focus_prev() {
    console.log("focus_prev",focus_el);
    var els=$("input:visible[tabindex!=-1],textarea:visible[tabindex!=-1],select:visible[tabindex!=-1],button:visible[tabindex!=-1],a:visible[tabindex!=-1]")
    if (focus_el) {
        var i=els.index(focus_el);
        if (i==-1) throw "Current focus element not found";
        if (i>0) {
            var prev=els.eq(i-1);
        } else {
            var prev=els.eq(els.length-1);
        }
    } else {
        var prev=els[els.length-1];
    }
    console.log("prev",prev);
    prev.focus();
    focus_el=prev[0];
}

/// fastclick

$(function() {
    //FastClick.attach(document.body); // cause some bugs in safari mobile...
});

// VERSION

function nf_get_version() {
    if (!ui_params) return null;
    return ui_params.version;
}
