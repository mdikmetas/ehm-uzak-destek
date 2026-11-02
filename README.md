# EHM Uzak Destek

Port açmadan, IP/port ayarıyla uğraşmadan çalışan, **onay tabanlı** uzak masaüstü destek aracı — TeamViewer/AnyDesk mantığında. Tek uygulama hem ekranını paylaşır hem karşıya bağlanır. Bağlantı yalnızca **karşı tarafın "Kabul Et" demesiyle** kurulur.

> Meşru, izinli uzaktan destek içindir. Karşı tarafın açık onayı olmadan kullanmayın.

---

## İçindekiler
- [Nasıl çalışır?](#nasıl-çalışır)
- [Neden bir "relay" gerekiyor?](#neden-bir-relay-gerekiyor)
- [Hızlı başlangıç](#hızlı-başlangıç)
- [1) Relay kurulumu (bir kez)](#1-relay-kurulumu-bir-kez)
- [2) Uygulamayı çalıştırma](#2-uygulamayı-çalıştırma)
- [3) Kullanım (bağlanma)](#3-kullanım-bağlanma)
- [Canlı kalite kontrolü](#canlı-kalite-kontrolü)
- [Ayarlar paneli](#ayarlar-paneli)
- [Kendin derle (.exe / .app)](#kendin-derle-exe--app)
- [Kaç kişi / bant genişliği](#kaç-kişi--bant-genişliği)
- [Sorun giderme](#sorun-giderme)
- [Güvenlik](#güvenlik)

---

## Nasıl çalışır?

İki uç da **dışarı doğru** (443/WSS) ortak bir **relay**'e bağlanır. Relay iki tarafı rastgele bir **kod** ile eşleştirir. Kimse port açmadığı için CGNAT arkasında bile çalışır.

```
Ekran kareleri:   Paylaşan  ─▶  Relay  ─▶  Bağlanan
Fare / klavye:    Bağlanan  ─▶  Relay  ─▶  Paylaşan
```

- **relay.py** — buluşma noktası (internetten erişilebilir bir yerde çalışır: Raspberry Pi + Tailscale Funnel veya bir VPS)
- **remote_support.py** — tek uygulama (hem paylaş hem bağlan)

**Verimlilik:** ekran bir ızgaraya bölünür ve her karede yalnızca **değişen bölgeler** gönderilir (dirty-tile). Ekran dururken trafik neredeyse sıfırdır.

---

## Neden bir "relay" gerekiyor?

Türkiye'de bağlantıların çoğu **CGNAT** arkasındadır; iki taraf da CGNAT'taysa doğrudan P2P (ve torrent/DHT mantığı) bağlantı kuramaz. Bu yüzden iki ucun da erişebildiği, trafiği taşıyan bir relay şarttır — TeamViewer/AnyDesk de aynı sebeple relay filoları işletir. Son kullanıcılar yine **hiç port açmaz**; sadece relay'in bir kez internetten erişilebilir olması gerekir.

---

## Hızlı başlangıç

1. Relay'i bir yerde çalıştır (aşağıda), public adresini al.
2. `relay.txt` içine o adresi yaz (ya da uygulamadaki **Ayarlar**'dan).
3. İki tarafta da uygulamayı aç → biri kod verir, diğeri kodu girip bağlanır → karşı taraf onaylar.

---

## 1) Relay kurulumu (bir kez)

Relay'i internetten erişilebilen bir yerde çalıştır. İki yaygın yol:

### A) Raspberry Pi + Tailscale Funnel (bedava, port açmadan)
CGNAT arkasındaki bir Pi'yi bile public yapar.

```bash
# Pi'de
mkdir -p ~/ehm && cd ~/ehm
# relay.py'yi buraya koy
sudo apt-get install -y python3-websockets      # ya da: pip install websockets
python3 relay.py                                 # "RELAY calisiyor, port: 8765"
```

Kalıcı servis (systemd) ve public adres:
```bash
# relay'i 127.0.0.1:8766'da çalıştırdığını varsayalım (PORT=8766)
tailscale funnel --bg --https=443 http://127.0.0.1:8766
tailscale funnel status          # https://<ad>.ts.net adresini verir
```

> Not: Funnel'ı ilk kez açarken Tailscale, node için Funnel'ı etkinleştirmeni isteyen bir onay linki verebilir; tarayıcıda onayla.

### B) VPS (simetrik hat, çok eşzamanlı oturum için)
```bash
pip install websockets
python relay.py        # 8765 portu; güvenlik duvarında aç
```

Her iki durumda da elde ettiğin adresi not et:
- Funnel: `wss://<ad>.ts.net`
- VPS:    `ws://SUNUCU_IP:8765`

### relay.txt
`relay.txt` içine tek satır olarak relay adresini yaz:
```
wss://<senin-funnel-adresin>.ts.net
```

---

## 2) Uygulamayı çalıştırma

**Windows**
- Hazır sürüm: `EHM-Uzak-Destek.exe` (Releases'ten indir) — açılışta yönetici (UAC) ister.
- Ya da kaynaktan: `baslat.bat` (gerekli paketleri otomatik kurar).

**macOS**
- `baslat.command` (çift tıkla) ya da derlenmiş `.app`.
- İlk kullanımda **System Settings → Privacy & Security** altında **Screen Recording** ve **Accessibility** izinlerini uygulamaya ver.

Gereken paketler (kaynaktan çalıştırırken otomatik kurulur):
```
pip install websocket-client mss pillow pynput certifi
```

---

## 3) Kullanım (bağlanma)

**Ekranını paylaşan (destek alan):**
1. Uygulamayı aç → **Ekranımı Paylaş**
2. Ekranda çıkan **9 haneli kodu** karşıya söyle
3. Bağlantı isteği gelince **Kabul Et**

**Bağlanan (destek veren):**
1. Uygulamayı aç → **Kod** kutusuna kodu yaz → **Bağlan**
2. Karşı taraf kabul edince uzak ekran açılır; fare ve klavye ile kontrol edebilirsin

---

## Canlı kalite kontrolü

Uzak ekran penceresinin üstündeki çubuktan, **bağlantıyı kesmeden** anında değiştirilir:

| Ayar | Seçenek |
|------|---------|
| **Mod** | Akıcı / Dengeli / Keskin / Özel |
| **Çözünürlük** | 800 – 1920 px |
| **FPS** | 3 – 15 |
| **Kalite** | Düşük / Orta / Yüksek / Çok Yüksek |

Sağda anlık **KB/s** göstergesi vardır.
- Görüntü takılıyorsa → **Akıcı** (düşük çözünürlük/kalite, yüksek FPS)
- Detay okuman gerekiyorsa → **Keskin**

---

## Ayarlar paneli

Ana ekrandaki **Ayarlar** düğmesinden:
- **Relay adresi** — uygulama içinden değiştir/kaydet (`relay.txt` düzenlemene gerek yok)
- **Varsayılan yayın modu** — Akıcı / Dengeli / Keskin
- **Windows'ta açılışta otomatik başlat**
- **Yönetici durumu** göstergesi

---

## Kendin derle (.exe / .app)

Tek dosya, dağıtılabilir sürüm:

- **Windows:** `derle_win.bat` çift tıkla → `dist\EHM-Uzak-Destek.exe` (açılışta UAC yönetici ister)
- **macOS:** `derle_mac.command` → `dist/EHM-Uzak-Destek.app`
  - Sonra: `xattr -dr com.apple.quarantine "dist/EHM-Uzak-Destek.app"` ve Screen Recording + Accessibility izinleri

> Derleme ilgili platformda yapılır (çapraz derleme yoktur): Windows exe'si Windows'ta, Mac app'i Mac'te.

---

## Kaç kişi / bant genişliği

Bir oturumda **2 kişi** (paylaşan + bağlanan). Aynı anda kaç ayrı oturum olabileceğini **relay'in upload hızı** belirler (tüm trafik relay'den geçer).

Oturum başına kabaca (Dengeli: 1280px, 8fps):

| Ekran durumu | ~Oturum başı |
|---|---|
| Boşta (sabit) | ~0 |
| Hafif (tık, menü) | ~0.3 Mbps |
| Orta (kaydırma) | ~2 Mbps |
| Ağır (video) | ~4.5 Mbps |

Ev hattında (düşük upload) birkaç aktif oturum; çok eşzamanlı oturum için relay'i simetrik hatlı bir **VPS**'e taşı (kod aynı, sadece `relay.txt` değişir).

---

## Sorun giderme

- **"Relay'e bağlanılıyor"da takılıyor / sertifika hatası (macOS):** python.org Python'unda CA sertifikaları eksik olabilir. Uygulama `certifi` kullanır; `pip install certifi` kurulu olduğundan emin ol. Gerekirse `/Applications/Python\ 3.x/Install\ Certificates.command` (sudo ile).
- **Relay 8765 portu dolu:** başka bir servisle çakışıyordur; relay'i farklı porta al (`PORT=8766`) ve Funnel'ı o porta yönlendir.
- **Funnel public adres vermiyor:** `tailscale funnel status` ile kontrol et; ilk kurulumda node için Funnel'ı admin panelinden etkinleştir.
- **Bağlanmıyor:** relay ayakta mı? `curl -i https://<ad>.ts.net` → `426` benzeri cevap = relay çalışıyor.
- **UAC pencerelerini kontrol edemiyorum (Windows):** uygulamayı yönetici olarak çalıştır (exe zaten açılışta ister).

---

## Güvenlik

- Bağlantı, karşı tarafın açık **onayı** olmadan kurulmaz.
- Relay yalnızca geçerli bir **kod** ile eşleştirir; trafik uçtan uca relay üzerinden akar.
- Yalnızca izinli, meşru uzaktan destek için kullanın.
