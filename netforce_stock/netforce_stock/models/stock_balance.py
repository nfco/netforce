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
from datetime import *
import time
from netforce import access
import math

class StockBalance(Model):
    _name = "stock.balance"
    _string = "Stock Balance"
    _fields = {
        "product_id": fields.Many2One("product", "Product", required=True, search=True),
        "lot_id": fields.Many2One("stock.lot", "Lot / Serial Number", search=True),
        "location_id": fields.Many2One("stock.location", "Location", required=True, search=True),
        "container_id": fields.Many2One("stock.container", "Container", search=True),
        "qty_phys": fields.Decimal("Physical Qty", required=True),
        "qty_virt": fields.Decimal("Virtual Qty", required=True),
        "uom_id": fields.Many2One("uom", "UoM", required=True),
        "min_qty": fields.Decimal("Min Qty"),
        "below_min": fields.Boolean("Below Min", search=True),
        "amount": fields.Decimal("Amount"),
        "last_change": fields.DateTime("Last Change"),
        "supplier_id": fields.Many2One("contact", "Supplier", store=False, search=True, function_search="search_supplier"),
        "qty2": fields.Decimal("Secondary Qty"),
    }
    _order = "product_id.code,location_id"
    _sql_constraints = [
        ("prod_loc_uniq", "unique (product_id, location_id, lot_id, container_id)",
         "Stock balances must have unique products and locations!"),
    ]

    def read(self, *a, **kw):
        self.update_balances()
        res = super().read(*a, **kw)
        return res

    def search(self, *a, **kw):
        self.update_balances()
        res = super().search(*a, **kw)
        return res

    def update_balances(self, context={}):
        print("UPDATE_BALANCES")
        user_id=access.get_active_user()
        access.set_active_user(1)
        try:
            db = database.get_connection()
            prod_ids = get_model("product").search(
                [["update_balance", "=", True], ["type", "=", "stock"]], context={"active_test": False})  # XXX
            if not prod_ids:
                return
            print("prod_ids", prod_ids)
            db.execute("LOCK stock_balance IN EXCLUSIVE MODE")
            db.execute("DELETE FROM stock_balance WHERE product_id IN %s", tuple(prod_ids))
            loc_ids = get_model("stock.location").search([["type", "=", "internal"]])
            if not loc_ids:
                return
            prod_uoms = {}
            res = db.query("SELECT id,uom_id FROM product WHERE id IN %s", tuple(prod_ids))
            for r in res:
                prod_uoms[r.id] = r.uom_id
            min_qtys = {}
            res = db.query(
                "SELECT location_id,product_id,min_qty,uom_id FROM stock_orderpoint WHERE product_id IN %s", tuple(prod_ids))
            for r in res:
                min_qtys[(r.location_id, r.product_id)] = (r.min_qty, r.uom_id)
            qtys = {}
            res = db.query(
                "SELECT location_to_id,container_to_id,product_id,lot_id,uom_id,state,sum(qty) AS total_qty,sum(cost_amount) AS total_amt,max(date) AS max_date,SUM(qty2) AS total_qty2 FROM stock_move WHERE product_id IN %s AND location_to_id IN %s AND state IN ('pending','approved','done') GROUP BY location_to_id,container_to_id,product_id,lot_id,uom_id,state", tuple(prod_ids), tuple(loc_ids))
            for r in res:
                qtys.setdefault((r.location_to_id, r.container_to_id, r.product_id, r.lot_id), []).append(
                    ("in", r.total_qty, r.total_amt or 0, r.uom_id, r.state, r.max_date, r.total_qty2 or 0))
            res = db.query(
                "SELECT location_from_id,container_from_id,product_id,lot_id,uom_id,state,sum(qty) AS total_qty,sum(cost_amount) AS total_amt,max(date) AS max_date,SUM(qty2) AS total_qty2 FROM stock_move WHERE product_id IN %s AND location_from_id IN %s AND state IN ('pending','approved','done') GROUP BY location_from_id,container_from_id,product_id,lot_id,uom_id,state", tuple(prod_ids), tuple(loc_ids))
            for r in res:
                qtys.setdefault((r.location_from_id, r.container_from_id, r.product_id, r.lot_id), []).append(
                    ("out", r.total_qty, r.total_amt or 0, r.uom_id, r.state, r.max_date, r.total_qty2 or 0))
            bals = {}
            prod_loc_qtys = {}
            for (loc_id, cont_id, prod_id, lot_id), totals in qtys.items():
                last_change = None
                for type, qty, amt, uom_id, state, max_date, qty2 in totals:
                    last_change = last_change and max(max_date, last_change) or max_date
                res = min_qtys.get((loc_id, prod_id))
                if res:
                    min_qty, min_uom_id = res
                else:
                    min_qty = 0
                    min_uom_id = None
                bal_uom_id = prod_uoms[prod_id]
                state_qtys = {}
                state_amts = {}
                state_qtys2 = {}
                for type, qty, amt, uom_id, state, max_date, qty2 in totals:
                    state_qtys.setdefault(state, 0)
                    state_amts.setdefault(state, 0)
                    state_qtys2.setdefault(state, 0)
                    qty_conv = get_model("uom").convert(qty, uom_id, bal_uom_id)
                    if type == "in":
                        state_qtys[state] += qty_conv
                        state_amts[state] += amt
                        state_qtys2[state] += qty2
                    elif type == "out":
                        state_qtys[state] -= qty_conv
                        state_amts[state] -= amt
                        state_qtys2[state] -= qty2
                qty_virt = state_qtys.get("done", 0) + state_qtys.get("pending", 0) + state_qtys.get("approved", 0)
                bals[(loc_id, cont_id, prod_id, lot_id)] = {
                    "qty_phys": state_qtys.get("done", 0),
                    "qty_virt": qty_virt,
                    "amt": state_amts.get("done", 0),
                    "last_change": last_change,
                    "uom_id": bal_uom_id,
                    "min_qty": min_qty and get_model("uom").convert(min_qty, min_uom_id, bal_uom_id) or 0,
                    "qty2": state_qtys2.get("done", 0),
                }
                prod_loc_qtys.setdefault((loc_id, prod_id), 0)
                prod_loc_qtys[(loc_id, prod_id)] += qty_virt
            for (loc_id, prod_id), (min_qty, uom_id) in min_qtys.items():
                if (loc_id, prod_id) not in prod_loc_qtys:
                    bals[(loc_id, None, prod_id, None)] = {
                        "qty_phys": 0,
                        "qty_virt": 0,
                        "amt": 0,
                        "min_qty": min_qty,
                        "uom_id": uom_id,
                        "last_change": None,
                        "qty2": 0,
                    }
            parent_locs = {}
            for loc in get_model("stock.location").search_browse([["parent_id", "!=", None]]):
                parent_locs[loc.id] = loc.parent_id.id
            for (loc_id, cont_id, prod_id, lot_id), bal_vals in list(bals.items()):
                child_id = loc_id
                while True:
                    parent_id = parent_locs.get(child_id)
                    if not parent_id:
                        break
                    k = (parent_id, cont_id, prod_id, lot_id)
                    if k not in bals:
                        bals[k] = {
                            "qty_phys": 0,
                            "qty_virt": 0,
                            "amt": 0,
                            "min_qty": 0,
                            "uom_id": prod_uoms[prod_id],
                            "last_change": None,
                            "qty2": 0,
                        }
                    parent_vals = bals[k]
                    parent_vals["qty_phys"] += bal_vals["qty_phys"]
                    parent_vals["qty_virt"] += bal_vals["qty_virt"]
                    parent_vals["amt"] += bal_vals["amt"]
                    parent_vals["min_qty"] += bal_vals["min_qty"]
                    if bal_vals["last_change"] and (not parent_vals["last_change"] or parent_vals["last_change"] < bal_vals["last_change"]):
                        parent_vals["last_change"] = bal_vals["last_change"]
                    parent_vals["qty2"] += bal_vals["qty2"]
                    child_id = parent_id
            total_virt_qtys={}
            for (loc_id, cont_id, prod_id, lot_id), bal_vals in bals.items():
                total_virt_qtys.setdefault(prod_id,0)
                total_virt_qtys[prod_id]+=bal_vals["qty_virt"]
            below_prods=set()
            for prod_id,qty_virt in total_virt_qtys.items():
                if qty_virt<0: # XXX: take into account min stock rules
                    below_prods.add(prod_id)
            for (loc_id, cont_id, prod_id, lot_id), bal_vals in bals.items():
                bal_vals["below_min"]=prod_id in below_prods
            for (loc_id, cont_id, prod_id, lot_id), bal_vals in bals.items():
                qty_phys = bal_vals["qty_phys"]
                qty_virt = bal_vals["qty_virt"]
                qty2 = bal_vals["qty2"]
                amt = bal_vals["amt"]
                min_qty = bal_vals["min_qty"]
                if qty_phys == 0 and qty_virt == 0 and min_qty == 0 and amt == 0:
                    continue
                prod_loc_qty = prod_loc_qtys.get((loc_id, prod_id), 0)
                below_min = bal_vals["below_min"]
                uom_id = bal_vals["uom_id"]
                last_change = bal_vals["last_change"]
                db.execute("INSERT INTO stock_balance (location_id,container_id,product_id,lot_id,qty_phys,qty_virt,amount,min_qty,uom_id,below_min,last_change,qty2) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                           loc_id, cont_id, prod_id, lot_id, qty_phys, qty_virt, amt, min_qty, uom_id, below_min, last_change, qty2)
            get_model("product").write(prod_ids, {"update_balance": False})
        finally:
            access.set_active_user(user_id)

    def get_qty_phys(self, location_id, product_id, lot_id):
        cond=[["location_id", "=", location_id], ["product_id", "=", product_id]]
        if lot_id: 
            cond.append(["lot_id","=",lot_id])
        qty=0
        for bal in self.search_browse(cond):
            qty+=bal.qty_phys
        return qty

    def get_unit_price(self, location_id, product_id):
        res = self.search([["location_id", "=", location_id], ["product_id", "=", product_id]])
        if not res:
            return 0
        obj = self.browse(res)[0]
        if obj.qty_phys:
            unit_price = obj.amount / obj.qty_phys
        else:
            unit_price = 0
        return unit_price

    def get_prod_qty(self, product_id, loc_type="internal"):
        ids = self.search([["location_id.type", "=", loc_type], ["product_id", "=", product_id]])
        qty = 0
        for obj in self.browse(ids):
            qty += obj.qty_phys
        return qty

    def make_po(self, ids, context={}):
        suppliers = {}
        for obj in self.browse(ids):
            if obj.qty_virt >= obj.min_qty:
                continue
            prod = obj.product_id
            if prod.supply_method!="purchase":
                raise Exception("Supply method for product %s is not set to 'Purchase'"%prod.code)
            res = get_model("stock.orderpoint").search([["product_id", "=", prod.id]])
            if res:
                op = get_model("stock.orderpoint").browse(res)[0]
                max_qty = op.max_qty
            else:
                max_qty = 0
            diff_qty = max_qty - obj.qty_virt
            if prod.purchase_uom_id:
                purch_uom=prod.purchase_uom_id
                if not prod.purchase_to_stock_uom_factor:
                    raise Exception("Missing purchase order -> stock uom factor for product %s"%prod.code)
                purch_qty=diff_qty/prod.purchase_to_stock_uom_factor
            else:
                purch_uom=prod.uom_id
                purch_qty=diff_qty
            if prod.purchase_qty_multiple:
                n=math.ceil(purch_qty/prod.purchase_qty_multiple)
                purch_qty=n*prod.purchase_qty_multiple
            if prod.purchase_uom_id:
                qty_stock=purch_qty*prod.purchase_to_stock_uom_factor
            else:
                qty_stock=None
            line_vals = {
                "product_id": prod.id,
                "description": prod.name_get()[0][1],
                "qty": purch_qty,
                "uom_id": purch_uom.id,
                "unit_price": prod.purchase_price or 0,
                "tax_id": prod.purchase_tax_id.id,
                "qty_stock": qty_stock,
            }
            if not prod.suppliers:
                raise Exception("Missing default supplier for product %s" % prod.name)
            contact_id = prod.suppliers[0].supplier_id.id
            suppliers.setdefault(contact_id, []).append(line_vals)
        if not suppliers:
            raise Exception("Nothing to order")
        count = 0
        for contact_id, lines in suppliers.items():
            vals = {
                "contact_id": contact_id,
                "lines": [("create", x) for x in lines],
            }
            purch_id = get_model("purchase.order").create(vals)
            count += 1
        return {
            "next": {
                "name": "purchase",
                "tab": "Draft",
            },
            "flash": "%d purchase orders created" % count,
        }

    def make_transfer(self, ids, context={}):
        if not ids:
            return
        first = self.browse(ids)[0]
        vals = {
            "location_from_id": first.location_id.id,
        }
        lines = []
        for obj in self.browse(ids):
            lines.append({
                "product_id": obj.product_id.id,
                "lot_id": obj.lot_id.id,
                "qty": obj.qty_phys,
                "uom_id": obj.uom_id.id,
                "container_from_id": obj.container_id.id,
                "container_to_id": obj.container_id.id,
            })
        vals["lines"] = [("create", v) for v in lines]
        new_id = get_model("barcode.transfer").create(vals)
        return {
            "next": {
                "name": "barcode_transfer",
                "active_id": new_id,
            },
        }

    def make_issue(self, ids, context={}):
        if not ids:
            return
        first = self.browse(ids)[0]
        vals = {
            "location_from_id": first.location_id.id,
        }
        lines = []
        for obj in self.browse(ids):
            lines.append({
                "product_id": obj.product_id.id,
                "lot_id": obj.lot_id.id,
                "qty": obj.qty_phys,
                "uom_id": obj.uom_id.id,
                "container_from_id": obj.container_id.id,
            })
        vals["lines"] = [("create", v) for v in lines]
        new_id = get_model("barcode.issue").create(vals)
        return {
            "next": {
                "name": "barcode_issue",
                "active_id": new_id,
            },
        }

    def search_supplier(self, clause, context={}):
        supplier_id = clause[2]
        prod_ids = get_model("product").search([['supplier_id','=',supplier_id]])
        return [["product_id", "in", prod_ids]]

    def get_totals(self, product_ids=None, location_ids=None, lot_ids=None, container_ids=None, date_from=None, date_to=None, virt_stock=False):
        print("stock_balance.get_totals product_ids=%s location_ids=%s lot_ids=%s container_ids=%s date_from=%s date_to=%s" % (
            product_ids, location_ids, lot_ids, container_ids, date_from, date_to))
        t0 = time.time()
        q = "SELECT product_id,lot_id,location_from_id,container_from_id,location_to_id,container_to_id,uom_id,SUM(qty) AS total_qty,SUM(cost_amount) AS total_amt,SUM(qty2) AS total_qty2 FROM stock_move WHERE"
        if virt_stock:
            q+=" state in ('pending','approved','done')"
        else:
            q+=" state='done'"
        q_args = []
        if product_ids is not None:
            if product_ids:
                q += " AND product_id IN %s"
                q_args.append(tuple(product_ids))
            else:
                q += " AND false"
        if location_ids is not None:
            if location_ids:
                q += " AND (location_from_id IN %s OR location_to_id IN %s)"
                q_args += [tuple(location_ids), tuple(location_ids)]
            else:
                q += " AND false"
        if lot_ids is not None:
            if lot_ids:
                q += " AND lot_id IN %s"
                q_args.append(tuple(lot_ids))
            else:
                q += " AND false"
        if container_ids is not None:
            if container_ids:
                q += " AND (container_from_id IN %s OR container_to_id IN %s)"
                q_args += [tuple(container_ids), tuple(container_ids)]
            else:
                q += " AND false"
        if date_from:
            q += " AND date>=%s"
            q_args.append(date_from)
        if date_to:
            q += " AND date<=%s"
            q_args.append(date_to)
        q += " GROUP BY product_id,lot_id,location_from_id,container_from_id,location_to_id,container_to_id,uom_id"
        db = database.get_connection()
        res = db.query(q, *q_args)
        totals = {}
        prod_ids = set()
        for r in res:
            prod_ids.add(r.product_id)
        prod_ids = list(prod_ids)
        prod_uoms = {}
        for prod in get_model("product").browse(prod_ids):
            prod_uoms[prod.id] = prod.uom_id.id
        for r in res:
            qty = get_model("uom").convert(r.total_qty, r.uom_id, prod_uoms[r.product_id])
            amt = r.total_amt or 0
            qty2 = r.total_qty2 or 0
            k = (r.product_id, r.lot_id, r.location_from_id, r.container_from_id, r.location_to_id, r.container_to_id)
            tot = totals.setdefault(k, [0, 0, 0])
            tot[0] += qty
            tot[1] += amt
            tot[2] += qty2
        t1 = time.time()
        print("totals size: %d" % len(totals))
        print("get_totals finished in %s ms" % ((t1 - t0) * 1000))
        return totals

    def compute_key_balances(self, keys, context={}):
        print("stock_balance.compute_key_balances", keys)
        t0 = time.time()
        all_prod_ids = set()
        all_loc_ids = set()
        for prod_id, lot_id, loc_id, cont_id in keys:
            all_prod_ids.add(prod_id)
            all_loc_ids.add(loc_id)
        all_prod_ids = list(all_prod_ids)
        all_loc_ids = list(all_loc_ids)
        date_to=context.get("date_to")
        virt_stock=context.get("virt_stock")
        tots = self.get_totals(product_ids=all_prod_ids, location_ids=all_loc_ids, date_to=date_to, virt_stock=virt_stock)
        prod_tots = {}

        def get_sum(prod, lot=None, loc_from=None, loc_to=None, cont_from=None, cont_to=None):
            tot_qty = 0
            tot_amt = 0
            tot_qty2 = 0
            if prod in prod_tots:
                # XXX: can still improve speed
                for (lot_id, loc_from_id, cont_from_id, loc_to_id, cont_to_id), (qty, amt, qty2) in prod_tots[prod].items():
                    if lot and lot_id != lot:
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
                    tot_qty2 += qty2
            return tot_qty, tot_amt, tot_qty2
        for (prod_id, lot_id, loc_from_id, cont_from_id, loc_to_id, cont_to_id), (qty, amt, qty2) in tots.items():
            prod_tots.setdefault(
                prod_id, {})[(lot_id, loc_from_id, cont_from_id, loc_to_id, cont_to_id)] = (qty, amt, qty2)
        bals = {}
        for key in keys:
            prod_id, lot_id, loc_id, cont_id = key
            qty_in, amt_in, qty2_in = get_sum(prod=prod_id, lot=lot_id, loc_to=loc_id, cont_to=cont_id)
            qty_out, amt_out, qty2_out = get_sum(prod=prod_id, lot=lot_id, loc_from=loc_id, cont_from=cont_id)
            qty = qty_in - qty_out
            amt = amt_in - amt_out
            qty2 = qty2_in - qty2_out
            bals[key] = [qty, amt, qty2]
        t1 = time.time()
        print("compute_key_balances finished in %d ms" % ((t1 - t0) * 1000))
        return bals

StockBalance.register()
