import logging
import os
import random

from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db

import gdata.service
import gdata.alt.appengine
import gdata.auth
import gdata.urlfetch

import gdata.contacts
import gdata.contacts.service

from django.utils import simplejson 

import models
import notify
from utils import getPrefs

dev_env = os.environ['SERVER_SOFTWARE'].startswith('Dev')

settings = {
  'GOOGLE_CONSUMER_KEY': 'your-move.appspot.com',
  'SIG_METHOD': gdata.auth.OAuthSignatureMethod.RSA_SHA1
}

if not dev_env:
  f = open('chessrsakey.pem')
  RSA_KEY = f.read()
  f.close()

  gcontacts = gdata.contacts.service.ContactsService()
  gdata.alt.appengine.run_on_appengine(gcontacts)
  gcontacts.SetOAuthInputParameters(settings['SIG_METHOD'], settings['GOOGLE_CONSUMER_KEY'], rsa_key=RSA_KEY)

from aeoid import users

def makeToken(tokenString, scope):
  logging.info('making key from string "%s"' % tokenString)
  oauth_input_params=gcontacts.GetOAuthInputParameters()
  token = gdata.auth.OAuthToken(scopes=[scope], oauth_input_params=oauth_input_params)
  token.set_token_string(tokenString)
  return token

def authRequired(fn):
  def authFunc(*args, **kwargs):
    user = users.get_current_user()
    if not dev_env:
      if not user:
        args[0].redirect(users.create_login_url(args[0].request.url))
        return
    else:
      user = users.User(identity_url = 'http://example.com/testAEOID', nickname = 'dev', email = 'dev@example.com', is_admin = True)
      os.environ['aeoid.user'] = str(user._user_info_key)
    kwargs.update({'user': user})
    return fn(*args, **kwargs)
  return authFunc
 
class BaseView(webapp.RequestHandler):
  def initialize(self, request, response):
    super(BaseView, self).initialize(request, response)
  def render_template(self, filename, template_values = {}):
    path = os.path.join(os.path.dirname(__file__), 'templates', filename)
    self.response.out.write(template.render(path, template_values))      

