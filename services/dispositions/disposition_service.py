from services.base import BaseService

class DispositionService(BaseService):
    def get_user_dispositions(self, user):
        return self.repository.get_by_user(user)
