from django.core.cache import cache
from rest_framework.authentication import get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings
from user_app.models import User


class BlacklistJWTAuthentication(JWTAuthentication):

    def get_raw_token(self, header):

        if not header:
            return None
        parts = header.split()
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            if parts[0].lower() in [t.lower().encode() for t in api_settings.AUTH_HEADER_TYPES]:
                return parts[1]
        return None

    def authenticate(self, request):

        header = get_authorization_header(request)
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

    def get_user(self, validated_token):

        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise AuthenticationFailed("Token缺少用户标识")
        try:
            return User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except User.DoesNotExist:
            raise AuthenticationFailed("用户不存在")

    def get_validated_token(self, raw_token):

        validated_token = super().get_validated_token(raw_token)
        token_str = raw_token.decode() if isinstance(raw_token, (bytes, bytearray)) else str(raw_token)
        if cache.get(f"blacklist_access:{token_str}") or cache.get(f"blacklist_refresh:{token_str}"):
            raise AuthenticationFailed("Token 已登出")
        return validated_token
