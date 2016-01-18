# Copyright (c) 2012-2015 Netforce Co. Ltd.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
# OR OTHER DEALINGS IN THE SOFTWARE.

# TODO: improve compliance with handlebars spec and split in separate module (initially based on pybars, but need to change)

from functools import partial
import re

from netforce.pymeta.grammar import OMeta

import collections

from netforce import database
from netforce.model import get_model, fields, BrowseList
from netforce.locale import _
import datetime
import time
from netforce import access
import json
import tempfile
try:
    import barcode
    from barcode.writer import ImageWriter
except:
    barcode = None
    print("WARNING: pyBarcode not installed")
import math
import os
from pprint import pprint
from xml.sax import saxutils

handlebars_grammar = r"""
template ::= (<text> | <templatecommand>)*:body => ['template'] + body
text ::= (~(<start>) <anything>)+:text => ('literal', ''.join(text))
other ::= <anything>:char => ('literal', char)
templatecommand ::= <blockrule>
    | <comment>
    | <escapedexpression>
    | <expression>
    | <partial>
start ::= '{' '{'
finish ::= '}' '}'
comment ::= <start> '!' (~(<finish>) <anything>)* <finish> => ('comment', )
space ::= ' '|'\t'|'\r'|'\n'
arguments ::= (<space>+ (<kwliteral>|<literal>|<path>))*:arguments => arguments
expression_inner ::= <spaces> <path>:p <arguments>:arguments <spaces> <finish> => (p, arguments)
expression ::= <start> '{' <expression_inner>:e '}' => ('expand', ) + e
    | <start> '&' <expression_inner>:e => ('expand', ) + e
escapedexpression ::= <start> <expression_inner>:e => ('escapedexpand', ) + e
block_inner ::= <spaces> <symbol>:s <arguments>:args <spaces> <finish>
    => (''.join(s), args)
alt_inner ::= <spaces> ('^' | 'e' 'l' 's' 'e') <spaces> <finish>
partial ::= <start> '>' <block_inner>:i => ('partial',) + i
path ::= ~('/') <pathseg>+:segments => ('path', segments)
kwliteral ::= <symbol>:s '=' (<literal>|<path>):v => ('kwparam', s, v)
literal ::= (<string>|<integer>|<boolean>):thing => ('literalparam', thing)
string ::= '"' <notquote>*:ls '"' => '"' + ''.join(ls) + '"'
integer ::= <digit>+:ds => int(''.join(ds))
boolean ::= <false>|<true>
false ::= 'f' 'a' 'l' 's' 'e' => False
true ::= 't' 'r' 'u' 'e' => True
notquote ::= <escapedquote> | (~('"') <anything>)
escapedquote ::= '\\' '"' => '\\"'
symbol ::=  ~<alt_inner> '['? (<letterOrDigit>|'-'|'@')+:symbol ']'? => ''.join(symbol)
pathseg ::= <symbol>
    | '/' => ''
    | ('.' '.' '/') => '__parent'
    | '.' => ''
pathfinish :expected ::= <start> '/' <path>:found ?(found == expected) <finish>
symbolfinish :expected ::= <start> '/' <symbol>:found ?(found == expected) <finish>
blockrule ::= <start> '#' <block_inner>:i
      <template>:t <alttemplate>:alt_t <symbolfinish i[0]> => ('block',) + i + (t, alt_t)
    | <start> '^' <block_inner>:i
      <template>:t <symbolfinish i[0]> => ('invertedblock',) + i + (t,)
alttemplate ::= (<start> <alt_inner> <template>)?:alt_t => alt_t or []
"""

