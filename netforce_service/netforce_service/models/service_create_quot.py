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


class CreateQuot(Model):
    _name = "service.create.quot"
    _transient = True
    _fields = {
        "contact_id": fields.Many2One("contact", "Contact", required=True),
        "job_template_id": fields.Many2One("job.template", "Service Order Template", required=True),
    }
    _defaults = {
        "job_template_id": lambda self, ctx: ctx.get("refer_id"),
    }

    def create_quot(self, ids, context={}):
        obj = self.browse(ids[0])
        vals = {
            "contact_id": obj.contact_id.id,
            "job_template_id": obj.job_template_id.id,
            "lines": [],
        }
        tmpl = obj.job_template_id
        for line in tmpl.lines:
            prod = line.product_id
            line_vals = {
                "product_id": prod.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
                "tax_id": prod.sale_tax_id.id if prod else None,
            }
            vals["lines"].append(("create", line_vals))
        quot_id = get_model("sale.quot").create(vals)
        quot = get_model("sale.quot").browse(quot_id)
        return {
            "next": {
                "name": "quot",
                "mode": "form",
                "active_id": quot_id,
            },
            "flash": "Quotation %s created from service order template %s" % (quot.number, tmpl.name),
        }

CreateQuot.register()
