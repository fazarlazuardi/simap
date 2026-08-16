from django import forms
from django.db.models import Case, When, Value, IntegerField
from .models import InternalMeeting
from users.models import Employee


def get_ordered_employee_queryset():
    return Employee.objects.filter(is_active=True).annotate(
        rank=Case(
            When(position__icontains='ketua', then=Value(1)),
            When(position__icontains='waka', then=Value(2)),
            When(position__icontains='kabid', then=Value(3)),
            When(position__icontains='kepala', then=Value(3)),
            When(position__icontains='kasubid', then=Value(4)),
            When(position__icontains='staf', then=Value(5)),
            When(position__icontains='pelaksana', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
    ).order_by('rank', 'full_name')


class EmployeeChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        if obj.position:
            return f"{obj.full_name} ({obj.position})"
        return f"{obj.full_name}"


class InternalMeetingForm(forms.ModelForm):
    scheduled_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control custom-input'
        }),
        label="Waktu & Tanggal Pelaksanaan"
    )
    leaders = EmployeeChoiceField(
        queryset=Employee.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label="Pimpinan Rapat (Dapat Disesuaikan Nanti)"
    )
    participants = EmployeeChoiceField(
        queryset=Employee.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label="Peserta Rapat / Amil Hadir (Dapat Disesuaikan Nanti)"
    )

    class Meta:
        model = InternalMeeting
        fields = [
            'title', 'meeting_type', 'scheduled_at', 'location',
            'leaders', 'participants', 'agenda_topics', 'attachment'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control custom-input', 'placeholder': 'Contoh: Coffee Morning / Rapat Evaluasi Program'}),
            'meeting_type': forms.Select(attrs={'class': 'form-select custom-input'}),
            'location': forms.TextInput(attrs={'class': 'form-control custom-input', 'placeholder': 'Contoh: Ruang Rapat Pimpinan BAZNAS / Aula'}),
            'agenda_topics': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Tuliskan agenda & poin utama pembahasan rapat...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control custom-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter Pimpinan Rapat hanya untuk Jabatan Struktural (Ketua s/d Kabid IV), exclude Staff Pelaksana
        pimpinan_qs = get_ordered_employee_queryset().exclude(position__icontains='staf').exclude(position__icontains='pelaksana')
        self.fields['leaders'].queryset = pimpinan_qs
        self.fields['participants'].queryset = get_ordered_employee_queryset()

        if self.instance and self.instance.pk:
            self.fields['leaders'].initial = self.instance.leaders.all()


class SingleEmployeeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if obj.position:
            return f"{obj.full_name} ({obj.position})"
        return f"{obj.full_name}"


class NotulensiForm(forms.ModelForm):
    notulis = SingleEmployeeChoiceField(
        queryset=Employee.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select custom-input'}),
        required=False,
        label="Notulis Rapat"
    )
    participants = EmployeeChoiceField(
        queryset=Employee.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label="Peserta Hadir Rapat"
    )

    class Meta:
        model = InternalMeeting
        fields = [
            'notulensi_summary', 'notulensi_decision', 'notulensi_action_items',
            'notulis', 'participants', 'notulensi_file', 'status'
        ]
        widgets = {
            'notulensi_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Tuliskan ringkasan pembahasan & dinamika rapat...'}),
            'notulensi_decision': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tuliskan kesimpulan & keputusan rapat...'}),
            'notulensi_action_items': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tuliskan rencana tindak lanjut (Action Plan) dan penanggung jawab...'}),
            'notulensi_file': forms.FileInput(attrs={'class': 'form-control custom-input'}),
            'status': forms.Select(attrs={'class': 'form-select custom-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notulis'].queryset = get_ordered_employee_queryset()
        self.fields['participants'].queryset = get_ordered_employee_queryset()
        if self.instance and self.instance.pk:
            self.fields['participants'].initial = self.instance.participants.all()
