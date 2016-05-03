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

from netforce.model import Model, fields


class TaxComponent(Model):
    _name = "account.tax.component"
    _fields = {
        "tax_rate_id": fields.Many2One("account.tax.rate", "Tax Rate", required=True, on_delete="cascade"),
        "name": fields.Char("Name", required=True),
        "compound": fields.Boolean("Compound"),
        "rate": fields.Decimal("Rate", required=True),
        "account_id": fields.Many2One("account.account", "Account", multi_company=True,required=True),
        "type": fields.Selection([["vat", "VAT"], ["vat_exempt", "VAT Exempt"], ["vat_defer", "Deferred VAT"], ["wht", "Withholding Tax"]], "Tax Type"),
        "trans_type": fields.Selection([["out", "Sale"], ["in", "Purchase"]], "Transaction Type"),
        "description": fields.Text("Description"),
    }
    _defaults = {
        "rate": 0,
    }

    def name_get(self, ids, context={}):
        vals = []
        for obj in self.browse(ids):
            name = "%s - %s" % (obj.tax_rate_id.name, obj.name)
            vals.append((obj.id, name))
        return vals

    def name_search(self, name, condition=[], limit=None, context={}):
        cond = [["or", ["name", "ilike", name], ["tax_rate_id.name", "=ilike", name + "%"]], condition]
        ids = self.search(cond, limit=limit)
        return self.name_get(ids, context)

TaxComponent.register()