compile_grammar = """
compile ::= <prolog> <rule>* => builder.finish()
prolog ::= "template" => builder.start()
compile_block ::= <prolog_block> <rule>* => builder.finish_block()
prolog_block ::= "template" => builder.start_block()
rule ::= <literal>
    | <expand>
    | <escapedexpand>
    | <comment>
    | <block>
    | <invertedblock>
    | <partial>
block ::= [ "block" <anything>:symbol [<arg>*:arguments] [<compile_block>:t] [<compile_block>?:alt_t] ] => builder.add_block(symbol, arguments, t, alt_t)
comment ::= [ "comment" ]
literal ::= [ "literal" :value ] => builder.add_literal(value)
expand ::= [ "expand" <path>:value [<arg>*:arguments]] => builder.add_expand(value, arguments)
escapedexpand ::= [ "escapedexpand" <path>:value [<arg>*:arguments]] => builder.add_escaped_expand(value, arguments)
invertedblock ::= [ "invertedblock" <anything>:symbol [<arg>*:arguments] [<compile>:t] ] => builder.add_invertedblock(symbol, arguments, t)
partial ::= ["partial" <anything>:symbol [<arg>*:arguments]] => builder.add_partial(symbol, arguments)
path ::= [ "path" [<pathseg>:segment]] => ("simple", segment)
 | [ "path" [<pathseg>+:segments] ] => ("complex", 'resolve(context, "'  + '","'.join(segments) + '")' )
simplearg ::= [ "path" [<pathseg>+:segments] ] => 'resolve(context, "'  + '","'.join(segments) + '")'
    | [ "literalparam" <anything>:value ] => str(value)
arg ::= [ "kwparam" <anything>:symbol <simplearg>:a ] => str(symbol) + '=' + a
    | <simplearg>
pathseg ::= "/" => ''
    | "." => ''
    | "" => ''
    | "this" => ''
pathseg ::= <anything>:symbol => ''.join(symbol)
"""
compile_grammar = compile_grammar.format()


class strlist(list):

    def __str__(self):
        return ''.join(self)

    def grow(self, thing):
        if type(thing) == str:
            self.append(thing)
        else:
            for element in thing:
                self.grow(element)

_map = {
    '&': '&amp;',
    '"': '&quot;',
    "'": '&#x27;',
    '`': '&#x60;',
    '<': '&lt;',
    '>': '&gt;',
}


def substitute(match, _map=_map):
    return _map[match.group(0)]


_escape_re = re.compile(r"&|\"|'|`|<|>")


def escape(something, _escape_re=_escape_re, substitute=substitute):
    return _escape_re.sub(substitute, something)


class Scope:

    def __init__(self, context, parent, data=None):
        self.context = context
        self.parent = parent
        if parent and isinstance(parent,Scope):
            self.data=parent.data
        else:
            self.data={}
        if data:
            self.data.update(data)

    def get(self, name, default=None):
        if name == '__parent':
            return self.parent
        elif name == 'this':
            return self.context
        elif name.startswith("@"):
            return self.data.get(name[1:])
        result = self.context.get(name, self)
        if result is not self:
            return result
        return default
    __getitem__ = get

    def __str__(self):
        return str(self.context)


def resolve(context, *segments):
    # print("resolve",segments)
    for segment in segments:
        if context is None:
            return None
        if segment in (None, ""):
            continue
        if type(context) in (list, tuple):
            offset = int(segment)
            try:
                context = context[offset]
            except:
                context = None
        else:
            if isinstance(segment, str) and segment.isdigit():
                segment = int(segment)
            context = context.get(segment)
    return context


