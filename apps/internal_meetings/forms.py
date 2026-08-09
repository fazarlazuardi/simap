from django import forms
from .models import InternalMeeting
from users.models import Employee


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
        required=True,
        label="Pimpinan Rapat"
    )
    participants = EmployeeChoiceField(
        queryset=Employee.objects.filter(is_active=True).order_by('full_name'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label="Peserta Rapat (Pegawai / Amil)"
    )

    class Meta:
        model = InternalMeeting
        fields = [
            'title', 'meeting_type', 'scheduled_at', 'location',
            'leaders', 'participants', 'agenda_topics', 'attachment'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control custom-input', 'placeholder': 'Contoh: Rapat Pleno Evaluation Program Pendistribusian'}),
            'meeting_type': forms.Select(attrs={'class': 'form-select custom-input'}),
            'location': forms.TextInput(attrs={'class': 'form-control custom-input', 'placeholder': 'Contoh: Ruang Rapat Utama BAZNAS / Zoom'}),
            'agenda_topics': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Tuliskan poin-poin agenda pembahasan...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control custom-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter Pimpinan Rapat hanya untuk Jabatan Struktural (Ketua s/d Kabid IV), exclude Staff Pelaksana
        pimpinan_qs = Employee.objects.filter(is_active=True).exclude(position__icontains='staf').exclude(position__icontains='pelaksana').order_by('id')
        self.fields['leaders'].queryset = pimpinan_qs

        if self.instance and self.instance.pk:
            self.fields['leaders'].initial = self.instance.leaders.all()


class SingleEmployeeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if obj.position:
            return f"{obj.full_name} ({obj.position})"
        return f"{obj.full_name}"


class NotulensiForm(forms.ModelForm):
    notulis = SingleEmployeeChoiceField(
        queryset=Employee.objects.filter(is_active=True).order_by('full_name'),
        widget=forms.Select(attrs={'class': 'form-select custom-input'}),
        required=False,
        label="Notulis Rapat"
    )

    class Meta:
        model = InternalMeeting
        fields = [
            'notulensi_summary', 'notulensi_decision', 'notulensi_action_items',
            'notulis', 'notulensi_file', 'status'
        ]
        widgets = {
            'notulensi_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Tuliskan ringkasan pembahasan & dinamika rapat...'}),
            'notulensi_decision': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tuliskan kesimpulan & keputusan rapat...'}),
            'notulensi_action_items': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tuliskan rencana tindak lanjut (Action Plan) dan penanggung jawab...'}),
            'notulensi_file': forms.FileInput(attrs={'class': 'form-control custom-input'}),
            'status': forms.Select(attrs={'class': 'form-select custom-input'}),
        }
