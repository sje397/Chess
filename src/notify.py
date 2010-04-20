import logging
from google.appengine.api import xmpp
from google.appengine.api import mail

from utils import getPrefs

def sendInviteIM(user, invite):
  toEmail = invite.toEmail
  if xmpp.get_presence(toEmail):
    xmpp.send_message(toEmail, user.nickname() +' has invited you to play a game of chess. http://your-move.appspot.com?i=' + str(invite.key()))

def sendYourMoveIM(movePlayer, opponent, gameKey):
  if xmpp.get_presence(movePlayer.email()):
    xmpp.send_message(movePlayer.email(), "Your Move. http://your-move.appspot.com/game?id=" + gameKey)

def sendInviteEmail(user, invite):
  toEmail = invite.toEmail
  logging.info('Sending email to %s with key %s' % (toEmail, str(invite.key())))
  mail.send_mail(sender="Your-Move Online Chess <sje397@gmail.com>",
              to=toEmail,
              subject="Chess Invitation",
              body="""Dear """ + toEmail + """,

""" + user.nickname() + """ (""" + user.email() + """) has invited you to play a game of chess.

Please visit http://your-move.appspot.com?i=""" + str(invite.key()) + """ to accept or reject this invite.

You can change email settings at http://your-move.appspot.com/prefs.""",
              html="""Dear """ + toEmail + """,<br><br>
<aref='mailTo:""" + user.email() + """'>""" + user.nickname() + """</a> has invited you to play a game of chess.<br>
Please <a href='http://your-move.appspot.com?i=""" + str(invite.key()) + """'>click here</a> to accept or reject this invite.<br><br>
You can change email settings <a href='http://your-move.appspot.com/prefs'>here</a>.""")

def sendYourMoveEmail(movePlayer, opponent, gameKey):
  mail.send_mail(sender="Your-Move Online Chess <sje397@gmail.com>",
              to=movePlayer.email(),
              subject="Your move",
              body="""Dear """ + movePlayer.nickname() + """,

It's your turn to move in a game against """ + opponent.nickname() + """.

You can view this game at http://your-move.appspot.com/game?id=""" + gameKey + """.

You can change email settings at http://your-move.appspot.com/prefs.""",
              html="""Dear """ + movePlayer.nickname() + """,<br><br>
It's your turn to move in a game against """ + opponent.nickname() + """.<br>
To view this game, <a href='http://your-move.appspot.com/game?id=""" + gameKey + """'>click here</a>.<br><br>
You can change email settings <a href='http://your-move.appspot.com/prefs'>here</a>.""")

def sendInvite(user, invite):
  prefs = getPrefs(invite.toUser)
  if prefs.emailInvited:
    sendInviteEmail(user, invite)
  if prefs.imInvited:
    sendInviteIm(user, invite)

def sendYourMove(movePlayer, otherPlayer, gameKey):
  prefs = getPrefs(movePlayer)
  if prefs.emailMyMove:
    sendYourMoveEmail(movePlayer, otherPlayer, gameKey)
  if prefs.imMyMove:
    sendYourMoveIM(movePlayer, otherPlayer, gameKey)
  
