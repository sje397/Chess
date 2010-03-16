from google.appengine.ext import db
from aeoid import users

INVITE_PENDING = 1
INVITE_ACCEPTED = 2
INVITE_REJECTED = 3

class Invite(db.Model):
  fromUser = users.UserProperty(required = True, auto_current_user_add = True)
  toUser = users.UserProperty()
  toEmail = db.StringProperty(required = True)
  status = db.IntegerProperty(required = True, default = INVITE_PENDING)
  created = db.DateTimeProperty(auto_now_add = True)
  updated = db.DateTimeProperty(auto_now = True)

