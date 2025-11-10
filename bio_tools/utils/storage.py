from django.core.files.storage import FileSystemStorage
import os


class SecureFileSystemStorage(FileSystemStorage):
    """Güvenli dosya saklama"""

    def get_valid_name(self, name):
        # Path traversal saldırılarını engelle
        name = super().get_valid_name(name)
        # .. karakterlerini kaldır
        name = name.replace('..', '')
        # Sadece basename'i al
        name = os.path.basename(name)
        return name

    def get_available_name(self, name, max_length=None):
        """Benzersiz dosya adı oluştur"""
        return super().get_available_name(name, max_length)