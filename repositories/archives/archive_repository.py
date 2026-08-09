from repositories.base import BaseRepository
from archives.models import Archive, Category

class ArchiveRepository(BaseRepository):
    model = Archive

    def get_with_related(self):
        return self.model.objects.select_related('category', 'uploaded_by').all().order_by('-created_at')

class CategoryRepository(BaseRepository):
    model = Category
