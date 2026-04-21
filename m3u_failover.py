#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
from collections import OrderedDict
from datetime import datetime

# ==================== AYARLAR ====================
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
OUTPUT_FILE = "failover.m3u"
# =================================================

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
            # Aynı linki tekrar ekleme
            if line not in channels[current_name]['links']:
                channels[current_name]['links'].append(line)
    
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
            for link in data['links']:
                if link not in merged[name]['links']:
                    merged[name]['links'].append(link)
    
    return merged

def write_output(channels, output_path):
    """Çıktı dosyasını yaz"""
    with open(output_path, 'w', encoding='utf-8') as f:
        # Header
        f.write('#EXTM3U\n')
        f.write(f'#EXTM3U url-tvg="https://raw.githubusercontent.com/AhmetSekerr/IPTV-List-Turkey/main/tr.xml"\n')
        f.write(f'# Güncelleme: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'# Toplam Kanal: {len(channels)}\n\n')
        
        # Kanalları yaz
        for name, data in channels.items():
            f.write(data['info'] + '\n')
            for link in data['links']:
                f.write(link + '\n')
            f.write('\n')

def main():
    print("=" * 50)
    print("🔄 M3U Failover Birleştirici Başlatıldı")
    print("=" * 50)
    
    # Input dosyalarını bul
    m3u_files = glob.glob(os.path.join(INPUT_FOLDER, "*.m3u"))
    m3u_files += glob.glob(os.path.join(INPUT_FOLDER, "*.m3u8"))
    
    if not m3u_files:
        print(f"❌ {INPUT_FOLDER} klasöründe M3U dosyası bulunamadı!")
        return
    
    print(f"📂 {len(m3u_files)} adet M3U dosyası bulundu:")
    for f in m3u_files:
        print(f"   → {f}")
    
    # Tüm dosyaları işle
    all_channels = []
    for m3u_file in m3u_files:
        print(f"\n🔍 İşleniyor: {m3u_file}")
        channels = process_m3u(m3u_file)
        print(f"   → {len(channels)} kanal bulundu")
        all_channels.append(channels)
    
    # Birleştir
    print("\n🔗 Kanallar birleştiriliyor...")
    merged = merge_all_channels(all_channels)
    
    # İstatistikler
    total_channels = len(merged)
    multi_link = sum(1 for x in merged.values() if len(x['links']) > 1)
    total_links = sum(len(x['links']) for x in merged.values())
    
    # Output yaz
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    output_path = os.path.join(OUTPUT_FOLDER, OUTPUT_FILE)
    write_output(merged, output_path)
    
    # Sonuç
    print("\n" + "=" * 50)
    print("✅ İşlem Tamamlandı!")
    print("=" * 50)
    print(f"📊 Toplam benzersiz kanal: {total_channels}")
    print(f"🔗 Birden fazla linki olan: {multi_link}")
    print(f"📎 Toplam link sayısı: {total_links}")
    print(f"📄 Çıktı dosyası: {output_path}")
    print("=" * 50)

if __name__ == "__main__":
    main()
