#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import glob
import requests
from collections import OrderedDict
from datetime import datetime
from urllib.parse import urlparse

# ==================== AYARLAR ====================
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
OUTPUT_FILE = "failover.m3u"

# 📡 M3U URL'LERİ (İstediğin kadar ekle)
M3U_URLS = [
    "https://raw.githubusercontent.com/kadirsener1/tivim/main/1.m3u",
    "https://raw.githubusercontent.com/kadirsener1/atom/main/playlist.m3u",
    # Daha fazla URL ekleyebilirsin...
]

# İstek ayarları
REQUEST_TIMEOUT = 30  # saniye
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Kalite sıralaması (en yüksek önce)
QUALITY_ORDER = {
    '4k': 1, 'uhd': 1, '2160p': 1, '2160': 1,
    'fhd': 2, 'fullhd': 2, 'full hd': 2, '1080p': 2, '1080': 2,
    'hd': 3, '720p': 3, '720': 3,
    'sd': 4, '576p': 4, '480p': 4, '480': 4,
    '360p': 5, '360': 5,
}
DEFAULT_QUALITY = 99
# =================================================


def download_m3u(url):
    """URL'den M3U içeriğini indir"""
    try:
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
        }
        
        print(f"   ⏳ İndiriliyor...")
        response = requests.get(
            url, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )
        response.raise_for_status()
        
        # Encoding düzelt
        response.encoding = response.apparent_encoding or 'utf-8'
        content = response.text
        
        # M3U dosyası mı kontrol et
        if not content.strip().startswith('#EXTM3U') and '#EXTINF' not in content:
            print(f"   ⚠️ Uyarı: Geçerli M3U formatı değil!")
            return None
        
        lines = content.splitlines()
        print(f"   ✓ {len(lines)} satır indirildi")
        return content
        
    except requests.exceptions.Timeout:
        print(f"   ❌ Zaman aşımı ({REQUEST_TIMEOUT}s)")
        return None
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Bağlantı hatası")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"   ❌ HTTP Hatası: {e.response.status_code}")
        return None
    except Exception as e:
        print(f"   ❌ Hata: {str(e)}")
        return None