def _paginate(this, options, data, limit=None, offset=None, url=None):
    if not data:
        return options['inverse'](this)
    if limit is None:
        limit = 10
    if offset is None:
        offset = 0
    count = len(data)
    page_no = math.floor(offset / limit) + 1
    num_pages = math.floor((count + limit - 1) / limit)
    paginate = {
        "data": data[offset:offset + limit],
        "limit": limit,
        "offset": offset,
        "count": count,
        "item_first": offset + 1,
        "item_last": min(offset + limit, count),
        "page_no": page_no,
        "num_pages": num_pages,
        "parts": [],
    }
    if url:
        base_url = re.sub("&offset=\d+", "", url)  # XXX
    else:
        base_url = ""
    if base_url.find("?")==-1: # XXX
        base_url+="?"
    if page_no > 1:
        p = page_no - 1
        o = (p - 1) * limit
        paginate["previous"] = {
            "page_no": p,
            "url": base_url + "&offset=%d" % o if base_url else None,
        }
    if page_no < num_pages:
        p = page_no + 1
        o = (p - 1) * limit
        paginate["next"] = {
            "page_no": p,
            "url": base_url + "&offset=%d" % o if base_url else None,
        }
    if num_pages > 1:
        first_part_page_no = max(1, page_no - 2)
        last_part_page_no = min(num_pages, page_no + 1)
        for p in range(first_part_page_no, last_part_page_no + 1):
            o = (p - 1) * limit
            part = {
                "page_no": p,
                "active": p == page_no,
                "url": base_url + "&offset=%d" % o if base_url else None,
            }
            paginate["parts"].append(part)
    scope = Scope({"paginate": paginate}, this)
    return options['fn'](scope)


def _each(this, options, context, order=None, offset=None, limit=None):
    if not context:
        return None
    result = strlist()
    i = 0
    if order:
        if len(order.split(" ")) == 2:
            if order.split(" ")[1] == "desc":
                context2 = sorted(context, key=lambda x: x[order.split(" ")[0]])[::-1]
        else:
            context2 = sorted(context, key=lambda x: x[order])
    else:
        context2 = context
    if offset:
        context2=context2[offset:]
    if limit:
        context2=context2[:limit]
    for ctx in context2:
        data={}
        if isinstance(context2, (list, BrowseList)):
            data['index'] = i
            data['item_no'] = i+1
            data['is_last'] = i == len(context2) - 1
        if isinstance(context2, dict):
            data['key'] = ctx
        scope = Scope(ctx, this, data=data)
        result.grow(options['fn'](scope))
        i += 1
    return result


def _if(this, options, context):
    if isinstance(context, collections.Callable):
        context = context(this)
    if context:
        return options['fn'](this)
    else:
        return options['inverse'](this)


def _log(this, context):
    log(context)


def _unless(this, options, context):
    if not context:
        return options['fn'](this)


def _blockHelperMissing(this, options, context):
    if isinstance(context, collections.Callable):
        context = context(this)
    if context != "" and not context:
        return options['inverse'](this)
    if type(context) in (list, strlist, tuple):
        return _each(this, options)
    if context is True:
        callwith = this
    else:
        callwith = context
    return options['fn'](callwith)


def _helperMissing(scope, name, *args):
    if not args:
        return None
    raise Exception("Could not find property %s" % (name,))


def _with(this, options, context):
    if context:
        scope = Scope(context, this)
        return options['fn'](scope)
    else:
        return options['inverse'](this)


def _file_path(this, context, thumbnail=None):
    if context is None:
        return ""
    try:
        dbname = database.get_active_db()
        if thumbnail:
            basename, ext = os.path.splitext(context)
            basename2, _, rand = basename.rpartition(",")
            fname = basename2 + "-resize-256," + rand + ext
        else:
            fname = context
        return "/static/db/" + dbname + "/files/" + fname
    except:
        return ""


def _currency(this, context, nogroup=False, zero=None):
    if context is None:
        return ""
    try:
        val = float(context)  # in case string
        if zero is not None and abs(val) < 0.0001:
            return zero
        val = "{:0,.2f}".format(val)
        if nogroup:
            val = val.replace(",", "")
        return val
    except:
        return ""


def _compare(this, options, val1, val2, operator="="):
    if operator == "=":
        res = val1 == val2
    elif operator == "!=":
        res = val1 == val2
    elif operator == "<=":
        res = val1 <= val2
    elif operator == ">=":
        res = val1 >= val2
    elif operator == "<":
        res = val1 < val2
    elif operator == ">":
        res = val1 > val2
    elif operator == "in":
        res = val1 in val2
    elif operator == "not in":
        res = val1 not in val2
    else:
        raise Exception("Invalid operator: '%s'" % operator)
    if res:
        return options['fn'](this)
    else:
        return options['inverse'](this)


