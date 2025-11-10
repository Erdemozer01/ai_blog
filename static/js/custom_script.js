// Tarayıcının global alanında kendi namespace'imizi oluşturuyoruz
window.dash_clientside = window.dash_clientside || {};

window.dash_clientside.clientside = {
    // Sayfayı yenileyecek olan fonksiyon
    reloadPage: function(n_clicks) {
        // Butona basıldıysa (n_clicks 1 veya daha fazlaysa)
        if (n_clicks > 0) {
            // Tarayıcıya sayfayı yeniden yükle komutunu gönder
            window.location.reload();
        }
        // Dash'e herhangi bir bileşeni güncellemamasını söyle
        return window.dash_clientside.no_update;
    }
};