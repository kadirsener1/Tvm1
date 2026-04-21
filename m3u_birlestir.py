#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import glob
import requests
from collections import OrderedDict
from datetime import datetime
from urllib.parse import urlparse

# ╔══════════════════════════════════════════════════════════════════╗
# ║                        AYARLAR                                   ║
# ╚══════════════════════════════════════════════════════════════════╝

# 📁 Klasör ayarları
INPUT_FOLDER  = "input"
OUTPUT_FOLDER = "output"
OUTPUT_FILE   = "failover.m3u"

# 📡 M3U URL LİSTESİ (İstediğin kadar ekle veya sil)
M3U_URLS = [
    "https://raw.githubusercontent.com/kadirsener1/tivim/main/1.m3u",
    "https://raw.githubusercontent.com/kadirsener1/atom/main/playlist.m3u"
    "https://iptv-org.github.io/iptv/countries/tr.m3u",
    # Buraya istediğin kadar URL ekleyebilirsin
]

# 🔐 Ortam değişkenlerinden URL al (GitHub Secrets için)
# GitHub Secrets'a M3U_URL_1, M3U_URL_2 ... şeklinde ekle
ENV_URL_COUNT = 10  # Kaç adet Secret URL kontrol edilsin

# ⚙️ İstek ayarları
REQUEST_TIMEOUT = 30
MAX_RETRIES     = 3
USER_AGENT      = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 📊 Kalite sıralaması (küçük sayı = yüksek öncelik)
QUALITY_ORDER = {
    # 4K
    '4k'    : 1,
    'uhd'   : 1,
    '2160p' : 1,
    '2160'  : 1,
    # FHD
    'fhd'     : 2,
    'fullhd'  : 2,
    'full hd' : 2,
    '1080p'   : 2,
    '1080'    : 2,
    # HD
    'hd'   : 3,
    '720p' : 3,
    '720'  : 3,
    # SD
    'sd'   : 4,
    '576p' : 4,
    '480p' : 4,
    '480'  : 4,
    # Düşük
    '360p' : 5,
    '360'  : 5,
    '240p' : 6,
    '240'  : 6,
}
DEFAULT_QUALITY = 99

# ╔══════════════════════════════════════════════════════════════════╗
# ║                     YARDIMCI FONKSİYONLAR                       ║
# ╚══════════════════════════════════════════════════════════════════╝

def print_banner():
    """Program başlığını yazdır"""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║    📺  M3U FAİLOVER BİRLEŞTİRİCİ  v3.0                          ║
║    ──────────────────────────────────────────────────────────    ║
║    📡  URL'den otomatik M3U çekme                                ║
║    📁  Yerel dosya desteği                                       ║
║    🔐  GitHub Secrets desteği                                    ║
║    📊  Kalite sıralama  (4K → FHD → HD → SD)                     ║
║    🔗  Failover desteği (1. link → 2. link → 3. link)            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)


def print_section(title):
    """Bölüm başlığı yazdır"""
    print(f"\n╔══════════════════════════════════════════════════════════════════╗")
    print(f"║  {title:<64}║")
    print(f"╚══════════════════════════════════════════════════════════════════╝")


def print_divider():
    """Ayırıcı çizgi"""
    print("─" * 68)


def detect_quality(text):
    """
    Metin içindeki kalite bilgisini tespit et.
    Kanal adı, link URL veya EXTINF satırından çalışır.
    """
    if not text:
        return DEFAULT_QUALITY

    text_lower = text.lower()

    # Tam kelime eşleşmesi (daha güvenilir)
    for quality, priority in QUALITY_ORDER.items():
        pattern = (
            r'(?:^|[\s\-_\.\[\]\(\)/])' +
            re.escape(quality) +
            r'(?:$|[\s\-_\.\[\]\(\)/])'
        )
        if re.search(pattern, text_lower):
            return priority

    # Gevşek eşleşme (yine de bul)
    for quality, priority in QUALITY_ORDER.items():
        if quality in text_lower:
            return priority

    return DEFAULT_QUALITY


