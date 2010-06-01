import logging
import os
import random

from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import users

import gdata.service
import gdata.alt.appengine
import gdata.auth
import gdata.urlfetch
# Use urlfetch instead of httplib
gdata.service.http_request_handler = gdata.urlfetch

import gdata.contacts
import gdata.contacts.service

from django.utils import simplejson 

import models
from models import getPrefs

import notify

dev_env = os.environ['SERVER_SOFTWARE'].startswith('Dev')

settings = {
  'GOOGLE_CONSUMER_KEY': 'your-move.appspot.com',
  'SIG_METHOD': gdata.auth.OAuthSignatureMethod.RSA_SHA1,
  'SCOPES': ['https://www.google.com/m8/feeds/']
}

if not dev_env:
  f = open('chessrsakey.pem')
  RSA_KEY = f.read()
  f.close()

def makeToken(tokenString, scope):
  logging.info('making key from string "%s"' % tokenString)
  oauth_input_params=gcontacts.GetOAuthInputParameters()
  token = gdata.auth.OAuthToken(scopes=[scope], oauth_input_params=oauth_input_params)
  token.set_token_string(tokenString)
  return token
 
class BaseView(webapp.RequestHandler):
  def initialize(self, request, response):
    super(BaseView, self).initialize(request, response)
  def render_template(self, filename, template_values = {}):
    path = os.path.join(os.path.dirname(__file__), 'templates', filename)
    self.response.out.write(template.render(path, template_values))      

class MainView(BaseView):
  def __init__(self):
    self.gcontacts = gdata.contacts.service.ContactsService()
    self.gcontacts.SetOAuthInputParameters(settings['SIG_METHOD'], settings['GOOGLE_CONSUMER_KEY'], rsa_key=RSA_KEY)
    gdata.alt.appengine.run_on_appengine(self.gcontacts)
    
    
  def get(self):
    user = users.get_current_user()
    # determine whether we got here via an invite to a different email address
    inviteKey = self.request.get('i')
    if inviteKey:
      invite = db.get(inviteKey)
      if invite:
        altEmail = invite.toEmail
        invite.toUser = user        
        invite.toEmail = user.email()
        logging.info("Invite was to %s - updating" % altEmail)
        invite.put()
              
    if dev_env:
      # some test data
      contacts = [{'title' : {'text': 'buddy number 1'}, 'email' : [{'primary': 'true', 'address': 'dev@example.com'}]},
                  {'title' : {'text': 'buddy number 2'}, 'email' : [{'primary': 'true', 'address': 'nobody@example.com'}]}]
    else:
      if not user.email():
        self.error(400)
        
      logging.info("Logged in as %s (%s)", user.nickname(), user.email())

      oauth_token = gdata.auth.OAuthTokenFromUrl(self.request.uri)
      if oauth_token:
        oauth_token.oauth_input_params = self.gcontacts.GetOAuthInputParameters()
        self.gcontacts.SetOAuthToken(oauth_token)
        
        oauth_verifier = self.request.get('oauth_verifier', default_value='')
        access_token = self.gcontacts.UpgradeToOAuthAccessToken(oauth_verifier = oauth_verifier)

        # Remember the access token in the current user's token store
        if access_token and users.get_current_user():
          self.gcontacts.token_store.add_token(access_token)
        elif access_token:
          self.gcontacts.current_token = access_token
          self.gcontacts.SetOAuthToken(access_token)

      access_token = self.gcontacts.token_store.find_token('%20'.join(settings['SCOPES']))
      if not isinstance(access_token, gdata.auth.OAuthToken):
        # 1.) REQUEST TOKEN STEP. Provide the data scope(s) and the page we'll
        # be redirected back to after the user grants access on the approval page.
        req_token = self.gcontacts.FetchOAuthRequestToken(scopes=settings['SCOPES'], oauth_callback=self.request.uri)
  
        # Generate the URL to redirect the user to.  Add the hd paramter for a
        # better user experience.  Leaving it off will give the user the choice
        # of what account (Google vs. Google Apps) to login with.
        domain = self.request.get('domain', default_value='default')
        approval_page_url = self.gcontacts.GenerateOAuthAuthorizationURL(extra_params={'hd': domain})
  
        # 2.) APPROVAL STEP.  Redirect to user to Google's OAuth approval page.
        self.redirect(approval_page_url)
        return
      else:
        #try:
        query = gdata.contacts.service.ContactsQuery()
        query.max_results = 500
        logging.info('Feed url: %s' % query.ToUri())
        feed = self.gcontacts.GetContactsFeed(query.ToUri())
        contacts = feed.entry
        #except:
        #  contacts = []
        
    games = models.Game.gql('where state = 0 and whitePlayer = :1', user).fetch(200) 
    games.extend(models.Game.gql('where state = 0 and blackPlayer = :1 and whitePlayer != :1', user).fetch(200)) 

    invitesFrom = models.Invite.gql('where fromUser = :1 and status = :2', user, models.INVITE_PENDING).fetch(100)
    invitesTo = models.Invite.gql('where toUser = :1 and status = :2', user, models.INVITE_PENDING).fetch(100)

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
    if dev_env:
      template_values.update({'pollPeriod': 5000})
    else:
      template_values.update({'pollPeriod': 120000})

    self.render_template('main.html', template_values)

  def post(self):
    user = users.get_current_user()
    toEmail = self.request.get('invited')
    if toEmail:
      prefs = models.Prefs.gql('where userEmail = :1', toEmail).get()
      if prefs:
        invite = models.Invite(toUser = prefs.user, toEmail = toEmail)
        invite.put()
        notify.sendInvite(user, invite)
      else:
        invite = models.Invite(toEmail = toEmail)
        invite.put()
        notify.sendInviteEmail(user, invite)
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
  def get(self):
    user = users.get_current_user()
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
          template_values.update({'pollPeriod': 60000})
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
  def get(self):
    user = users.get_current_user()
    games = models.Game.gql('where state = 0 and whitePlayer = :1', user).fetch(200) 
    games.extend(models.Game.gql('where state = 0 and blackPlayer = :1 and whitePlayer != :1', user).fetch(200)) 

    invitesFrom = models.Invite.gql('where fromUser = :1 and status = :2', user, models.INVITE_PENDING).fetch(100)
    invitesTo = models.Invite.gql('where toUser = :1 and status = :2', user, models.INVITE_PENDING).fetch(100)

    invitesToEtc = models.Invite.gql('where toUser = NULL and toEmail = :1 and status = :2', user.email(), models.INVITE_PENDING).fetch(100)
    for i in invitesToEtc:
      i.toUser = user
    db.put(invitesToEtc) #update toUser
    invitesTo.extend(invitesToEtc)
    
    data = {}
    data['games'] = []
    for g in games:
      data['games'].append({'key': str(g.key()), 'moves': len(g.moves), 'myMove' : g.myMove(), 'whiteNick': g.whitePlayer.nickname(), 'blackNick': g.blackPlayer.nickname()})
      
    data['invitesTo'] = []
    for i in invitesTo:
      data['invitesTo'].append({'key': str(i.key()), 'fromUser': {'nickname': i.fromUser.nickname(), 'email': i.fromUser.email()}})
      
    data['invitesFrom'] = []
    for i in invitesFrom:
      iData = {'key': str(i.key()), 'toEmail': i.toEmail}
      if i.toUser:
        iData['toUser'] = {'nickname': i.toUser.nickname(), 'email': i.toUser.email()}
      data['invitesFrom'].append(iData)
    self.response.out.write(simplejson.dumps(data))