def read_local_m3u(file_path):
    """Yerel M3U dosyasını oku"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        print(f"   ✓ {len(content.splitlines())} satır okundu")
        return content
    except Exception as e:
        print(f"   ❌ Dosya okunamadı: {str(e)}")
        return None


def detect_quality(text):
    """Link veya kanal adından kaliteyi tespit et"""
    text_lower = text.lower()
    
    for quality, priority in QUALITY_ORDER.items():
        pattern = r'[\s\-_\.\[\]\(\)]' + re.escape(quality) + r'[\s\-_\.\[\]\(\)]'
        if re.search(pattern, text_lower) or quality in text_lower:
            return priority
    
    return DEFAULT_QUALITY


def get_quality_label(priority):
    """Kalite önceliğinden etiket döndür"""
    labels = {
        1: "4K/UHD",
        2: "FHD/1080p", 
        3: "HD/720p",
        4: "SD/480p",
        5: "360p",
        99: "Bilinmiyor"
    }
    return labels.get(priority, "Bilinmiyor")


def parse_m3u_content(content, source_name=""):
    """M3U içeriğini parse et"""
    channels = OrderedDict()
    current_info = None
    current_name = None
    
    if not content:
        return channels
    
    lines = content.splitlines()
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('#EXTINF'):
            current_info = line
            current_name = line.split(',')[-1].strip()
            
        elif line and not line.startswith('#') and current_name:
            if current_name not in channels:
                channels[current_name] = {
                    'info': current_info,
                    'links': []
                }
            
            # Aynı linki ekleme
            existing_urls = [l['url'] for l in channels[current_name]['links']]
            if line not in existing_urls:
                quality_from_name = detect_quality(current_name)
                quality_from_link = detect_quality(line)
                quality_from_info = detect_quality(current_info)
                final_quality = min(quality_from_name, quality_from_link, quality_from_info)
                
                channels[current_name]['links'].append({
                    'url': line,
                    'quality': final_quality,
                    'source': source_name
                })
    
    return channels


def merge_all_channels(all_channels_list):
    """Tüm kanalları birleştir"""
    merged = OrderedDict()
    
    for channels in all_channels_list:
        for name, data in channels.items():
            if name not in merged:
                merged[name] = {
                    'info': data['info'],
                    'links': []
                }
            
            existing_urls = [l['url'] for l in merged[name]['links']]
            for link in data['links']:
                if link['url'] not in existing_urls:
                    merged[name]['links'].append(link)
                    existing_urls.append(link['url'])
    
    return merged


def sort_links_by_quality(channels):
    """Her kanalın linklerini kaliteye göre sırala"""
    for name, data in channels.items():
        data['links'].sort(key=lambda x: x['quality'])
    return channels


def write_output(channels, output_path, stats):
    """Çıktı dosyasını yaz"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        f.write(f'# ╔════════════════════════════════════════════════════════════╗\n')
        f.write(f'# ║  📺 M3U Failover Liste - Kalite Sıralamalı                 ║\n')
        f.write(f'# ║  📅 Güncelleme: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}                       ║\n')
        f.write(f'# ║  📊 Toplam Kanal: {stats["total_channels"]:<42}║\n')
        f.write(f'# ║  🔗 Toplam Link: {stats["total_links"]:<43}║\n')
        f.write(f'# ║  📈 Sıralama: 4K → FHD → HD → SD                           ║\n')
        f.write(f'# ╚════════════════════════════════════════════════════════════╝\n\n')
        
        for name, data in channels.items():
            f.write(data['info'] + '\n')
            
            for i, link in enumerate(data['links']):
                quality_label = get_quality_label(link['quality'])
                
                if len(data['links']) > 1:
                    f.write(f'#EXTVLCOPT:network-caching=1000\n')
                    f.write(f'# Link {i+1}: {quality_label}\n')
                
                f.write(link['url'] + '\n')
            
            f.write('\n')


def generate_stats(channels):
    """İstatistik oluştur"""
    stats = {
        'total_channels': len(channels),
        'multi_link': 0,
        'total_links': 0,
        'quality_counts': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 99: 0}
    }
    
    for name, data in channels.items():
        link_count = len(data['links'])
        stats['total_links'] += link_count
        
        if link_count > 1:
            stats['multi_link'] += 1
        
        if data['links']:
            best_quality = data['links'][0]['quality']
            stats['quality_counts'][best_quality] = stats['quality_counts'].get(best_quality, 0) + 1
    
    return stats


