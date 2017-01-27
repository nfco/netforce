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

import csv
import xlrd
import tempfile
import os.path
from io import StringIO

from netforce.model import Model, fields, get_model
from netforce.database import get_active_db
from netforce.utils import get_file_path, get_data_path

def excel2csv(ExcelFile):
    x,fname=tempfile.mkstemp()
    path=get_file_path(ExcelFile)
    workbook = xlrd.open_workbook(path)
    SheetName = workbook.sheet_names()[-1] # always first sheet
    worksheet = workbook.sheet_by_name(SheetName)
    with open(fname,'w') as csvfile:
        wr = csv.writer(csvfile, delimiter=',')
        for rownum in range(worksheet.nrows):
            rows=[]
            for x in worksheet.row_values(rownum):
                if isinstance(x, (str)):
                    x.encode("utf-8")
                rows.append(x)	
            wr.writerow(rows)
        #csvfile.close()
    data=open(fname,"r").read()
    os.remove(fname)	
    return data

class MatchField(Model):
    _name = "match.field"
    _transient = True
    _fields = {
        "model": fields.Char("Model", required=True),
        "next": fields.Char("Next"),
        "title": fields.Char("Title"),
        "file": fields.File("File to verify"),
        "file_import": fields.File("File to import"),
        'lines': fields.One2Many("match.field.line","match_id","Lines"),
        'log_lines': fields.One2Many("match.field.log","match_id","Log Lines"),
        'state': fields.Selection([['to_verify','To Veriry'],['done','Done'],['error','Error']], 'State'),
    }
    
    def get_default_next(self, context={}):
        return context.get("next")

    def get_default_title(self, context={}):
        model = context["import_model"]
        m = get_model(model)
        title = "Import"
        if m._string:
            title += " " + m._string
        else:
            title += " " + m._name.title()
        return title

    def get_default_model(self, context={}):
        model = context["import_model"]
        m=get_model(model)
        #load for select
        items=m._fields
        extra_fields=[('id','Database ID')]
        for fname, v in extra_fields:
            res=get_model('import.field').search([['name','=',fname],['model','=',model]])
            if not res:
                get_model('import.field').create({'name': fname, 'string': v, 'model': model})
        for fname, v in m._fields.items():
            res=get_model('import.field').search([['name','=',fname],['model','=',model]])
            if not res:
                if fname in ('create_time','write_time','create_uid','write_uid'):
                    continue
                get_model('import.field').create({'name': fname, 'string': v.string, 'model': model})
                f=m._fields.get(fname)
                if isinstance(f,fields.One2Many):
                    mr=get_model(f.relation)
                    for fname2, v2 in mr._fields.items():
                        if fname2 in ('create_time','write_time','create_uid','write_uid'):
                            continue
                        get_model('import.field').create({'name': '%s.%s'%(fname,fname2), 'string': '%s/%s'%(v.string,v2.string), 'model': model})
        return model

    _defaults={
        "model": get_default_model,
        "title": get_default_title,
        "next": get_default_next,
        'state': 'to_verify',
    }
    
    def get_data(self, context={}):
        model = context["import_model"]
        m = get_model(model)
        title = "Import"
        if m._string:
            title += " " + m._string
        return {
            "model": model,
            "title": title,
            "next": context.get("next"),
        }

    def do_import(self, ids, context={}):
        obj = self.browse(ids[0])
        if not obj.file_import or obj.state!='done':
            raise Exception("Please verify")
        dbname = get_active_db()
        data = open(os.path.join("static", "db", dbname, "files", obj.file_import), "rU", errors="replace").read()
         
        count=0
        for line in obj.lines:
            if not line.field_id:
                count+=1
        if count==len(obj.lines):
            raise Exception("Please match field!")

        m = get_model(obj.model)
        m.import_data(data)
        if obj.next:
            return {
                "next": {
                    "name": obj.next,
                },
                "flash": "Data imported successfully",
            }

    def onchange_file(self, context={}):
        data=context['data']
        f=data['file']
        suffix=f.split(".")[-1]
        csv_data=''
        if suffix=='csv':
            path=get_file_path(f)
            csv_data=open(path,"r").read()
        elif suffix in ('xlsx','xls'):
            csv_data=excel2csv(f)
        else:
            raise Exception("Wrong format!!")
        # check type xlsx or csv
        f = StringIO(csv_data)
        rd = csv.reader(f)
        headers = next(rd)
        headers = [h.strip() for h in headers]
        lines=[]
        for head in headers:
            vals={
                'customer_field': head,
            }
            for field_id in get_model("import.field").search([['string','=',head], ['model','=', data['model']]]):
                vals['field_id']=field_id
            lines.append(vals)

        rows = [r for r in rd]
        for index, line in enumerate(lines):
            try:
                row=rows[index]
                r=row[index]
                line.update({'simple_value': r})
            except:
                pass

        data['lines']=lines
        return data

    def do_verify(self, ids, context={}):
        """
            prepare file_import
            0. check file format 
            1. list all error
            2. change header
            3. to import file
            4. change state to done
        """
        obj = self.browse(ids[0])
        if not obj.file:
            raise Exception("Missing File")

        suffix=obj.file.split(".")[-1]
        csv_data=''
        if suffix=='csv':
            path=get_file_path(obj.file)
            csv_data=open(path,"r").read()
        elif suffix in ('xlsx','xls'):
            csv_data=excel2csv(obj.file)
        else:
            raise Exception("Wrong format!!")
        f = StringIO(csv_data)
        rd = csv.reader(f)
        headers = next(rd)
        #headers = [h.strip() for h in headers]
        rows = [r for r in rd]
        cols=[]
        text=""
        for index,line in enumerate(obj.lines):
            fld=line.field_id
            if fld:
                text+=fld.string+","
                cols.append(index)
        text+="\r\n"
        for row in rows:
            st=""
            for col in cols:
                st+=row[col]+","
            text+=st+"\r\n"

        context['verify']=True

        #----------- Check value existing in key -----------#
        f = StringIO(text)
        rd = csv.reader(f)
        headers = next(rd)
        headers = [h.strip() for h in headers]
        rows = [r for r in rd]
        key_model = get_model(obj.model)._key
        index = []
        strings = dict([(f.string, n) for n, f in get_model(obj.model)._fields.items()])
        for k in key_model:
            for i,h in enumerate(headers):
                n = strings.get(h.replace("&#47;", "/").strip())
                if n == k:
                    index.append(i)
        log = []
        if index:
            k_ext = []
            for ind in index:
                for i,row in enumerate(rows):
                    if not row[ind]:
                        log.append({
                            'no' : i+1,
                            'description' : 'Key [%s] empty'%headers[ind],
                        })
                    elif not k_ext:
                        k_ext.append(row[ind])
                        continue
                    elif k_ext:
                        if row[ind] in k_ext:
                            log.append({
                                'no' : i+1,
                                'description' : 'Key existing'
                            })
                        else:
                            k_ext.append(row[ind])
        if log:
            lines=[]
            obj.write({'log_lines': ([('delete_all',)])})
            for l in log:
                lines.append(('create',{
                    'sequence': l['no']+1,
                    'description': l['description'],
                }))
            obj.write({'log_lines': lines, 'state': 'error'})
            return {
                'flash': {
                        'type': 'error',
                        'message': 'Can not import data! Please check your file or try to match field again.',
                }
            }
        #---------------------------------------------------#

        log=get_model(obj.model).import_data(text,context)
        #clear log
        obj.write({
            'log_lines': ([('delete_all',)]),
            'state': 'verify',
        })
        if log:
            lines=[]
            for l in log:
                lines.append(('create',{
                    'sequence': l['no']+1, 
                    'description': l['description'], 
                }))
            obj.write({'log_lines': lines, 'state': 'error'})
            return {
                'flash': {
                        'type': 'error',
                        'message': 'Can not import data! Please check your file or try to match field again.',
                }
            }
        else:
            fname='to-import-%s'%obj.file
            print(fname)
            path=get_file_path(fname)
            open(path,"w").write(text)
            obj.write({
                'file_import': fname,
                'state': 'done',
            })
            return {
                'flash': 'Verify successful!',
            }
        

    def onchange_line(self, context={}):
        data=context['data']
        path=context['path']
        item=get_data_path(data, path, parent=True)
        fld_id=item['field_id']
        for line in data['lines']:
            fld2_id=line.get("field_id")
            if fld2_id and fld2_id==fld_id:
                line['field_id']=None
        item['field_id']=fld_id
        return data


MatchField.register()
