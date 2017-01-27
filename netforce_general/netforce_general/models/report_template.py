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

import os
import random
import requests
import uuid

from netforce.model import Model, fields, get_model
from netforce.database import get_connection, get_active_db

def get_rand():
    return int(random.random()*10000)

class ReportTemplate(Model):
    _name = "report.template"
    _string = "Report Template"
    _multi_company = True
    _fields = {
        "name": fields.Char("Template Name", required=True, search=True),
        "type": fields.Selection([
            ["cust_invoice", "Customer Invoice"],
            ["cust_debit_note", "Customer Debit Note"],
            ["cust_credit_note", "Customer Credit Note"],
            ["supp_invoice", "Supplier Invoice"],
            ["payment", "Payment"],
            ["account_move", "Journal Entry"],
            ["sale_quot", "Quotation"],
            ["sale_order", "Sales Order"],
            ["purch_order", "Purchase Order"],
            ["purchase_request", "Purchase Request"],
            ["prod_order", "Production Order"],
            ["goods_receipt", "Goods Receipt"],
            ["goods_transfer", "Goods Transfer"],
            ["goods_issue", "Goods Issue"],
            ["pay_slip", "Pay Slip"],
            ["tax_detail", "Tax Detail"],
            ["hr_expense", "HR Expense"],
            ["landed_cost","Landed Cost"],
            ["borrow_form", "Borrow Request"],
            ["claim_bill","Claim Bill"],

            # XXX: Better add by config
            ["account_bill","Bill Issue"],
            ["account_cheque","Cheque"],
            ["account_advance","Advance Payment"],
            ["account_advance_clear","Advance Clearing"],

            ["other", "Other"]], "Template Type", required=True, search=True),
        "format": fields.Selection([["odt", "ODT (old)"],
                                    ["odt2", "ODT"],
                                    ["ods", "ODS"],
                                    ["docx", "DOCX (old)"],
                                    ["xlsx", "XLSX"],
                                    ["jrxml", "JRXML (old)"],
                                    ["jrxml2", "JRXML"]], "Template Format", required=True, search=True),
        "file": fields.File("Template File"),
        "company_id": fields.Many2One("company", "Company"),
        "model_id": fields.Many2One("model", "Model"),
        "method": fields.Char("Method"),
        "default": fields.Boolean("Default"),
    }
    _defaults = {
        "file_type": "odt",
        'default': False,
    }

    _order="name"

    def write(self, ids, vals, **kw):
        for obj in self.browse(ids):
            if obj.default:
                raise Exception("Can not edit default template!")
        super().write(ids, vals, **kw)

    def default_template(self, type):
        templates=self.search_browse([['type','=',type], ['default','=',True],['format','=','jrxml2']])
        if templates:
            return templates[0]

    def delete(self, ids, context={}):
        ids2=[] #ids for delete
        fetch=context.get('fetch') or False
        for obj in self.browse(ids):
            if not obj.default: #custom
                ids2.append(obj.id)
            elif fetch: # fetch
                ids2.append(obj.id)
        super().delete(ids2)

    def get_default_template(self, context={}):
        """
            Copy from from MGT to local
        """
        #clear all default
        ids=self.search([['default','=',True]])
        context['fetch']=True
        self.delete(ids,context)

        custom_ids=self.search([['default','=',False]])

        url="http://mgt.netforce.com/get_report_template?%s"%(get_rand())
        res=requests.get(url)
        if res.status_code!=200:
            raise Exception("Wrong url")
        lines=eval(res.text)
        dbname=get_active_db()
        for line in lines:
            try:
                fname=line['file']
                url="http://mgt.netforce.com/static/db/ctrl/files/%s?%s"%(fname,get_rand())
                res2=requests.get(url)
                if res2.status_code!=200:
                    raise Exception("Wrong url")

                path=os.path.join(os.getcwd(), "static", "db", dbname, "files")
                if not os.path.exists(path):
                    os.makedirs(path)
                path=os.path.join(path,fname)

                #data=str(res2.content,'utf-8')
                data=res2.content
                open(path,"wb").write(data)

                vals={
                    'name': line['name'],
                    'file': fname,
                    'type': line['type'],
                    'default': True,
                    'format': line['format'],
                    'method': line['method'],
                }
                res3=get_model("report.template").search([['name','=',vals['name']]])
                if not res3:
                    get_model("report.template").create(vals) #new
                    vals['default']=False #custom
                    if not custom_ids:
                        get_model("report.template").create(vals) #new
                    print('new default report template ', vals['name'])
            except Exception as e:
                print("ERROR ", e, line['name'])

        return {
            'next': {
                'name': 'report_template',
            },
            'flash': 'Update default template successful!',

        }

ReportTemplate.register()
