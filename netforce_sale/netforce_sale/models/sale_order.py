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
from netforce.utils import get_data_path, roundup
import time
from netforce.access import get_active_user, set_active_user
from netforce.access import get_active_company, check_permission_other, set_active_company
from . import utils
from datetime import datetime, timedelta
from decimal import Decimal


class SaleOrder(Model):
    _name = "sale.order"
    _string = "Sales Order"
    _audit_log = True
    _name_field = "number"
    _multi_company = True
    _key = ["company_id", "number"]  # need migration first otherwise can't add constraint...
    _fields = {
        "number": fields.Char("Number", required=True, search=True),
        "ref": fields.Char("Ref", search=True),
        "contact_id": fields.Many2One("contact", "Customer", required=True, search=True),
        "date": fields.Date("Date", required=True, search=True),
        "state": fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed"), ("done", "Completed"), ("voided", "Voided")], "Status", required=True),
        "lines": fields.One2Many("sale.order.line", "order_id", "Lines"),
        "amount_subtotal": fields.Decimal("Subtotal", function="get_amount", function_multi=True, store=True),
        "amount_tax": fields.Decimal("Tax Amount", function="get_amount", function_multi=True, store=True),
        "amount_total": fields.Decimal("Total", function="get_amount", function_multi=True, store=True),
        "amount_total_discount": fields.Decimal("Total Discount", function="get_amount", function_multi=True, store=True),
        "amount_total_words": fields.Char("Total Words", function="get_amount_total_words"),
        "amount_total_cur": fields.Decimal("Total", function="get_amount", function_multi=True, store=True),
        "qty_total": fields.Decimal("Total", function="get_qty_total"),
        "currency_id": fields.Many2One("currency", "Currency", required=True, search=True),
        "quot_id": fields.Many2One("sale.quot", "Quotation", search=True), # XXX: deprecated
        "user_id": fields.Many2One("base.user", "Owner", search=True),
        "tax_type": fields.Selection([["tax_ex", "Tax Exclusive"], ["tax_in", "Tax Inclusive"], ["no_tax", "No Tax"]], "Tax Type", required=True),
        "invoice_lines": fields.One2Many("account.invoice.line", "sale_id", "Invoice Lines"),
        "invoices": fields.One2Many("account.invoice", "related_id", "Invoices"),
        "pickings": fields.Many2Many("stock.picking", "Stock Pickings", function="get_pickings"),
        "is_delivered": fields.Boolean("Delivered", function="get_delivered"),
        "is_paid": fields.Boolean("Paid", function="get_paid"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "activities": fields.One2Many("activity", "related_id", "Activities"),
        "location_id": fields.Many2One("stock.location", "Warehouse", search=True),  # XXX: deprecated
        "price_list_id": fields.Many2One("price.list", "Price List", condition=[["type", "=", "sale"]]),
        "payment_terms": fields.Text("Payment Terms"),
        "delivery_date": fields.Date("Due Date"),  # XXX; deprecated
        "due_date": fields.Date("Due Date"),
        "team_id": fields.Many2One("mfg.team", "Production Team"),
        "ship_method_id": fields.Many2One("ship.method", "Shipping Method"),  # XXX: deprecated
        "emails": fields.One2Many("email.message", "related_id", "Emails"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "addresses": fields.One2Many("address", "related_id", "Addresses"),
        "bill_address_id": fields.Many2One("address", "Billing Address"),
        "ship_address_id": fields.Many2One("address", "Shipping Address"),
        "coupon_id": fields.Many2One("sale.coupon", "Coupon"),
        "purchase_lines": fields.One2Many("purchase.order.line", "sale_id", "Purchase Orders"),
        "production_orders": fields.One2Many("production.order", "sale_id", "Production Orders"),
        "other_info": fields.Text("Other Information"),
        "costs": fields.One2Many("sale.cost", "sale_id", "Costs"),
        "est_cost_total": fields.Decimal("Estimated Cost Total", function="get_profit", function_multi=True, store=True), # XXX: deprecated
        "est_profit": fields.Decimal("Estimated Profit", function="get_profit", function_multi=True, store=True), # XXX: deprecated
        "est_profit_percent": fields.Decimal("Estimated Profit Percent", function="get_profit", function_multi=True, store=True), # XXX: deprecated
        "act_cost_total": fields.Decimal("Actual Cost Total", function="get_profit", function_multi=True, store=True), # XXX: deprecated
        "act_profit": fields.Decimal("Actual Profit", function="get_profit", function_multi=True, store=True), # XXX: deprecated
        "act_profit_percent": fields.Decimal("Actual Profit Percent", function="get_profit", function_multi=True, store=True), # XXX: deprecated
        "company_id": fields.Many2One("company", "Company"),
        "production_status": fields.Json("Production", function="get_production_status"),
        "overdue": fields.Boolean("Overdue", function="get_overdue", function_search="search_overdue"),
        "ship_term_id": fields.Many2One("ship.term", "Shipping Terms"),
        "approved_by_id": fields.Many2One("base.user", "Approved By", readonly=True),
        "sequence_id": fields.Many2One("sequence", "Number Sequence"),
        "stock_moves": fields.One2Many("stock.move", "related_id", "Stock Movements"),
        "state_label": fields.Char("Status Label", function="get_state_label"),  # XXX: not needed
        "ship_tracking": fields.Char("Tracking Numbers", function="get_ship_tracking"),
        "job_template_id": fields.Many2One("job.template", "Service Order Template"),
        "jobs": fields.One2Many("job", "related_id", "Service Orders"),
        "agg_amount_total": fields.Decimal("Total Amount", agg_function=["sum", "amount_total"]),
        "agg_amount_total_cur": fields.Decimal("Total Amount (Converted)", agg_function=["sum", "amount_total_cur"]),
        "agg_amount_subtotal": fields.Decimal("Total Amount w/o Tax", agg_function=["sum", "amount_subtotal"]),
        "agg_est_profit": fields.Decimal("Total Estimated Profit", agg_function=["sum", "est_profit_amount"]),
        "agg_act_profit": fields.Decimal("Total Actual Profit", agg_function=["sum", "act_profit_amount"]),
        "year": fields.Char("Year", sql_function=["year", "date"]),
        "quarter": fields.Char("Quarter", sql_function=["quarter", "date"]),
        "month": fields.Char("Month", sql_function=["month", "date"]),
        "week": fields.Char("Week", sql_function=["week", "date"]),
        "pay_method_id": fields.Many2One("payment.method", "Payment Method",search=True),
        "sale_channel_id": fields.Many2One("sale.channel", "Sales Channel",search=True),
        "related_id": fields.Reference([["sale.quot", "Quotation"], ["ecom.cart", "Ecommerce Cart"], ["purchase.order", "Purchase Order"]], "Related To", search=True),
        "est_costs": fields.One2Many("sale.cost","sale_id","Costs"),
        "est_cost_amount": fields.Float("Est. Cost Amount", function="get_est_profit", function_multi=True, store=True),
        "est_profit_amount": fields.Float("Est. Profit Amount", function="get_est_profit", function_multi=True, store=True),
        "est_margin_percent": fields.Float("Est. Margin %", function="get_est_profit", function_multi=True, store=True),
        "act_cost_amount": fields.Float("Act. Cost Amount", function="get_act_profit", function_multi=True, store=True),
        "act_profit_amount": fields.Float("Act. Profit Amount", function="get_act_profit", function_multi=True, store=True),
        "act_margin_percent": fields.Float("Act. Margin %", function="get_act_profit", function_multi=True, store=True),
        "track_id": fields.Many2One("account.track.categ","Tracking Code"),
        "track_entries": fields.One2Many("account.track.entry",None,"Tracking Entries",function="get_track_entries",function_write="write_track_entries"),
        "track_balance": fields.Decimal("Tracking Balance",function="_get_related",function_context={"path":"track_id.balance"}),
        "used_promotions": fields.One2Many("sale.order.promotion", "sale_id", "Used Promotions"),
        "seller_id": fields.Many2One("seller","Seller"),
        "product_id": fields.Many2One("product","Product",store=False,function_search="search_product",search=True),
        "currency_rates": fields.One2Many("custom.currency.rate","related_id","Currency Rates"),
        "delivery_slot_id": fields.Many2One("delivery.slot","Delivery Slot"),
    }

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence(type="sale_order",context=context)
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            if not num:
                return None
            user_id = get_active_user()
            set_active_user(1)
            res = self.search([["number", "=", num]])
            set_active_user(user_id)
            if not res:
                return num
            get_model("sequence").increment_number(seq_id, context=context)

    def _get_currency(self, context={}):
        settings = get_model("settings").browse(1)
        return settings.currency_id.id

    def _get_currency_rates(self,context={}):
        settings = get_model("settings").browse(1)
        lines=[]
        date = time.strftime("%Y-%m-%d")
        line_vals={
            "currency_id": settings.currency_id.id,
            "rate": settings.currency_id and settings.currency_id.get_rate(date,"sell") or 1
        }
        if context.get("is_create"):
            lines.append(('create',line_vals))
        else:
            lines.append(line_vals)
        return lines 

    _defaults = {
        "state": "draft",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "number": _get_number,
        "currency_id": _get_currency,
        "tax_type": "tax_ex",
        "user_id": lambda *a: get_active_user(),
        "company_id": lambda *a: get_active_company(),
        "currency_rates": _get_currency_rates,
    }
    _order = "date desc,number desc"

    def search_product(self, clause, context={}):
        product_id = clause[2]
        product = get_model("product").browse(product_id)
        product_ids = [product_id]
        for var in product.variants:
            product_ids.append(var.id)
        for comp in product.components:
            product_ids.append(comp.component_id.id)
        order_ids = []
        for line in get_model("sale.order.line").search_browse([["product_id","in",product_ids]]):
            order_ids.append(line.order_id.id)
        cond = [["id","in",order_ids]]
        return cond

    def create(self, vals, context={}):
        context['is_create']=True #send to function _get_currency_rates
        id = super(SaleOrder, self).create(vals, context)
        self.function_store([id])
        quot_id = vals.get("quot_id")
        if quot_id:
            get_model("sale.quot").function_store([quot_id])
        if 'lines' in vals.keys():
            self.create_est_costs([id])
        return id

    def write(self, ids, vals, **kw):
        quot_ids = []
        for obj in self.browse(ids):
            if obj.quot_id:
                quot_ids.append(obj.quot_id.id)
        super(SaleOrder, self).write(ids, vals, **kw)
        self.function_store(ids)
        if 'lines' in vals.keys():
            self.create_est_costs(ids)

        quot_id = vals.get("quot_id")
        if quot_id:
            quot_ids.append(quot_id)
        if quot_ids:
            get_model("sale.quot").function_store(quot_ids)

    def delete(self, ids, **kw):
        quot_ids = []
        for obj in self.browse(ids):
            if obj.state in ("confirmed", "done"):
                raise Exception("Can not delete sales order in this status")
            if obj.quot_id:
                quot_ids.append(obj.quot_id.id)
        super(SaleOrder, self).delete(ids, **kw)
        if quot_ids:
            get_model("sale.quot").function_store(quot_ids)

    def get_amount(self, ids, context={}):
        res = {}
        settings = get_model("settings").browse(1)
        for obj in self.browse(ids):
            vals = {}
            subtotal = 0
            tax = 0
            discount = 0
            for line in obj.lines:
                discount += line.amount_discount
                if line.tax_id:
                    line_tax = get_model("account.tax.rate").compute_tax(
                        line.tax_id.id, line.amount, tax_type=obj.tax_type)
                else:
                    line_tax = 0
                tax += line_tax
                if obj.tax_type == "tax_in":
                    subtotal += line.amount - line_tax
                else:
                    subtotal += line.amount
            for line in obj.used_promotions:
                if line.product_id or line.percent:
                    continue
                prom=line.promotion_id
                prod=prom.product_id
                prom_tax=prod.sale_tax_id if prod else None
                if prom_tax:
                    line_tax = get_model("account.tax.rate").compute_tax(
                        prom_tax.id, line.amount, tax_type=obj.tax_type)
                else:
                    line_tax = 0
                tax -= line_tax
                if obj.tax_type == "tax_in":
                    subtotal -= line.amount - line_tax
                else:
                    subtotal -= line.amount
            vals["amount_subtotal"] = subtotal
            vals["amount_tax"] = tax
            vals["amount_total"] = (subtotal + tax)
            vals["amount_total_cur"] = get_model("currency").convert(
                vals["amount_total"], obj.currency_id.id, settings.currency_id.id, rate_type="sell", date=obj.date)
            vals["amount_total_discount"] = discount
            res[obj.id] = vals
        return res

    def get_qty_total(self, ids, context={}):
        res = {}
        for obj in self.browse(ids):
            qty = sum([line.qty for line in obj.lines])
            res[obj.id] = qty or 0
        return res

    def confirm(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.state != "draft":
            raise Exception("Invalid state")
        for line in obj.lines:
            prod = line.product_id
            if prod and prod.type in ("stock", "consumable", "bundle") and not line.location_id:
                raise Exception("Missing location for product %s" % prod.code)
        obj.write({"state": "confirmed"})
        settings = get_model("settings").browse(1)
        if settings.sale_copy_picking:
            res=obj.copy_to_picking()
            picking_id=res["picking_id"]
            get_model("stock.picking").pending([picking_id])
        if settings.sale_copy_invoice:
            obj.copy_to_invoice()
        if settings.sale_copy_production:
            obj.copy_to_production()
        obj.trigger("confirm")
        return {
            "next": {
                "name": "sale",
                "mode": "form",
                "active_id": obj.id,
            },
            "flash": "Sales order %s confirmed" % obj.number,
        }

    def done(self, ids, context={}):
        for obj in self.browse(ids):
            if obj.state != "confirmed":
                raise Exception("Invalid state")
            obj.write({"state": "done"})

    def reopen(self, ids, context={}):
        for obj in self.browse(ids):
            if obj.state != "done":
                raise Exception("Invalid state")
            obj.write({"state": "confirmed"})

    def to_draft(self, ids, context={}):
        for obj in self.browse(ids):
            obj.write({"state": "draft"})

    def onchange_currency(self,context={}):
        settings=get_model("settings").browse(1)
        data = context["data"]
        for line in data["lines"]:
            if not line:
                continue
            amt = (line.get("qty") or 0) * (line.get("unit_price") or 0)
            new_cur=get_model("currency").convert(amt, int(data.get("currency_id")), settings.currency_id.id)
            line['amount_cur']=new_cur and new_cur or None
        return data

    def update_amounts(self, context):
        settings=get_model("settings").browse(1)
        data = context["data"]
        data["amount_subtotal"] = 0
        data["amount_tax"] = 0
        tax_type = data["tax_type"]
        for line in data["lines"]:
            if not line:
                continue
            amt = (line.get("qty") or 0) * (line.get("unit_price") or 0)
            amt = roundup(amt)
            if line.get("discount"):
                disc = amt * line["discount"] / Decimal(100)
                amt -= disc
            if line.get("discount_amount"):
                amt -= line["discount_amount"]
            line["amount"] = amt
            new_cur=get_model("currency").convert(amt, int(data.get("currency_id")), settings.currency_id.id)
            line['amount_cur']=new_cur and new_cur or None
            tax_id = line.get("tax_id")
            if tax_id:
                tax = get_model("account.tax.rate").compute_tax(tax_id, amt, tax_type=tax_type)
                data["amount_tax"] += tax
            else:
                tax = 0
            amt=Decimal(round(float(amt),2)) # # convert to float because Decimal gives wrong rounding
            if tax_type == "tax_in":
                data["amount_subtotal"] += amt - tax
            else:
                data["amount_subtotal"] += amt
        data["amount_total"] = data["amount_subtotal"] + data["amount_tax"]
        return data

    def onchange_product(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        line["description"] = prod.description or "/"
        line["qty"] = 1
        line["uom_id"] = prod.sale_uom_id.id or prod.uom_id.id
        line["qty_stock"] = 0
        pricelist_id = data["price_list_id"]
        price = None
        if pricelist_id:
            price = get_model("price.list").get_price(pricelist_id, prod.id, 1)
            line['discount'] = get_model("price.list").get_discount(pricelist_id, prod.id, 1)
            price_list = get_model("price.list").browse(pricelist_id)
            price_currency_id = price_list.currency_id.id
        if price is None:
            price = prod.sale_price
            settings = get_model("settings").browse(1)
            price_currency_id = settings.currency_id.id
        if price is not None:
            currency_id = data["currency_id"]
            price_cur = get_model("currency").convert(price, price_currency_id, currency_id)
            line["unit_price"] = price_cur
        if prod.sale_tax_id is not None:
            line["tax_id"] = prod.sale_tax_id.id
        if prod.location_id:
            line["location_id"] = prod.location_id.id
        elif prod.locations:
            line["location_id"] = prod.locations[0].location_id.id
            for loc in prod.locations:
                if loc.stock_qty:
                    line['location_id']=loc.location_id.id
                    break
        if "location_id" in line and line["location_id"]:
            qty_stock = get_model("stock.balance").search_browse([["product_id","=",prod_id],["location_id","=",line["location_id"]]])
            if len(qty_stock) > 0:
                line["qty_stock"] = qty_stock[0].qty_phys
        data = self.update_amounts(context)
        return data

    def onchange_qty(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        pricelist_id = data["price_list_id"]
        qty = line["qty"]
        price = None
        if pricelist_id:
            price = get_model("price.list").get_price(pricelist_id, prod.id, qty)
            price_list = get_model("price.list").browse(pricelist_id)
            price_currency_id = price_list.currency_id.id
        if price is None:
            price = prod.sale_price
            settings = get_model("settings").browse(1)
            price_currency_id = settings.currency_id.id
        if price is not None:
            currency_id = data["currency_id"]
            price_cur = get_model("currency").convert(price, price_currency_id, currency_id)
            line["unit_price"] = price_cur
        data = self.update_amounts(context)
        return data

    def onchange_location(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        line["qty_stock"] = 0
        if "product_id" in line and line["product_id"]:
            qty_stock = get_model("stock.balance").search_browse([["product_id","=",line["product_id"]],["location_id","=",line["location_id"]]])
            if len(qty_stock) > 0:
                line["qty_stock"] = qty_stock[0].qty_phys
        return data

    def onchange_uom(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        uom_id = line.get("uom_id")
        if not uom_id:
            return {}
        uom = get_model("uom").browse(uom_id)
        if prod.sale_price is not None:
            line["unit_price"] = prod.sale_price * uom.ratio / prod.uom_id.ratio
        data = self.update_amounts(context)

        #update est .....
        sale = self.browse(int(data['id']))
        item_costs=Decimal(0)
        for cost in sale.est_costs:
            k=(sale.id,cost.sequence)
            amt=cost.amount or 0
            if cost.currency_id:
                rate=sale.get_relative_currency_rate(cost.currency_id.id)
                amt=amt*rate
            item_costs+=amt
        cost=item_costs
        profit=line['amount']-Decimal(cost)
        margin=Decimal(profit)*100/Decimal(line['amount']) if line['amount'] else None
        amount={
            "est_cost_amount": cost,
            "est_profit_amount": profit,
            "est_margin_percent": margin,
        }
        line['est_cost_amount'] = amount['est_cost_amount']
        line['est_profit_amount'] = amount['est_profit_amount']
        line['est_margin_percent'] = amount['est_margin_percent']
        return data

    def get_qty_to_deliver(self, ids):
        obj = self.browse(ids)[0]
        sale_quants = {}
        for line in obj.lines:
            prod = line.product_id
            if not prod or prod.type == "service":
                continue
            uom = line.uom_id
            sale_quants.setdefault((prod.id, uom.id), 0)
            sale_quants[(prod.id, uom.id)] += line.qty  # XXX: uom
        done_quants = {}
        for move in obj.stock_moves:
            if move.state == "cancelled":
                continue
            prod = move.product_id
            done_quants.setdefault(prod.id, 0)
            done_quants[prod.id] += move.qty  # XXX: uom
        to_deliver = {}
        for (prod_id, uom_id), qty in sale_quants.items():
            qty_done = done_quants.get(prod_id, 0)
            if qty_done < qty:
                to_deliver[(prod_id, uom_id)] = qty - qty_done
        return to_deliver

    def copy_to_picking(self, ids, context={}):
        id = ids[0]
        obj = self.browse(id)
        pick_vals = {}
        contact = obj.contact_id
        res = get_model("stock.location").search([["type", "=", "customer"]])
        if not res:
            raise Exception("Customer location not found")
        cust_loc_id = res[0]
        res = get_model("stock.location").search([["type", "=", "internal"]])
        if not res:
            raise Exception("Warehouse not found")
        wh_loc_id = res[0]

        for obj_line in obj.lines:
            picking_key = obj_line.ship_method_id and obj_line.ship_method_id.id or 0
            if picking_key in pick_vals: continue
            if not obj.due_date:
                raise Exception("Missing due date in sales order %s"%obj.number)
            pick_vals[picking_key] = {
                "type": "out",
                "ref": obj.number,
                "related_id": "sale.order,%s" % obj.id,
                "contact_id": contact.id,
                "ship_address_id": obj.ship_address_id.id,
                "lines": [],
                "state": "draft",
                "ship_method_id": obj_line.ship_method_id.id or obj.ship_method_id.id,
                "company_id": obj.company_id.id,
                "date": obj.due_date+" 00:00:00",
            }
            if contact and contact.pick_out_journal_id:
                pick_vals[picking_key]["journal_id"] = contact.pick_out_journal_id.id
        for line in obj.lines:
            picking_key = line.ship_method_id and line.ship_method_id.id or 0
            prod = line.product_id
            if not prod:
                continue
            if prod.type not in ("stock", "consumable"):
                continue
            if line.qty <= 0:
                continue
            qty_remain = line.qty - line.qty_delivered
            if qty_remain <= 0:
                continue
            line_vals = {
                "product_id": prod.id,
                "qty": qty_remain,
                "uom_id": prod.uom_id.id if line.qty_stock else line.uom_id.id,
                "location_from_id": line.location_id.id or wh_loc_id,
                "location_to_id": cust_loc_id,
                "related_id": "sale.order,%s" % obj.id,
            }
            pick_vals[picking_key]["lines"].append(("create", line_vals))
        for picking_key, picking_value in pick_vals.items():
            if not picking_value["lines"]: Exception("Nothing left to deliver")
            pick_id = get_model("stock.picking").create(picking_value, context={"pick_type": "out"})
            pick = get_model("stock.picking").browse(pick_id)
        return {
            "next": {
                "name": "pick_out",
                "mode": "form",
                "active_id": pick_id,
            },
            "flash": "Picking %s created from sales order %s" % (pick.number, obj.number),
            "picking_id": pick_id,
        }

    def copy_to_invoice(self, ids, context={}):
        print("sale.copy_to_invoice",ids)
        obj = self.browse(ids[0])
        company_id=get_active_company()
        set_active_company(obj.company_id.id) # XXX
        try:
            ship_method_ids=[]
            ship_method_amts={}
            ship_amt_total=0
            for line in obj.lines:
                ship_method_ids.append(line.ship_method_id.id)
                ship_method_amts.setdefault(line.ship_method_id.id,0)
                ship_method_amts[line.ship_method_id.id]+=line.amount
                ship_amt_total+=line.amount
            ship_method_ids=list(set(ship_method_ids))
            inv_ids=[]
            for ship_method_id in ship_method_ids:
                contact = obj.contact_id
                inv_vals = {
                    "type": "out",
                    "inv_type": "invoice",
                    "ref": obj.number,
                    "related_id": "sale.order,%s" % obj.id,
                    "contact_id": contact.id,
                    "bill_address_id": obj.bill_address_id.id,
                    "currency_id": obj.currency_id.id,
                    "tax_type": obj.tax_type,
                    "pay_method_id": obj.pay_method_id.id,
                    "lines": [],
                    "company_id": obj.company_id.id,
                }
                if contact.sale_journal_id:
                    inv_vals["journal_id"] = contact.sale_journal_id.id
                    if contact.sale_journal_id.sequence_id:
                        inv_vals["sequence_id"] = contact.sale_journal_id.sequence_id.id
                for line in obj.lines:
                    if line.unit_price is None:
                        continue
                    if line.ship_method_id.id!=ship_method_id:
                        continue
                    prod = line.product_id
                    remain_qty = line.qty - line.qty_invoiced
                    if remain_qty <= 0:
                        continue

                    # TODO: this get account should call from product.get_account()["sale_account_id"]

                    sale_acc_id=None
                    if prod:
                        #1. get account from product
                        sale_acc_id=prod.sale_account_id and prod.sale_account_id.id or None

                        # 2. if not get from master/parent product
                        if not sale_acc_id and prod.parent_id:
                            sale_acc_id=prod.parent_id.sale_account_id.id
                        # 3. if not get from product category
                        categ=prod.categ_id
                        if categ and not sale_acc_id:
                            sale_acc_id=categ.sale_account_id and categ.sale_account_id.id or None

                    #if not sale_acc_id:
                        #raise Exception("Missing sale account for product [%s] " % prod.name )


                    line_vals = {
                        "product_id": prod.id,
                        "description": line.description,
                        "qty": remain_qty,
                        "uom_id": line.uom_id.id,
                        "unit_price": line.unit_price,
                        "discount": line.discount,
                        "discount_amount": line.discount_amount,
                        "account_id": sale_acc_id,
                        "tax_id": line.tax_id.id,
                        "amount": remain_qty*line.unit_price*(1-(line.discount or Decimal(0))/100)-(line.discount_amount or Decimal(0)),
                    }
                    inv_vals["lines"].append(("create", line_vals))
                    if line.promotion_amount:
                        prom_acc_id=None
                        if prod:
                            prom_acc_id=prod.sale_promotion_account_id.id
                            if not prom_acc_id and prod.parent_id:
                                prom_acc_id=prod.parent_id.sale_promotion_account_id.id
                        if not prom_acc_id:
                            prom_acc_id=sale_acc_id
                        line_vals = {
                            "product_id": prod.id,
                            "description": "Promotion on product %s"%prod.code,
                            "account_id": prom_acc_id,
                            "tax_id": line.tax_id.id,
                            "amount": -line.promotion_amount,
                        }
                        inv_vals["lines"].append(("create", line_vals))
                for line in obj.used_promotions:
                    if line.product_id or line.percent:
                        continue
                    ratio=ship_method_amts[ship_method_id]/ship_amt_total if ship_amt_total else 0
                    prom=line.promotion_id
                    prod = prom.product_id
                    line_vals = {
                        "product_id": prod.id,
                        "description": prom.name,
                        "account_id": prod and prod.sale_account_id.id or None,
                        "tax_id": prod and prod.sale_tax_id.id or None,
                        "amount": -line.amount*ratio,
                    }
                    inv_vals["lines"].append(("create", line_vals))
                if not inv_vals["lines"]:
                    continue
                inv_id = get_model("account.invoice").create(inv_vals, {"type": "out", "inv_type": "invoice"})
                inv_ids.append(inv_id)
            if not inv_ids:
                raise Exception("Nothing to invoice")
            print("inv_ids",inv_ids)
            return {
                "next": {
                    "name": "view_invoice",
                    "active_id": inv_ids[0],
                },
                "flash": "Invoice created from sales order %s" % obj.number,
                "invoice_id": inv_ids[0],
            }
        finally:
            set_active_company(company_id)

    def get_delivered(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            is_delivered = True
            for line in obj.lines:
                prod = line.product_id
                if prod.type not in ("stock", "consumable", "bundle", None):
                    continue
                remain_qty = (line.qty or line.qty_stock) - line.qty_delivered
                if remain_qty > 0:
                    is_delivered = False
                    break
            vals[obj.id] = is_delivered
        return vals

    def get_paid(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            amt_paid = 0
            for inv in obj.invoices:
                if inv.state != "paid":
                    continue
                amt_paid += inv.amount_total
            is_paid = amt_paid >= obj.amount_total
            vals[obj.id] = is_paid
        return vals

    def void(self, ids, context={}):
        for obj in self.browse(ids):
            for pick in obj.pickings:
                if pick.state == "pending":
                    raise Exception("There are still pending goods issues for this sales order")
            for inv in obj.invoices:
                if inv.state == "waiting_payment":
                    raise Exception("There are still invoices waiting payment for this sales order")
            obj.write({"state": "voided"})

    def copy(self, ids, context):
        obj = self.browse(ids)[0]
        vals = {
            "contact_id": obj.contact_id.id,
            "date": obj.date,
            "ref": obj.ref,
            "currency_id": obj.currency_id.id,
            "tax_type": obj.tax_type,
            "user_id": obj.user_id.id,
            "quot_id": obj.quot_id.id,
            "lines": [],
        }
        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "description": line.description,
                "qty": line.qty,
                "discount": line.discount,
                "discount_amount": line.discount_amount,
                "uom_id": line.uom_id.id,
                "location_id": line.location_id.id,
                "unit_price": line.unit_price,
                "tax_id": line.tax_id.id,
            }
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals)
        new_obj = self.browse(new_id)
        return {
            "next": {
                "name": "sale",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "Sales order %s copied to %s" % (obj.number, new_obj.number),
            "sale_id": new_id,
        }

    def get_invoices(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            inv_ids = []
            for inv_line in obj.invoice_lines:
                inv_id = inv_line.invoice_id.id
                if inv_id not in inv_ids:
                    inv_ids.append(inv_id)
            vals[obj.id] = inv_ids
        return vals

    def get_pickings(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            pick_ids = []
            for move in obj.stock_moves:
                pick_id = move.picking_id.id
                if pick_id not in pick_ids:
                    pick_ids.append(pick_id)
            vals[obj.id] = pick_ids
        return vals

    def onchange_contact(self, context):
        data = context["data"]
        contact_id = data.get("contact_id")
        contact = get_model("contact").browse(contact_id) if contact_id else None
        data["payment_terms"] = contact.payment_terms if contact else None
        data["price_list_id"] = contact.sale_price_list_id.id if contact else None
        data["bill_address_id"] = contact.get_address(pref_type="billing") if contact else None
        data["ship_address_id"] = contact.get_address(pref_type="shipping") if contact else None
        if contact.currency_id:
            data["currency_id"] = contact.currency_id.id
        else:
            settings = get_model("settings").browse(1)
            data["currency_id"] = settings.currency_id.id
        return data

    def check_delivered_qtys(self, ids, context={}):
        obj = self.browse(ids)[0]
        for line in obj.lines:
            if line.qty < 0:
                continue
            if line.qty_delivered > line.qty:
                raise Exception("Can not deliver excess quantity for sales order %s and product %s (order qty: %s, delivered qty: %s)" % (
                    obj.number, line.product_id.code, line.qty, line.qty_delivered))

    def copy_to_purchase(self, ids, context={}):
        obj = self.browse(ids)[0]
        suppliers = {}
        for line in obj.lines:
            prod = line.product_id
            if not prod:
                continue
            if prod.procure_method != "mto" or prod.supply_method != "purchase":
                continue
            if not prod.suppliers:
                raise Exception("Missing supplier for product '%s'" % prod.name)
            supplier_id = prod.suppliers[0].supplier_id.id
            suppliers.setdefault(supplier_id, []).append((prod.id, line.qty, line.uom_id.id, line.location_id.id))
        if not suppliers:
            raise Exception("No purchase orders to create")
        po_ids = []
        for supplier_id, lines in suppliers.items():
            supplier = get_model("contact").browse(supplier_id)
            purch_vals = {
                "contact_id": supplier_id,
                "ref": obj.number,
                "lines": [],
                "payment_terms": obj.payment_terms or supplier.payment_terms,
            }
            for prod_id, qty, uom_id, location_id in lines:
                prod = get_model("product").browse(prod_id)
                line_vals = {
                    "product_id": prod_id,
                    "description": prod.description or "/",
                    "qty": qty,
                    "uom_id": uom_id,
                    "unit_price": prod.purchase_price or 0,
                    "tax_id": prod.purchase_tax_id.id,
                    "sale_id": obj.id,
                    'location_id': location_id,
                }
                purch_vals["lines"].append(("create", line_vals))
            po_id = get_model("purchase.order").create(purch_vals)
            po_ids.append(po_id)
        po_objs = get_model("purchase.order").browse(po_ids)
        return {
            "next": {
                "name": "purchase",
                "search_condition": [["ref", "=", obj.number]],
            },
            "flash": "Purchase orders created successfully: " + ", ".join([po.number for po in po_objs]),
        }

    def copy_to_production(self, ids, context={}):
        order_ids = []
        mfg_orders = {}
        for obj in self.browse(ids):
            for line in obj.lines:
                prod = line.product_id
                if not prod:
                    continue
                if prod.procure_method != "mto" or prod.supply_method != "production":
                    continue
                if line.production_id:
                    raise Exception("Production order already created for sales order %s, product %s"%(obj.number,prod.code))
                if not obj.due_date:
                    raise Exception("Missing due date in sales order %s"%obj.number)
                if not prod.mfg_lead_time:
                    raise Exception("Missing manufacturing lead time in product %s"%prod.code)
                k=(prod.id,obj.due_date)
                mfg_orders.setdefault(k,[]).append(line.id)
        for (prod_id,due_date),sale_line_ids in mfg_orders.items():
            prod=get_model("product").browse(prod_id)
            res=get_model("bom").search([["product_id","=",prod.id]]) # TODO: select bom in separate function
            if not res:
                raise Exception("BoM not found for product '%s'" % prod.name)
            bom_id = res[0]
            bom = get_model("bom").browse(bom_id)
            loc_id = bom.location_id.id
            if not loc_id:
                raise Exception("Missing FG location in BoM %s" % bom.number)
            routing = bom.routing_id
            if not routing:
                raise Exception("Missing routing in BoM %s" % bom.number)
            loc_prod_id = routing.location_id.id
            if not loc_prod_id:
                raise Exception("Missing production location in routing %s" % routing.number)
            uom = prod.uom_id
            mfg_qty=0
            for line in get_model("sale.order.line").browse(sale_line_ids):
                if line.qty_stock:
                    qty = line.qty_stock
                else:
                    qty = get_model("uom").convert(line.qty, line.uom_id.id, uom.id)
                mfg_qty+=qty
            if not prod.mfg_lead_time:
                raise Exception("Missing manufacturing lead time for product %s"%prod.code)
            mfg_date=(datetime.strptime(due_date,"%Y-%m-%d")-timedelta(days=prod.mfg_lead_time)).strftime("%Y-%m-%d")
            order_vals = {
                "product_id": prod.id,
                "qty_planned": mfg_qty,
                "uom_id": uom.id,
                "bom_id": bom_id,
                "routing_id": routing.id,
                "production_location_id": loc_prod_id,
                "location_id": loc_id,
                "order_date": mfg_date,
                "due_date": due_date,
                "state": "waiting_confirm",
            }
            order_id = get_model("production.order").create(order_vals)
            get_model("production.order").create_components([order_id])
            get_model("production.order").create_operations([order_id])
            order_ids.append(order_id)
            get_model("sale.order.line").write(sale_line_ids,{"production_id":order_id})
        if not order_ids:
            return {
                "flash": "No production orders to create",
            }
        get_model("production.order").copy_to_production_all(order_ids)
        return {
            "flash": "Production orders created successfully",
        }

    def get_production_status(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            num_done = 0
            num_total = 0
            for prod in obj.production_orders:
                if prod.state == "done":
                    num_done += 1
                if prod.state not in ("voided", "split"):
                    num_total += 1
            if num_total != 0:
                percent = num_done * 100 / num_total
                vals[obj.id] = {
                    "percent": percent,
                    "string": "%d / %d" % (num_done, num_total)
                }
            else:
                vals[obj.id] = None
        return vals

    def get_overdue(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.due_date:
                vals[obj.id] = obj.due_date < time.strftime("%Y-%m-%d") and obj.state in ("draft", "waiting", "ready")
            else:
                vals[obj.id] = False
        return vals

    def search_overdue(self, clause, context={}):
        return [["due_date", "<", time.strftime("%Y-%m-%d")], ["state", "in", ["draft", "waiting", "ready"]]]

    def get_amount_total_words(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            amount_total_words = utils.num2word(obj.amount_total)
            vals[obj.id] = amount_total_words
            return vals

    def approve(self, ids, context={}):
        if not check_permission_other("sale_approve_done"):
            raise Exception("Permission denied")
        obj = self.browse(ids)[0]
        user_id = get_active_user()
        obj.write({"approved_by_id": user_id})
        return {
            "next": {
                "name": "sale",
                "mode": "form",
                "active_id": obj.id,
            },
            "flash": "Sales order approved successfully",
        }

    def find_sale_line(self, ids, product_id, context={}):
        obj = self.browse(ids)[0]
        for line in obj.lines:
            if line.product_id.id == product_id:
                return line.id
        return None

    def onchange_sequence(self, context={}):
        data = context["data"]
        context['date'] = data['date']
        seq_id = data["sequence_id"]
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            res = self.search([["number", "=", num]])
            if not res:
                break
            get_model("sequence").increment_number(seq_id, context=context)
        data["number"] = num
        return data

    def get_state_label(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.state == "draft":
                s = "Draft"
            if obj.state == "confirmed":
                s = "Confirmed"
            elif obj.state == "done":
                s = "Completed"
            elif obj.state == "voided":
                s = "Voided"
            else:
                s = "/"
            vals[obj.id] = s
        return vals

    def get_ship_tracking(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            track_nos = []
            for pick in obj.pickings:
                if pick.ship_tracking:
                    if pick.ship_tracking:
                        track_nos.append(pick.ship_tracking)
            vals[obj.id] = ",".join(track_nos)
        return vals

    def get_pickings(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            pick_ids = []
            for move in obj.stock_moves:
                pick_ids.append(move.picking_id.id)
            pick_ids = sorted(list(set(pick_ids)))
            vals[obj.id] = pick_ids
        return vals

    def copy_to_job(self, ids, context={}):
        obj = self.browse(ids)[0]
        tmpl = obj.job_template_id
        if not tmpl:
            raise Exception("Missing service order template in sales order")
        #job_id = tmpl.create_job(sale_id=obj.id)
        sale = get_model("sale.order").browse(obj.id)
        contact_id = sale.contact_id.id
        vals = {
            "number": get_model("job")._get_number(),
            "contact_id": contact_id,
            "template_id": obj.job_template_id.id,
            "service_type_id": obj.job_template_id.service_type_id.id,
            "state": "planned",
            "related_id": "sale.order,%s" % obj.id,
            "lines": [],
        }
        template_products = []
        for line in obj.job_template_id.lines:
            line_vals = {
                "sequence": line.sequence,
                "type": line.type,
                "product_id": line.product_id.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
                "amount": line.amount,
                "payment_type": "job",
            }
            vals["lines"].append(("create", line_vals))
            template_products.append((line.product_id.id,line.description))
        for line in obj.lines:
            if (line.product_id.id,line.description) not in template_products:
                line_vals = {
                    "sequence": line.sequence,
                    "type": "parts" if line.product_id.type == "stockable" else "other",
                    "product_id": line.product_id.id,
                    "description": line.description,
                    "qty": line.qty,
                    "uom_id": line.uom_id.id,
                    "unit_price": line.unit_price,
                    "amount": line.amount,
                    "payment_type": "job",
                }
                vals["lines"].append(("create", line_vals))
        job_id = get_model("job").create(vals)
        job = get_model("job").browse(job_id)
        return {
            "flash": "Service order %s created from sales order %s" % (job.number, obj.number),
            "next": {
                "name": "job",
                "mode": "form",
                "active_id": job_id,
            },
        }

    def get_profit(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            est_cost_total = 0
            act_cost_total = 0
            for cost in obj.costs:
                amt = cost.amount or 0
                if cost.currency_id:
                    amt = get_model("currency").convert(amt, cost.currency_id.id, obj.currency_id.id)
                est_cost_total += amt
                act_amt = cost.actual_amount or 0
                if cost.currency_id:
                    act_amt = get_model("currency").convert(act_amt, cost.currency_id.id, obj.currency_id.id)
                act_cost_total += act_amt
            est_profit = obj.amount_subtotal - est_cost_total
            est_profit_percent = est_profit * 100 / obj.amount_subtotal if obj.amount_subtotal else None
            act_profit = obj.amount_subtotal - act_cost_total
            act_profit_percent = act_profit * 100 / obj.amount_subtotal if obj.amount_subtotal else None
            vals[obj.id] = {
                "est_cost_total": est_cost_total,
                "est_profit": est_profit,
                "est_profit_percent": est_profit_percent,
                "act_cost_total": act_cost_total,
                "act_profit": act_profit,
                "act_profit_percent": act_profit_percent,
            }
        return vals

    def onchange_cost_product(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if prod_id:
            prod = get_model("product").browse(prod_id)
            line["description"] = prod.description
            line["unit_price"] = prod.landed_cost
            line["qty"] = 1
            line["uom_id"] = prod.uom_id.id
            line["currency_id"] = prod.purchase_currency_id.id
            line["purchase_duty_percent"] = prod.purchase_duty_percent
            line["purchase_ship_percent"] = prod.purchase_ship_percent
            line["landed_cost"] = prod.landed_cost
            line["purchase_price"] = prod.purchase_price
            if prod.suppliers:
                line["supplier_id"] = prod.suppliers[0].supplier_id.id
        return data

    def get_cost_per_supplier(self, ids, context):
        vals = {}
        for obj in self.browse(ids):
            sup_cost = {}
            for line in obj.costs:
                sup = line.supplier_id.name if line.supplier_id else "/"
                sup_cost.setdefault(sup, [0, 0])
                sup_cost[sup][0] += line.amount or 0
                sup_cost[sup][1] += line.actual_amount or 0
            data = []
            for sup in sorted(sup_cost):
                data.append({
                    "name": sup,
                    "est_cost_total": sup_cost[sup][0],
                    "act_cost_total": sup_cost[sup][1],
                })
            vals[obj.id] = data
        return vals

    def cancel_unpaid_order(self, num_days=7):
        exp_date = datetime.now() - timedelta(days=num_days)
        exp_date = exp_date.strftime("%Y-%m-%d")
        res = self.search([["date", "<", exp_date], ["state", "=", "confirmed"]])
        number = "Expired Date-" + exp_date + " Order -"
        for obj in self.browse(res):
            if not obj.is_paid:
                number += obj.number + "-"
                for pick in obj.pickings:
                    pick.void()
                for inv in obj.invoices:
                    if inv.state == "waiting_payment":
                        inv.void()
                obj.void()
        print(number)

    def get_est_profit(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            cost=0
            for line in obj.lines:
                cost+=line.est_cost_amount or 0
            profit=obj.amount_subtotal-cost
            margin=profit*100/obj.amount_subtotal if obj.amount_subtotal else None
            vals[obj.id] = {
                "est_cost_amount": cost,
                "est_profit_amount": profit,
                "est_margin_percent": margin,
            }
        return vals

    def get_track_entries(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            if not obj.track_id:
                vals[obj.id]=[]
                continue
            res=get_model("account.track.entry").search([["track_id","child_of",obj.track_id.id]])
            vals[obj.id]=res
        return vals

    def write_track_entries(self,ids,field,val,context={}):
        for op in val:
            if op[0]=="create":
                rel_vals=op[1]
                for obj in self.browse(ids):
                    if not obj.track_id:
                        continue
                    rel_vals["track_id"]=obj.track_id.id
                    get_model("account.track.entry").create(rel_vals,context=context)
            elif op[0]=="write":
                rel_ids=op[1]
                rel_vals=op[2]
                get_model("account.track.entry").write(rel_ids,rel_vals,context=context)
            elif op[0]=="delete":
                rel_ids=op[1]
                get_model("account.track.entry").delete(rel_ids,context=context)

    def get_act_profit(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            cost=0
            for line in obj.track_entries:
                cost-=line.amount
            subtotal=obj.amount_subtotal or 0
            profit=subtotal-cost
            margin=profit*100/subtotal if subtotal else None
            vals[obj.id] = {
                "act_cost_amount": cost,
                "act_profit_amount": profit,
                "act_margin_percent": margin,
            }
        return vals

    def create_track(self,ids,context={}):
        obj=self.browse(ids[0])
        count=0
        code=obj.number
        res=get_model("account.track.categ").search([["code","=",code]])
        if res:
            sale_track_id=res[0]
        else:
            sale_track_id=get_model("account.track.categ").create({
                "code": code,
                "name": code,
                "type": "1",
                })
            count+=1
        obj.write({"track_id":sale_track_id})
        for line in obj.lines:
            if not line.sequence:
                raise Exception("Missing sequence in sales order line")
            code="%s / %s"%(obj.number,line.sequence)
            res=get_model("account.track.categ").search([["code","=",code]])
            if res:
                continue
            vals={
                "code": code,
                "parent_id": sale_track_id,
                "name": obj.number, #XXX
                "type": "1",
            }
            get_model("account.track.categ").create(vals)
            count+=1
        return {
            "next": {
                "name": "sale",
                "mode": "form",
                "active_id": obj.id,
            },
            "flash": "%d tracking codes created"%count,
        }

    def create_est_costs(self,ids,context={}):
        obj=self.browse(ids[0])
        obj.write({"est_costs":[("delete_all",)]})
        line_sequence = 1
        for line in obj.lines:
            cur_line_sequence = line_sequence
            prod=line.product_id
            if not prod:
                continue
            if not prod.purchase_price and prod.type != "service":
                continue
            if not prod.cost_price and prod.type == "service":
                continue
            if "bundle" == prod.type:
                continue

            # update line seqence
            if not line.sequence:
                line.write({"sequence": cur_line_sequence})
                line_sequence += 1
            else:
                line_sequence = round(Decimal(line.sequence)) + Decimal(1)

            landed_cost = prod.landed_cost
            # compute cost if product is service
            if prod.type == "service":
                if prod.uom_id.type=='time': #day
                    landed_cost = prod.cost_price or 0
                elif prod.uom_id.type=='unit': #job
                    landed_cost = (prod.sale_price or 0) * (prod.cost_price or 0)
            elif prod.type == "stock" and prod.supply_method == 'production':
                    landed_cost = prod.cost_price or 0
            vals={
                "sale_id": obj.id,
                "sequence": line.sequence,
                "product_id": prod.id,
                "description": prod.name,
                "supplier_id": prod.suppliers[0].supplier_id.id if prod.suppliers else None,
                "list_price": prod.purchase_price,
                "purchase_price": prod.purchase_price,
                "landed_cost": landed_cost,
                "purchase_duty_percent": prod.purchase_duty_percent,
                "purchase_ship_percent": prod.purchase_ship_percent,
                "qty": line.qty,
                "currency_id": prod.purchase_currency_id.id,
                "currency_rate": prod.purchase_currency_rate,
            }
            get_model("sale.cost").create(vals)
            if not obj.track_id:
                obj.create_track()

    def copy_cost_to_purchase(self, ids, context={}):
        obj = self.browse(ids)[0]
        suppliers = {}
        for cost in obj.est_costs:
            prod = line.product_id
            if not prod:
                continue
            if not prod.suppliers:
                raise Exception("Missing supplier for product '%s'" % prod.name)
            supplier_id = prod.suppliers[0].supplier_id.id
            suppliers.setdefault(supplier_id, []).append((prod.id, line.qty, line.uom_id.id))
        if not suppliers:
            raise Exception("No purchase orders to create")
        po_ids = []
        for supplier_id, lines in suppliers.items():
            purch_vals = {
                "contact_id": supplier_id,
                "ref": obj.number,
                "lines": [],
            }
            for prod_id, qty, uom_id in lines:
                prod = get_model("product").browse(prod_id)
                line_vals = {
                    "product_id": prod_id,
                    "description": prod.description or "/",
                    "qty": qty,
                    "uom_id": uom_id,
                    "unit_price": prod.purchase_price or 0,
                    "tax_id": prod.purchase_tax_id.id,
                    "sale_id": obj.id,
                }
                purch_vals["lines"].append(("create", line_vals))
            po_id = get_model("purchase.order").create(purch_vals)
            po_ids.append(po_id)
        po_objs = get_model("purchase.order").browse(po_ids)
        return {
            "next": {
                "name": "purchase",
                "search_condition": [["ref", "=", obj.number]],
            },
            "flash": "Purchase orders created successfully: " + ", ".join([po.number for po in po_objs]),
        }

    def get_relative_currency_rate(self,ids,currency_id):
        obj=self.browse(ids[0])
        rate=None
        for r in obj.currency_rates:
            if r.currency_id.id==currency_id:
                rate=r.rate
                break
        if rate is None:
            rate_from=get_model("currency").get_rate([currency_id],obj.date) or Decimal(1)
            rate_to=obj.currency_id.get_rate(obj.date) or Decimal(1)
            rate=rate_from/rate_to
        return rate

    def copy_to_sale_return(self,ids,context={}):
        for obj in self.browse(ids):
            order_vals = {}
            order_vals = {
                "contact_id":obj.contact_id.id,
                "date":obj.date,
                "ref":obj.number,
                "due_date":obj.due_date,
                "currency_id":obj.currency_id.id,
                "tax_type":obj.tax_type,
                "bill_address_id":obj.bill_address_id.id,
                "ship_address_id":obj.ship_address_id.id,
                "orig_sale_id": obj.id,
                "lines":[],
            }
            for line in obj.lines:
                line_vals = {
                    "product_id":line.product_id.id,
                    "description":line.description,
                    "qty":line.qty,
                    "uom_id":line.uom_id.id,
                    "unit_price":line.unit_price,
                    "discount":line.discount,
                    "discount_amount":line.discount_amount,
                    "tax_id":line.tax_id.id,
                    "amount":line.amount,
                    "location_id":line.location_id.id,
                }
                order_vals["lines"].append(("create", line_vals))
            sale_id = get_model("sale.return").create(order_vals)
            sale = get_model("sale.return").browse(sale_id)
        return {
            "next": {
                "name": "sale_return",
                "mode": "form",
                "active_id": sale_id,
            },
            "flash": "Sale Return %s created from sales order %s" % (sale.number, obj.number),
            "order_id": sale_id,
        }

    def get_template_sale_form(self, ids, context={}):
        #obj = self.browse(ids)[0]
        return "sale_form"

    def update_cost_amount(self,context={}):
        data=context['data']
        path=context['path']
        line=get_data_path(data,path,parent=True)
        line['amount']=(line['qty'] or 0) *(line['landed_cost'] or 0)
        return data

SaleOrder.register()
