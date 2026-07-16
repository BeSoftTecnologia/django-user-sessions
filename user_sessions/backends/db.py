from django.contrib import auth
from django.contrib.sessions.backends.db import SessionStore as DBStore


class SessionStore(DBStore):
    """
    Implements database session store.
    """
    def __init__(self, session_key=None, user_agent=None, ip=None):
        super().__init__(session_key)
        # Truncate user_agent string to max_length of the CharField
        self.user_agent = user_agent[:200] if user_agent else user_agent
        self.ip = ip
        self.user_id = None

    # Used by superclass to get self.model, which is used elsewhere
    @classmethod
    def get_model_class(cls):
        # Avoids a circular import and allows importing SessionStore when
        # user_sessions is not in INSTALLED_APPS
        from ..models import Session

        return Session

    def __setitem__(self, key, value):
        if key == auth.SESSION_KEY:
            self.user_id = value
        super().__setitem__(key, value)

    # Used in DBStore.load()
    def _get_session_from_db(self):
        s = super()._get_session_from_db()
        if s is None:
            self.user_id = None
            return None
        self.user_id = s.user_id
        # do not overwrite user_agent/ip, as those might have been updated
        if self.user_agent != s.user_agent or self.ip != s.ip:
            self.modified = True
        return s

    def create(self):
        # Preserva dados já carregados em memória. O cycle_key() do Django
        # restaura o cache depois do create(); o caminho flush()+login()
        # (ex.: loginas) não restaura. Se _session_cache ficar como {},
        # o próximo acesso NÃO recarrega do banco e o save() seguinte
        # sobrescreve a sessão autenticada com payload vazio.
        cached = getattr(self, '_session_cache', None)
        user_id = self.user_id
        super().create()
        if cached:
            self._session_cache = cached
            self.user_id = user_id
        else:
            self._session_cache = {}

    # Used in DBStore.save()
    def create_model_instance(self, data):
        """
        Return a new instance of the session model object, which represents the
        current session state. Intended to be used for saving the session data
        to the database.
        """
        return self.model(
            session_key=self._get_or_create_session_key(),
            session_data=self.encode(data),
            expire_date=self.get_expiry_date(),
            user_agent=self.user_agent,
            user_id=self.user_id,
            ip=self.ip,
        )

    def clear(self):
        super().clear()
        self.user_id = None
