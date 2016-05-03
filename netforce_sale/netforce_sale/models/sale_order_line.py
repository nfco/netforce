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
from decimal import Decimal
import math

class SaleOrderLine(Model):
    _name = "sale.order.line"
    _name_field = "order_id"
    _fields = {
        "order_id": fields.Many2One("sale.order", "Sales Order", required=True, on_delete="cascade", search=True),
        "product_id": fields.Many2One("product", "Product", search=True),
        "description": fields.Text("Description", required=True, search=True),
        "qty": fields.Decimal("Qty"),
        "uom_id": fields.Many2One("uom", "UoM"),
        "unit_price": fields.Decimal("Unit Price", search=True, required=True, scale=6),
        "tax_id": fields.Many2One("account.tax.rate", "Tax Rate"),
        "amount": fields.Decimal("Amount", function="get_amount", function_multi=True, store=True, function_order=1, search=True),
        "amount_cur": fields.Decimal("Amount (Cur)", function="get_amount", function_multi=True, store=True, function_order=1, search=True),
        "qty_stock": fields.Decimal("Qty (Stock UoM)"),
        "qty_delivered": fields.Decimal("Delivered Qty", function="get_qty_delivered"),
        "qty_invoiced": fields.Decimal("Invoiced Qty", function="get_qty_invoiced"),
        "contact_id": fields.Many2One("contact", "Contact", function="_get_related", function_search="_search_related", function_context={"path": "order_id.contact_id"}, search=True),
        "date": fields.Date("Date", function="_get_related", function_search="_search_related", function_context={"path": "order_id.date"}, search=True),
        "user_id": fields.Many2One("base.user", "Owner", function="_get_related", function_search="_search_related", function_context={"path": "order_id.user_id"}, search=True),
        "amount_discount": fields.Decimal("Discount Amount", function="get_amount", function_multi=True),
        "state": fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed"), ("done", "Completed"), ("voided", "Voided")], "Status", function="_get_related", function_search="_search_related", function_context={"path": "order_id.state"}, search=True),
        "qty2": fields.Decimal("Secondary Qty"),
        "location_id": fields.Many2One("stock.location", "Location", condition=[["type", "=", "internal"]]),
        "product_categs": fields.Many2Many("product.categ", "Product Categories", function="_get_related", function_context={"path": "product_id.categs"}, function_search="_search_related", search=True),
        "discount": fields.Decimal("Disc %"),  # XXX: rename to discount_percent later
        "discount_amount": fields.Decimal("Disc Amt"),
        "qty_avail": fields.Decimal("Qty In Stock", function="get_qty_avail"),
        "agg_amount": fields.Decimal("Total Amount", agg_function=["sum", "amount"]),
        "agg_amount_cur": fields.Decimal("Total Amount Cur", agg_function=["sum", "amount_cur"]),
        "agg_qty": fields.Decimal("Total Order Qty", agg_function=["sum", "qty"]),
        "remark": fields.Char("Remark"),
        "ship_method_id": fields.Many2One("ship.method", "Shipping Method"),
        "sequence": fields.Char("Item No."),
        "est_cost_amount": fields.Float("Est. Cost Amount",function="get_est_profit",function_multi=True),
        "est_profit_amount": fields.Float("Est. Profit Amount",function="get_est_profit",function_multi=True),
        "est_margin_percent": fields.Float("Est. Margin %",function="get_est_profit",function_multi=True),
        "act_cost_amount": fields.Float("Act. Cost Amount",function="get_act_profit",function_multi=True),
        "act_profit_amount": fields.Float("Act. Profit Amount",function="get_act_profit",function_multi=True,store=True),
        "act_margin_percent": fields.Float("Act. Margin %",function="get_act_profit",function_multi=True),
        "promotion_amount": fields.Decimal("Prom Amt",function="get_amount",function_multi=True),
        "agg_act_profit": fields.Decimal("Total Actual Profit", agg_function=["sum", "act_profit_amount"]),
        "production_id": fields.Many2One("production.order","Production Order"),
    }

    def create(self, vals, context={}):
        id = super(SaleOrderLine, self).create(vals, context)
        self.function_store([id])
        return id

    def write(self, ids, vals, context={}):
        super(SaleOrderLine, self).write(ids, vals, context)
        self.function_store(ids)

    def get_amount(self, ids, context={}):
        vals = {}
        settings = get_model("settings").browse(1)
        sale_ids=[]
        for line in self.browse(ids):
            sale_ids.append(line.order_id.id)
        sale_ids=list(set(sale_ids))
        for sale in get_model("sale.order").browse(sale_ids):
            prod_qtys={}
            prom_amts={}
            prom_pcts={}
            for line in sale.lines:
                prod_qtys.setdefault(line.product_id.id,0)
                prod_qtys[line.product_id.id]+=line.qty
            for line in sale.used_promotions:
                if line.amount and line.product_id:
                    prom_amts.setdefault(line.product_id.id,0)
                    prom_amts[line.product_id.id]+=line.amount
                elif line.percent:
                    prom_pcts.setdefault(line.product_id.id,0)
                    prom_pcts[line.product_id.id]+=line.percent
            for line in sale.lines:
                amt = line.qty * line.unit_price
                if line.discount:
                    disc = amt * line.discount / 100
                else:
                    disc = 0
                if line.discount_amount:
                    disc += line.discount_amount
                amt-=disc
                amt_before_prom=amt
                prom_amt=prom_amts.get(line.product_id.id,Decimal(0))/prod_qtys[line.product_id.id]*line.qty
                prom_pct=prom_pcts.get(line.product_id.id,Decimal(0))+prom_pcts.get(None,0)
                if prom_pct:
                    prom_amt+=math.ceil(amt_before_prom/line.qty*prom_pct/100)*line.qty
                if prom_amt:
                    amt-=prom_amt
                order = line.order_id
                new_cur=get_model("currency").convert(amt, order.currency_id.id, settings.currency_id.id)
                vals[line.id] = {
                    "amount": Decimal(round(float(amt),2)), # convert to float because Decimal gives wrong rounding
                    "amount_discount": disc,
                    "promotion_amount": prom_amt,
                    "amount_cur": new_cur and new_cur or None,
                }
        return vals

    def get_qty_delivered(self, ids, context={}):
        order_ids = []
        for obj in self.browse(ids):
            order_ids.append(obj.order_id.id)
        order_ids = list(set(order_ids))
        vals = {}
        for order in get_model("sale.order").browse(order_ids):
            delivered_qtys = {}
            for move in order.stock_moves:
                if move.state != "done":
                    continue
                prod_id = move.product_id.id
                k = (prod_id, move.location_from_id.id)
                delivered_qtys.setdefault(k, 0)
                delivered_qtys[k] += move.qty  # XXX: uom
                k = (prod_id, move.location_to_id.id)
                delivered_qtys.setdefault(k, 0)
                delivered_qtys[k] -= move.qty  # XXX: uom
            for line in order.lines:
                k = (line.product_id.id, line.location_id.id)
                delivered_qty = delivered_qtys.get(k, 0)  # XXX: uom
                used_qty = min(line.qty, delivered_qty)
                vals[line.id] = used_qty
                if k in delivered_qtys:
                    delivered_qtys[k] -= used_qty
            for line in reversed(order.lines):
                k = (line.product_id.id, line.location_id.id)
                remain_qty = delivered_qtys.get(k, 0)  # XXX: uom
                if remain_qty:
                    vals[line.id] += remain_qty
                    delivered_qtys[k] -= remain_qty
        vals = {x: vals[x] for x in ids}
        return vals

    def get_qty_invoiced(self, ids, context={}):
        order_ids = []
        for obj in self.browse(ids):
            order_ids.append(obj.order_id.id)
        order_ids = list(set(order_ids))
        vals = {}
        for order in get_model("sale.order").browse(order_ids):
            inv_qtys = {}
            for inv in order.invoices:
                if inv.state not in ("draft","waiting_payment","paid"):
                    continue
                for line in inv.lines:
                    prod_id = line.product_id.id
                    inv_qtys.setdefault(prod_id, 0)
                    inv_qtys[prod_id] += line.qty or 0
            for line in order.lines:
                if line.id not in ids:
                    continue
                prod_id = line.product_id.id
                inv_qty = inv_qtys.get(prod_id, 0)  # XXX: uom
                used_qty = min(line.qty, inv_qty)
                vals[line.id] = used_qty
                if prod_id in inv_qtys:
                    inv_qtys[prod_id] -= used_qty
            for line in reversed(order.lines):
                prod_id = line.product_id.id
                remain_qty = inv_qtys.get(prod_id, 0)  # XXX: uom
                if remain_qty:
                    vals[line.id] += remain_qty
                    inv_qtys[prod_id] -= remain_qty
        vals = {x: vals[x] for x in ids}
        return vals

    def get_qty_avail(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            prod_id = obj.product_id.id
            loc_id = obj.location_id.id
            if prod_id and loc_id:
                res = get_model("stock.location").compute_balance([loc_id], prod_id)
                qty = res["bal_qty"]
            else:
                qty = None
            vals[obj.id] = qty
        return vals

    def get_est_profit(self,ids,context={}):
        sale_ids=[]
        for line in self.browse(ids):
            sale_ids.append(line.order_id.id)
        sale_ids=list(set(sale_ids))
        item_costs={}
        for sale in get_model("sale.order").browse(sale_ids):
            for cost in sale.est_costs:
                k=(sale.id,cost.sequence)
                if k not in item_costs:
                    item_costs[k]=0
                amt=cost.amount or 0
                if cost.currency_id:
                    rate=sale.get_relative_currency_rate(cost.currency_id.id)
                    amt=amt*rate
                item_costs[k]+=amt
        vals={}
        for line in self.browse(ids):
            k=(line.order_id.id,line.sequence)
            cost=item_costs.get(k,0)
            profit=line.amount-cost
            margin=profit*100/line.amount if line.amount else None
            vals[line.id]={
                "est_cost_amount": cost,
                "est_profit_amount": profit,
                "est_margin_percent": margin,
            }
        return vals

    def get_act_profit(self,ids,context={}):
        sale_ids=[]
        for line in self.browse(ids):
            sale_ids.append(line.order_id.id)
        sale_ids=list(set(sale_ids))
        item_costs={}
        for sale in get_model("sale.order").browse(sale_ids):
            for line in sale.track_entries:
                k=(sale.id,line.track_id.code)
                if k not in item_costs:
                    item_costs[k]=0
                # TODO: convert currency
                item_costs[k]-=line.amount
        vals={}
        for line in self.browse(ids):
            track_code="%s / %s"%(line.order_id.number,line.sequence)
            k=(line.order_id.id,track_code)
            cost=item_costs.get(k,0)
            profit=line.amount-cost
            margin=profit*100/line.amount if line.amount else None
            vals[line.id]={
                "act_cost_amount": cost,
                "act_profit_amount": profit,
                "act_margin_percent": margin,
            }
        return vals

SaleOrderLine.register()
