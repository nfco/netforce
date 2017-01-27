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

from netforce.controller import Controller
import tornado.ioloop
import time
from netforce.database import get_connection,set_active_db
from netforce.access import get_active_user
from netforce.model import get_model
import os
from netforce import config

class DownloadDB(Controller):
    _path="/download_db"
    
    def get(self):
        dbname=self.get_argument("dbname")
        datenow=time.strftime("%Y-%m-%dT%H:%M:%S")
        fname='%s.%s.sql.gz'%(dbname, datenow)
        #path=os.path.join("static", "db", dbname, "files", fname)
        path="/tmp/"+fname
        os.system("pg_dump -vO %s | gzip > %s"%(dbname, path))
        #data=open(os.path.join("static", "db", dbname, "files", fname),"rb").read()
        data=open(path,"rb").read()
        os.remove(path) #FIXME not work
        self.write(data)
        self.set_header("Content-Disposition", "attachment; filename=%s" % fname)
        self.set_header("Content-Type", "text/plain")

DownloadDB.register()