def get_quality_label(priority):
    """Kalite önceliğini etiket olarak döndür"""
    labels = {
        1  : "🏆 4K/UHD",
        2  : "🥇 FHD/1080p",
        3  : "🥈 HD/720p",
        4  : "🥉 SD/480p",
        5  : "📉 360p",
        6  : "📉 240p",
        99 : "❓ Bilinmiyor",
    }
    return labels.get(priority, "❓ Bilinmiyor")


def shorten_url(url, max_len=60):
    """URL'yi kısalt (görüntü için)"""
    try:
        parsed = urlparse(url)
        short = f"{parsed.netloc}{parsed.path}"
        if len(short) > max_len:
            short = short[:max_len] + "..."
        return short
    except:
        return url[:max_len] + "..."


# ╔══════════════════════════════════════════════════════════════════╗
# ║                         URL'DEN İNDİR                           ║
# ╚══════════════════════════════════════════════════════════════════╝

def download_m3u(url, retry=1):
    """
    URL'den M3U içeriğini indir.
    Başarısız olursa MAX_RETRIES kadar tekrar dener.
    """
    headers = {
        'User-Agent'      : USER_AGENT,
        'Accept'          : '*/*',
        'Accept-Language' : 'tr-TR,tr;q=0.9,en-US;q=0.8',
        'Accept-Encoding' : 'gzip, deflate',
        'Connection'      : 'keep-alive',
    }

    try:
        print(f"   ⏳ Deneme {retry}/{MAX_RETRIES} - İndiriliyor...")
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )
        response.raise_for_status()

        # Encoding düzelt
        if response.encoding is None:
            response.encoding = 'utf-8'
        content = response.content.decode('utf-8', errors='ignore')

        # Geçerli M3U mi kontrol et
        if not content.strip():
            print(f"   ❌ Boş içerik döndü!")
            return None

        if '#EXTINF' not in content and '#EXTM3U' not in content:
            print(f"   ⚠️  Geçerli M3U formatı değil!")
            return None

        line_count = len(content.splitlines())
        size_kb    = len(content.encode('utf-8')) / 1024
        print(f"   ✅ Başarılı! ({line_count} satır, {size_kb:.1f} KB)")
        return content

    except requests.exceptions.Timeout:
        print(f"   ⏱️  Zaman aşımı ({REQUEST_TIMEOUT}s)")
    except requests.exceptions.ConnectionError:
        print(f"   🔌 Bağlantı hatası")
    except requests.exceptions.HTTPError as e:
        print(f"   🌐 HTTP Hatası: {e.response.status_code}")
    except requests.exceptions.TooManyRedirects:
        print(f"   🔄 Çok fazla yönlendirme")
    except Exception as e:
        print(f"   ❌ Beklenmeyen hata: {str(e)}")

    # Tekrar dene
    if retry < MAX_RETRIES:
        print(f"   🔁 Tekrar deneniyor...")
        return download_m3u(url, retry + 1)

    return None


# ╔══════════════════════════════════════════════════════════════════╗
# ║                       YEREL DOSYA OKU                           ║
# ╚══════════════════════════════════════════════════════════════════╝

