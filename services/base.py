class BaseService:
    repository = None

    def __init__(self, repository=None):
        self.repository = repository

    def get_all(self):
        return self.repository.get_all()

    def get_by_id(self, id):
        return self.repository.get_by_id(id)
