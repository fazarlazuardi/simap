from django import forms
from django.db.models import Case, When, Value, IntegerField
from .models import InternalMeeting
from users.models import Employee


def get_ordered_employee_queryset():
    return Employee.objects.filter(is_active=True).annotate(
        rank=Case(
            When(position__icontains='wakil ketua iv', then=Value(5)),
            When(position__icontains='wakil ketua 4', then=Value(5)),
            When(position__icontains='waka iv', then=Value(5)),
            When(position__icontains='waka 4', then=Value(5)),
            When(position__icontains='wakil ketua iii', then=Value(4)),
            When(position__icontains='wakil ketua 3', then=Value(4)),
            When(position__icontains='waka iii', then=Value(4)),
            When(position__icontains='waka 3', then=Value(4)),
            When(position__icontains='wakil ketua ii', then=Value(3)),
            When(position__icontains='wakil ketua 2', then=Value(3)),
            When(position__icontains='waka ii', then=Value(3)),
            When(position__icontains='waka 2', then=Value(3)),
            When(position__icontains='wakil ketua i', then=Value(2)),
            When(position__icontains='wakil ketua 1', then=Value(2)),
            When(position__icontains='waka i', then=Value(2)),
            When(position__icontains='waka 1', then=Value(2)),
            When(position__icontains='ketua', then=Value(1)),
            When(position__icontains='kabid iv', then=Value(9)),
            When(position__icontains='kabid 4', then=Value(9)),
            When(position__icontains='kabid iii', then=Value(8)),
            When(position__icontains='kabid 3', then=Value(8)),
            When(position__icontains='kabid ii', then=Value(7)),
            When(position__icontains='kabid 2', then=Value(7)),
            When(position__icontains='kabid i', then=Value(6)),
            When(position__icontains='kabid 1', then=Value(6)),
            When(position__icontains='kabid', then=Value(10)),
            When(position__icontains='kepala', then=Value(10)),
            When(position__icontains='sekretaris', then=Value(11)),
            When(position__icontains='staf', then=Value(12)),
            When(position__icontains='pelaksana', then=Value(12)),
            default=Value(13),
            output_field=IntegerField(),
        )
    ).order_by('rank', 'full_name')


class EmployeeChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        if obj.position:
            return f"{obj.full_name} ({obj.position})"
        return f"{obj.full_name}"


class SingleEmployeeChoiceField(forms.ModelChoiceField):
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
        widget=forms.SelectMultiple(attrs={'class': 'form-select custom-input select2-leaders', 'multiple': 'multiple'}),
        required=False,
        label="Pimpinan Rapat (Multi-Select)"
    )
    notulis = SingleEmployeeChoiceField(
        queryset=Employee.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select custom-input select2-notulis'}),
        required=False,
        label="Notulis Rapat / Pencatat Risalah"
    )
    participants = EmployeeChoiceField(
        queryset=Employee.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select custom-input select2-participants', 'multiple': 'multiple'}),
        required=False,
        label="Peserta Rapat Internal (Amil / Pegawai BAZNAS)"
    )
    send_wa = forms.BooleanField(
        required=False,
        initial=True,
        label="Kirim Notifikasi Undangan WA Gateway ke Pimpinan & Peserta Rapat",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'})
    )

    class Meta:
        model = InternalMeeting
        fields = [
            'title', 'meeting_type', 'scheduled_at', 'location',
            'leaders', 'notulis', 'participants', 'guest_names', 'agenda_topics', 'attachment'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control custom-input', 'placeholder': 'Contoh: Rapat Pleno Evaluasi Program / Coffee Morning'}),
            'meeting_type': forms.Select(attrs={'class': 'form-select custom-input'}),
            'location': forms.TextInput(attrs={'class': 'form-control custom-input', 'placeholder': 'Contoh: Ruang Rapat Utama BAZNAS / Aula Pemkab'}),
            'agenda_topics': forms.Textarea(attrs={'class': 'form-control custom-input', 'rows': 4, 'placeholder': 'Tuliskan poin-poin utama agenda pembahasan rapat...'}),
            'guest_names': forms.Textarea(attrs={'class': 'form-control custom-input', 'rows': 3, 'placeholder': 'Tuliskan nama/instansi peserta luar (Contoh: Perwakilan UPZ Kecamatan, OPD Pemkab, Tokoh Agama, Media, Vendor)'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control custom-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        all_emp = get_ordered_employee_queryset()
        
        self.fields['leaders'].queryset = all_emp
        self.fields['notulis'].queryset = all_emp
        self.fields['participants'].queryset = all_emp

        if self.instance and self.instance.pk:
            self.fields['leaders'].initial = self.instance.leaders.all()
            self.fields['participants'].initial = self.instance.participants.all()


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notulis'].queryset = get_ordered_employee_queryset()