class MainView(BaseView):
  @authRequired
  def get(self, user):
    if not dev_env:
      logging.warn("Logged in as %s (%s)", user.nickname(), user.email())
                
      if (hasattr(user.user_info(), 'access_token') == False or user.user_info().access_token is None) and hasattr(user.user_info(), 'request_token'):
        signed_request_token = gdata.auth.OAuthToken(key=user.user_info().request_token, secret='')
    
        access_token = gcontacts.UpgradeToOAuthAccessToken(signed_request_token)
        logging.info('access token: %s' % access_token)
        user.updateInfo(access_token = str(access_token))
      
      if hasattr(user.user_info(), 'access_token') and user.user_info().access_token is not None:
        # TODO: if access token is not valid, renew
        gcontacts.current_token = makeToken(user.user_info().access_token, 'http://www.google.com/m8/feeds/')  
        #gcontacts.SetOAuthToken(makeToken(user.user_info().access_token, 'http://www.google.com/m8/feeds/'))
        
        query = gdata.contacts.service.ContactsQuery()
        query.max_results = 500
        try:
          feed = gcontacts.GetContactsFeed(query.ToUri())
          contacts = feed.entry
        except:
          user.updateInfo(access_token = None)
          contacts = []
      else:
        contacts = []
        
    else:
      contacts = [{'title' : {'text': 'buddy number 1'}, 'email' : [{'primary': 'true', 'address': 'dev@example.com'}]},
                  {'title' : {'text': 'buddy number 2'}, 'email' : [{'primary': 'true', 'address': 'nobody@example.com'}]}]

    games = models.Game.gql('where state = 0 and whitePlayer = :1', user._user_info_key).fetch(200) 
    games.extend(models.Game.gql('where state = 0 and blackPlayer = :1 and whitePlayer != :1', user._user_info_key).fetch(200)) 

    invitesFrom = models.Invite.gql('where fromUser = :1 and status = :2', user._user_info_key, models.INVITE_PENDING).fetch(100)
    invitesTo = models.Invite.gql('where toUser = :1 and status = :2', user._user_info_key, models.INVITE_PENDING).fetch(100)

    invitesToEtc = models.Invite.gql('where toUser = NULL and toEmail = :1 and status = :2', user.email(), models.INVITE_PENDING).fetch(100)
    for i in invitesToEtc:
      i.toUser = user
    db.put(invitesToEtc) #update toUser
    invitesTo.extend(invitesToEtc)
    
    template_values = {}
    template_values.update({'logoutUrl': users.create_logout_url("/")})
    template_values.update({'user': user})
    template_values.update({'contacts': contacts})
    template_values.update({'games': games})
    template_values.update({'invitesFrom': invitesFrom})
    template_values.update({'invitesTo': invitesTo})

    self.render_template('main.html', template_values)

  @authRequired
  def post(self, user):
    toEmail = self.request.get('invited')
    if toEmail:
      info = users.UserInfo.gql('where email = :1', toEmail).get()
      if info:
        other = users.User(identity_url = info.key().name())
        invite = models.Invite(toUser = other, toEmail = toEmail)
        notify.sendInvite(user, other)
      else:
        invite = models.Invite(toEmail = toEmail)
        notify.sendInviteEmail(user, toEmail)
      invite.put()
    if self.request.get('submit') == 'Delete':
      invites = self.request.get_all('select')
      for i in invites:
        invite = db.get(i)
        invite.delete()
    if self.request.get('submit') == 'Accept':
      invites = self.request.get_all('select')
      for i in invites:
        invite = db.get(i)
        if invite:
          invite.status = models.INVITE_ACCEPTED
          if invite.fromPlayAs == models.PLAYAS_RANDOM:
            invite.fromPlayAs = random.choice([models.PLAYAS_WHITE, models.PLAYAS_BLACK])
          invite.put()
          if invite.fromPlayAs == models.PLAYAS_WHITE:
            game = models.Game(whitePlayer = invite.fromUser, blackPlayer = invite.toUser)
          else:
            game = models.Game(whitePlayer = invite.toUser, blackPlayer = invite.fromUser)
          game.put()
          notify.sendYourMove(game.whitePlayer, game.blackPlayer, str(game.key()))
    if self.request.get('submit') == 'Reject':
      invites = self.request.get_all('select')
      for i in invites:
        invite = db.get(i)
        if invite:
          invite.status = models.INVITE_REJECTED
          invite.put()
    self.redirect('/')

class GameView(BaseView):
  @authRequired
  def get(self, user):
    gameKeyStr = self.request.get('id')
    if gameKeyStr:
      game = db.get(gameKeyStr)
      if game:
        template_values = {}

        prefs = getPrefs(user)
        template_values.update({'prefs': prefs})
        if dev_env:
          template_values.update({'pollPeriod': 5000})
        else:
          template_values.update({'pollPeriod': 30000})
        template_values.update({'logoutUrl': users.create_logout_url("/")})
        template_values.update({'user': user})
        template_values.update({'game': game})
        # HACK - if playing yourself, it's your move
        if game.whiteMove:
          playAsWhite = game.whitePlayer.user_id() == user.user_id()
        else:
          playAsWhite = not game.blackPlayer.user_id() == user.user_id()
        template_values.update({'playAsWhite': playAsWhite})
        self.render_template('chess.html', template_values)
      else:
        self.error(404)
    else:
      self.error(500)
      
