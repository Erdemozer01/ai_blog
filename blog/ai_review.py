"""
AI Makale İnceleme Servisi
Bir makaleyi okuyup yayınlanabilirlik skoru (0-100) ve düzeltme önerileri üretir,
sonucu veritabanına kaydeder ve makale sahibine e-posta gönderir.
"""
import json
import re
from django.utils import timezone


def _build_review_prompt(article):
    """AI'a gönderilecek inceleme istemi."""
    import re as _re
    title = article.title or "Başlık yok"

    # Sistem yer tutucularını temizle (AI bunları "eksik içerik" sanmasın)
    raw_content = article.full_content or ""
    # _||_STRUCTURED_DATA_N_||_ ve _||_SECTION_BREAK_||_ gibi işaretleri kaldır
    raw_content = _re.sub(r'_\|\|_STRUCTURED_DATA_\d+_\|\|_', '', raw_content)
    raw_content = _re.sub(r'_\|\|_SECTION_BREAK_\|\|_', '\n\n', raw_content)
    raw_content = _re.sub(r'_\|\|_[A-Z_]+\d*_\|\|_', '', raw_content)  # diğer olası yer tutucular
    content = raw_content.strip()[:8000]  # token sınırı için kırp

    abstract = article.turkish_abstract or article.english_abstract or ""

    return (
        "Sen akademik bir editör ve içerik moderatörüsün. Aşağıdaki makaleyi yayına "
        "uygunluk açısından değerlendir. Şunları kontrol et: bilimsel/olgusal doğruluk, "
        "akademik dil ve üslup, mantıksal tutarlılık, dilbilgisi ve yazım, uygunsuz/etik "
        "olmayan içerik, eksik veya yüzeysel bölümler.\n\n"
        "NOT: Makaledeki grafik ve tablolar sistem tarafından otomatik olarak ayrı bir "
        "alanda yerleştirilir; metinde görmesen bile eksik olarak değerlendirme.\n\n"
        "Yanıtını YALNIZCA şu JSON formatında ver (başka açıklama ekleme):\n"
        "{\n"
        '  "score": <0-100 arası tamsayı, yayınlanabilirlik skoru>,\n'
        '  "publishable": <true veya false>,\n'
        '  "suggestions": "<varsa düzeltme önerileri, madde madde. Hata yoksa boş bırak>"\n'
        "}\n\n"
        "Skor rehberi: 80-100 = yayına hazır, 60-79 = küçük düzeltmeler gerekli, "
        "40-59 = önemli düzeltmeler gerekli, 0-39 = yayına uygun değil.\n\n"
        f"BAŞLIK: {title}\n\n"
        f"ÖZET: {abstract}\n\n"
        f"İÇERİK:\n{content}"
    )


