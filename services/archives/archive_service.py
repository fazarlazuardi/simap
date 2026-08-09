from services.base import BaseService

class ArchiveService(BaseService):
    def get_all_archives(self):
        return self.repository.get_with_related()

    def create_archive(self, data, file):
        return self.repository.create(**data, file_path=file)
