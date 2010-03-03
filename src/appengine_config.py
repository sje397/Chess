from aeoid import middleware

def webapp_add_wsgi_middleware(app):
  app = middleware.AeoidMiddleware(app)
  return app