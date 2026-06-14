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
            'Çeşitli konularda üretilmiş akademik makaleleri ve Biyoinformatik Araçlarını keşfedin.'
            if lang == 'tr' else
            'Discover academic articles on various topics and bioinformatics tools.'
        ),
    }