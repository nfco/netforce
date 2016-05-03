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
from netforce import config
from netforce import database
from netforce import access


class Company(Model):
    _name = "company"
    _string = "Company"
    _key = ["name"]
    _audit_log = True
    _fields = {
        "name": fields.Char("Company Name", required=True, search=True, translate=True),
        "code": fields.Char("Company Code", search=True),
        "parent_id": fields.Many2One("company", "Parent"),
        "description": fields.Text("Description"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "contact_id": fields.Many2One("contact","Contact"),
        'prevent_trans': fields.Boolean("Prevent Transaction"),
    }
    _order = "name"
    _constraints = ["_check_cycle"]

Company.register()
