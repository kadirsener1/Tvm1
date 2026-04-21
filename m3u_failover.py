# m3u_failover.py
from collections import OrderedDict

def merge_m3u_with_failover(input_file, output_file):
    channels = OrderedDict()  # Sırayı korumak için
    current_info = None
    current_name = None
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('#EXTINF'):
            current_info = line
            # Kanal adını al (virgülden sonraki kısım)
            current_name = line.split(',')[-1].strip()
            i += 1
            continue
            
        elif line and not line.startswith('#') and current_name:
            # Link bulundu
            if current_name not in channels:
                channels[current_name] = {
                    'info': current_info,
                    'links': []
                }
            if line not in channels[current_name]['links']:  # Aynı linki tekrar ekleme
                channels[current_name]['links'].append(line)
                
        i += 1
    
    # Yeni M3U dosyasını oluştur
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')
        for name, data in channels.items():
            f.write(data['info'] + '\n')
            for link in data['links']:
                f.write(link + '\n')
            f.write('\n')
    
    print(f"✅ İşlem tamamlandı!")
    print(f"   Toplam benzersiz kanal: {len(channels)}")
    for name, data in channels.items():
        if len(data['links']) > 1:
            print(f"   → {name} → {len(data['links'])} link birleştirildi")

# ===================== KULLANIM =====================
if __name__ == "__main__":
    input_dosya = "orijinal.m3u"      # Dosyanızın adı
    output_dosya = "failover_m3u.m3u"
    
    merge_m3u_with_failover(input_dosya, output_dosya)