def read_local_m3u(file_path):
    """Yerel M3U dosyasını oku"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        if not content.strip():
            print(f"   ❌ Dosya boş!")
            return None

        line_count = len(content.splitlines())
        size_kb    = os.path.getsize(file_path) / 1024
        print(f"   ✅ Okundu! ({line_count} satır, {size_kb:.1f} KB)")
        return content

    except FileNotFoundError:
        print(f"   ❌ Dosya bulunamadı!")
        return None
    except PermissionError:
        print(f"   ❌ Dosyaya erişim izni yok!")
        return None
    except Exception as e:
        print(f"   ❌ Hata: {str(e)}")
        return None


# ╔══════════════════════════════════════════════════════════════════╗
# ║                        M3U PARSE ET                             ║
# ╚══════════════════════════════════════════════════════════════════╝

def parse_m3u_content(content, source_name="Bilinmiyor"):
    """
    M3U içeriğini parse ederek kanal sözlüğü oluştur.
    Her kanal için kalite bilgisiyle birlikte linkleri saklar.
    """
    if not content:
        return OrderedDict()

    channels      = OrderedDict()
    current_info  = None
    current_name  = None
    line_num      = 0
    parsed_count  = 0
    skipped_count = 0

    lines = content.splitlines()

    for line in lines:
        line_num += 1
        line = line.strip()

        # Boş satır veya sadece başlık satırı
        if not line or line == '#EXTM3U':
            continue

        # EXTINF satırı - kanal bilgisi
        if line.startswith('#EXTINF'):
            current_info = line
            # Virgülden sonraki kısmı kanal adı olarak al
            if ',' in line:
                current_name = line.split(',', 1)[-1].strip()
            else:
                current_name = f"Kanal_{line_num}"
            continue

        # Yorum satırları
        if line.startswith('#'):
            continue

        # Link satırı
        if current_name and current_info:
            # http, https, rtmp, rtsp destekle
            if any(line.startswith(proto) for proto in ['http://', 'https://', 'rtmp://', 'rtsp://']):

                if current_name not in channels:
                    channels[current_name] = {
                        'info'   : current_info,
                        'links'  : [],
                        'source' : source_name
                    }

                # Aynı linki tekrar ekleme
                existing_urls = [l['url'] for l in channels[current_name]['links']]
                if line not in existing_urls:

                    # Kaliteyi 3 yerden tespit et, en iyisini al
                    q_name = detect_quality(current_name)
                    q_link = detect_quality(line)
                    q_info = detect_quality(current_info)
                    final_quality = min(q_name, q_link, q_info)

                    channels[current_name]['links'].append({
                        'url'     : line,
                        'quality' : final_quality,
                        'source'  : source_name
                    })
                    parsed_count += 1
                else:
                    skipped_count += 1
            else:
                skipped_count += 1

    print(f"   📺 {len(channels)} kanal, {parsed_count} link bulundu"
          + (f" ({skipped_count} tekrar atlandı)" if skipped_count > 0 else ""))

    return channels


# ╔══════════════════════════════════════════════════════════════════╗
# ║                       BİRLEŞTİR VE SIRALA                       ║
# ╚══════════════════════════════════════════════════════════════════╝

def merge_all_channels(all_channels_list):
    """
    Birden fazla kaynaktan gelen kanalları birleştir.
    Aynı isimli kanalların linkleri tek kanal altında toplanır.
    """
    merged = OrderedDict()

    for channels in all_channels_list:
        for name, data in channels.items():
            if name not in merged:
                merged[name] = {
                    'info'  : data['info'],
                    'links' : []
                }
            # Linkleri ekle (tekrar olmasın)
            existing_urls = [l['url'] for l in merged[name]['links']]
            for link in data['links']:
                if link['url'] not in existing_urls:
                    merged[name]['links'].append(link)
                    existing_urls.append(link['url'])

    return merged


def sort_links_by_quality(channels):
    """
    Her kanalın linklerini kaliteye göre sırala.
    En yüksek kalite (4K) ilk sıraya gelir.
    """
    for name, data in channels.items():
        data['links'].sort(key=lambda x: x['quality'])
    return channels


# ╔══════════════════════════════════════════════════════════════════╗
# ║                        ÇIKTI DOSYASI                            ║
# ╚══════════════════════════════════════════════════════════════════╝

def write_output(channels, output_path, stats):
    """Birleştirilmiş ve sıralanmış M3U dosyasını yaz"""

    with open(output_path, 'w', encoding='utf-8') as f:

        # ── Başlık ──────────────────────────────────────────────────
        f.write('#EXTM3U\n')
        f.write(f'# ╔══════════════════════════════════════════════════════════════╗\n')
        f.write(f'# ║  📺 M3U Failover Liste - Kalite Sıralamalı                   ║\n')
        f.write(f'# ║  📅 Güncelleme : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}                         ║\n')
        f.write(f'# ║  📊 Toplam Kanal: {stats["total_channels"]:<44}║\n')
        f.write(f'# ║  🔗 Toplam Link : {stats["total_links"]:<44}║\n')
        f.write(f'# ║  📈 Sıralama    : 4K → FHD → HD → SD → Bilinmiyor            ║\n')
        f.write(f'# ╚══════════════════════════════════════════════════════════════╝\n\n')

        # ── Kanalları yaz ───────────────────────────────────────────
        for name, data in channels.items():

            # EXTINF satırı
            f.write(data['info'] + '\n')

            link_count = len(data['links'])

            for i, link in enumerate(data['links']):
                quality_label = get_quality_label(link['quality'])

                # Birden fazla link varsa etiket ekle
                if link_count > 1:
                    f.write(f'#EXTVLCOPT:network-caching=1000\n')
                    f.write(f'# ▶ Link {i + 1}/{link_count} : {quality_label}\n')

                f.write(link['url'] + '\n')

            f.write('\n')


# ╔══════════════════════════════════════════════════════════════════╗
# ║                        İSTATİSTİKLER                            ║
# ╚══════════════════════════════════════════════════════════════════╝

def generate_stats(channels):
    """İstatistik bilgilerini hesapla"""
    stats = {
        'total_channels' : len(channels),
        'multi_link'     : 0,
        'single_link'    : 0,
        'total_links'    : 0,
        'quality_counts' : {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 99: 0},
        'max_links'      : 0,
        'max_links_name' : '',
    }

    for name, data in channels.items():
        link_count = len(data['links'])
        stats['total_links'] += link_count

        if link_count > 1:
            stats['multi_link'] += 1
        else:
            stats['single_link'] += 1

        if link_count > stats['max_links']:
            stats['max_links']      = link_count
            stats['max_links_name'] = name

        # En iyi kaliteye göre say
        if data['links']:
            best_quality = data['links'][0]['quality']
            stats['quality_counts'][best_quality] = \
                stats['quality_counts'].get(best_quality, 0) + 1

    return stats


def print_stats(stats):
    """İstatistikleri ekrana yazdır"""
    print("\n╔══════════════════════════════════════════════════════════════════╗")
    print("║                       📊 İSTATİSTİKLER                           ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  📺  Toplam benzersiz kanal  : {stats['total_channels']:<33}║")
    print(f"║  🔗  Birden fazla linkli     : {stats['multi_link']:<33}║")
    print(f"║  🔁  Tek linkli              : {stats['single_link']:<33}║")
    print(f"║  📎  Toplam link sayısı      : {stats['total_links']:<33}║")
    print(f"║  🏅  En çok link             : {stats['max_links_name'][:20]} ({stats['max_links']} link){' '*(10-len(str(stats['max_links'])))}║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  📈  KALİTE DAĞILIMI (En iyi linke göre):                        ║")
    print(f"║      🏆  4K/UHD      : {stats['quality_counts'].get(1, 0):<42}║")
    print(f"║      🥇  FHD/1080p   : {stats['quality_counts'].get(2, 0):<42}║")
    print(f"║      🥈  HD/720p     : {stats['quality_counts'].get(3, 0):<42}║")
    print(f"║      🥉  SD/480p     : {stats['quality_counts'].get(4, 0):<42}║")
    print(f"║      📉  360p        : {stats['quality_counts'].get(5, 0):<42}║")
    print(f"║      ❓  Bilinmiyor  : {stats['quality_counts'].get(99, 0):<42}║")
    print("╚══════════════════════════════════════════════════════════════════╝")


# ╔══════════════════════════════════════════════════════════════════╗
# ║                          ANA FONKSİYON                          ║
# ╚══════════════════════════════════════════════════════════════════╝

def main():
    start_time = datetime.now()
    print_banner()

    all_channels       = []
    successful_sources = 0
    failed_sources     = 0

    # ── Ortam değişkenlerinden URL al (GitHub Secrets) ──────────────
    env_urls = []
    for i in range(1, ENV_URL_COUNT + 1):
        env_url = os.environ.get(f'M3U_URL_{i}', '').strip()
        if env_url:
            env_urls.append(env_url)

    # URL listesini birleştir (ortam değişkenleri + sabit liste)
    all_urls = env_urls + [u for u in M3U_URLS if u not in env_urls]
    # Boş URL'leri temizle
    all_urls = [u for u in all_urls if u.strip()]

    # ── URL'lerden indir ─────────────────────────────────────────────
    if all_urls:
        print_section("📡 URL'LERDEN M3U ÇEKİLİYOR")

        for i, url in enumerate(all_urls, 1):
            print(f"\n  [{i}/{len(all_urls)}] {shorten_url(url)}")

            content = download_m3u(url)
            if content:
                source_name = f"URL_{i}_{urlparse(url).netloc}"
                channels = parse_m3u_content(content, source_name)
                if channels:
                    all_channels.append(channels)
                    successful_sources += 1
                else:
                    print(f"   ⚠️  İçerik parse edilemedi!")
                    failed_sources += 1
            else:
                failed_sources += 1
    else:
        print("\n  ℹ️  URL listesi boş, yerel dosyalara geçiliyor...")

    # ── Yerel dosyaları oku ─────────────────────────────────────────
    os.makedirs(INPUT_FOLDER, exist_ok=True)
    m3u_files  = glob.glob(os.path.join(INPUT_FOLDER, "*.m3u"))
    m3u_files += glob.glob(os.path.join(INPUT_FOLDER, "*.m3u8"))
    m3u_files  = sorted(m3u_files)

    if m3u_files:
        print_section("📁 YEREL DOSYALAR OKUNUYOR")

        for i, m3u_file in enumerate(m3u_files, 1):
            filename = os.path.basename(m3u_file)
            print(f"\n  [{i}/{len(m3u_files)}] {filename}")

            content = read_local_m3u(m3u_file)
            if content:
                channels = parse_m3u_content(content, filename)
                if channels:
                    all_channels.append(channels)
                    successful_sources += 1
                else:
                    print(f"   ⚠️  İçerik parse edilemedi!")
                    failed_sources += 1
            else:
                failed_sources += 1
    else:
        print("\n  ℹ️  Yerel M3U dosyası bulunamadı")

    # ── Kaynak kontrolü ─────────────────────────────────────────────
    if not all_channels:
        print("\n")
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║  ❌ HİÇBİR KAYNAK BULUNAMADI!                                    ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
        print("║  Lütfen aşağıdakilerden birini yapın:                            ║")
        print("║  1. M3U_URLS listesine URL ekleyin                               ║")
        print("║  2. 'input' klasörüne .m3u dosyası koyun                         ║")
        print("║  3. GitHub Secrets'a M3U_URL_1 ekleyin                           ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        return

    # ── Birleştir ve Sırala ─────────────────────────────────────────
    print_section("🔄 BİRLEŞTİRİLİYOR VE SIRRALANIYOR")

    print("\n  🔗 Kanallar birleştiriliyor...")
    merged = merge_all_channels(all_channels)
    print(f"     ✓ {len(merged)} benzersiz kanal oluşturuldu")

    print("\n  📊 Linkler kaliteye göre sıralanıyor (4K → FHD → HD → SD)...")
    sorted_channels = sort_links_by_quality(merged)
    print(f"     ✓ Sıralama tamamlandı")

    # ── Çıktı dosyasını oluştur ─────────────────────────────────────
    print("\n  💾 Çıktı dosyası oluşturuluyor...")
    stats = generate_stats(sorted_channels)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    output_path = os.path.join(OUTPUT_FOLDER, OUTPUT_FILE)
    write_output(sorted_channels, output_path, stats)

    file_size = os.path.getsize(output_path) / 1024
    print(f"     ✓ {output_path} ({file_size:.1f} KB)")

    # ── İstatistikler ───────────────────────────────────────────────
    print_stats(stats)

    # ── Özet ────────────────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).seconds

    print("\n╔══════════════════════════════════════════════════════════════════╗")
    print("║                      ✅ İŞLEM TAMAMLANDI                         ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  📄  Çıktı    : {output_path:<49}║")
    print(f"║  💾  Boyut    : {file_size:.1f} KB{' '*(48-len(f'{file_size:.1f} KB'))}║")
    print(f"║  ⏱️   Süre     : {elapsed} saniye{' '*(46-len(f'{elapsed} saniye'))}║")
    print(f"║  ✅  Başarılı : {successful_sources} kaynak{' '*(47-len(f'{successful_sources} kaynak'))}║")
    print(f"║  ❌  Başarısız: {failed_sources} kaynak{' '*(47-len(f'{failed_sources} kaynak'))}║")
    print("╚══════════════════════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    main()
