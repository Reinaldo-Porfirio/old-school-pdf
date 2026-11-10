"""Erros públicos; mensagens devem ser seguras para exibição local."""


class DocForgeError(Exception):
    """Erro recuperável do aplicativo."""


class FeatureUnavailableError(DocForgeError):
    """Uma capacidade ainda não implementada foi solicitada."""


class InvalidTransitionError(DocForgeError):
    """Uma tarefa não aceita a transição solicitada."""


class SettingsError(DocForgeError):
    """Preferências locais não puderam ser gravadas."""
