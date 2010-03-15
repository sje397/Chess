import logging
import os

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

class UserData(db.Expando):
  user = users.UserProperty
  access_token = db.StringProperty

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
        self.redirect(users.create_login_url(self.request.url))
        return
    else:
      user = {'nickname':'dev'}
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
                
      if not hasattr(user.user_info(), 'access_token') and hasattr(user.user_info(), 'request_token'):
        signed_request_token = gdata.auth.OAuthToken(key=user.user_info().request_token, secret='')
    
        access_token = gcontacts.UpgradeToOAuthAccessToken(signed_request_token)
        logging.info('access token: %s' % access_token)
        user.updateInfo(access_token = str(access_token))
      
      if hasattr(user.user_info(), 'access_token'):
        # TODO: if access token is not valid, renew
        gcontacts.current_token = makeToken(user.user_info().access_token, 'http://www.google.com/m8/feeds/')  
        #gcontacts.SetOAuthToken(makeToken(user.user_info().access_token, 'http://www.google.com/m8/feeds/'))
        
        query = gdata.contacts.service.ContactsQuery()
        query.max_results = 500
        feed = gcontacts.GetContactsFeed(query.ToUri())
        contacts = feed.entry
    else:
      contacts = [{'title' : {'text': 'buddy number 1'}}]

    template_values = {}
    template_values.update({'logoutUrl': users.create_logout_url("/")})
    template_values.update({'user': user})
    template_values.update({'contacts': contacts})

    self.render_template('main.html', template_values)

class GameView(BaseView):
  @authRequired
  def get(self, user):
    template_values = {}
    template_values.update({'logoutUrl': users.create_logout_url("/")})
    template_values.update({'user': user})
    self.render_template('chess.html', template_values)

application = webapp.WSGIApplication(
                                     [ ('/', MainView),
                                       ('/game', GameView),
                                      ],
                                     debug=True)
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()