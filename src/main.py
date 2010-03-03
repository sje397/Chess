import logging
import os

from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from aeoid import users

class MainView(webapp.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.url))
      return
    logging.warn("Logged in as %s (%s)", user.nickname(), user.email())
        
    template_values = {
      'user': user,
      'logoutUrl': users.create_logout_url("/"),
    }

    path = os.path.join(os.path.dirname(__file__), 'main.html')
    self.response.out.write(template.render(path, template_values))      


application = webapp.WSGIApplication(
                                     [ ('/', MainView),
                                      ],
                                     debug=True)
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()