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
from netforce.utils import get_data_path
import time
from netforce.access import get_active_user, set_active_user
from netforce.access import get_active_company, check_permission_other, set_active_company
from . import utils
from datetime import datetime, timedelta
from decimal import Decimal


class SaleReturn(Model):
    _name = "sale.return"
    _string = "Sales Return"
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
        "lines": fields.One2Many("sale.return.line", "order_id", "Lines"),
        "amount_subtotal": fields.Decimal("Subtotal", function="get_amount", function_multi=True, store=True),
        "amount_tax": fields.Decimal("Tax Amount", function="get_amount", function_multi=True, store=True),
        "amount_total": fields.Decimal("Total", function="get_amount", function_multi=True, store=True),
        "amount_total_discount": fields.Decimal("Total Discount", function="get_amount", function_multi=True, store=True),
        "amount_total_words": fields.Char("Total Words", function="get_amount_total_words"),
        "amount_total_cur": fields.Decimal("Total", function="get_amount", function_multi=True, store=True),
        "qty_total": fields.Decimal("Total", function="get_qty_total"),
        "currency_id": fields.Many2One("currency", "Currency", required=True),
        "user_id": fields.Many2One("base.user", "Owner", search=True),
        "tax_type": fields.Selection([["tax_ex", "Tax Exclusive"], ["tax_in", "Tax Inclusive"], ["no_tax", "No Tax"]], "Tax Type", required=True),
        "invoice_lines": fields.One2Many("account.invoice.line", "sale_id", "Invoice Lines"),
        "invoices": fields.One2Many("account.invoice", "related_id", "Credit Notes"),
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
        "company_id": fields.Many2One("company", "Company"),
        "production_status": fields.Json("Production", function="get_production_status"),
        "ship_term_id": fields.Many2One("ship.term", "Shipping Terms"),
        "approved_by_id": fields.Many2One("base.user", "Approved By", readonly=True),
        "sequence_id": fields.Many2One("sequence", "Number Sequence"),
        "stock_moves": fields.One2Many("stock.move", "related_id", "Stock Movements"),
        "agg_amount_total": fields.Decimal("Total Amount", agg_function=["sum", "amount_total"]),
        "agg_amount_subtotal": fields.Decimal("Total Amount w/o Tax", agg_function=["sum", "amount_subtotal"]),
        "agg_est_profit": fields.Decimal("Total Estimated Profit", agg_function=["sum", "est_profit"]),
        "agg_act_profit": fields.Decimal("Total Actual Profit", agg_function=["sum", "act_profit"]),
        "year": fields.Char("Year", sql_function=["year", "date"]),
        "quarter": fields.Char("Quarter", sql_function=["quarter", "date"]),
        "month": fields.Char("Month", sql_function=["month", "date"]),
        "week": fields.Char("Week", sql_function=["week", "date"]),
        "pay_method_id": fields.Many2One("payment.method", "Payment Method",search=True),
        "related_id": fields.Reference([["sale.quot", "Quotation"], ["ecom.cart", "Ecommerce Cart"], ["purchase.order", "Purchase Order"]], "Related To"),
        "orig_sale_id": fields.Many2One("sale.order","Original Sales Order"),
    }

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence(type="sale_return",context=context)
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            if not num:
                return None
            res = self.search([["number", "=", num]])
            if not res:
                return num
            get_model("sequence").increment_number(seq_id, context=context)

    def _get_currency(self, context={}):
        settings = get_model("settings").browse(1)
        return settings.currency_id.id

    _defaults = {
        "state": "draft",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "number": _get_number,
        "currency_id": _get_currency,
        "tax_type": "tax_ex",
        "user_id": lambda *a: get_active_user(),
        "company_id": lambda *a: get_active_company(),
    }
    _order = "date desc,number desc"

    def create(self, vals, context={}):
        id = super().create(vals, context)
        self.function_store([id])
        return id

    def write(self, ids, vals, **kw):
        super().write(ids, vals, **kw)
        self.function_store(ids)

    def delete(self, ids, **kw):
        for obj in self.browse(ids):
            if obj.state in ("confirmed", "done"):
                raise Exception("Can not delete sales order in this status")
        super(self).delete(ids, **kw)

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
            vals["amount_subtotal"] = subtotal
            vals["amount_tax"] = tax
            vals["amount_total"] = subtotal + tax
            vals["amount_total_cur"] = get_model("currency").convert(
                vals["amount_total"], obj.currency_id.id, settings.currency_id.id)
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
        obj.trigger("confirm")
        return {
            "next": {
                "name": "sale_return",
                "mode": "form",
                "active_id": obj.id,
            },
            "flash": "Sales Return %s confirmed" % obj.number,
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

    def update_amounts(self, context):
        data = context["data"]
        data["amount_subtotal"] = 0
        data["amount_tax"] = 0
        tax_type = data["tax_type"]
        for line in data["lines"]:
            if not line:
                continue
            amt = (line.get("qty") or 0) * (line.get("unit_price") or 0)
            if line.get("discount"):
                disc = amt * line["discount"] / 100
                amt -= disc
            if line.get("discount_amount"):
                amt -= line["discount_amount"]
            line["amount"] = amt
            tax_id = line.get("tax_id")
            if tax_id:
                tax = get_model("account.tax.rate").compute_tax(tax_id, amt, tax_type=tax_type)
                data["amount_tax"] += tax
            else:
                tax = 0
            if tax_type == "tax_in":
                data["amount_subtotal"] += amt - tax
            else:
                data["amount_subtotal"] += amt
        data["amount_total"] = data["amount_subtotal"] + data["amount_tax"]
        return data

    def onchange_product(self, context):
        data = context["data"]
        contact_id = data.get("contact_id")
        if contact_id:
            contact = get_model("contact").browse(contact_id)
        else:
            contact = None
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        line["description"] = prod.description or "/"
        line["qty"] = 1
        line["uom_id"] = prod.sale_uom_id.id or prod.uom_id.id
        pricelist_id = data["price_list_id"]
        price = None
        if pricelist_id:
            price = get_model("price.list").get_price(pricelist_id, prod.id, 1)
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
            pick_vals[picking_key] = {
                "type": "in",
                "ref": obj.number,
                "related_id": "sale.return,%s" % obj.id,
                "contact_id": contact.id,
                "ship_address_id": obj.ship_address_id.id,
                "lines": [],
                "state": "draft",
                "ship_method_id": obj_line.ship_method_id.id or obj.ship_method_id.id,
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
            qty_remain = (line.qty_stock or line.qty) - line.qty_received
            if qty_remain <= 0:
                continue
            line_vals = {
                "product_id": prod.id,
                "qty": qty_remain,
                "uom_id": prod.uom_id.id if line.qty_stock else line.uom_id.id,
                "location_from_id": cust_loc_id,
                "location_to_id": line.location_id.id or wh_loc_id,
                "related_id": "sale.return,%s" % obj.id,
            }
            pick_vals[picking_key]["lines"].append(("create", line_vals))
        for picking_key, picking_value in pick_vals.items():
            if not picking_value["lines"]: Exception("Nothing left to deliver")
            pick_id = get_model("stock.picking").create(picking_value, context={"pick_type": "in"})
            pick = get_model("stock.picking").browse(pick_id)
        return {
            "next": {
                "name": "pick_in",
                "mode": "form",
                "active_id": pick_id,
            },
            "flash": "Picking %s created from sales order %s" % (pick.number, obj.number),
            "picking_id": pick_id,
        }

    def copy_to_credit_note(self, ids, context={}):
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
                    "inv_type": "credit",
                    "ref": obj.number,
                    "related_id": "sale.return,%s" % obj.id,
                    "contact_id": contact.id,
                    "bill_address_id": obj.bill_address_id.id,
                    "currency_id": obj.currency_id.id,
                    "tax_type": obj.tax_type,
                    "pay_method_id": obj.pay_method_id.id,
                    "lines": [],
                }
                if contact.sale_journal_id:
                    inv_vals["journal_id"] = contact.sale_journal_id.id
                    if contact.sale_journal_id.sequence_id:
                        inv_vals["sequence_id"] = contact.sale_journal_id.sequence_id.id
                for line in obj.lines:
                    if not line.unit_price:
                        continue
                    if line.ship_method_id.id!=ship_method_id:
                        continue
                    prod = line.product_id
                    remain_qty = line.qty - line.qty_invoiced
                    if remain_qty <= 0:
                        continue

                    sale_acc_id=None
                    if prod:
                        #1. get account from product
                        sale_acc_id=prod.sale_return_account_id and prod.sale_return_account_id.id
                        if not sale_acc_id and prod.sale_account_id:
                            sale_acc_id=prod.sale_account_id.id
                        # 2. if not get from master/parent product
                        if not sale_acc_id and prod.parent_id:
                            sale_acc_id=prod.parent_id.sale_account_id.id
                        # 3. if not get from product category
                        categ=prod.categ_id
                        if categ and not sale_acc_id:
                            sale_acc_id= categ.sale_account_id and categ.sale_account_id.id or None

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
                        "amount": line.qty*line.unit_price*(1-(line.discount or Decimal(0))/100)-(line.discount_amount or Decimal(0)),
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
                "flash": "Credit note created from sales order %s" % obj.number,
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
                if prod.type not in ("stock", "consumable", "bundle"):
                    continue
                remain_qty = (line.qty_stock or line.qty) - line.qty_received
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
                "name": "sale_return",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "Sales Return %s copied to %s" % (obj.number, new_obj.number),
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
        if not contact_id:
            return {}
        contact = get_model("contact").browse(contact_id)
        data["payment_terms"] = contact.payment_terms
        data["price_list_id"] = contact.sale_price_list_id.id
        data["bill_address_id"] = contact.get_address(pref_type="billing")
        data["ship_address_id"] = contact.get_address(pref_type="shipping")
        return data

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

    def get_pickings(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            pick_ids = []
            for move in obj.stock_moves:
                pick_ids.append(move.picking_id.id)
            pick_ids = sorted(list(set(pick_ids)))
            vals[obj.id] = pick_ids
        return vals

SaleReturn.register()
