#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import glob
from collections import OrderedDict
from datetime import datetime

# ==================== AYARLAR ====================
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
OUTPUT_FILE = "failover.m3u"

# Kalite sıralaması (en yüksek önce)
# Sayı ne kadar küçükse o kadar önce gelir
QUALITY_ORDER = {
    '4k': 1,
    'uhd': 1,
    '2160p': 1,
    '2160': 1,
    
    'fhd': 2,
    'fullhd': 2,
    'full hd': 2,
    '1080p': 2,
    '1080': 2,
    
    'hd': 3,
    '720p': 3,
    '720': 3,
    
    'sd': 4,
    '576p': 4,
    '480p': 4,
    '480': 4,
    '360p': 5,
    '360': 5,
}

# Varsayılan kalite (eşleşme yoksa)
DEFAULT_QUALITY = 99
# =================================================


def detect_quality(text):
    """
    Link veya kanal adından kaliteyi tespit et
    Düşük sayı = Yüksek kalite
    """
    text_lower = text.lower()
    
    # Önce kesin eşleşmeleri kontrol et
    for quality, priority in QUALITY_ORDER.items():
        # Tam kelime eşleşmesi için regex kullan
        pattern = r'[\s\-_\.\[\]\(\)]' + re.escape(quality) + r'[\s\-_\.\[\]\(\)]|^' + re.escape(quality) + r'[\s\-_\.\[\]\(\)]|[\s\-_\.\[\]\(\)]' + re.escape(quality) + r'$'
        if re.search(pattern, text_lower):
            return priority
    
    # Basit içerme kontrolü (daha gevşek)
    for quality, priority in QUALITY_ORDER.items():
        if quality in text_lower:
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


