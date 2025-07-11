import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, dcc, Input, Output, State, no_update


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
def submit_contact_form(n_clicks, name, email, subject, message):
    from blog.models import ContactMessage

    if not all([name, email, subject, message]):
        return dbc.Alert("Lütfen tüm alanları doldurun.", color="warning")
    try:
        ContactMessage.objects.create(
            name=name, email=email, subject=subject, message=message
        )
        return dbc.Alert("Mesajınız başarıyla gönderildi. Teşekkür ederiz!", color="success")
    except Exception as e:
        print(f"İletişim formu hatası: {e}")
        return dbc.Alert("Mesajınız gönderilirken bir hata oluştu.", color="danger")


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n_clicks, is_open):
    """
    Kullanıcı hamburger menü butonuna bastığında, menünün
    açık/kapalı durumunu tersine çevirir.
    """
    if n_clicks:
        return not is_open
    return is_open