def _parse_ai_response(text):
    """AI yanıtından JSON çıkarır (markdown bloğu içinde olabilir)."""
    if not text:
        return None
    # ```json ... ``` veya düz JSON
    cleaned = re.sub(r'```(?:json)?', '', text).strip()
    # İlk { ... son } arasını al
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        score = int(data.get('score', 0))
        score = max(0, min(100, score))  # 0-100 sınırla

        # suggestions string, liste veya None olabilir — hepsini metne çevir
        raw_suggestions = data.get('suggestions')
        if isinstance(raw_suggestions, list):
            # Liste → madde madde metin
            suggestions = '\n'.join(
                f"• {str(item).strip()}" for item in raw_suggestions if str(item).strip()
            )
        elif isinstance(raw_suggestions, str):
            suggestions = raw_suggestions.strip()
        elif raw_suggestions is None:
            suggestions = ''
        else:
            # dict veya başka tip → düz metne çevir
            suggestions = str(raw_suggestions).strip()

        return {
            'score': score,
            'publishable': bool(data.get('publishable', score >= 60)),
            'suggestions': suggestions,
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def review_article(article):
    """
    Makaleyi AI ile inceler, sonucu kaydeder ve sahibine e-posta gönderir.
    (ok: bool, mesaj: str) döner.
    """
    from ai_engine.services import generate_with_pool

    try:
        prompt = _build_review_prompt(article)
        response_text, _key = generate_with_pool(
            prompt, service_name="Google Gemini", model_name="gemini-2.5-flash"
        )
    except Exception as e:
        return False, f"AI çağrısı başarısız: {e}"

    result = _parse_ai_response(response_text)
    if result is None:
        return False, "AI yanıtı işlenemedi (geçersiz format)."

    # Sonucu kaydet
    article.ai_review_score = result['score']
    article.ai_review_notes = result['suggestions'] or "Önemli bir hata tespit edilmedi."
    article.ai_reviewed_at = timezone.now()
    article.save(update_fields=['ai_review_score', 'ai_review_notes', 'ai_reviewed_at'])

    # Sahibine e-posta gönder
    email_sent = _send_review_email(article, result)

    msg = f"İnceleme tamamlandı. Skor: {result['score']}/100."
    if email_sent:
        msg += " Kullanıcıya e-posta gönderildi."
    else:
        msg += " (E-posta gönderilemedi veya kullanıcının e-postası yok.)"
    return True, msg


def _send_review_email(article, result):
    """Makale sahibine AI inceleme sonucunu e-posta ile gönderir."""
    from django.core.mail import send_mail
    from django.conf import settings

    owner = article.owner
    if not owner or not owner.email:
        return False

    score = result['score']
    suggestions = result['suggestions'] or "Önemli bir hata tespit edilmedi."
    publishable = result['publishable']

    durum = "yayına uygun görünüyor" if publishable else "yayınlanmadan önce düzeltme gerektiriyor"

    subject = f"Makaleniz İncelendi: {article.title or 'Makale'}"
    body = (
        f"Merhaba,\n\n"
        f"\"{article.title}\" başlıklı makaleniz yapay zeka tarafından incelendi.\n\n"
        f"Yayınlanabilirlik Skoru: {score}/100\n"
        f"Değerlendirme: Makaleniz {durum}.\n\n"
        f"Düzeltme Önerileri:\n{suggestions}\n\n"
        f"Önerileri dikkate alarak makalenizi düzenleyebilir ve tekrar yayın talebi "
        f"gönderebilirsiniz.\n\n"
        f"İyi çalışmalar,\nAI Blog Ekibi"
    )
    from_email = getattr(settings, 'EMAIL_HOST_USER', 'noreply@example.com')

    try:
        send_mail(subject, body, from_email, [owner.email], fail_silently=False)
        return True
    except Exception:
        return False


def notify_superusers_correction_request(article, user_message=""):
    """
    Kullanıcı düzeltme/tekrar inceleme talebi gönderdiğinde superuser'lara e-posta atar.
    Sabit alıcı: ozer246@gmail.com (+ veritabanındaki diğer superuser e-postaları).
    """
    from django.core.mail import send_mail
    from django.conf import settings
    from django.contrib.auth.models import User

    # Alıcılar: sabit adres + tüm superuser e-postaları
    recipients = {'ozer246@gmail.com'}
    for su in User.objects.filter(is_superuser=True).exclude(email='').values_list('email', flat=True):
        if su:
            recipients.add(su)

    subject = f"Düzeltme Talebi Var: {article.title or 'Makale'}"
    body = (
        f"Bir kullanıcı makalesi için düzeltme/inceleme talebi gönderdi.\n\n"
        f"Makale: {article.title}\n"
        f"Sahibi: {article.owner.username} ({article.owner.email})\n"
        f"Mevcut AI Skoru: {article.ai_review_score if article.ai_review_score is not None else 'Henüz incelenmedi'}\n\n"
    )
    if user_message:
        body += f"Kullanıcının mesajı:\n{user_message}\n\n"
    body += "Lütfen admin panelinden makaleyi inceleyin."

    from_email = getattr(settings, 'EMAIL_HOST_USER', 'noreply@example.com')

    try:
        send_mail(subject, body, from_email, list(recipients), fail_silently=False)
        return True
    except Exception:
        return False