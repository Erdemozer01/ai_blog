from django import forms

from django_ckeditor_5.fields import CKEditor5Field, CKEditor5Widget
from .models import GeneratedArticle, Category

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
                    'placeholder': 'Örn: "Yenilenebilir enerji kaynaklarının Türkiye ekonomisine etkileri üzerine bir analiz"'
                }
            ),
        }



