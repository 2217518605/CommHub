from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.core.cache import cache

class BlacklistJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        validated_token = super().get_validated_token(raw_token)
        token_str = raw_token.decode()
        key = f"blacklist_refresh:{token_str}"  # 和登出时的 key 一致
        if cache.get(key):
            raise AuthenticationFailed('Token 已登出')
        return validated_token