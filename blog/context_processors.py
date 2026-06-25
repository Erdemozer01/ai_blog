"""
Context processor — her template render edildiğinde dil bilgisini ve
footer/genel çevirileri context'e ekler.

settings.py TEMPLATES -> OPTIONS -> context_processors listesine eklenmeli:
    'blog.context_processors.i18n_context'
"""


def i18n_context(request):
    from dash_apps.i18n_helper import get_lang, t
    lang = get_lang(request)
    # Template'lerde {{ i18n.footer_home }} gibi erişilebilir
    keys = [
        'footer_quick_access', 'footer_home', 'footer_login', 'footer_contact',
        'footer_generate', 'footer_follow', 'footer_rights',
        'nav_blog', 'nav_contact', 'nav_login',
    ]
    return {
        'site_lang': lang,
        'i18n': {k: t(k, lang) for k in keys},
        'footer_tagline': (
            'Yapay zekâ destekli akademik içerik üretimi ile güçlü biyoinformatik '
            'araçları tek çatı altında. Sekanstan CRISPR tasarımına, makale üretiminden '
            'veri analizine kadar bilimi erişilebilir kılıyoruz.'
            if lang == 'tr' else
            'AI-powered academic content generation and a powerful suite of bioinformatics '
            'tools under one roof. From sequence analysis to CRISPR design, we make '
            'science accessible.'
        ),
    }