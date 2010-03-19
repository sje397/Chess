import models

def getPrefs(user):
  prefs = models.Prefs.gql('where user = :1', user._user_info_key).get()
  if not prefs:
    prefs = models.Prefs(user = user)
  return prefs