def process_m3u(input_file):
    """Tek bir M3U dosyasını işle"""
    channels = OrderedDict()
    current_info = None
    current_name = None
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
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
            
            # Link ve kalite bilgisini kaydet
            if line not in [l['url'] for l in channels[current_name]['links']]:
                # Kaliteyi hem kanal adından hem linkten kontrol et
                quality_from_name = detect_quality(current_name)
                quality_from_link = detect_quality(line)
                quality_from_info = detect_quality(current_info)
                
                # En iyi kaliteyi al
                final_quality = min(quality_from_name, quality_from_link, quality_from_info)
                
                channels[current_name]['links'].append({
                    'url': line,
                    'quality': final_quality
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
            
            # Linkleri ekle (tekrar olmasın)
            existing_urls = [l['url'] for l in merged[name]['links']]
            for link in data['links']:
                if link['url'] not in existing_urls:
                    merged[name]['links'].append(link)
                    existing_urls.append(link['url'])
    
    return merged


def sort_links_by_quality(channels):
    """Her kanalın linklerini kaliteye göre sırala (en iyi önce)"""
    for name, data in channels.items():
        # Kaliteye göre sırala (düşük sayı = yüksek kalite = önce)
        data['links'].sort(key=lambda x: x['quality'])
    
    return channels


def write_output(channels, output_path):
    """Çıktı dosyasını yaz"""
    with open(output_path, 'w', encoding='utf-8') as f:
        # Header
        f.write('#EXTM3U\n')
        f.write(f'# ╔══════════════════════════════════════════════════════╗\n')
        f.write(f'# ║  M3U Failover Liste - Kalite Sıralamalı              ║\n')
        f.write(f'# ║  Güncelleme: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}                    ║\n')
        f.write(f'# ║  Toplam Kanal: {len(channels):<39}║\n')
        f.write(f'# ║  Sıralama: 4K → FHD → HD → SD                        ║\n')
        f.write(f'# ╚══════════════════════════════════════════════════════╝\n\n')
        
        # Kanalları yaz
        for name, data in channels.items():
            # Kanal bilgisi
            f.write(data['info'] + '\n')
            
            # Linkleri kalite sırasına göre yaz
            for i, link in enumerate(data['links']):
                quality_label = get_quality_label(link['quality'])
                
                # İlk link için yorum ekleme, diğerleri için kalite notu ekle
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
        
        # En iyi kaliteyi say (ilk link)
        if data['links']:
            best_quality = data['links'][0]['quality']
            stats['quality_counts'][best_quality] = stats['quality_counts'].get(best_quality, 0) + 1
    
    return stats


def print_stats(stats):
    """İstatistikleri yazdır"""
    print("\n" + "═" * 55)
    print("📊 İSTATİSTİKLER")
    print("═" * 55)
    print(f"  📺 Toplam benzersiz kanal : {stats['total_channels']}")
    print(f"  🔗 Birden fazla linkli    : {stats['multi_link']}")
    print(f"  📎 Toplam link sayısı     : {stats['total_links']}")
    print("─" * 55)
    print("  📈 KALİTE DAĞILIMI (En iyi linke göre):")
    print(f"      🏆 4K/UHD     : {stats['quality_counts'].get(1, 0)} kanal")
    print(f"      🥇 FHD/1080p  : {stats['quality_counts'].get(2, 0)} kanal")
    print(f"      🥈 HD/720p    : {stats['quality_counts'].get(3, 0)} kanal")
    print(f"      🥉 SD/480p    : {stats['quality_counts'].get(4, 0)} kanal")
    print(f"      ❓ Bilinmiyor : {stats['quality_counts'].get(99, 0)} kanal")
    print("═" * 55)


def main():
    print("═" * 55)
    print("🔄 M3U FAİLOVER BİRLEŞTİRİCİ")
    print("   📊 Kalite Sıralamalı (4K → FHD → HD → SD)")
    print("═" * 55)
    
    # Input dosyalarını bul
    m3u_files = glob.glob(os.path.join(INPUT_FOLDER, "*.m3u"))
    m3u_files += glob.glob(os.path.join(INPUT_FOLDER, "*.m3u8"))
    
    if not m3u_files:
        print(f"\n❌ {INPUT_FOLDER} klasöründe M3U dosyası bulunamadı!")
        print("   Lütfen M3U dosyalarınızı 'input' klasörüne koyun.")
        return
    
    print(f"\n📂 {len(m3u_files)} adet M3U dosyası bulundu:")
    for f in m3u_files:
        print(f"   📄 {os.path.basename(f)}")
    
    # Tüm dosyaları işle
    all_channels = []
    for m3u_file in m3u_files:
        print(f"\n🔍 İşleniyor: {os.path.basename(m3u_file)}")
        channels = process_m3u(m3u_file)
        print(f"   ✓ {len(channels)} kanal bulundu")
        all_channels.append(channels)
    
    # Birleştir
    print("\n🔗 Kanallar birleştiriliyor...")
    merged = merge_all_channels(all_channels)
    
    # Kaliteye göre sırala
    print("📊 Linkler kaliteye göre sıralanıyor (4K > FHD > HD > SD)...")
    sorted_channels = sort_links_by_quality(merged)
    
    # İstatistikleri hesapla
    stats = generate_stats(sorted_channels)
    
    # Output yaz
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    output_path = os.path.join(OUTPUT_FOLDER, OUTPUT_FILE)
    write_output(sorted_channels, output_path)
    
    # Sonuçları göster
    print_stats(stats)
    
    print(f"\n✅ İŞLEM TAMAMLANDI!")
    print(f"📄 Çıktı dosyası: {output_path}")
    print("═" * 55)
    
    # Örnek kanalları göster
    print("\n📋 ÖRNEK KANALLAR (İlk 5):")
    print("─" * 55)
    
    count = 0
    for name, data in sorted_channels.items():
        if count >= 5:
            break
        if len(data['links']) > 1:
            print(f"\n  📺 {name}")
            for i, link in enumerate(data['links'][:3]):  # İlk 3 link
                quality = get_quality_label(link['quality'])
                print(f"     {i+1}. [{quality}] {link['url'][:50]}...")
            if len(data['links']) > 3:
                print(f"     ... ve {len(data['links']) - 3} link daha")
            count += 1
    
    print("\n" + "═" * 55)


if __name__ == "__main__":
    main()
