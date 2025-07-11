import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import html, Output, Input, State

# Sadece uygulamayı tanımlıyoruz.
app = DjangoDash('ResumeApp',
                 external_stylesheets=[dbc.themes.BOOTSTRAP, 'https://use.fontawesome.com/releases/v5.8.1/css/all.css'])


# BU DOSYADA ARTIK app.layout ATAMASI YOK.

def create_resume_layout(profile):
    """
    Bir Profile nesnesi alır ve buna dayanarak tam bir özgeçmiş sayfası
    Dash layout'u oluşturup döndürür.
    """
    # Eğer view'dan bir profil gelmediyse (örn: veritabanında hiç profil yoksa)
    if not profile:
        return dbc.Alert(
            "Görüntülenecek profil bulunamadı. Lütfen admin panelinden bir profil oluşturun.",
            color="danger", className="m-5 text-center"
        )

    # Veritabanından ilişkili verileri çek
    experiences = profile.experience.all().order_by('-start_date')
    educations = profile.education.all().order_by('-graduation_year')
    skills = profile.skills.all().order_by('-level')

    # Deneyim bölümünü oluştur
    experience_section = [
        html.Div([
            html.H5(exp.job_title, className="fw-bold"),
            html.P(html.Em(
                f"{exp.company} | {exp.start_date.strftime('%Y-%m')} - {exp.end_date.strftime('%Y-%m') if exp.end_date else 'Halen'}"),
                   className="text-muted"),
            # Açıklamayı satırlara bölerek liste yap
            html.Ul([html.Li(item.strip()) for item in exp.description.splitlines() if item.strip()])
        ], className="mb-4") for exp in experiences
    ]

    # Eğitim bölümünü oluştur
    education_section = [
        html.Div([
            html.H5(edu.degree, className="fw-bold"),
            html.P(html.Em(f"{edu.institution} | {edu.graduation_year}"), className="text-muted"),
        ], className="mb-4") for edu in educations
    ]

    # Yetenekler bölümünü oluştur
    skills_section = [
        html.Div([
            html.P(skill.name, className="mb-1"),
            dbc.Progress(value=skill.level, color="primary", className="mb-3", style={'height': '12px'}),
        ]) for skill in skills
    ]

    # Tüm parçaları birleştirerek layout'u döndür
    return dbc.Container([
        dbc.Row(dbc.Col(html.Div([
            html.Img(
                src=profile.profile_picture.url if profile.profile_picture else "https://via.placeholder.com/150",
                className="rounded-circle mb-4 shadow-sm",
                style={'width': '150px', 'height': '150px', 'object-fit': 'cover'}
            ),
            html.H1(f"{profile.first_name} {profile.last_name}", className="display-4"),
            html.H4(profile.title, className="text-muted"),
            html.P([
                html.A([html.I(className="fas fa-envelope me-2"), profile.email or ""], href=f"mailto:{profile.email}",
                       className="text-decoration-none me-3"),
                html.A([html.I(className="fab fa-linkedin me-2"), "LinkedIn"], href=profile.linkedin_url,
                       target="_blank", className="text-decoration-none me-3"),
                html.A([html.I(className="fab fa-github me-2"), "GitHub"], href=profile.github_url, target="_blank",
                       className="text-decoration-none"),
            ], className="lead mt-3")
        ]), width=12, className="text-center my-5")),

        dbc.Row([
            dbc.Col([
                html.H2("Özet"), html.P(profile.summary), html.Hr(className="my-4"),
                html.H2("Deneyim"), experience_section if experience_section else [html.P("İş deneyimi eklenmemiş.")],
                html.Hr(className="my-4"),
                html.H2("Eğitim"), education_section if education_section else [html.P("Eğitim bilgisi eklenmemiş.")],
            ], md=8),
            dbc.Col([html.H2("Yetenekler"), html.Hr(className="my-4"),
                     skills_section if skills_section else [html.P("Yetenek eklenmemiş.")]], md=4),
        ])
    ], className="mt-4")


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