def print_banner():
    """Banner yazdır"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   🔄 M3U FAİLOVER BİRLEŞTİRİCİ v2.0                          ║
║   ────────────────────────────────────────────────────────   ║
║   📡 URL'den M3U Çekme                                       ║
║   📊 Kalite Sıralama (4K → FHD → HD → SD)                    ║
║   🔗 Failover Desteği                                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)


def print_stats(stats):
    """İstatistikleri yazdır"""
    print("\n╔═══════════════════════════════════════════════════════════════╗")
    print("║                     📊 İSTATİSTİKLER                          ║")
    print("╠═══════════════════════════════════════════════════════════════╣")
    print(f"║  📺 Toplam benzersiz kanal : {stats['total_channels']:<31}║")
    print(f"║  🔗 Birden fazla linkli    : {stats['multi_link']:<31}║")
    print(f"║  📎 Toplam link sayısı     : {stats['total_links']:<31}║")
    print("╠═══════════════════════════════════════════════════════════════╣")
    print("║  📈 KALİTE DAĞILIMI (En iyi linke göre):                      ║")
    print(f"║      🏆 4K/UHD     : {stats['quality_counts'].get(1, 0):<39}║")
    print(f"║      🥇 FHD/1080p  : {stats['quality_counts'].get(2, 0):<39}║")
    print(f"║      🥈 HD/720p    : {stats['quality_counts'].get(3, 0):<39}║")
    print(f"║      🥉 SD/480p    : {stats['quality_counts'].get(4, 0):<39}║")
    print(f"║      ❓ Bilinmiyor : {stats['quality_counts'].get(99, 0):<39}║")
    print("╚═══════════════════════════════════════════════════════════════╝")


def main():
    print_banner()
    
    all_channels = []
    successful_sources = 0
    failed_sources = 0
    
    # ═══════════════════════════════════════════
    # 1️⃣ URL'LERDEN M3U ÇEK
    # ═══════════════════════════════════════════
    if M3U_URLS:
        print("╔═══════════════════════════════════════════════════════════════╗")
        print("║  📡 URL'LERDEN M3U ÇEKİLİYOR                                  ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        
        for i, url in enumerate(M3U_URLS, 1):
            # URL'yi kısalt (görüntü için)
            parsed = urlparse(url)
            short_url = f"{parsed.netloc}{parsed.path[:30]}..."
            
            print(f"\n📡 [{i}/{len(M3U_URLS)}] {short_url}")
            
            content = download_m3u(url)
            if content:
                channels = parse_m3u_content(content, f"URL_{i}")
                print(f"   📺 {len(channels)} kanal bulundu")
                all_channels.append(channels)
                successful_sources += 1
            else:
                failed_sources += 1
    
    # ═══════════════════════════════════════════
    # 2️⃣ YEREL DOSYALARI OKU
    # ═══════════════════════════════════════════
    m3u_files = glob.glob(os.path.join(INPUT_FOLDER, "*.m3u"))
    m3u_files += glob.glob(os.path.join(INPUT_FOLDER, "*.m3u8"))
    
    if m3u_files:
        print("\n╔═══════════════════════════════════════════════════════════════╗")
        print("║  📁 YEREL DOSYALAR OKUNUYOR                                   ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        
        for i, m3u_file in enumerate(m3u_files, 1):
            filename = os.path.basename(m3u_file)
            print(f"\n📄 [{i}/{len(m3u_files)}] {filename}")
            
            content = read_local_m3u(m3u_file)
            if content:
                channels = parse_m3u_content(content, filename)
                print(f"   📺 {len(channels)} kanal bulundu")
                all_channels.append(channels)
                successful_sources += 1
            else:
                failed_sources += 1
    
    # ═══════════════════════════════════════════
    # 3️⃣ SONUÇ KONTROLÜ
    # ═══════════════════════════════════════════
    if not all_channels:
        print("\n❌ Hiçbir kaynak bulunamadı!")
        print("   • M3U_URLS listesine URL ekleyin")
        print("   • veya 'input' klasörüne M3U dosyası koyun")
        return
    
    # ═══════════════════════════════════════════
    # 4️⃣ BİRLEŞTİR VE SIRALA
    # ═══════════════════════════════════════════
    print("\n╔═══════════════════════════════════════════════════════════════╗")
    print("║  🔄 İŞLENİYOR                                                  ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    
    print("\n🔗 Kanallar birleştiriliyor...")
    merged = merge_all_channels(all_channels)
    
    print("📊 Linkler kaliteye göre sıralanıyor...")
    sorted_channels = sort_links_by_quality(merged)
    
    # ═══════════════════════════════════════════
    # 5️⃣ ÇIKTI DOSYASINI OLUŞTUR
    # ═══════════════════════════════════════════
    stats = generate_stats(sorted_channels)
    
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    output_path = os.path.join(OUTPUT_FOLDER, OUTPUT_FILE)
    write_output(sorted_channels, output_path, stats)
    
    # ═══════════════════════════════════════════
    # 6️⃣ SONUÇLARI GÖSTER
    # ═══════════════════════════════════════════
    print_stats(stats)
    
    print("\n╔═══════════════════════════════════════════════════════════════╗")
    print("║                    ✅ İŞLEM TAMAMLANDI                        ║")
    print("╠═══════════════════════════════════════════════════════════════╣")
    print(f"║  📄 Çıktı dosyası: {output_path:<41}║")
    print(f"║  ✓  Başarılı kaynak: {successful_sources:<39}║")
    print(f"║  ✗  Başarısız kaynak: {failed_sources:<38}║")
    print("╚═══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
