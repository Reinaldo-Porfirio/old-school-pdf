"""Erros públicos; mensagens devem ser seguras para exibição local."""


class OldSchoolPDFError(Exception):
    """Erro recuperável do aplicativo."""


class FeatureUnavailableError(OldSchoolPDFError):
    """Uma capacidade ainda não implementada foi solicitada."""


class InvalidTransitionError(OldSchoolPDFError):
    """Uma tarefa não aceita a transição solicitada."""


class SettingsError(OldSchoolPDFError):
    """Preferências locais não puderam ser gravadas."""