def _ifeq(this, options, val1, val2):
    if val1 == val2:
        return options['fn'](this)
    else:
        return options['inverse'](this)


def _change_lang_url(this, lang):  # FIXME
    return "/ecom_index?set_lang=%s" % lang


def _if_match(this, options, val, pattern):
    if not val:
        val = ""
    exp = pattern.replace("%", ".*")
    if re.match(exp, val):
        return options['fn'](this)
    else:
        return options['inverse'](this)


def _first(this, options, items):
    if not items:
        return ""
    item = items[0]
    return options['fn'](item)


def _after_first(this, options, items):
    html = strlist()
    for item in items[1:]:
        html.grow(options["fn"](item))
    return html


def _translate(this, val):
    return _(val)


def _padding(this, val):
    if not val:
        return ""
    return "-" + " " * int(val / 10)  # XXX


def remove_zeros(s):
    z = 0
    while s[-1 - z] == "0":
        z += 1
    if s[-1 - z] == ".":
        z += 1
    if z:
        s = s[:-z]
    return s


def _fmt_ths_qty(this, val):
    if val is None:
        return ""
    return "{:0,.0f}".format(val)


def _fmt_qty(this, val):
    if val is None:
        return ""
    try:
        val = float(val)  # in case string
        return remove_zeros("%.6f" % val)
    except:
        return "ERR"


def _fmt_number(this, val):
    if val is None:
        return ""
    try:
        val = float(val)  # in case string
        return remove_zeros("%.6f" % val)
    except:
        return "ERR"


def _filename(this, val):
    if val is None:
        return ""
    try:
        name, ext = os.path.splitext(val)
        name2 = name.rsplit(",")[0]
        return name2 + ext
    except:
        return val


def _lookup(this, o, *inds):
    v = resolve(o, *inds)
    if not v:
        return ""
    return str(v)


def _if_lookup(this, options, o, *inds):
    v = resolve(o, *inds)
    if v:
        return options['fn'](this)
    else:
        return options['inverse'](this)


def _unless_lookup(this, options, o, *inds):
    v = resolve(o, *inds)
    if not v:
        return options['fn'](this)


def _length(this, val):
    if val is None:
        return ""
    return len(val)


def _unless_eq(this, options, val1, val2):
    if val1 != val2:
        return options['fn'](this)


def _ldelim(this):
    return "{{"


def _rdelim(this):
    return "}}"


def _fmt_date(this, val, fmt=None):
    if not val:
        return None
    try:
        d = datetime.datetime.strptime(val[:10], "%Y-%m-%d")
        settings = get_model("settings").browse(1)  # FIXME: speed
        if not fmt:
            fmt = settings.date_format
            if fmt:
                fmt = fmt.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
            else:
                fmt = "%Y-%m-%d"
        s = d.strftime(fmt)
    except:
        print("Cannot convert date format for %s" % val)
        s = val
    return s

def _fmt_datetime(this, val, fmt=None):
    if not val:
        return None
    try:
        d = datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        settings = get_model("settings").browse(1)  # FIXME: speed
        if not fmt:
            fmt = settings.date_format
            if fmt:
                fmt = fmt.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
            else:
                fmt = "%Y-%m-%d"
            fmt+=" %H:%M:%S"
        s = d.strftime(fmt)
    except:
        print("Cannot convert datetime format for %s" % val)
        s = val
    return s

def _fmt_bool(this, val):
    if val:
        return "Yes"
    return "No"


def _col_if(this, val):
    if val:
        return ""
    else:
        return "[[HIDE_COL]]"

if barcode:
    class NFBarWriter(ImageWriter):

        def calculate_size(self, *args, **kw):
            self.text = ""  # XXX
            if self.custom_module_height:
                self.module_height = self.custom_module_height
            return ImageWriter.calculate_size(self, *args, **kw)


