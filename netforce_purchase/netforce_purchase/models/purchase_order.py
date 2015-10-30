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
from netforce.access import get_active_company, get_active_user, set_active_user
from . import utils
from decimal import Decimal


class PurchaseOrder(Model):
    _name = "purchase.order"
    _string = "Purchase Order"
    _audit_log = True
    _name_field = "number"
    _multi_company = True
    _key = ["company_id", "number"]
    _fields = {
        "number": fields.Char("Number", required=True, search=True),
        "ref": fields.Char("Ref", search=True),
        "contact_id": fields.Many2One("contact", "Supplier", required=True, search=True),
        "customer_id": fields.Many2One("contact", "Customer", search=True),
        "date": fields.Date("Date", required=True, search=True),
        "date_required": fields.Date("Required Date"),
        "state": fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed"), ("done", "Completed"), ("voided", "Voided")], "Status", required=True),
        "lines": fields.One2Many("purchase.order.line", "order_id", "Lines"),
        "amount_subtotal": fields.Decimal("Subtotal", function="get_amount", function_multi=True, store=True),
        "amount_tax": fields.Decimal("Tax Amount", function="get_amount", function_multi=True, store=True),
        "amount_total": fields.Decimal("Total", function="get_amount", function_multi=True, store=True),
        "amount_total_cur": fields.Decimal("Total", function="get_amount", function_multi=True, store=True),
        "amount_total_words": fields.Char("Total Words", function="get_amount_total_words"),
        "qty_total": fields.Decimal("Total Quantity", function="get_qty_total"),
        "currency_id": fields.Many2One("currency", "Currency", required=True),
        "tax_type": fields.Selection([["tax_ex", "Tax Exclusive"], ["tax_in", "Tax Inclusive"], ["no_tax", "No Tax"]], "Tax Type", required=True),
        "invoice_lines": fields.One2Many("account.invoice.line", "purch_id", "Invoice Lines"),
        #"stock_moves": fields.One2Many("stock.move","purch_id","Stock Moves"),
        "invoices": fields.One2Many("account.invoice", "related_id", "Invoices"),
        "pickings": fields.Many2Many("stock.picking", "Stock Pickings", function="get_pickings"),
        "is_delivered": fields.Boolean("Delivered", function="get_delivered"),
        "is_paid": fields.Boolean("Paid", function="get_paid"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "location_id": fields.Many2One("stock.location", "Warehouse"),  # XXX: deprecated
        "delivery_date": fields.Date("Delivery Date"),
        "ship_method_id": fields.Many2One("ship.method", "Shipping Method"),  # XXX: deprecated
        "payment_terms": fields.Text("Payment Terms"),
        "ship_term_id": fields.Many2One("ship.term", "Shipping Terms"),
        "price_list_id": fields.Many2One("price.list", "Price List", condition=[["type", "=", "purchase"]]),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "company_id": fields.Many2One("company", "Company"),
        "purchase_type_id": fields.Many2One("purchase.type", "Purchase Type"),
        "other_info": fields.Text("Other Info"),
        "bill_address_id": fields.Many2One("address", "Billing Address"),
        "ship_address_id": fields.Many2One("address", "Shipping Address"),
        "sequence_id": fields.Many2One("sequence", "Number Sequence"),
        "stock_moves": fields.One2Many("stock.move", "related_id", "Stock Movements"),
        "agg_amount_total": fields.Decimal("Total Amount", agg_function=["sum", "amount_total"]),
        "year": fields.Char("Year", sql_function=["year", "date"]),
        "quarter": fields.Char("Quarter", sql_function=["quarter", "date"]),
        "month": fields.Char("Month", sql_function=["month", "date"]),
        "week": fields.Char("Week", sql_function=["week", "date"]),
        "agg_amount_subtotal": fields.Decimal("Total Amount w/o Tax", agg_function=["sum", "amount_subtotal"]),
        "user_id": fields.Many2One("base.user", "Owner", search=True),
        "emails": fields.One2Many("email.message", "related_id", "Emails"),
    }
    _order = "date desc,number desc"

    _sql_constraints = [
        ("key_uniq", "unique (company_id, number)", "The number of each company must be unique!")
    ]

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence(type="purchase_order")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id)
            user_id = get_active_user()
            set_active_user(1)
            res = self.search([["number", "=", num]])
            set_active_user(user_id)
            if not res:
                return num
            get_model("sequence").increment_number(seq_id)

    def _get_currency(self, context={}):
        settings = get_model("settings").browse(1)
        return settings.currency_id.id

    _defaults = {
        "state": "draft",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "number": _get_number,
        "currency_id": _get_currency,
        "tax_type": "tax_ex",
        "company_id": lambda *a: get_active_company(),
        "user_id": lambda *a: get_active_user(),
    }

    def create(self, vals, **kw):
        id = super(PurchaseOrder, self).create(vals, **kw)
        self.function_store([id])
        return id

    def write(self, ids, vals, **kw):
        super(PurchaseOrder, self).write(ids, vals, **kw)
        self.function_store(ids)

    def confirm(self, ids, context={}):
        for obj in self.browse(ids):
            if obj.state != "draft":
                raise Exception("Invalid state")
            for line in obj.lines:
                prod = line.product_id
                if prod and prod.type in ("stock", "consumable", "bundle") and not line.location_id:
                    raise Exception("Missing location for product %s" % prod.code)
            obj.write({"state": "confirmed"})
            obj.trigger("confirm")

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

    def get_amount(self, ids, context={}):
        settings = get_model("settings").browse(1)
        res = {}
        for obj in self.browse(ids):
            vals = {}
            subtotal = 0
            tax = 0
            for line in obj.lines:
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
            res[obj.id] = vals
        return res

    def get_qty_total(self, ids, context={}):
        res = {}
        for obj in self.browse(ids):
            qty = sum([line.qty for line in obj.lines])
            res[obj.id] = qty or 0
        return res

    def update_amounts(self, context):
        data = context["data"]
        data["amount_subtotal"] = 0
        data["amount_tax"] = 0
        tax_type = data["tax_type"]
        for line in data["lines"]:
            if not line:
                continue
            amt = Decimal(((line.get("qty") or 0) * (line.get("unit_price") or 0)) - (line.get("discount_amount") or 0))
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
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        line["description"] = prod.description
        line["qty"] = 1
        if prod.uom_id is not None:
            line["uom_id"] = prod.uom_id.id
        pricelist_id = data["price_list_id"]
        price = None
        if pricelist_id:
            price = get_model("price.list").get_price(pricelist_id, prod.id, 1)
            price_list = get_model("price.list").browse(pricelist_id)
            price_currency_id = price_list.currency_id.id
        if price is None:
            price = prod.purchase_price
            settings = get_model("settings").browse(1)
            price_currency_id = settings.currency_id.id
        if price is not None:
            currency_id = data["currency_id"]
            price_cur = get_model("currency").convert(price, price_currency_id, currency_id)
            line["unit_price"] = price_cur
        if prod.purchase_tax_id is not None:
            line["tax_id"] = prod.purchase_tax_id.id
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
            price = prod.purchase_price
            settings = get_model("settings").browse(1)
            price_currency_id = settings.currency_id.id
        if price is not None:
            currency_id = data["currency_id"]
            price_cur = get_model("currency").convert(price, price_currency_id, currency_id)
            line["unit_price"] = price_cur
        data = self.update_amounts(context)
        return data

    def copy_to_picking(self, ids, context):
        id = ids[0]
        settings=get_model("settings").browse(1)
        obj = self.browse(id)
        contact = obj.contact_id
        pick_vals = {
            "type": "in",
            "ref": obj.number,
            "related_id": "purchase.order,%s" % obj.id,
            "contact_id": contact.id,
            "currency_id": obj.currency_id.id,
            "lines": [],
        }
        if contact and contact.pick_in_journal_id:
            pick_vals["journal_id"] = contact.pick_in_journal_id.id
        res = get_model("stock.location").search([["type", "=", "supplier"]],order="id")
        if not res:
            raise Exception("Supplier location not found")
        supp_loc_id = res[0]
        res = get_model("stock.location").search([["type", "=", "internal"]])
        if not res:
            raise Exception("Warehouse not found")
        wh_loc_id = res[0]
        for line in obj.lines:
            prod = line.product_id
            if prod.type not in ("stock", "consumable"):
                continue
            remain_qty = line.qty - line.qty_received
            if remain_qty <= 0:
                continue
            unit_price=line.amount/line.qty if line.qty else 0
            cost_price_cur=unit_price
            #if obj.tax_type=="tax_ex":
                #cost_price_cur=unit_price
            if obj.tax_type=="tax_in":
                if line.tax_id:
                    tax_amt = get_model("account.tax.rate").compute_tax(
                        line.tax_id.id, unit_price, tax_type=obj.tax_type)
                else:
                    tax_amt = 0
                cost_price_cur=round(unit_price-tax_amt,2)
            cost_price=get_model("currency").convert(cost_price_cur,obj.currency_id.id,settings.currency_id.id)
            cost_amount=cost_price*remain_qty
            line_vals = {
                "product_id": prod.id,
                "qty": remain_qty,
                "uom_id": line.uom_id.id,
                "cost_price_cur": cost_price_cur,
                "cost_price": cost_price,
                "cost_amount": cost_amount,
                "location_from_id": supp_loc_id,
                "location_to_id": line.location_id.id or wh_loc_id,
                "related_id": "purchase.order,%s" % obj.id,
            }
            pick_vals["lines"].append(("create", line_vals))
        if not pick_vals["lines"]:
            raise Exception("Nothing left to receive")
        pick_id = get_model("stock.picking").create(pick_vals, {"pick_type": "in"})
        pick = get_model("stock.picking").browse(pick_id)
        return {
            "next": {
                "name": "pick_in",
                "mode": "form",
                "active_id": pick_id,
            },
            "flash": "Goods receipt %s created from purchase order %s" % (pick.number, obj.number),
        }

    def copy_to_invoice(self, ids, context={}):
        id = ids[0]
        obj = self.browse(id)
        contact = obj.contact_id
        inv_vals = {
            "type": "in",
            "inv_type": "invoice",
            "ref": obj.number,
            "related_id": "purchase.order,%s" % obj.id,
            "contact_id": obj.contact_id.id,
            "currency_id": obj.currency_id.id,
            "lines": [],
            "tax_type": obj.tax_type,
        }
        if contact.purchase_journal_id:
            inv_vals["journal_id"] = contact.purchase_journal_id.id
            if contact.purchase_journal_id.sequence_id:
                inv_vals["sequence_id"] = contact.purchase_journal_id.sequence_id.id
        for line in obj.lines:
            prod = line.product_id
            remain_qty = line.qty - line.qty_invoiced
            if remain_qty <= 0:
                continue
            line_vals = {
                "product_id": prod.id,
                "description": line.description,
                "qty": remain_qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
                "account_id": prod and prod.purchase_account_id.id or None,
                "tax_id": line.tax_id.id,
                "amount": line.amount,
            }
            inv_vals["lines"].append(("create", line_vals))
        if not inv_vals["lines"]:
            raise Exception("Nothing left to invoice")
        inv_id = get_model("account.invoice").create(inv_vals, {"type": "in", "inv_type": "invoice"})
        inv = get_model("account.invoice").browse(inv_id)
        return {
            "next": {
                "name": "view_invoice",
                "active_id": inv_id,
            },
            "flash": "Invoice %s created from purchase order %s" % (inv.number, obj.number),
        }

    def get_delivered(self, ids, context={}):
        vals = {}
        #import pdb; pdb.set_trace()
        for obj in self.browse(ids):
            is_delivered = True
            for line in obj.lines:
                prod = line.product_id
                if prod.type not in ("stock", "consumable"):
                    continue
                remain_qty = line.qty - line.qty_received
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
        obj = self.browse(ids)[0]
        for pick in obj.pickings:
            if pick.state != "voided":
                raise Exception("There are still goods receipts for this purchase order")
        for inv in obj.invoices:
            if inv.state != "voided":
                raise Exception("There are still invoices for this purchase order")
        obj.write({"state": "voided"})

    def copy(self, ids, context):
        obj = self.browse(ids)[0]
        vals = {
            "contact_id": obj.contact_id.id,
            "date": obj.date,
            "ref": obj.ref,
            "currency_id": obj.currency_id.id,
            "tax_type": obj.tax_type,
            "lines": [],
        }
        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
                "tax_id": line.tax_id.id,
            }
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals)
        new_obj = self.browse(new_id)
        return {
            "next": {
                "name": "purchase",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "Purchase order %s copied to %s" % (obj.number, new_obj.number),
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
        data["price_list_id"] = contact.purchase_price_list_id.id
        return data

    def check_received_qtys(self, ids, context={}):
        obj = self.browse(ids)[0]
        for line in obj.lines:
            if line.qty_received > line.qty:
                raise Exception("Can not receive excess quantity for purchase order %s and product %s (order qty: %s, received qty: %s)" % (
                    obj.number, line.product_id.code, line.qty, line.qty_received))

    def get_purchase_form_template(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.state == "draft":
            return "rfq_form"
        else:
            return "purchase_form"

    def get_amount_total_words(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            amount_total_words = utils.num2word(obj.amount_total)
            vals[obj.id] = amount_total_words
            return vals

    def onchange_sequence(self, context={}):
        data = context["data"]
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

    def delete(self, ids, **kw):
        for obj in self.browse(ids):
            if obj.state in ("confirmed", "done"):
                raise Exception("Can not delete purchase order in this status")
        super().delete(ids, **kw)

PurchaseOrder.register()
