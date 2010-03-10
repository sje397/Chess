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

class MainView(webapp.RequestHandler):
  def get(self):
    user = users.get_current_user()
    template_values = {
      'logoutUrl': users.create_logout_url("/")
    }
    if not dev_env:
      if not user:
        self.redirect(users.create_login_url(self.request.url))
        return
      logging.warn("Logged in as %s (%s)", user.nickname(), user.email())
        
      template_values.update({'user': user})
        
      if not hasattr(user.user_info(), 'access_token') and hasattr(user.user_info(), 'request_token'):
        signed_request_token = gdata.auth.OAuthToken(key=user.user_info().request_token, secret='')
    
        access_token = gcontacts.UpgradeToOAuthAccessToken(signed_request_token)
        logging.info('access token: %s' % access_token)
        user.updateInfo(access_token = str(access_token))
      
      if hasattr(user.user_info(), 'access_token'):
        gcontacts.current_token = makeToken(user.user_info().access_token, 'http://www.google.com/m8/feeds/')  
        #gcontacts.SetOAuthToken(makeToken(user.user_info().access_token, 'http://www.google.com/m8/feeds/'))
        
        query = gdata.contacts.service.ContactsQuery()
        query.max_results = 500
        feed = gcontacts.GetContactsFeed(query.ToUri())

        template_values.update({'feed': feed})

    path = os.path.join(os.path.dirname(__file__), 'chess.html')
    self.response.out.write(template.render(path, template_values))      


application = webapp.WSGIApplication(
                                     [ ('/', MainView),
                                      ],
                                     debug=True)
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()