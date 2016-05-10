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

from netforce.model import Model, fields, get_model, BrowseRecord
import uuid
from decimal import *


class TaxRate(Model):
    _name = "account.tax.rate"
    _string = "Tax Rate"
    _key = ["name"]
    _name_field = "name"
    _fields = {
        "name": fields.Char("Name", required=True, search=True),
        "code": fields.Char("Code", search=True),
        "rate": fields.Decimal("Tax Rate", function="get_rate", function_multi=True),
        "wht_rate": fields.Decimal("WHT Rate", function="get_rate", function_multi=True),
        "components": fields.One2Many("account.tax.component", "tax_rate_id", "Components"),
        "uuid": fields.Char("UUID"),
        "active": fields.Boolean("Active"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
    }
    _defaults = {
        "uuid": lambda *a: str(uuid.uuid4()),
        "active": True,
    }
    _order = "name"

    def get_rate(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            rate = Decimal(0)
            wht_rate = Decimal(0)
            for comp in obj.components:
                if comp.type == "vat":
                    rate += comp.rate
                elif comp.type == "wht":
                    wht_rate += comp.rate
            res = {
                "rate": rate,
                "wht_rate": wht_rate
            }
            vals[obj.id] = res
        return vals

    def update_total(self, context={}):
        data = context["data"]
        data["rate"] = 0
        for comp in data["components"]:
            data["rate"] += comp["rate"]
        return data

    # XXX: remove this
    def compute_tax(self, tax_id, amt, tax_type="tax_ex", wht=False):
        if not tax_id:
            return 0
        if tax_type == "no_tax":
            return 0
        obj = self.browse(tax_id)
        vat_rate = Decimal(0)
        wht_rate = Decimal(0)
        for comp in obj.components:
            if comp.type == "wht":
                wht_rate += comp.rate or 0
            elif comp.type == "vat":
                vat_rate += comp.rate or 0
        base_amt = 0
        if tax_type == "tax_ex":
            base_amt = amt or 0
        elif tax_type == "tax_in":
            base_amt = (amt or 0) / (1 + vat_rate / 100)
        if wht:
            return base_amt * wht_rate / 100
        else:
            return base_amt * vat_rate / 100

    # XXX: remove this
    # (not used in payment)
    def compute_components(self, tax_id, amt, tax_type="tax_ex", when="invoice"):
        assert(when != "payment")  # XXX
        if tax_type == "no_tax":
            return {}
        obj = self.browse(tax_id)
        if tax_type == "tax_in":
            base_amt = amt / (1 + obj.rate / 100)
        else:
            base_amt = amt
        has_defer = False
        for comp in obj.components:
            if comp.type == "vat_defer":
                has_defer = True
        comps = {}
        for comp in obj.components:
            if comp.type == "wht":
                continue
            if has_defer and comp.type == "vat":
                continue
            comps[comp.id] = base_amt * (comp.rate / 100)
        return comps

    def compute_base(self, tax_id, amt=0, tax_type="tax_ex"):
        if isinstance(tax_id, BrowseRecord):  # XXX: for speed (use browse cache)
            obj = tax_id
        else:
            obj = self.browse(tax_id)
        amt=Decimal(amt)
        if tax_type == "tax_in":
            base_amt = amt / (1 + obj.rate / 100)
        elif tax_type == "tax_ex":
            base_amt = amt
        return base_amt

    # TODO: use this in invoice/claim
    def compute_taxes(self, tax_id, base, when="invoice"):
        if isinstance(tax_id, BrowseRecord):  # XXX: for speed (use browse cache)
            obj = tax_id
        else:
            obj = self.browse(tax_id)
        has_defer = False
        for comp in obj.components:
            if comp.type == "vat_defer":
                has_defer = True
        comps = {}
        for comp in obj.components:
            if when == "invoice":
                if comp.type in ("vat", "vat_exempt") and has_defer:
                    continue
                if comp.type == "wht":
                    continue
            elif when == "invoice_payment":
                if comp.type in ("vat", "vat_exempt") and not has_defer:
                    continue
            elif when == "invoice_payment_inv":
                if comp.type != "vat_defer":
                    continue
            elif when == "invoice_payment_pmt":
                if comp.type in ("vat", "vat_exempt") and not has_defer:
                    continue
                if comp.type == "vat_defer":
                    continue
            elif when == "direct_payment":
                if comp.type == "vat_defer":
                    continue
            else:
                raise Exception("Can't compute taxes: invalid 'when'")
            if when == "invoice" and comp.type not in ("vat", "vat_exempt", "vat_defer"):
                continue
            if when == "payment" and comp.type != "wht":
                continue
            tax = base * (comp.rate / 100)
            if comp.type == "wht":
                tax = -tax
            elif comp.type == "vat_defer" and when in ("invoice_payment", "invoice_payment_inv"):
                tax = -tax
            comps[comp.id] = tax
        return comps

    def has_defer_vat(self, ids, context={}):
        for obj in self.browse(ids):
            for comp in obj.components:
                if comp.type == "vat_defer":
                    return True
        return False

TaxRate.register()
