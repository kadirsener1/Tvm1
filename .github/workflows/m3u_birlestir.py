from collections import OrderedDict

print("=== M3U Failover Birleştirici ===\n")

# Kullanıcıdan dosya isimlerini al
input_file = input("Orijinal M3U dosyanızın adını yazın (örnek: liste.m3u): ").strip()
output_file = input("Yeni dosyanın adı ne olsun? (Varsayılan: failover.m3u): ").strip()
if not output_file:
    output_file = "failover.m3u"

channels = OrderedDict()
current_info = None
current_name = None

try:
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('#EXTINF'):
            current_info = line
            current_name = line.split(',')[-1].strip()
            i += 1
            continue
            
        elif line and not line.startswith('#') and current_name:
            if current_name not in channels:
                channels[current_name] = {'info': current_info, 'links': []}
            if line not in channels[current_name]['links']:
                channels[current_name]['links'].append(line)
        i += 1

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')
        for name, data in channels.items():
            f.write(data['info'] + '\n')
            for link in data['links']:
                f.write(link + '\n')
            f.write('\n')

    print("\n✅ Başarıyla tamamlandı!")
    print(f"Çıktı dosyası: {output_file}")
    print(f"Toplam kanal: {len(channels)}")

    coklu = sum(1 for x in channels.values() if len(x['links']) > 1)
    print(f"{coklu} kanalın birden fazla linki birleştirildi.")

except FileNotFoundError:
    print(f"\n❌ Hata: '{input_file}' dosyası bulunamadı!")
    print("Dosyanın scriptle aynı klasörde olduğundan emin olun.")

input("\nKapatmak için Enter tuşuna basın...")