class SummaryData(BaseView):
  @authRequired
  def get(self, user):
    games = models.Game.gql('where state = 0 and whitePlayer = :1', user._user_info_key).fetch(200) 
    games.extend(models.Game.gql('where state = 0 and blackPlayer = :1 and whitePlayer != :1', user._user_info_key).fetch(200)) 

    invitesFrom = models.Invite.gql('where fromUser = :1 and status = :2', user._user_info_key, models.INVITE_PENDING).fetch(100)
    invitesTo = models.Invite.gql('where toUser = :1 and status = :2', user._user_info_key, models.INVITE_PENDING).fetch(100)

    invitesToEtc = models.Invite.gql('where toUser = NULL and toEmail = :1 and status = :2', user.email(), models.INVITE_PENDING).fetch(100)
    for i in invitesToEtc:
      i.toUser = user
    db.put(invitesToEtc) #update toUser
    invitesTo.extend(invitesToEtc)
    
    data = {}
    data['games'] = []
    for g in games:
      data['games'].append({'key': str(g.key()), 'moves': len(g.moves), 'myMove' : g.myMove(), 'whiteNick': g.whitePlayer.nickname(), 'blackNick': g.blackPlayer.nickname()})
    data['invitesFrom'] = []
    for i in invitesFrom:
      data['invitesFrom'].append({'key': str(i.key()), 'nick': i.fromUser.nickname(), 'email': i.fromUser.email()})
    data['invitesTo'] = []
    for i in invitesTo:
      if i.toUser is None:
        nick = "Unknown"
      else:
        nick = i.toUser.nickname()
      data['invitesTo'].append({'key': str(i.key()), 'nick': nick, 'email': i.toEmail})
    self.response.out.write(simplejson.dumps(data))

class GameData(BaseView):
  @authRequired
  def get(self, user):
    gameKeyStr = self.request.get('id')
    if gameKeyStr:
      game = db.get(gameKeyStr)
      if game:
        self.response.out.write(simplejson.dumps(game.moves))
          #self.redirect('/game?id=' + str(game.key()))
      else:
        self.error(404)
    else:
      self.error(500)
    
  @authRequired
  def post(self, user):
    gameKeyStr = self.request.get('id')
    move = self.request.get('move')
    moveNum = int(self.request.get('moveNum'))
    logging.info("state: %s" % self.request.get('state'))
    state = int(self.request.get('state'))
    if gameKeyStr and move:
      game = db.get(gameKeyStr)
      if game:
        if len(game.moves) == moveNum - 1 and game.state == models.NOT_FINISHED:
          game.moves.append(move)
          game.whiteMove = not game.whiteMove
          game.state = state
          game.put()
          
          if game.whiteMove:
            movePlayer = game.whitePlayer
            otherPlayer = game.blackPlayer
          else:
            movePlayer = game.blackPlayer
            otherPlayer = game.whitePlayer
          notify.sendYourMove(movePlayer, otherPlayer, str(game.key()))
        else:
          logging.warn('Out of sync move, move list length: %s, move number: %s, state: %s' % (len(game.moves), moveNum, game.state))
          self.error(409)
      else:
        self.error(404)
    else:
      self.error(500)
    

class PrefsView(BaseView):
  @authRequired
  def get(self, user):
    template_values = {}
    
    prefs = models.Prefs.gql('where user = :1', user._user_info_key).get()
    if not prefs:
      prefs = models.Prefs(user = user)
    template_values.update({'prefs': prefs})

    template_values.update({'logoutUrl': users.create_logout_url("/")})
    template_values.update({'user': user})
    self.render_template('prefs.html', template_values)

  @authRequired
  def post(self, user):
    prefs = models.Prefs.gql('where user = :1', user._user_info_key).get()
    if not prefs:
      prefs = models.Prefs()
      
    prefs.whitePieceType = self.request.get('wpcType')
    prefs.blackPieceType = self.request.get('bpcType')
    prefs.whiteSquareImage = self.request.get('wsqType')
    prefs.blackSquareImage = self.request.get('bsqType')
    
    logging.info('emailMyMove: ' + self.request.get('emailMyMove'))
    prefs.emailMyMove = self.request.get('emailMyMove') == 'on'
    prefs.emailInvited = self.request.get('emailInvited') == 'on'
    prefs.imMyMove = self.request.get('imMyMove') == 'on'
    prefs.imInvited = self.request.get('imInvited') == 'on'
    prefs.put()
    
    self.redirect('/')

application = webapp.WSGIApplication(
                                     [ ('/', MainView),
                                       ('/game', GameView),
                                       ('/gameData', GameData),
                                       ('/summaryData', SummaryData),
                                       ('/prefs', PrefsView),
                                      ],
                                     debug=True)
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()