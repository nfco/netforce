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


class InvoiceLine(Model):
    _name = "account.invoice.line"
    _fields = {
        "invoice_id": fields.Many2One("account.invoice", "Invoice", required=True, on_delete="cascade"),
        "product_id": fields.Many2One("product", "Product"),
        "description": fields.Text("Description", required=True),
        "qty": fields.Decimal("Qty"),
        "uom_id": fields.Many2One("uom", "UoM"),
        "unit_price": fields.Decimal("Unit Price", scale=6),
        "discount": fields.Decimal("Disc %"),  # XXX: rename to discount_percent later
        "discount_amount": fields.Decimal("Disc Amt"),
        "account_id": fields.Many2One("account.account", "Account", condition=[["type", "!=", "view"]]),
        "tax_id": fields.Many2One("account.tax.rate", "Tax Rate", on_delete="restrict"),
        "amount": fields.Decimal("Amount", required=True),
        "invoice_date": fields.Date("Invoice Date", function="_get_related", function_context={"path": "invoice_id.date"}),
        "invoice_contact_id": fields.Many2One("contact", "Invoice Partner", function="_get_related", function_context={"path": "invoice_id.contact_id"}),
        "purch_id": fields.Many2One("purchase.order", "Purchase Order"),
        "track_id": fields.Many2One("account.track.categ", "Track-1", condition=[["type", "=", "1"]]),
        "track2_id": fields.Many2One("account.track.categ", "Track-2", condition=[["type", "=", "2"]]),
        "amount_discount": fields.Decimal("Discount", function="get_discount"),
        "related_id": fields.Reference([["sale.order", "Sales Order"], ["purchase.order", "Purchase Order"], ["production.order","Production Order"], ["project", "Project"], ["job", "Service Order"], ["service.contract", "Service Contract"]], "Related To"),
        "sale_id": fields.Many2One("sale.order", "Sale Order"),
        "purchase_id": fields.Many2One("purchase.order","Purchase Order"),
    }

    def create(self, vals, **kw):
        id = super(InvoiceLine, self).create(vals, **kw)
        sale_id = vals.get("sale_id")
        if sale_id:
            get_model("sale.order").function_store([sale_id])
        purch_id = vals.get("purch_id")
        if purch_id:
            get_model("purchase.order").function_store([purch_id])
        return id

    def write(self, ids, vals, **kw):
        sale_ids = []
        purch_ids = []
        for obj in self.browse(ids):
            if obj.sale_id:
                sale_ids.append(obj.sale_id.id)
            if obj.purch_id:
                purch_ids.append(obj.purch_id.id)
        super(InvoiceLine, self).write(ids, vals, **kw)
        sale_id = vals.get("sale_id")
        if sale_id:
            sale_ids.append(sale_id)
        purch_id = vals.get("purch_id")
        if purch_id:
            purch_ids.append(purch_id)
        if sale_ids:
            get_model("sale.order").function_store(sale_ids)
        if purch_ids:
            get_model("purchase.order").function_store(purch_ids)

    def delete(self, ids, **kw):
        sale_ids = []
        purch_ids = []
        for obj in self.browse(ids):
            if obj.sale_id:
                sale_ids.append(obj.sale_id.id)
            if obj.purch_id:
                purch_ids.append(obj.purch_id.id)
        super(InvoiceLine, self).delete(ids, **kw)
        if sale_ids:
            get_model("sale.order").function_store(sale_ids)
        if purch_ids:
            get_model("purchase.order").function_store(purch_ids)

    def get_discount(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            amt = (obj.qty or 0) * (obj.unit_price or 0)
            if obj.discount:
                amt *= (1 - obj.discount / 100)
            if obj.discount_amount:
                amt -= obj.discount_amount
            vals[obj.id] = amt
        return vals

InvoiceLine.register()
