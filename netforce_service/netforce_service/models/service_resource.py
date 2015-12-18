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
from datetime import *


class Resource(Model):
    _name = "service.resource"
    _string = "Resource"
    _fields = {
        "name": fields.Char("Name", required=True, search=True),
        "employee_id": fields.Many2One("hr.employee", "Employee", search=True),
        "product_categs": fields.Many2Many("product.categ", "Product Categories"),
        "regions": fields.Many2Many("region", "Regions"),
        "skill_level_id": fields.Many2One("skill.level", "Skill Level"),
        "allocs": fields.One2Many("service.resource.alloc", "resource_id", "Resource Allocations"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "can_alloc": fields.Boolean("Can Allocate", function="get_can_alloc"),
        "is_avail": fields.Boolean("Is Available", store=False, function_search="is_avail_search"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "time_sheets": fields.One2Many("time.sheet", "resource_id", "Time Sheets"),
        "user_id": fields.Many2One("base.user", "User"),
        "type": fields.Selection([["person","Person"],["machine","Machine"]],"Resource Type"),
        "product_id": fields.Many2One("product","Product"),
    }
    _order = "name"

    def name_get(self, ids, context={}):
        vals = []
        for obj in self.browse(ids, context=context):
            name = obj.name
            can_alloc = obj.can_alloc
            if can_alloc == False:
                name += " [WARNING]"
            vals.append((obj.id, name))
        return vals

    def get_can_alloc(self, ids, context={}):
        print("get_can_alloc", ids, context)
        job_id = context.get("job_id")
        if not job_id:
            return {id: None for id in ids}
        job = get_model("job").browse(job_id)
        prod_ids = []
        for item in job.items:
            sitem = item.service_item_id
            if sitem.product_id:
                prod_ids.append(sitem.product_id.id)
        print("prod_ids", prod_ids)
        vals = {}
        for obj in self.browse(ids):
            if job.skill_level_id:
                if obj.skill_level_id and obj.skill_level_id.level < job.skill_level_id.level:
                    vals[obj.id] = False
                    continue
            if obj.product_categs and prod_ids:
                categ_ids = [c.id for c in obj.product_categs]
                res = get_model("product").search([["id", "in", prod_ids], ["categs.id", "child_of", categ_ids]])
                if not res:
                    vals[obj.id] = False
                    continue
            region = job.contact_id.region_id
            if obj.regions and region:
                region_ids = [r.id for r in obj.regions]
                if region.id not in region_ids:
                    vals[obj.id] = False
                    continue
            vals[obj.id] = True
        return vals

    def is_avail_search(self, clause, context={}):
        print("is_avail_search", clause, context)
        time_start = context.get("time_start")
        time_stop = context.get("time_stop")
        job_id = context.get("job_id")
        if job_id:
            job = get_model("job").browse(job_id)
            if job.state == "planned":
                job.write({"state": "allocated"})
        if not time_start or not time_stop:
            return []
        ids = []
        for alloc in get_model("service.resource.alloc").search_browse([["time_stop", ">", time_start], ["time_start", "<", time_stop]]):
            ids.append(alloc.resource_id.id)
        ids = list(set(ids))
        return [["id", "not in", ids]]

Resource.register()