def _barcode(this, val, height=None, type="code39", add_checksum=False):
    if not barcode:
        return ""
    if not val:
        return ""
    try:
        bar_cls = barcode.get_barcode_class(type)
        writer = NFBarWriter()
        writer.custom_module_height = height
        if type == "code39":
            bar = bar_cls(str(val), writer=writer, add_checksum=add_checksum)
        else:
            bar = bar_cls(str(val), writer=writer)
        _, fname = tempfile.mkstemp(suffix=".png", prefix="barcode-")
        fullname = bar.save(fname.replace(".png", ""))
        return fullname
    except Exception as e:
        print("WARNING: failed to generate barcode: %s (%s)" % (val, e))
        return ""

_acc_bal_cache = {}


def get_all_balances(date_from=None, date_to=None, track1=None, track2=None):
    t = time.time()
    k = (date_from, date_to, track1, track2)
    if k in _acc_bal_cache:
        res, res_t = _acc_bal_cache[k]
        if t - res_t <= 10:
            print("cache hit", k)
            return res
    print("cache miss", k)
    if track1:
        res = get_model("account.track.categ").search([["code", "=", track1]])
        if not res:
            raise Exception("Invalid tracking category: %s" % track1)
        track_id = res[0]
    else:
        track_id = None
    if track2:
        res = get_model("account.track.categ").search([["code", "=", track2]])
        if not res:
            raise Exception("Invalid tracking category: %s" % track2)
        track2_id = res[0]
    else:
        track2_id = None
    ctx = {
        "date_from": date_from,
        "date_to": date_to,
        "track_id": track_id,
        "track2_id": track2_id,
    }
    res = get_model("account.account").search_read([["type", "!=", "view"]], ["code", "balance"], context=ctx)
    _acc_bal_cache[k] = (res, t)
    return res


def _acc_balance(this, acc_from=None, acc_to=None, date_from=None, date_to=None, track1=None, track2=None, negate=False):
    print("_acc_balance", acc_from, acc_to, date_from, date_to, track1, track2)
    res = get_all_balances(date_from=date_from, date_to=date_to, track1=track1, track2=track2)
    bal = 0
    for r in res:
        if r["code"] >= acc_from and r["code"] <= acc_to:
            bal += r["balance"]
    if negate:
        return -bal
    return bal


def _editable_field(this, name, text_only=False):
    obj = this.context
    model = obj["_model"]
    m = get_model(model)
    f = m._fields[name]
    val = obj[name]  # XXX
    if isinstance(f, fields.Char):
        field_type = "char"
    elif isinstance(f, fields.Text):
        field_type = "text"
    elif isinstance(f, fields.Float):
        field_type = "float"
    else:
        raise Exception("Unsupported editable field: %s.%s" % (model, name))
    html = '<div class="nf-editable" data-model="%s" data-field="%s" data-type="%s" data-id="%s"' % (
        model, name, field_type, obj["id"])
    if text_only:
        html += ' data-text-only="1"'
    html += '>%s</div>' % val
    return html


def _editable_block(this, options, name, page_id=None, post_id=None):
    block = get_model("cms.block").get_block(name, page_id=page_id, post_id=post_id)
    if block:
        out = '<div class="nf-editable" data-model="cms.block" data-field="html" data-type="text" data-id="%s">%s</div>' % (
            block["id"], block["html"])
    else:
        html = options['fn'](this)
        defaults = {
            "name": name,
        }
        if page_id:
            defaults["page_id"] = page_id
        if post_id:
            defaults["post_id"] = post_id
        out = '<div class="nf-editable" data-model="cms.block" data-field="html" data-type="text" data-defaults=\'%s\'>%s</div>' % (
            json.dumps(defaults), html)
    return out


def _if_perm(this, options, perm):
    if access.check_permission_other(perm):
        return options['fn'](this)
    else:
        return options['inverse'](this)


