class BaseRepository:
    model = None

    def get_all(self):
        return self.model.objects.all()

    def get_by_id(self, id):
        return self.model.objects.filter(id=id).first()

    def create(self, **kwargs):
        return self.model.objects.create(**kwargs)

    def update(self, instance, **kwargs):
        for attr, value in kwargs.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    def delete(self, instance):
        instance.delete()
