from django.dispatch import Signal

# Sent after a request is authenticated as an impersonated user.
# Keyword arguments: request, actor, target. Sender: the authentication class.
user_impersonated = Signal()