def _odt_linebreak(this, val):
    if val is None:
        return ""
    val = str(val)
    val = saxutils.escape(val)
    return val.replace("\n", "<text:line-break></text:line-break>")

_globals_ = {
    'helpers': {
        'blockHelperMissing': _blockHelperMissing,
        'paginate': _paginate,
        'each': _each,
        'if': _if,
        'helperMissing': _helperMissing,
        'log': _log,
        'unless': _unless,
        'with': _with,
        "file_path": _file_path,
        "currency": _currency,
        "change_lang_url": _change_lang_url,
        'compare': _compare,
        'ifeq': _ifeq,
        'if_match': _if_match,
        't': _translate,
        'padding': _padding,
        'fmt_qty': _fmt_qty,
        'fmt_ths_qty': _fmt_ths_qty,
        'fmt_number': _fmt_number,
        'fmt_date': _fmt_date,
        'fmt_datetime': _fmt_datetime,
        'fmt_bool': _fmt_bool,
        'filename': _filename,
        'first': _first,
        'after_first': _after_first,
        "lookup": _lookup,
        "if_lookup": _if_lookup,
        "unless_lookup": _unless_lookup,
        "length": _length,
        "unless_eq": _unless_eq,
        "ldelim": _ldelim,
        "rdelim": _rdelim,
        "col_if": _col_if,
        #"acc_balance": _acc_balance, # XXX: move this
        "editable_field": _editable_field,
        "editable_block": _editable_block,
        "if_perm": _if_perm,
        "barcode": _barcode,
        "odt_linebreak": _odt_linebreak,
    },
}

def register_helper(name,func):
    _globals_["helpers"][name]=func

