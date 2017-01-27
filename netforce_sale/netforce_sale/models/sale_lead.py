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
from netforce.access import get_active_company


class Lead(Model):
    _name = "sale.lead"
    _string = "Lead"
    _audit_log = True
    _multi_company = True
    _key = ["first_name","last_name"]
    _fields = {
        "user_id": fields.Many2One("base.user", "Lead Owner", required=True),
        "first_name": fields.Char("First Name", search=True),
        "last_name": fields.Char("Last Name", required=True, search=True),
        "name": fields.Char("Name", function="get_name"),
        "company": fields.Char("Company", search=True),
        "title": fields.Char("Title"),
        "state": fields.Selection([["open", "Open"], ["contacted", "Contacted"], ["qualified", "Qualified"], ["unqualified", "Unqualified"], ["recycled", "Recycled"]], "Status", required=True),
        "phone": fields.Char("Phone", search=True),
        "email": fields.Char("Email", search=True),
        "rating": fields.Selection([["hot", "Hot"], ["warm", "Warm"], ["cold", "Cold"]], "Rating"),
        "street": fields.Char("Street"),
        "city": fields.Char("City"),
        "province": fields.Char("State/Province"),
        "zip": fields.Char("Zip/Postal Code"),
        "country_id": fields.Many2One("country", "Country"),
        "website": fields.Char("Website"),
        "employees": fields.Char("No. of Employees"),
        "revenue": fields.Char("Annual Revenue"),
        "lead_source": fields.Char("Lead Source", search=True),
        "industry": fields.Char("Industry", search=True),
        "description": fields.Text("Description"),
        "assigned_id": fields.Many2One("base.user", "Assigned To"),
        "date": fields.Date("Date", search=True),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "activities": fields.One2Many("activity", "name_id", "Activities"),
        "addresses": fields.One2Many("address", "lead_id", "Addresses"),
        "company_id": fields.Many2One("company", "Company"),
        "emails": fields.One2Many("email.message", "related_id", "Emails"),
        "year": fields.Char("Year", sql_function=["year", "date"]),
        "quarter": fields.Char("Quarter", sql_function=["quarter", "date"]),
        "month": fields.Char("Month", sql_function=["month", "date"]),
        "week": fields.Char("Week", sql_function=["week", "date"]),
    }
    _defaults = {
        "state": "open",
        "active": True,
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "user_id": lambda self, context: int(context["user_id"]),
        "company_id": lambda *a: get_active_company(),
    }

    def get_name(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            vals[obj.id] = obj.first_name + " " + obj.last_name if obj.first_name else obj.last_name
        return vals

    def name_search(self, name, condition=[], context={}):
        cond = [["or", ["last_name", "ilike", "%" + name + "%"], ["first_name", "ilike", "%" + name + "%"]], condition]
        ids = self.search(cond)
        return self.name_get(ids, context)

    def copy_to_contact(self, ids, context={}):
        obj = self.browse(ids)[0]
        messages = []
        addresses = []
        for addr in obj.addresses:
            addr_vals={
                "type": addr.type,
                "first_name": addr.first_name,
                "last_name": addr.last_name,
                "company": addr.company,
                "unit_no": addr.unit_no,
                "floor": addr.floor,
                "bldg_name": addr.bldg_name,
                "bldg_no": addr.bldg_no,
                "village": addr.village,
                "soi": addr.soi,
                "moo": addr.moo,
                "street": addr.street,
                "sub_district": addr.sub_district,
                "district": addr.district,
                "address": addr.address,
                "address2": addr.address2,
                "city": addr.city,
                "postal_code": addr.postal_code,
                "province": addr.province,
                "province_id": addr.province_id.id,
                "district_id": addr.district_id.id,
                "subdistrict_id": addr.subdistrict_id.id,
                "country_id": addr.country_id.id,
                "phone": addr.phone,
                "fax": addr.fax,
                "contact_id": addr.contact_id.id,
                "company_id": addr.company_id.id,
                "settings_id": addr.settings_id.id,
                #"lead_id": addr.lead_id.id,
                "employee_id": addr.employee_id.id,
                #"related_id": addr.related_id.id, #XXX
                "address_text": addr.address_text,
                "sequence": addr.sequence,
            }
            addresses.append(('create',addr_vals))
        if obj.company:
            res = get_model("contact").search([["name", "=", obj.company]])
            if res:
                comp_contact_id = res[0]
                messages.append("Contact already exists for %s." % obj.company)
            else:
                vals = {
                    "type": "org",
                    "name": obj.company,
                    "phone": obj.phone,
                    "website": obj.website,
                    "industry": obj.industry,
                    "employees": obj.employees,
                    "email": obj.email,
                    "description": obj.description,
                    "lead_source": obj.lead_source,
                    "revenue": obj.revenue,
                    'addresses': addresses,
                }
                comp_contact_id = get_model("contact").create(vals, context=context)
                messages.append("Contact created for %s." % obj.company)
        else:
            comp_contact_id = None

        if obj.first_name:
            name = obj.first_name + " " + obj.last_name
        else:
            name = obj.last_name
        res = get_model("contact").search([["name", "=", name]])
        if res:
            contact_id = res[0]
            messages.append("Contact already exists for %s." % name)
        else:
            vals = {
                "type": "person",
                "code": obj.last_name,
                "first_name": obj.first_name,
                "last_name": obj.last_name,
                "contact_id": comp_contact_id,
                "title": obj.title,
                "phone": obj.phone,
                "email": obj.email,
                "description": obj.description,
                "lead_source": obj.lead_source,
                'addresses': addresses,
            }
            # TODO: copy address
            contact_id = get_model("contact").create(vals, context=context)
            messages.append("Contact created for %s." % name)
        return {
            "next": {
                "name": "contact",
                "mode": "form",
                "active_id": contact_id,
            },
            "flash": "\n".join(messages),
        }

Lead.register()
