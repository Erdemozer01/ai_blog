import requests
import time


def verify_dois_with_crossref(doi_list):
    """
    Verilen DOI listesini Crossref API'si üzerinden kontrol eder
    ve makalelerin gerçekliğini, başlıklarını ve yayın tarihlerini döndürür.
    """
    base_url = "https://api.crossref.org/works/"
    results = []

    # Crossref API kullanım kuralları (Polite Pool) gereği User-Agent belirtilmesi isteklerin hızlı yanıtlanmasını sağlar.
    headers = {
        "User-Agent": "ArticleSearchApp/1.0 (mailto:ozer246@gmail.com)"
    }

    for doi in doi_list:
        # DOI formatını temizleme (URL olarak verildiyse sadece ID kısmını alma)
        clean_doi = doi.replace("https://doi.org/", "").strip()
        url = f"{base_url}{clean_doi}"

        try:
            # 10 saniyelik zaman aşımı ile GET isteği
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                item = data.get("message", {})

                title = item.get("title", ["Bilinmeyen Başlık"])[0]
                publisher = item.get("publisher", "Bilinmeyen Yayıncı")

                # Crossref üzerinde tarih formatları değişkenlik gösterebilir
                published_date = item.get("published-print", item.get("published-online", {}))
                date_parts = published_date.get("date-parts", [["Bilinmiyor"]])
                year = date_parts[0][0]

                results.append({
                    "doi": clean_doi,
                    "status": "Doğrulandı",
                    "title": title,
                    "publisher": publisher,
                    "year": year
                })
            elif response.status_code == 404:
                results.append({
                    "doi": clean_doi,
                    "status": "Bulunamadı (404)",
                    "title": "-",
                    "publisher": "-",
                    "year": "-"
                })
            else:
                results.append({
                    "doi": clean_doi,
                    "status": f"Hata ({response.status_code})",
                    "title": "-",
                    "publisher": "-",
                    "year": "-"
                })

        except requests.exceptions.RequestException as e:
            results.append({
                "doi": clean_doi,
                "status": f"Bağlantı Hatası: {e}",
                "title": "-",
                "publisher": "-",
                "year": "-"
            })

        # Crossref API hız sınırına (rate limit) takılmamak için bekleme süresi
        time.sleep(0.1)

    return results


if __name__ == "__main__":
    # PDF metninizden alınan bazı güncel DOI numaraları
    test_dois = [
        "10.1038/s41586-025-09678-5",  # Wang et al. (Nature, 2026)
        "10.1007/s10142-026-01827-x",  # Li et al. (Funct. Integr. Genomics, 2026)
        "10.1111/mpp.13183",  # van de Vossenberg et al. (Mol. Plant Pathol., 2022)
        "10.3390/genes14061170",  # He et al. (Genes, 2023)
        "10.1111/mpp.13435",  # Schmey et al. (Mol. Plant Pathol., 2024)
        "10.1093/jxb/eraf393"  # Yeo et al. (J. Exp. Bot., 2025)
    ]

    print("Crossref API üzerinden DOI doğrulaması başlatılıyor...\n")
    verification_results = verify_dois_with_crossref(test_dois)

    for result in verification_results:
        print(f"DOI: {result['doi']}")
        print(f"Durum: {result['status']}")
        if result['status'] == "Doğrulandı":
            print(f"Başlık: {result['title']}")
            print(f"Yayıncı: {result['publisher']}")
            print(f"Yıl: {result['year']}")
        print("-" * 50)