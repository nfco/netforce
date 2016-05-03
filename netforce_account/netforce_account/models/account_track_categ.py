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

from netforce.model import Model, fields, get_model
import time
from netforce import database
import datetime


class TrackCateg(Model):
    _name = "account.track.categ"
    _string = "Tracking Category"
    _key = ["code"]
    _fields = {
        "name": fields.Char("Name", required=True),
        "parent_id": fields.Many2One("account.track.categ", "Parent"),
        "full_name": fields.Char("Full Name", function="get_full_name", search=True, store=True),
        "code": fields.Char("Code", required=True,search=True),
        "description": fields.Text("Description"),
        "type": fields.Selection([["1", "Primary"], ["2", "Secondary"]], "Type", required=True,search=True),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "track_entries": fields.One2Many("account.track.entry","track_id","Tracking Entries"),
        "balance": fields.Decimal("Tracking Balance",function="get_balance"),
        "sub_tracks": fields.One2Many("account.track.categ","parent_id","Sub Tracking Categories"),
        "self_id": fields.Many2One("account.track.categ","Tracking Category",function="_get_related",function_context={"path":"id"}), # XXX: for some UI stuff
        "currency_id": fields.Many2One("currency","Currency"),
        # XXX: Multi company ?
    }
    _order = "type,code,full_name"
    _constraints = ["_check_cycle"]

    def name_search(self, name, condition=[], limit=None, context={}):
        cond = [["or", ["name", "ilike", "%" + name + "%"], ["code", "ilike", "%" + name + "%"]], condition]
        ids = self.search(cond, limit=limit)
        return self.name_get(ids, context)

    def name_get(self, ids, context={}):
        vals = []
        for obj in self.browse(ids):
            name = "[%s] %s" % (obj.code, obj.name)
            vals.append((obj.id, name))
        return vals

    def create(self, vals, **kw):
        new_id = super().create(vals, **kw)
        self.function_store([new_id])
        return new_id

    def write(self, ids, vals, **kw):
        super().write(ids, vals, **kw)
        child_ids = self.search(["id", "child_of", ids])
        self.function_store(child_ids)

    def get_full_name(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            names = [obj.name or ""]
            p = obj.parent_id
            while p:
                names.append(p.name or "")
                p = p.parent_id
            full_name = " / ".join(reversed(names))
            vals[obj.id] = full_name
        return vals

    def get_balance(self,ids,context={}):
        print("account.track.categ get_balance")
        db=database.get_connection()
        child_ids=self.search([["id","child_of",ids]])
        print("child_ids",child_ids)
        res=db.query("SELECT track_id,SUM(amount) AS total FROM account_track_entry WHERE track_id IN %s GROUP BY track_id",tuple(child_ids))
        totals={}
        for r in res:
            totals[r.track_id]=r.total
        res=db.query("SELECT id,parent_id FROM account_track_categ WHERE id IN %s",tuple(child_ids))
        sub_ids={}
        for r in res:
            sub_ids.setdefault(r.parent_id,[])
            sub_ids[r.parent_id].append(r.id)
        def _get_total(track_id):
            amt=totals.get(track_id,0)
            for child_id in sub_ids.get(track_id,[]):
                amt+=_get_total(child_id)
            return amt
        vals={}
        for obj in self.browse(ids):
            vals[obj.id]=_get_total(obj.id)
        return vals

TrackCateg.register()
