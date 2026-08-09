from repositories.base import BaseRepository
from dispositions.models import Disposition

class DispositionRepository(BaseRepository):
    model = Disposition

    def get_by_user(self, user):
        return self.model.objects.filter(receiver=user).select_related('archive', 'sender').order_by('-created_at')
