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
from netforce import config
from netforce.database import get_connection
from netforce import access
from netforce.model import get_model

class Root(Controller):
    _path="/"

    def get(self):
        url=None
        db=get_connection()
        try:
            if db:
                res=db.get("SELECT root_url FROM settings WHERE id=1")
                url=res.root_url
            if url:
                self.redirect(url)
                return
            user_id=access.get_active_user()
            action=None
            if user_id:
                user=get_model("base.user").browse(user_id)
                profile=user.profile_id
                action=profile.home_action
            if action:
                self.redirect("/ui#name=%s"%action)
                return
            self.redirect("/ui#name=login")
        finally:
            if db:
                db.commit()

Root.register()
