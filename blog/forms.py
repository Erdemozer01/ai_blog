from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import GeneratedArticle


class SignUpForm(UserCreationForm):
    """E-posta zorunlu kayıt formu (Django UserCreationForm tabanlı)."""
    email = forms.EmailField(required=True, label="E-posta")

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Kullanıcı Adı"
        self.fields['password1'].label = "Şifre"
        self.fields['password2'].label = "Şifre (Tekrar)"
        # Admin temasında tüm alanlar eşit/geniş görünsün
        for name in ('username', 'email', 'password1', 'password2'):
            self.fields[name].widget.attrs.update({'class': 'vLargeTextField'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Bu e-posta adresi zaten kullanımda.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class ArticleRequestForm(forms.ModelForm):
    class Meta:
        model = GeneratedArticle
        # Formda sadece bu alanı göstereceğiz
        fields = ['user_request']
        # Alana özel etiket ve widget ayarları
        labels = {
            'user_request': 'Makale Konusu, Sorusu veya Anahtar Kelimeler'
        }
        widgets = {
            'user_request': forms.Textarea(
                attrs={
                    'rows': 5,
                    'placeholder': ('Örn: "Yenilenebilir enerji kaynaklarının Türkiye ekonomisine '
                                    'etkileri üzerine bir analiz"')
                }
            ),
        }