class GameData(BaseView):
  def get(self):
    user = users.get_current_user()
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
    
  def post(self):
    user = users.get_current_user()
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
          if game.state == models.NOT_FINISHED:
            notify.sendYourMove(movePlayer, otherPlayer, str(game.key()))
        else:
          logging.warn('Out of sync move, move list length: %s, move number: %s, state: %s' % (len(game.moves), moveNum, game.state))
          self.error(409)
      else:
        self.error(404)
    else:
      self.error(500)
    

class PrefsView(BaseView):
  def get(self):
    user = users.get_current_user()
    template_values = {}
    
    prefs = models.Prefs.gql('where user = :1', user).get()
    if not prefs:
      prefs = models.Prefs(user = user)
    template_values.update({'prefs': prefs})

    template_values.update({'logoutUrl': users.create_logout_url("/")})
    template_values.update({'user': user})
    self.render_template('prefs.html', template_values)

  def post(self):
    user = users.get_current_user()
    prefs = models.Prefs.gql('where user = :1', user).get()
    if not prefs:
      prefs = models.Prefs(user = user, userEmail = user.email())
      
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

class AdminView(BaseView):
  def get(self):
    user = users.get_current_user()
    action = self.request.get('action')
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Hello, %s.\n\n' % user.nickname())
    if action=='flush':
      memcache.flush_all()
      self.response.out.write('Cache flushed.\n')
    
application = webapp.WSGIApplication(
                                     [ ('/', MainView),
                                       ('/game', GameView),
                                       ('/gameData', GameData),
                                       ('/summaryData', SummaryData),
                                       ('/prefs', PrefsView),
                                       ('/admin', AdminView)
                                      ],
                                     debug=True)
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()