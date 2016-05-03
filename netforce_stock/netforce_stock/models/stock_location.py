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
from netforce import database
import datetime
import time
from netforce.access import get_active_company
from pprint import pprint


class Location(Model):
    _name = "stock.location"
    _name_field = "name"
    #_key = ["code"]
    _string = "Location"
    _multi_company = True
    _fields = {
        "name": fields.Char("Location Name", required=True, search=True, size=256),
        "code": fields.Char("Location Code", search=True),
        "type": fields.Selection([["internal", "Internal"], ["customer", "Customers"], ["supplier", "Suppliers"], ["inventory", "Inventory Loss"], ["production", "Production"], ["transform", "Transform"], ["view", "View"], ["other", "Other"]], "Type", required=True, search=True),
        "account_id": fields.Many2One("account.account", "Inventory Account", multi_company=True, search=True),
        "track_id": fields.Many2One("account.track.categ", "Tracking Category", search=True),
        "balance": fields.Decimal("Inventory Cost", function="get_balance"),
        "active": fields.Boolean("Active"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "products": fields.One2Many("stock.balance", "location_id", "Product Stock"),
        "stock_moves": fields.One2Many("stock.move", None, "Stock Moves", condition='["or",["location_from_id","=",id],["location_to_id","=",id]]'),
        "description": fields.Text("Description"),
        "balance_90d": fields.Json("Balance 90d", function="get_balance_90d"),
        "parent_id": fields.Many2One("stock.location", "Parent Location", condition=[["type", "=", "view"]]),
        "company_id": fields.Many2One("company", "Company"),
        "contact_id": fields.Many2One("contact", "Contact"),
        "company2_id": fields.Many2One("company", "Company #2"),
    }
    _order = "name"
    _defaults = {
        "active": True,
        "company_id": lambda *a: get_active_company(),
    }

    def get_balance(self, ids, context={}):
        db = database.get_connection()
        q = "SELECT location_from_id,location_to_id,SUM(cost_amount) AS amount FROM stock_move WHERE (location_from_id IN %s OR location_to_id IN %s) AND state='done'"
        args = [tuple(ids), tuple(ids)]
        if context.get("date_to"):
            q += " AND date<=%s"
            args.append(context["date_to"] + " 23:59:59")
        q += " GROUP BY location_from_id,location_to_id"
        res = db.query(q, *args)
        vals = {id: 0 for id in ids}
        for r in res:
            if r.location_from_id in vals:
                vals[r.location_from_id] -= r.amount or 0
            if r.location_to_id in vals:
                vals[r.location_to_id] += r.amount or 0
        return vals

    def get_balance_90d(self, ids, context={}, nocache=False):
        if not nocache:
            min_ctime = time.strftime("%Y-%m-%d 00:00:00")
            vals = get_model("field.cache").get_value("stock.location", "balance_90d", ids, min_ctime=min_ctime)
            remain_ids = [id for id in ids if id not in vals]
            if remain_ids:
                res = self.get_balance_90d(remain_ids, context=context, nocache=True)
                for id, data in res.items():
                    vals[id] = data
                    get_model("field.cache").set_value("stock.location", "balance_90d", id, data)
            return vals
        print("#########################################################################")
        print("location.get_balance_90d CACHE MISS", ids)
        date_from = datetime.date.today() - datetime.timedelta(days=90)
        date_to = datetime.date.today()
        db = database.get_connection()
        vals = {}
        for id in ids:
            balance = self.get_balance([id], context={"date_to": date_from.strftime("%Y-%m-%d")})[id]
            q = "SELECT date,location_from_id,location_to_id,cost_amount FROM stock_move WHERE (location_from_id=%s OR location_to_id=%s) AND date>%s AND date<=%s AND state='done' ORDER BY date"
            res = db.query(q, id, id, date_from.strftime("%Y-%m-%d 23:59:59"), date_to.strftime("%Y-%m-%d 23:59:59"))
            d = date_from
            data = []
            for r in res:
                while d.strftime("%Y-%m-%d 23:59:59") < r.date:
                    data.append([time.mktime(d.timetuple()) * 1000, balance])
                    d += datetime.timedelta(days=1)
                if r.location_to_id == id and r.location_from_id != id:
                    balance += r.cost_amount or 0
                elif r.location_from_id == id and r.location_to_id != id:
                    balance -= r.cost_amount or 0
            while d <= date_to:
                data.append([time.mktime(d.timetuple()) * 1000, balance])
                d += datetime.timedelta(days=1)
            vals[id] = data
        return vals

    def compute_balance(self, ids, product_id, date=None, lot_id=None, container_id=None, uom_id=None):
        print("compute_balance", ids, product_id, date)
        prod = get_model("product").browse(product_id)
        if not uom_id:
            uom_id = prod.uom_id.id
        db = database.get_connection()
        q = "SELECT uom_id,SUM(qty) AS total_qty,SUM(cost_amount) AS total_amount,SUM(qty2) AS total_qty2 FROM stock_move WHERE location_to_id IN %s AND product_id=%s AND state='done'"
        args = [tuple(ids), product_id]
        if date:
            q += " AND date<=%s"
            args.append(date)
        if lot_id:
            q += " AND lot_id=%s"
            args.append(lot_id)
        if container_id:
            q += " AND container_to_id=%s"
            args.append(container_id)
        q += " GROUP BY uom_id"
        res = db.query(q, *args)
        in_qty = 0
        in_amount = 0
        in_qty2 = 0
        for r in res:
            qty = get_model("uom").convert(r.total_qty, r.uom_id, uom_id)
            in_qty += qty
            in_amount += r.total_amount or 0
            in_qty2 += r.total_qty2 or 0
        q = "SELECT uom_id,SUM(qty) AS total_qty,SUM(cost_amount) AS total_amount,SUM(qty2) AS total_qty2 FROM stock_move WHERE location_from_id IN %s AND product_id=%s AND state='done'"
        args = [tuple(ids), product_id]
        if date:
            q += " AND date<=%s"
            args.append(date)
        if lot_id:
            q += " AND lot_id=%s"
            args.append(lot_id)
        if container_id:
            q += " AND container_from_id=%s"
            args.append(container_id)
        q += " GROUP BY uom_id"
        res = db.query(q, *args)
        out_qty = 0
        out_amount = 0
        out_qty2 = 0
        for r in res:
            qty = get_model("uom").convert(r.total_qty, r.uom_id, uom_id)
            out_qty += qty
            out_amount += r.total_amount or 0
            out_qty2 += r.total_qty2 or 0
        return {
            "bal_qty": in_qty - out_qty,
            "bal_amount": in_amount - out_amount,
            "bal_qty2": in_qty2 - out_qty2,
        }

    def get_contents(self, ids, context={}):
        print("location.get_contents", ids)
        t0 = time.time()
        obj = self.browse(ids)[0]  # XXX
        date_to = context.get("date")
        product_categ_id = context.get("product_categ_id")
        if product_categ_id:
            # Categs deprecated
            product_ids = get_model("product").search([["categs.id", "=", product_categ_id]])
            prod_ids = get_model("product").search([["categ_id", "=", product_categ_id]])
            product_ids = list(set(product_ids + prod_ids))
        else:
            product_ids = None
        tots = get_model("stock.balance").get_totals(product_ids=product_ids, location_ids=[obj.id], date_to=date_to)
        prod_tots = {}

        def get_sum(prod, lot=None, loc_from=None, loc_to=None, cont_from=None, cont_to=None):
            tot_qty = 0
            tot_amt = 0
            tot_qty2 = 0
            for (lot_id, loc_from_id, cont_from_id, loc_to_id, cont_to_id), (qty, amt, qty2) in prod_tots[prod].items():
                if (lot and lot_id != lot) or (not lot and lot_id):
                    continue
                if loc_from and loc_from_id != loc_from:
                    continue
                if loc_to and loc_to_id != loc_to:
                    continue
                if cont_from and cont_from_id != cont_from:
                    continue
                if cont_to and cont_to_id != cont_to:
                    continue
                tot_qty += qty
                tot_amt += amt
                tot_qty2 += qty2 or 0
            return tot_qty, tot_amt, tot_qty2
        prod_locs = set()
        for (prod_id, lot_id, loc_from_id, cont_from_id, loc_to_id, cont_to_id), (qty, amt, qty2) in tots.items():
            prod_locs.add((prod_id, lot_id, loc_from_id, cont_from_id))
            prod_locs.add((prod_id, lot_id, loc_to_id, cont_to_id))
            prod_tots.setdefault(
                prod_id, {})[(lot_id, loc_from_id, cont_from_id, loc_to_id, cont_to_id)] = (qty, amt, qty2)
        print("num prod_locs:", len(prod_locs))
        contents = {}
        for prod_id, lot_id, loc_id, cont_id in prod_locs:
            if loc_id != obj.id:
                continue
            qty_in, amt_in, qty2_in = get_sum(prod=prod_id, lot=lot_id, loc_to=loc_id, cont_to=cont_id)
            qty_out, amt_out, qty2_out = get_sum(prod=prod_id, lot=lot_id, loc_from=loc_id, cont_from=cont_id)
            qty = qty_in - qty_out
            amt = amt_in - amt_out
            qty2 = qty2_in - qty2_out
            if qty <= 0:
                continue
            contents[(prod_id, lot_id, cont_id)] = (qty, amt, qty2)
        t1 = time.time()
        print("get_contents finished in %d ms" % ((t1 - t0) * 1000))
        return contents

Location.register()
