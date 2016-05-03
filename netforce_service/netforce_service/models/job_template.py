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
import time
import datetime
from netforce.utils import get_data_path


class JobTemplate(Model):
    _name = "job.template"
    _string = "Service Order Template"
    _name_field = "name"
    _fields = {
        "name": fields.Char("Template Name", required=True, search=True),
        "product_id": fields.Many2One("product", "Product", required=True),
        "description": fields.Text("Description"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "period_type": fields.Selection([["month", "Month"], ["counter", "Service Item Counter"]], "Period Type"),
        "period_value": fields.Integer("Period Value"),
        "lines": fields.One2Many("job.template.line", "job_template_id", "Worksheet"),
        "amount_total": fields.Decimal("Total Amount", function="get_total", function_multi=True),
        "amount_labor": fields.Decimal("Labor Amount", function="get_total", function_multi=True),
        "amount_part": fields.Decimal("Parts Amount", function="get_total", function_multi=True),
        "amount_other": fields.Decimal("Other Amount", function="get_total", function_multi=True),
        "service_type_id": fields.Many2One("service.type", "Service Type"),
        "skill_level_id": fields.Many2One("skill.level", "Skill Level", search=True),
    }
    _order = "name"

    def create_job(self, ids, contract_line_id=None, sale_id=None, date=None, description=None, context={}):
        print("job_tmpl.create_job", ids, contract_line_id, date)
        obj = self.browse(ids)[0]
        contract = None
        item = None
        contact_id = None
        if sale_id:
            sale = get_model("sale.order").browse(sale_id)
            contact_id = sale.contact_id.id
        vals = {
            "contact_id": contact_id,
            "project_id": contract.project_id.id if contract else None,
            "template_id": obj.id,
            "service_type_id": obj.service_type_id.id,
            "state": "planned",
            "due_date": date,
            "lines": [],
        }
        if sale_id:
            vals["related_id"] = "sale.order,%s" % sale_id
        for line in obj.lines:
            line_vals = {
                "sequence": line.sequence,
                "type": line.type,
                "product_id": line.product_id.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
            }
            if line.type == "labor" and contract and contract.incl_labor:
                line_vals["payment_type"] = "contract"
            elif line.type == "part" and contract and contract.incl_part:
                line_vals["payment_type"] = "contract"
            elif line.type == "other" and contract and contract.incl_other:
                line_vals["payment_type"] = "contract"
            else:
                line_vals["payment_type"] = "job"
            vals["lines"].append(("create", line_vals))
        if item:
            item_vals = {
                "service_item_id": item.id,
                "description": description,
            }
            vals["items"] = [("create", item_vals)]
        new_id = get_model("job").create(vals)
        return new_id

    def onchange_product(self, context={}):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line["product_id"]
        prod = get_model("product").browse(prod_id)
        line["uom_id"] = prod.uom_id.id
        line["unit_price"] = prod.sale_price
        line["description"] = prod.description
        return data

    def get_total(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            amt_total = 0
            amt_labor = 0
            amt_part = 0
            amt_other = 0
            for line in obj.lines:
                amt_total += line.amount
                if line.type == "labor":
                    amt_labor += line.amount
                if line.type == "part":
                    amt_part += line.amount
                if line.type == "other":
                    amt_other += line.amount
            vals[obj.id] = {
                "amount_total": amt_total,
                "amount_labor": amt_labor,
                "amount_part": amt_part,
                "amount_other": amt_other,
            }
        return vals

    def copy(self, ids, context={}):
        obj = self.browse(ids)[0]
        vals = {
            "name": obj.name + " (copy)",
            "product_id": obj.product_id.id,
            "description": obj.description,
            "period_type": obj.period_type,
            "period_value": obj.period_value,
            "skill_level_id": obj.skill_level_id.id,
            "lines": [],
        }
        for line in obj.lines:
            line_vals = {
                "sequence": line.sequence,
                "type": line.type,
                "product_id": line.product_id.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
                "amount": line.amount,
            }
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals)
        return {
            "next": {
                "name": "job_template",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "Service order template copied",
        }

JobTemplate.register()