class CodeBuilder:

    def __init__(self):
        self.stack = []
        self.blocks = {}

    def start(self):
        self._result = strlist()
        self.stack.append((self._result, "render"))
        self._result.grow("def render(context, helpers=None, partials=None):\n")
        self._result.grow("    result = strlist()\n")
        self._result.grow("    _helpers = dict(_globals_['helpers'])\n")
        self._result.grow("    if helpers is not None: _helpers.update(helpers)\n")
        self._result.grow("    helpers = _helpers\n")
        self._result.grow("    if partials is None: partials = {}\n")

    def finish(self):
        self._result.grow("    return result\n")
        source = "from netforce.hbs_compiler import strlist,escape,Scope,partial,_globals_,resolve\n\n"
        for name, lines in reversed(sorted(self.blocks.items())):
            source += "".join(lines) + "\n"
        lines = self._result
        source += "".join(lines)
        return source

    def start_block(self):
        name = "render_block%d" % len(self.blocks)
        self._result = strlist()
        self.blocks[name] = self._result
        self.stack.append((self._result, name))
        self._result.grow("def %s(context, helpers=None, partials=None):\n" % name)
        self._result.grow("    result = strlist()\n")
        self._result.grow("    _helpers = dict(_globals_['helpers'])\n")
        self._result.grow("    if helpers is not None: _helpers.update(helpers)\n")
        self._result.grow("    helpers = _helpers\n")
        self._result.grow("    if partials is None: partials = {}\n")

    def finish_block(self):
        self._result.grow("    return result\n")
        name = self.stack.pop(-1)[1]
        self._result = self.stack and self.stack[-1][0]
        return name

    def add_block(self, symbol, arguments, name, alt_name):
        call = self.arguments_to_call(arguments)
        self._result.grow([
            "    options = {'fn': %s}\n" % name,
            "    options['helpers'] = helpers\n"
            "    options['partials'] = partials\n"
        ])
        if alt_name:
            self._result.grow(["    options['inverse'] = %s\n" % alt_name])
        else:
            self._result.grow([
                "    options['inverse'] = lambda this: None\n"
            ])
        self._result.grow([
            "    value = helper = helpers.get('%s')\n" % symbol,
            "    if value is None:\n"
            "        value = context.get('%s')\n" % symbol,
            "    if helper and callable(helper):\n"
            "        this = Scope(context, context)\n"
            "        value = value(this, options, %s\n" % call,
            "    else:\n"
            "        helper = helpers['blockHelperMissing']\n"
            "        value = helper(context, options, value)\n"
            "    if value is None: value = ''\n"
            "    result.grow(value)\n"
        ])

    def add_literal(self, value):
        self._result.grow("    result.append(%r)\n" % value)

    def _lookup_arg(self, arg):
        if not arg:
            return "context"
        return arg

    def arguments_to_call(self, arguments):
        params = list(map(self._lookup_arg, arguments))
        return ", ".join(params) + ")"

    def find_lookup(self, path, path_type, call):
        if path and path_type == "simple":  # simple names can reference helpers.
            # TODO: compile this whole expression in the grammar; for now,
            # fugly but only a compile time overhead.
            # XXX: just rm.
            realname = path.replace('.get("', '').replace('")', '')
            self._result.grow([
                "    value = helpers.get('%s')\n" % realname,
                "    if value is None:\n"
                "        value = resolve(context, '%s')\n" % path,
            ])
        elif path_type == "simple":
            realname = None
            self._result.grow([
                "    value = resolve(context, '%s')\n" % path,
            ])
        else:
            realname = None
            self._result.grow("    value = %s\n" % path)
        self._result.grow([
            "    if callable(value):\n"
            "        this = Scope(context, context)\n"
            "        value = value(this, %s\n" % call,
        ])
        if realname:
            self._result.grow(
                "    elif value is None:\n"
                "        this = Scope(context, context)\n"
                "        value = helpers.get('helperMissing')(this, '%s', %s\n"
                % (realname, call)
            )
        self._result.grow("    if value is None: value = ''\n")

    def add_escaped_expand(self, path_type_path, arguments):
        (path_type, path) = path_type_path
        call = self.arguments_to_call(arguments)
        self.find_lookup(path, path_type, call)
        self._result.grow([
            "    if type(value) is not strlist:\n",
            "        value = escape(str(value))\n",
            "    result.grow(value)\n"
        ])

    def add_expand(self, path_type_path, arguments):
        (path_type, path) = path_type_path
        call = self.arguments_to_call(arguments)
        self.find_lookup(path, path_type, call)
        self._result.grow([
            "    if type(value) is not strlist:\n",
            "        value = str(value)\n",
            "    result.grow(value)\n"
        ])

    def _debug(self):
        self._result.grow("    import pdb;pdb.set_trace()\n")

    def add_invertedblock(self, symbol, arguments, name):
        self._result.grow([
            "    value = context.get('%s')\n" % symbol,
            "    if not value:\n"
            "    "])
        self._invoke_template(name, "context")

    def _invoke_template(self, fn_name, this_name):
        self._result.grow([
            "    result.grow(",
            fn_name,
            "(",
            this_name,
            ", helpers=helpers, partials=partials))\n"
        ])

    def add_partial(self, symbol, arguments):
        if arguments:
            assert len(arguments) == 1, arguments
            arg = arguments[0]
        else:
            arg = ""
        self._result.grow([
            "    inner = partials['%s']\n" % symbol,
            "    scope = Scope(%s, context)\n" % self._lookup_arg(arg)])
        self._invoke_template("inner", "scope")


class Compiler:
    _handlebars = OMeta.makeGrammar(handlebars_grammar, {}, 'handlebars')
    _builder = CodeBuilder()
    _compiler = OMeta.makeGrammar(compile_grammar, {'builder': _builder})

    def __init__(self):
        self._helpers = {}

    def compile(self, source):
        self._builder.stack = []
        self._builder.blocks = {}
        print("compile step 1...")
        tree, err = self._handlebars(source).apply('template')
        if err.error:
            raise Exception(err.formatError(source))
        print("compile step 2...")
        code, err = self._compiler(tree).apply('compile')
        if err.error:
            raise Exception(err.formatError(tree))
        return code
