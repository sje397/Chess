from google.appengine.ext import db
from aeoid import users

INVITE_PENDING = 1
INVITE_ACCEPTED = 2
INVITE_REJECTED = 3

PLAYAS_RANDOM = 1
PLAYAS_WHITE = 2
PLAYAS_BLACK = 3

class Invite(db.Model):
  fromUser = users.UserProperty(required = True, auto_current_user_add = True)
  toUser = users.UserProperty()
  toEmail = db.StringProperty()
  status = db.IntegerProperty(required = True, default = INVITE_PENDING)
  created = db.DateTimeProperty(auto_now_add = True)
  updated = db.DateTimeProperty(auto_now = True)
  fromPlayAs = db.IntegerProperty(required = True, default = PLAYAS_RANDOM)

class Game(db.Model):
  whitePlayer = users.UserProperty(required = True)
  blackPlayer = users.UserProperty(required = True)
  whiteMove = db.BooleanProperty(required = True, default = True)
  finished = db.BooleanProperty(required = True, default = False)
  moves = db.StringListProperty()
  
  def myMove(self):
    return (self.whiteMove and self.whitePlayer.user_id() == users.get_current_user().user_id()) \
       or (not self.whiteMove and self.blackPlayer.user_id() == users.get_current_user().user_id())
