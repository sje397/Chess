from google.appengine.ext import db
from aeoid import users

INVITE_PENDING = 1
INVITE_ACCEPTED = 2
INVITE_REJECTED = 3

PLAYAS_RANDOM = 1
PLAYAS_WHITE = 2
PLAYAS_BLACK = 3

NOT_FINISHED = 0
STALEMATE = 1
WHITE_RESIGNED = 2
BLACK_RESIGNED = 3
WHITE_CHECKMATED = 4
BLACK_CHECKMATED = 5

class Invite(db.Model):
  fromUser = users.UserProperty(required = True, auto_current_user_add = True)
  toUser = users.UserProperty()
  toEmail = db.StringProperty()
  status = db.IntegerProperty(required = True, default = INVITE_PENDING, choices = [INVITE_PENDING, INVITE_ACCEPTED, INVITE_REJECTED])
  created = db.DateTimeProperty(auto_now_add = True)
  updated = db.DateTimeProperty(auto_now = True)
  fromPlayAs = db.IntegerProperty(required = True, default = PLAYAS_RANDOM, choices = [PLAYAS_RANDOM, PLAYAS_WHITE, PLAYAS_BLACK])

class Game(db.Model):
  whitePlayer = users.UserProperty(required = True)
  blackPlayer = users.UserProperty(required = True)
  whiteMove = db.BooleanProperty(required = True, default = True)
  state = db.IntegerProperty(required = True, default = NOT_FINISHED, choices = [NOT_FINISHED, STALEMATE, WHITE_RESIGNED, BLACK_RESIGNED, WHITE_CHECKMATED, BLACK_CHECKMATED])
  moves = db.StringListProperty()
  
  def myMove(self):
    return (self.whiteMove and self.whitePlayer.user_id() == users.get_current_user().user_id()) \
       or (not self.whiteMove and self.blackPlayer.user_id() == users.get_current_user().user_id())

class Prefs(db.Expando):
  user = users.UserProperty(required = True, auto_current_user_add = True)
  whitePieceType = db.StringProperty(default='paper') 
  blackPieceType = db.StringProperty(default='cloth')
  whiteSquareImage = db.StringProperty(default='white-marble.jpg')
  blackSquareImage = db.StringProperty(default='grey-marble.jpg')
