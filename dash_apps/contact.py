import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, dcc, Input, Output, State, no_update
from django.core.mail import send_mail, BadHeaderError
from django.conf import settings
from django.urls import reverse
from django.contrib.sites.models import Site

external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]

app = DjangoDash('ContactApp', external_stylesheets=external_stylesheets)


@app.callback(
    Output('contact-form-feedback', 'children'),
    Input('submit-contact-button', 'n_clicks'),
    State('contact-name', 'value'),
    State('contact-email', 'value'),
    State('contact-subject', 'value'),
    State('contact-message', 'value'),
    prevent_initial_call=True
)
def submit_contact_form(n_clicks, name, email, subject, message, **kwargs):
    from blog.models import ContactMessage
    from dash_apps.i18n_helper import t, get_lang

    # Dili request cookie'sinden belirle
    request = kwargs.get('request')
    lang = get_lang(request) if request is not None else 'en'

    if not all([name, email, subject, message]):
        return dbc.Alert(t('contact_fill_all', lang), color="warning")

    try:
        new_message = ContactMessage.objects.create(
            name=name, email=email, subject=subject, message=message
        )

        try:
            # --- BU BÖLÜM GÜNCELLENDİ ---
            current_site = Site.objects.get_current()
            admin_path = reverse('admin:blog_contactmessage_change', args=[new_message.id])
            # URL'nin sonuna özel işaretçimizi ekliyoruz: ?source=email
            admin_url = f"http://{current_site.domain}{admin_path}?source=email"

            notification_subject = f"AI Blog - Yeni İletişim Mesajı: {subject}"

            plain_message = f"""
            Merhaba, bir iletişim mesajı aldınız.
            Gönderen: {name} ({email})
            Konu: {subject}
            Mesaj: {message}
            Mesajı görüntülemek ve okundu olarak işaretlemek için linki ziyaret edin: {admin_url}
            """

            html_message = f"""
            <p>Merhaba, siteniz üzerinden yeni bir iletişim mesajı aldınız.</p>
            <hr>
            <p><strong>Gönderen:</strong> {name}</p>
            <p><strong>E-posta:</strong> {email}</p>
            <p><strong>Konu:</strong> {subject}</p>
            <p><strong>Mesaj:</strong></p>
            <blockquote style="border-left: 2px solid #ccc; padding-left: 10px; margin-left: 5px;">
                <p>{message.replace(chr(10), "<br>")} </p>
            </blockquote>
            <hr>
            <p>

                <a href="{admin_url}" style="background-color: #198754; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">
                    Mesajı Görüntüle ve Okundu Olarak İşaretle
                </a>
            </p>
            <br>
            <p style="font-size: smaller; color: #777;">Bu mesaj AI Blog sitenizden otomatik olarak gönderilmiştir.</p>
            """

            send_mail(
                subject=notification_subject,
                message=plain_message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=['ozer246@gmail.com'],
                fail_silently=False,
                html_message=html_message
            )
            # --- GÜNCELLEME BİTTİ ---
        except (BadHeaderError, Exception) as e:
            print(f"!!! E-posta gönderim hatası: {e}")

        return dbc.Alert(t('contact_success', lang), color="success")

    except Exception as e:
        print(f"İletişim formu veritabanı kaydı hatası: {e}")
        return dbc.Alert(t('contact_error', lang), color="danger")


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open