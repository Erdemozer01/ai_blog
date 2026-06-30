"""
Filogenetik ağaç ortak motoru.
Hem sekans analizinde (çoklu dizi) hem ayrı Filogenetik Ağaç aracında kullanılır.

Akış: çoklu dizi → basit hizalama → mesafe matrisi → NJ/UPGMA ağacı →
      Plotly görseli + Newick metni + (opsiyonel) AI evrimsel yorum.

NOT: Tam MSA (ClustalW/MUSCLE) için harici araç gerekir; burada diziler
en kısa ortak uzunluğa kırpılarak basit bir hizalama yapılır. Aynı gen/bölgeye
ait benzer diziler için (örn. ortolog gen dizileri) bu pratik bir yaklaşımdır.
"""
import io
import warnings

warnings.filterwarnings('ignore')


def _clean_taxon_name(record):
    """SeqRecord'dan okunabilir bir takson (tür) adı çıkarır."""
    desc = (record.description or '').strip()
    # 'Opuntia marenae rpl16 gene...' gibi açıklamadan tür adını al
    name = desc
    for marker in (' rpl', ' gene', ' chloroplast', ' partial', ' complete'):
        idx = name.lower().find(marker.lower())
        if idx > 0:
            name = name[:idx]
    # gi|...|gb|ACC| önekini temizle
    if '|' in name:
        name = name.split('|')[-1].strip()
    name = name.strip()
    if not name:
        name = record.id
    # Newick/görsel için güvenli: boşlukları alt çizgiyle değiştir, kısalt
    return name.replace(' ', '_').replace(':', '_').replace(',', '_')[:30]


def build_phylo_tree(records, method='nj'):
    """
    SeqRecord listesinden filogenetik ağaç kurar.

    records: Bio.SeqRecord listesi (en az 3 dizi gerekir)
    method: 'nj' (Neighbor-Joining) veya 'upgma'

    Döner: dict {
        'success': bool,
        'error': str (varsa),
        'tree': Bio.Phylo ağaç nesnesi,
        'newick': Newick formatında metin,
        'taxa': takson adları listesi,
        'method': kullanılan yöntem,
        'n_taxa': dizi sayısı,
        'aln_length': hizalama uzunluğu,
        'distance_summary': mesafe matrisi özeti (str),
    }
    """
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord
    from Bio.Align import MultipleSeqAlignment
    from Bio.Phylo.TreeConstruction import DistanceCalculator, DistanceTreeConstructor

    if not records or len(records) < 3:
        return {'success': False,
                'error': 'Filogenetik ağaç için en az 3 dizi gerekir.'}

    try:
        # Basit hizalama: en kısa ortak uzunluğa kırp
        min_len = min(len(r.seq) for r in records)
        if min_len < 20:
            return {'success': False, 'error': 'Diziler ağaç için çok kısa.'}

        seen_names = {}
        aln_records = []
        for r in records:
            name = _clean_taxon_name(r)
            # Aynı isim tekrarını engelle
            if name in seen_names:
                seen_names[name] += 1
                name = f"{name}_{seen_names[name]}"
            else:
                seen_names[name] = 0
            aln_records.append(SeqRecord(Seq(str(r.seq)[:min_len].upper()), id=name))

        alignment = MultipleSeqAlignment(aln_records)
        taxa = [rec.id for rec in aln_records]

        # Mesafe matrisi (identity = paylaşılan pozisyon oranı)
        calc = DistanceCalculator('identity')
        dm = calc.get_distance(alignment)

        constructor = DistanceTreeConstructor()
        method = (method or 'nj').lower()
        if method == 'upgma':
            tree = constructor.upgma(dm)
        else:
            method = 'nj'
            tree = constructor.nj(dm)

        # İç düğüm adlarını temizle (Inner1, Inner2 görselde gürültü yapar)
        for clade in tree.find_clades():
            if clade.name and clade.name.startswith('Inner'):
                clade.name = None

        # Newick metni
        newick_io = io.StringIO()
        from Bio import Phylo
        Phylo.write(tree, newick_io, 'newick')
        newick = newick_io.getvalue().strip()

        # Mesafe matrisi özeti (en yakın/uzak çiftler)
        dist_summary = _distance_summary(dm, taxa)

        # Her taksonun (yaprağın) terminal dal uzunluğu — akrabalık göstergesi
        branch_lengths = []
        for leaf in tree.get_terminals():
            bl = leaf.branch_length or 0.0
            branch_lengths.append({'taxon': leaf.name, 'branch_length': round(bl, 4)})
        # Uzun dal = daha ayrık/farklı; kısa dal = diğerlerine yakın
        branch_lengths.sort(key=lambda x: x['branch_length'])

        # İkili mesafe tablosu (taksonlar arası tüm uzaklıklar)
        pairwise = []
        for i in range(len(taxa)):
            for j in range(i + 1, len(taxa)):
                try:
                    d = dm[taxa[i], taxa[j]]
                    pairwise.append({'a': taxa[i], 'b': taxa[j],
                                     'distance': round(d, 4)})
                except Exception:
                    pass
        pairwise.sort(key=lambda x: x['distance'])

        return {
            'success': True,
            'tree': tree,
            'newick': newick,
            'taxa': taxa,
            'method': 'Neighbor-Joining (NJ)' if method == 'nj' else 'UPGMA',
            'n_taxa': len(taxa),
            'aln_length': min_len,
            'distance_summary': dist_summary,
            'branch_lengths': branch_lengths,
            'pairwise_distances': pairwise,
        }
    except Exception as e:
        return {'success': False, 'error': f'Ağaç oluşturulamadı: {e}'}


