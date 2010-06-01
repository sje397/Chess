import os
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from google.appengine.api import users

class OpenIDLogin(webapp.RequestHandler):
  def get(self):
    cont = self.request.get('continue')
    logging.info('creating login form, cont: %s' % cont)
    template_values = {
      'continue': cont
    }

    path = os.path.join(os.path.dirname(__file__), 'templates', 'login.html')
    logging.info('Rendering template with path: %s' % path)
    self.response.out.write(template.render(path, template_values))      

  def post(self):
    cont = self.request.get('continue')
    logging.info('OpenIDLogin handler called, cont: %s' % cont)
    openid = self.request.get('openid_url')
    if openid:
      logging.info('creating login url for openid: %s' % openid)
      login_url = users.create_login_url(cont, None, openid)
      logging.info('redirecting to url: %s' % login_url)
      self.redirect(login_url)
    else:
      self.error(400)

application = webapp.WSGIApplication([('/_ah/login_required', OpenIDLogin)], debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
