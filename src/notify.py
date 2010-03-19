from google.appengine.api import xmpp
from google.appengine.api import mail

from utils import getPrefs

def sendInviteIM(user, toEmail):
  if xmpp.get_presence(toEmail):
    xmpp.send_message(toEmail, user.nickname() +' has invited you to play a game of chess. http://your-move.appspot.com')

def sendYourMoveIM(movePlayer, opponent, gameKey):
  if xmpp.get_presence(movePlayer.email()):
    xmpp.send_message(movePlayer.email(), "Your Move. http://your-move.appspot.com/game?id=" + gameKey)

def sendInviteEmail(user, toEmail):
  mail.send_mail(sender="Your-Move Online Chess <sje397@gmail.com>",
              to=toEmail,
              subject="Chess Invitation",
              body="""
Dear """ + toEmail + """,

""" + user.nickname() + """ (""" + user.email() + """) has invited you to play a game of chess.

Note that you need to log in using the OpenID provider that matches the address to which this
email was sent. Otherwise we'll be unable to match the invite to your login.

Please visit http://your-move.appspot.com to accept or reject this invite.

You can change email settings at http://your-move.appspot.com/prefs.
""")

def sendYourMoveEmail(movePlayer, opponent, gameKey):
  mail.send_mail(sender="Your-Move Online Chess <sje397@gmail.com>",
              to=movePlayer.email(),
              subject="Your move",
              body="""
Dear """ + movePlayer.nickname() + """,

It's your turn to move in a game against """ + opponent.nickname() + """.

You can view this game at http://your-move.appspot.com/game?id=""" + gameKey + """.

You can change email settings at http://your-move.appspot.com/prefs.
""")

def sendInvite(user, toUser):
  prefs = getPrefs(toUser)
  if prefs.emailInvited:
    sendInviteEmail(user, toUser.email())
  if prefs.imInvited:
    sendInviteIm(user, toUser.email())

def sendYourMove(movePlayer, otherPlayer, gameKey):
  prefs = getPrefs(movePlayer)
  if prefs.emailMyMove:
    sendYourMoveEmail(movePlayer, otherPlayer, gameKey)
  if prefs.imMyMove:
    sendYourMoveIM(movePlayer, otherPlayer, gameKey)
  