def _distance_summary(dm, taxa):
    """Mesafe matrisinden en yakın ve en uzak tür çiftlerini özetler."""
    try:
        pairs = []
        for i in range(len(taxa)):
            for j in range(i + 1, len(taxa)):
                pairs.append((dm[taxa[i], taxa[j]], taxa[i], taxa[j]))
        if not pairs:
            return ""
        pairs.sort()
        closest = pairs[0]
        farthest = pairs[-1]
        return (f"En yakın çift: {closest[1]} ↔ {closest[2]} (mesafe {closest[0]:.4f}); "
                f"En uzak çift: {farthest[1]} ↔ {farthest[2]} (mesafe {farthest[0]:.4f})")
    except Exception:
        return ""


def tree_to_plotly(tree_result):
    """
    build_phylo_tree sonucundaki ağacı bir Plotly figürüne çevirir (dendrogram tarzı).
    Döner: plotly.graph_objects.Figure veya None.
    """
    if not tree_result or not tree_result.get('success'):
        return None
    try:
        import plotly.graph_objects as go
        tree = tree_result['tree']

        # Yaprakların y konumlarını ata
        leaves = tree.get_terminals()
        y_pos = {}
        for i, leaf in enumerate(leaves):
            y_pos[leaf] = i

        # İç düğümlerin y'si = çocuklarının ortalaması (alttan üste)
        def get_y(clade):
            if clade in y_pos:
                return y_pos[clade]
            ys = [get_y(c) for c in clade.clades]
            y = sum(ys) / len(ys)
            y_pos[clade] = y
            return y

        # x = kökten uzaklık (dal uzunlukları toplamı)
        x_pos = {}
        def get_x(clade, x0=0.0):
            bl = clade.branch_length or 0.0
            x = x0 + bl
            x_pos[clade] = x
            for c in clade.clades:
                get_x(c, x)
        get_x(tree.root, 0.0)
        get_y(tree.root)

        edge_x, edge_y = [], []
        # Yatay dallar (her düğümden kendine) + dikey bağlantılar (çocuklar arası)
        for clade in tree.find_clades():
            cx = x_pos[clade]
            cy = y_pos[clade]
            for child in clade.clades:
                chx = x_pos[child]
                chy = y_pos[child]
                # dikey: ebeveyn x'inde, çocuk y'sinden ebeveyn y'sine
                edge_x += [cx, cx, None]
                edge_y += [cy, chy, None]
                # yatay: ebeveyn x'inden çocuk x'ine, çocuk y'sinde
                edge_x += [cx, chx, None]
                edge_y += [chy, chy, None]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y, mode='lines',
            line=dict(color='#3F4F75', width=1.5),
            hoverinfo='none', showlegend=False))

        # Yaprak etiketleri
        leaf_x = [x_pos[l] for l in leaves]
        leaf_y = [y_pos[l] for l in leaves]
        leaf_names = [l.name for l in leaves]
        fig.add_trace(go.Scatter(
            x=leaf_x, y=leaf_y, mode='markers+text',
            text=leaf_names, textposition='middle right',
            marker=dict(size=7, color='#2E8B57'),
            hoverinfo='text', showlegend=False))

        fig.update_layout(
            title=f"Filogenetik Ağaç — {tree_result.get('method', '')}",
            xaxis=dict(title='Evrimsel Mesafe', showgrid=True, zeroline=False),
            yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
            plot_bgcolor='white', height=max(350, 60 * len(leaves)),
            margin=dict(l=20, r=160, t=50, b=40))
        return fig
    except Exception:
        return None


def interpret_tree_ai(tree_result, lang='tr'):
    """
    Ağacı AI ile evrimsel olarak yorumlar (model fallback ile).
    Döner: yorum metni (str) veya boş str.
    """
    if not tree_result or not tree_result.get('success'):
        return ""
    try:
        from ai_engine.services import generate_with_pool, get_fallback_models

        taxa = tree_result.get('taxa', [])
        if lang == 'en':
            prompt = (
                "Below is a phylogenetic analysis result. Write a SHORT interpretation "
                "in English: just 1-2 complete sentences summarizing the key evolutionary "
                "relationship (which taxa cluster, which is most divergent).\n\n"
                f"Method: {tree_result.get('method')}\n"
                f"Number of taxa: {tree_result.get('n_taxa')}\n"
                f"Taxa: {', '.join(taxa)}\n"
                f"Distance summary: {tree_result.get('distance_summary', '')}\n\n"
                "Write only 1-2 complete sentences. No headings, no bullet points, "
                "no lists. Finish every sentence."
            )
        else:
            prompt = (
                "Aşağıda bir filogenetik analiz sonucu var. KISA bir yorum yaz: "
                "sadece 1-2 tam cümleyle temel evrimsel ilişkiyi özetle (hangi taksonlar "
                "kümeleniyor, hangisi en ayrık).\n\n"
                f"Yöntem: {tree_result.get('method')}\n"
                f"Takson sayısı: {tree_result.get('n_taxa')}\n"
                f"Taksonlar: {', '.join(taxa)}\n"
                f"Mesafe özeti: {tree_result.get('distance_summary', '')}\n\n"
                "Sadece 1-2 TAM cümle yaz. Başlık, madde işareti veya liste KULLANMA. "
                "Her cümleyi tamamla. Uzun yazma."
            )
        for svc, mdl in get_fallback_models("Google Gemini", "gemini-3.5-flash",
                                            cross_provider=True):
            try:
                text, _ = generate_with_pool(prompt, service_name=svc, model_name=mdl,
                                             max_tokens=512, temperature=0.5)
                if text and len(text.strip()) > 30:
                    return text.strip()
            except Exception:
                continue
        return ""
    except Exception:
        return ""
