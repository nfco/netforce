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
from netforce.access import get_active_company, get_active_user, set_active_user
from netforce.utils import get_data_path


class PurchaseRequest(Model):
    _name = "purchase.request"
    _string = "Purchase Request"
    _fields = {
        "number": fields.Char("Number", required=True, search=True),
        "ref": fields.Char("Ref", search=True),
        "date": fields.Date("Date", required=True, search=True),
        "date_required": fields.Date("Required Date"),
        "company_id": fields.Many2One("company", "Company"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "other_info": fields.Text("Other Info"),
        "employee_id": fields.Many2One("hr.employee", "Employee", required=True, search=True),
        "state": fields.Selection([("draft", "Draft"), ("waiting_approval", "Waiting Approval"), ("waiting_po", "Waiting PO"), ("done", "Completed"), ("voided", "Voided")], "Status", required=True),
        "lines": fields.One2Many("purchase.request.line", "request_id", "Lines"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "request_by_id": fields.Many2One("base.user", "Request By", required=True, readonly=True),
        "approve_by_id": fields.Many2One("base.user", "Approved By", readonly=True),
    }
    _order = "date desc,number desc"

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence(type="purchase_request")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id,context=context)
            user_id = get_active_user()
            set_active_user(1)
            res = self.search([["number", "=", num]])
            set_active_user(user_id)
            if not res:
                return num
            get_model("sequence").increment_number(seq_id,context=context)

    def _get_employee(self, context={}):
        user_id = get_active_user()
        res = get_model("hr.employee").search([["user_id", "=", user_id]])
        if not res:
            return None
        return res[0]

    def _get_request_by_id(self, context={}):
        return get_active_user()

    _defaults = {
        "state": "draft",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "number": _get_number,
        "employee_id": _get_employee,
        "company_id": lambda *a: get_active_company(),
        "request_by_id": _get_request_by_id,
    }

    def onchange_product(self, context={}):
        data = context.get('data')
        path = context.get('path')
        line = get_data_path(data, path, parent=True)
        product = get_model('product').browse(line['product_id'])
        line['description'] = product.description if product.description else "-"
        line['uom_id'] = product.uom_id.id
        return data

    def btn_submit(self, ids, context={}):
        obj = self.browse(ids)
        obj.write({"state": "waiting_approval"})

    def btn_approve(self, ids, context={}):
        obj = self.browse(ids)
        obj.write({"state": "waiting_po", "approve_by_id": get_active_user()})

    def btn_done(self, ids, context={}):
        obj = self.browse(ids)
        obj.write({"state": "done"})

    def btn_reopen(self, ids, context={}):
        obj = self.browse(ids)
        obj.write({"state": "waiting_po"})

    def btn_draft(self, ids, context={}):
        obj = self.browse(ids)
        obj.write({"state": "draft"})

    def btn_void(self, ids, context={}):
        obj = self.browse(ids)
        obj.write({"state": "voided"})

PurchaseRequest.register()
